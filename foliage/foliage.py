
from   boltons.iterutils import flatten
import csv
from   commonpy.data_utils import unique, pluralized
from   commonpy.file_utils import exists, readable
from   commonpy.interrupt import wait
from   commonpy.string_utils import antiformat
from   datetime import datetime as dt
from   dateutil import tz
from   functools import partial
from   getpass import getuser
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
from   pywebio.output import put_success, put_info, put_table, put_grid, span
from   pywebio.output import put_tabs, put_image, put_scrollable, put_code
from   pywebio.output import put_processbar, set_processbar, put_loading
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
from   pywebio.pin import put_textarea, put_radio, put_checkbox, put_select
from   pywebio.session import run_js, eval_js
import re
import webbrowser

if __debug__:
    from sidetrack import set_debug, log

from .folio import Folio, RecordKind, RecordIdKind, TypeKind
from .ui import quit_app, reload_page, alert, warn, confirm, image_data


# Overall main page structure
# .............................................................................

def foliage_main_page(log_file, backup_dir):
    log(f'creating index page')
    put_image(image_data('foliage-icon-r.png'), width='90px').style('float: left')
    put_image(image_data('foliage-icon.png'), width='90px').style('float: right')
    put_html('<h1 class="text-center">Foliage</h1>')
    put_html('<div class="font-italic text-muted font-weight-light text-center mx-auto">'
             ' Foliage ("FOLIo chAnGe Editor") is an app that runs'
             ' on your computer and lets you perform FOLIO operations over'
             ' the network. This web page is its user interface.'
             '</div>').style('width: 85%')
    put_tabs([
        {'title': 'Look up records', 'content': find_records_tab()},
        {'title': 'Delete records', 'content': delete_records_tab()},
#        {'title': 'Change records', 'content': change_records_tab()},
        {'title': 'Show IDs', 'content': list_types_tab()},
        ])

    put_actions('show_log',
                buttons = [dict(label = 'Show log file', value = 'show_log',
                                color = 'secondary')]
                ).style('position: absolute; bottom: -20px; left: 1em; z-index: 2')

    put_actions('quit',
                buttons = [dict(label = 'Quit Foliage', value = 'quit',
                                color = 'warning')]
                ).style('position: absolute; bottom: -20px; left: calc(50% - 3.5em); z-index: 2')

    put_actions('show_backups',
                buttons = [dict(label = 'Show backups', value = 'show_backups',
                                color = 'secondary')]
                ).style('position: absolute; bottom: -20px; right: 1em; z-index: 2')

    # Start the infinite loop for processing user input.
    run_main_loop(log_file, backup_dir)


def run_main_loop(log_file, backup_dir):
    log(f'running main loop')
    folio = Folio()
    while True:
        event = pin_wait_change('do_list', 'reset_find', 'do_find',
                                'reset_delete', 'do_delete', 'quit',
                                'show_log', 'show_backups')
        event_type = event['name']

        if event_type.startswith('reset'):  # catches all reset_* buttons.
            log(f'resetting page')
            pin.textbox_find = ''
            pin.textbox_delete = ''
            clear('output')

        elif event_type == 'quit':
            log(f'quit button clicked')
            quit_app()

        elif event_type == 'show_log':
            log(f'opening log file')
            if log_file and exists(log_file):
                if readable(log_file):
                    webbrowser.open_new("file://" + log_file)
                else:
                    alert(f'Log file is unreadable -- please report this error.')
            elif not log_file:
                warn('No log file -- log output is directed to the terminal.')

        elif event_type == 'show_backups':
            log(f'showing backup directory')
            webbrowser.open_new("file://" + backup_dir)


        elif event_type == 'do_list':
            log(f'listing id types')
            with use_scope('output', clear = True):
                put_processbar('bar')
                set_processbar('bar', 1/2)
                type_name = pin.list_type.replace('-', ' ')
                try:
                    types = folio.types(pin.list_type)
                except Exception as ex:
                    put_html('<br>')
                    put_error(f'Error: {antiformat(str(ex))}')
                    continue
                finally:
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
                        put_error(f'Could not recognize {id} as an existing'
                                  + ' barcode, hrid, item id, instance id,'
                                  + ' or accession number.')
                        set_processbar('bar', index/steps)
                        continue

                    record_kind = pin.select_kind_find
                    try:
                        records = folio.records(id, id_type, record_kind)
                    except Exception as ex:
                        put_error(f'Error: {antiformat(str(ex))}')
                        break
                    set_processbar('bar', index/steps)
                    this = pluralized(record_kind + " record", records, True)
                    how = f'by searching for {id_type.value} {id}'
                    if not records or len(records) == 0:
                        put_error(f'No record(s) for {id_type.value} "{id}".')
                        continue
                    put_success(f'Found {this} {how}').style('text-align: center')
                    show_index = (len(records) > 1)
                    for index, record in enumerate(records, start = 1):
                        print_record(record, record_kind, id, id_type,
                                     index, show_index, pin.show_raw)


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
                        put_error(f'Could not recognize {id} as an existing'
                                  + ' barcode, hrid, item id, instance id,'
                                  + ' or accession number.')
                        set_processbar('bar', index/steps)
                        continue
                    try:
                        record = folio.records(id, id_type)[0]
                    except Exception as ex:
                        alert(f'Error: {antiformat(str(ex))}')
                        break
                    set_processbar('bar', index/steps)
                    if not record:
                        put_error(f'Could not find a record for {id_type.value} {id}.')
                        continue
                    backup_record(record, backup_dir)
                    if id_type in [RecordIdKind.ITEMID, RecordIdKind.BARCODE]:
                        delete_item(folio, record, id)
                    else:
                        put_warning('Instance record deletion is currently turned off.')
                        # delete_instance(folio, record, id)

