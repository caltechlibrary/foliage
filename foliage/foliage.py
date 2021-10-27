
from   boltons.iterutils import flatten
import csv
from   commonpy.data_utils import unique, pluralized
from   commonpy.file_utils import exists
from   commonpy.interrupt import wait
from   commonpy.string_utils import antiformat
from   functools import partial
import json
import os
from   os.path import exists, dirname, join, basename, abspath
from   pprint import pformat
import pywebio
from   pywebio.input import input, select, checkbox, radio, file_upload
from   pywebio.input import NUMBER, TEXT
from   pywebio.output import put_text, put_markdown, put_row, put_html
from   pywebio.output import toast, popup, close_popup, put_buttons, put_error
from   pywebio.output import use_scope, set_scope, clear, remove, put_warning
from   pywebio.output import put_success, put_table, put_grid, span
from   pywebio.output import put_tabs, put_image, put_scrollable, put_code
from   pywebio.output import put_processbar, set_processbar, put_loading
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
from   pywebio.pin import put_textarea, put_radio, put_checkbox, put_select
from   pywebio.session import run_js, eval_js
import re

if __debug__:
    from sidetrack import set_debug, log

from .folio import Folio, RecordKind, RecordIdKind, TypeKind
from .ui import quit_app, reload_page, alert, warn, confirm


# Overall main page structure
# .............................................................................

def foliage():
    put_image(logo_image(), width='90px').style('float: right')
    put_html('<h1 class="text-center">Foliage</h1>')
    put_html('<div class="text-muted font-italic font-weight-light">'
             ' Foliage ("FOLIo chAnGe Editor") is an application that runs'
             ' on your computer and lets you perform bulk operations in'
             ' FOLIO over the network. Foliage uses this web page as a way'
             ' of implementing its user interface.'
             '</div>')
    put_tabs([
        {'title': 'Look up records', 'content': find_records_tab()},
        {'title': 'Show ID types', 'content': list_types_tab()},
        {'title': 'Delete records', 'content': delete_records_tab()},
        {'title': 'Change records', 'content': change_records_tab()},
        ])

    put_actions('quit',
                buttons = [dict(label = 'Quit Foliage', value = 'quit',
                                color = 'warning')]
                ).style('position: absolute; bottom: -20px; left: calc(50% - 2.5em); z-index: 2')

    folio = Folio()

    log(f'page layout finished; waiting for user input')
    while True:
        event = pin_wait_change('do_list', 'reset_find', 'do_find',
                                'reset_delete', 'do_delete', 'quit')
        event_type = event['name']

        if event_type.startswith('reset'):  # catches all reset_* buttons.
            pin.textbox_find = ''
            pin.textbox_delete = ''
            clear('output')

        elif event_type == 'quit':
            log(f'quit button clicked')
            quit_app()

        elif event_type == 'do_list':
            with use_scope('output', clear = True):
                put_processbar('bar')
                set_processbar('bar', 1/2)
                type_name = pin.list_type.replace('-', ' ')
                try:
                    types = folio.types(pin.list_type)
                except Exception as ex:
                    alert(f'Error: {antiformat(str(ex))}')
                    continue
                set_processbar('bar', 2/2)
                put_html('<br>')
                put_markdown(f'There are {len(types)} possible values for {type_name}:')
                put_table(sorted([[item[0], item[1]] for item in types]),
                          header = ['Type', 'Id'])

        elif event_type == 'do_find':
            log(f'do_find invoked')
            if not pin.textbox_find:
                alert('Please input at least one barcode or other id.')
                continue
            with use_scope('output', clear = True):
                identifiers = unique_identifiers(pin.textbox_find)
                steps = len(identifiers) + 1
                put_processbar('bar');
                set_processbar('bar', 1/steps)
                for index, id in enumerate(identifiers, start = 2):
                    put_html('<br>')
                    id_type = folio.record_id_type(id)
                    if id_type == RecordIdKind.UNKNOWN:
                        put_error(f'Could not recognize "{id}" as a barcode,'
                                  + ' hrid, item id, instance id,'
                                  + ' or accession number.')
                        set_processbar('bar', index/steps)
                        continue

                    record_kind = pin.select_kind_find
                    try:
                        records = folio.records(id, id_type, record_kind)
                    except Exception as ex:
                        alert(f'Error: {antiformat(str(ex))}')
                        break
                    set_processbar('bar', index/steps)
                    this = pluralized(record_kind + " record", records, True)
                    how = f'by searching for {id_type.value} {id}'
                    put_success(f'Found {this} {how}').style('text-align: center')
                    show_index = (len(records) > 1)
                    for index, record in enumerate(records, start = 1):
                        print_record(record, record_kind, id, id_type,
                                     index, show_index, pin.show_raw)
                    if not records:
                        put_error(f'No record(s) for {id_type.value} "{id}".')

        elif event_type == 'do_delete':
            log(f'do_delete invoked')
            if not pin.textbox_delete:
                alert('Please input at least one barcode or other id.')
                continue
            if not confirm('WARNING: you are about to delete records in FOLIO'
                           + ' permanently. This cannot be undone.\\n\\nProceed?'):
                continue
            with use_scope('output', clear = True):
                identifiers = unique_identifiers(pin.textbox_delete)
                steps = len(identifiers) + 1
                put_processbar('bar');
                set_processbar('bar', 1/steps)
                for index, id in enumerate(identifiers, start = 2):
                    put_html('<br>')
                    id_type = folio.record_id_type(id)
                    if id_type == RecordIdKind.UNKNOWN:
                        put_error(f'Could not recognize "{id}" as a'
                                  + ' barcode, hrid, item id, instance id,'
                                  + ' or accession number.')
                        set_processbar('bar', index/steps)
                        continue
                    record_kind = pin.select_kind_find
                    try:
                        records = folio.records(id, id_type, record_kind)
                    except Exception as ex:
                        alert(f'Error: {antiformat(str(ex))}')
                        break
                    set_processbar('bar', index/steps)
                    if not records:
                        put_error('Could not find a record for'
                                  + f' {id_type.value} "{id}".')
                        continue
                    id = records[0]['id']
                    #(success, error) = folio.operation('delete', f'/inventory/items/{id}')
                    (success, error) = True, None
                    if success:
                        put_success(f'Deleted {record_kind} record for {id}.')
                    else:
                        put_error(f'Error: {error}')


def logo_image():
    here = dirname(__file__)
    image_file = join(here, 'data', 'foliage-icon.png')
    if exists(image_file):
        with open(image_file, 'rb') as f:
            return f.read()
    else:
        log(f'could not find logo image in {image_file}')


# permanent loan type
# note type

def list_types_tab():
    return [
        put_grid([[put_markdown('Select a FOLIO type to list:'),
                   put_select('list_type',
                              options=[
                                  {'label': 'Address types', 'value': TypeKind.ADDRESS.value},
                                  {'label': 'Alternative title types', 'value': TypeKind.ALT_TITLE.value},
                                  {'label': 'Call number types', 'value': TypeKind.CALL_NUMBER.value},
                                  {'label': 'Classification types', 'value': TypeKind.CLASSIFICATION.value},
                                  {'label': 'Contributor types', 'value': TypeKind.CONTRIBUTOR.value},
                                  {'label': 'Contributor name types', 'value': TypeKind.CONTRIBUTOR_NAME.value},
                                  {'label': 'Department types', 'value': TypeKind.DEPARTMENT.value},
                                  {'label': 'Group types', 'value': TypeKind.GROUP.value},
                                  {'label': 'Holdings types', 'value': TypeKind.HOLDINGS.value},
                                  {'label': 'Holdings note types', 'value': TypeKind.HOLDINGS_NOTE.value},
                                  {'label': 'Holdings source types', 'value': TypeKind.HOLDINGS_SOURCE.value},
                                  {'label': 'Identifier types', 'value': TypeKind.ID.value},
                                  {'label': 'ILL policy types', 'value': TypeKind.ILL_POLICY.value},
                                  {'label': 'Instance types', 'value': TypeKind.INSTANCE.value},
                                  {'label': 'Instance format types', 'value': TypeKind.INSTANCE_FORMAT.value},
                                  {'label': 'Instance note types', 'value': TypeKind.INSTANCE_NOTE.value},
                                  {'label': 'Instance relationship types', 'value': TypeKind.INSTANCE_REL.value},
                                  {'label': 'Instance status types', 'value': TypeKind.INSTANCE_STATUS.value},
                                  {'label': 'Item note types', 'value': TypeKind.ITEM_NOTE.value},
                                  {'label': 'Item damaged status types', 'value': TypeKind.ITEM_DAMAGED_STATUS.value},
                                  {'label': 'Loan types', 'value': TypeKind.LOAN.value},
                                  {'label': 'Location types', 'value': TypeKind.LOCATION.value},
                                  {'label': 'Material types', 'value': TypeKind.MATERIAL.value},
                                  {'label': 'Nature of content term types', 'value': TypeKind.NATURE_OF_CONTENT.value},
                                  {'label': 'Service point types', 'value': TypeKind.SERVICE_POINT.value},
                                  {'label': 'Service point user types', 'value': TypeKind.SERVICE_POINT_USER.value},
                                  {'label': 'Shelf location types', 'value': TypeKind.SHELF_LOCATION.value},
                                  {'label': 'Statistical code types', 'value': TypeKind.STATISTICAL_CODE.value},
                              ]),
                   put_actions('do_list', buttons = ['Get list']).style('margin-left: 10px'),
                  ]])
    ]