# permanent loan type
# note type

def list_types_tab():
    return [
        put_grid([[put_markdown('Select a FOLIO type to list:').style('margin-top: 5px'),
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
        put_markdown('Write one or more barcode, HRID, item id, or instance id'
                     + ' in the field below, then press he button to delete'
                     + ' the corresponding FOLIO records. Note that **deleting'
                     + ' instance records will cause multiple holdings and item'
                     + ' records to be deleted**. Handle with extreme caution!'),
        put_textarea('textbox_delete', rows = 4),
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


def backup_record(record, backup_dir):
    timestamp = dt.now(tz = tz.tzlocal()).strftime('%Y%m%d-%H%M%S%f')[:-3]
    id = record['id']
    file = join(backup_dir, id + '.' + timestamp + '.json')
    with open(file, 'w') as f:
        log(f'backing up record {id} to {file}')
        json.dump(record, f, indent = 2)


def delete_item(folio, record, for_id = None):
    id = record['id']
    (success, msg) = folio.operation('delete', f'/inventory/items/{id}')
    if success:
        why = " (for request to delete " + (for_id if for_id else '') + ")"
        put_success(f'Deleted item record {id}{why}')
    else:
        put_error(f'Error: {msg}')


def delete_holdings(folio, record, for_id = None):
    id = record['id']
    (success, msg) = folio.operation('delete', f'/holdings-storage/holdings/{id}')
    if success:
        why = " (for request to delete " + (for_id if for_id else '') + ")"
        put_success(f'Deleted holdings record {id}{why}.')
    else:
        put_error(f'Error: {msg}')


# The following is based on
# https://github.com/FOLIO-FSE/shell-utilities/blob/master/instance-delete

def delete_instance(folio, record, for_id = None):
    inst_id = record['id']

    # Starting at the bottom, delete the item records.
    items = folio.records(inst_id, RecordIdKind.INSTANCEID, RecordKind.ITEM.value)
    put_warning(f'Deleting {pluralized("item record", items, True)} due to'
                + f' the deletion of instance record {inst_id}.')
    for item in items:
        delete_item(folio, item, for_id)

    # Now delete the holdings records.
    holdings = folio.records(inst_id, RecordIdKind.INSTANCEID, RecordKind.HOLDINGS.value)
    put_warning(f'Deleting {pluralized("holdings record", holdings, True)} due to'
                + f' the deletion of instance record {inst_id}.')
    for hr in holdings:
        delete_holdings(folio, hr, for_id)

    # Finally, the instance record. There are two parts to this.
    (success, msg) = folio.operation('delete', f'/instance-storage/instances/{inst_id}/source-record')
    if success:
        (success, msg) = folio.operation('delete', f'/instance-storage/instances/{inst_id}')
        if success:
            why = " (for request to delete " + (for_id if for_id else '') + ")"
            put_info(f'Deleted instance record {inst_id}{why}.')
        else:
            put_error(f'Error: {msg}')
    else:
        put_error(f'Error: {msg}')

    # FIXME
    # Need to deal with EDS update.