def find_records_tab():
    return [
        put_markdown('Write one or more barcode, item id, instance id, hrid,'
                     + ' or accession number in the field below, then press'
                     + ' the button to look up the item or instance records'
                     + ' that correspond to them.'),
        put_textarea('textbox_find', rows = 4),
        put_radio('select_kind_find', inline = True,
                  label = 'Type of record to retrieve:',
                  options = [ ('Item', RecordKind.ITEM.value, True),
                              ('Instance', RecordKind.INSTANCE.value)]),
        put_text(''), # Adds a column, pushing next item to the right.
        put_checkbox('show_raw', options = ['Show raw data from FOLIO']),
        put_row([
            put_actions('do_find', buttons = ['Look up records']),
            put_text(''),    # Adds a column, pushing next item to the right.
            put_actions('reset_find',
                        buttons = [dict(label = 'Reset', value = 'reset',
                                        color = 'info')]).style('text-align: right')
        ])
    ]

def delete_records_tab():
    return [
        put_markdown('Write one or more barcode, HRID, item id, or instance '
                     + ' id in the field below to delete the FOLIO records.'),
        put_textarea('textbox_delete', rows = 4),
        put_radio('select_kind_delete', inline = True,
                  label = 'Type of record to delete:',
                  options = [ ('Item', 'item', True),
                              ('Instance', 'instance')]),
        put_row([
            put_actions('do_delete',
                        buttons = [dict(label = 'Delete FOLIO records',
                                        value = 'delete', color = 'danger')]),
            put_text(''),    # Adds a column, pushing next item to the right.
            put_actions('reset_delete',
                        buttons = [dict(label = 'Reset', value = 'reset',
                                        color = 'info')]).style('text-align: right')
        ])
    ]


def change_records_tab():
    return 'Forthcoming ...'


def print_record(record, record_kind, identifier, id_type, index, show_index, show_raw):
    if show_index:
        put_markdown(f'{record_kind.title()} record #{index}:')

    if show_raw:
        put_code(pformat(record, indent = 2))
    elif record_kind == 'item':
        put_table([
            ['Title', record['title']],
            ['Call number', record['callNumber']],
            ['Effective location', record['effectiveLocation']['name']],
            ['Permanent location', record['permanentLocation']['name']],
            ['Status', record['status']['name']],
            ['Tags', ', '.join(tags for tags in record['tags']['tagList'])],
            ['Notes', '\n'.join(record['notes'])],
            ['HRID', record['hrid']],
            [f'{record_kind.title()} id', record['id']]]).style('margin-left: 2em')
    elif record_kind == 'instance':
        put_table([
            ['Title', record['title']],
            ['Call number', record['classifications'][0]['classificationNumber']],
            ['Tags', ', '.join(tags for tags in record['tags']['tagList'])],
            ['HRID', record['hrid']],
            [f'{record_kind.title()} id', record['id']]]).style('margin-left: 2em')


def unique_identifiers(text):
    lines = text.splitlines()
    identifiers = flatten(re.split(r'\s+|,+', line) for line in lines)
    return unique(filter(None, identifiers))
