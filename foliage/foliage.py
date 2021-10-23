
from   boltons.iterutils import flatten
import csv
from   commonpy.data_utils import unique, pluralized
from   commonpy.file_utils import exists
from   commonpy.interrupt import wait
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
from   pywebio.pin import put_textarea, put_radio, put_checkbox
from   pywebio.session import run_js, eval_js
import re

if __debug__:
    from sidetrack import set_debug, log

from .folio import Folio, IdType
from .ui import quit_app, alert, warn, confirm


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
        {'title': 'Delete records', 'content': delete_records_tab()},
        {'title': 'Change records', 'content': change_records_tab()},
        ])

    folio = Folio()
    text = None
    record_type = 'item'
    show_raw = False

    log(f'page layout finished; waiting for user input')
    while True:
        event = pin_wait_change('set_record_type_find', 'edit_ids_find',
                                'edit_ids_delete', 'do_find', 'do_delete',
                                'set_raw')
        event_type = event['name']

        if event_type == 'set_record_type_find':
            record_type = event['value']
            log(f'selected record type {record_type}')
            clear('output')

        elif event_type == 'set_raw':
            show_raw = not show_raw
            log(f'show_raw = {show_raw}')
            clear('output')

        elif event_type in ['edit_ids_find', 'edit_ids_delete']:
            text = event['value'].strip()
            clear('output')

        elif event_type == 'do_find':
            log(f'do_find invoked')
            if not text:
                alert('Please input at least one barcode or other id.')
                continue
            clear('output')
            with use_scope('output'):
                identifiers = unique_identifiers(text)
                num_identifiers = len(identifiers)
                put_processbar('bar');
                for index, identifier in enumerate(identifiers, start = 1):
                    id_type = folio.id_type(identifier)
                    if id_type == IdType.UNKNOWN:
                        put_error(f'Could not recognize "{identifier}" as a'
                                  + ' barcode, HRID, item id, instance id,'
                                  + ' or holdings id.')
                        continue
                    record = folio.record(identifier, record_type)
                    if not record:
                        put_error('Could not find a record for '
                                  + f' {id_type.value} "{identifier}".')
                        continue
                    print_record(record, identifier, record_type, show_raw)
                    set_processbar('bar', index/num_identifiers)

        elif event_type == 'do_delete':
            log(f'do_delete invoked')
            if not text:
                alert('Please input at least one barcode or other id.')
                continue
            if not confirm('WARNING: you are about to delete records in FOLIO'
                           + ' permanently. This cannot be undone.\\n\\nProceed?'):
                continue
            clear('output')
            with use_scope('output'):
                identifiers = unique_identifiers(text)
                num_identifiers = len(identifiers)
                put_processbar('bar');
                for index, identifier in enumerate(identifiers, start = 1):
                    id_type = folio.id_type(identifier)
                    if id_type == IdType.UNKNOWN:
                        put_error(f'Could not recognize "{identifier}" as a'
                                  + ' barcode, HRID, item id, instance id,'
                                  + ' or holdings id.')
                        continue
                    record = folio.record(identifier, record_type)
                    if not record:
                        put_error('Could not find a record for '
                                  + f' {id_type.value} "{identifier}".')
                        continue
                    id = record['id']
                    put_text(f'Deleting {identifier} {record_type} record ...')
                    (success, error) = folio.operation('delete', f'/inventory/items/{id}')
                    if success:
                        put_success(f'Deleted {record_type} record for {identifier}.')
                    else:
                        put_error(f'Error: {error}')
                    set_processbar('bar', index/num_identifiers)


def logo_image():
    here = dirname(__file__)
    image_file = join(here, 'data', 'foliage-icon.png')
    if exists(image_file):
        with open(image_file, 'rb') as f:
            return f.read()
    else:
        log(f'could not find logo image in {image_file}')


def find_records_tab():
    return [
        put_markdown('Write one or more barcode, HRID, item id, or instance '
                     + ' id in the field below to find the FOLIO records.'),
        put_textarea('edit_ids_find', rows = 4),
        put_row([
            put_radio('set_record_type_find', inline = True,
                      label = 'Type of record to retrieve:',
                      options = [ ('Item', 'item', True),
                                  ('Instance', 'instance')]),
            put_text(''), # Adds a column, pushing next item to the right.
            put_checkbox('set_raw', options = ['Show raw data from FOLIO'])]),
        put_actions('do_find', buttons = ['Look up records']),
    ]


def delete_records_tab():
    return [
        put_markdown('Write one or more barcode, HRID, item id, or instance '
                     + ' id in the field below to delete the FOLIO records.'),
        put_textarea('edit_ids_delete', rows = 4),
        put_radio('set_record_type_delete', inline = True,
                  label = 'Type of record to delete:',
                  options = [ ('Item', 'item', True),
                              ('Instance', 'instance')]),
        put_actions('do_delete',
                    buttons = [dict(label = 'Delete FOLIO records',
                                    value = 'delete', color = 'danger')]),
    ]


def change_records_tab():
    return 'Forthcoming ...'


def print_record(record, identifier, record_type, show_raw):
    if show_raw:
        put_markdown(f'Raw FOLIO data for **{identifier}**:')
        put_code(pformat(record, indent = 2))
    elif record_type == 'item':
        put_html('<br>')
        put_grid([[put_markdown(f'**{identifier}**'),
                   put_table([
                       ['Title', record['title']],
                       ['Call number', record['callNumber']],
                       ['Effective location', record['effectiveLocation']['name']],
                       ['Permanent location', record['permanentLocation']['name']],
                       ['Status', record['status']['name']],
                       ['Tags', ', '.join(tags for tags in record['tags']['tagList'])],
                       ['Notes', '\n'.join(record['notes'])],
                       ['HRID', record['hrid']],
                       [f'{record_type.title()} id', record['id']]]).style('font-size: smaller')]],
                 cell_widths = "20% 80%")
    elif record_type == 'instance':
        put_html('<br>')
        put_grid([[put_markdown(f'**{identifier}**'),
                   put_table([
                       ['Title', record['title']],
                       ['Call number', record['classifications'][0]['classificationNumber']],
                       ['Tags', ', '.join(tags for tags in record['tags']['tagList'])],
                       ['HRID', record['hrid']],
                       [f'{record_type.title()} id', record['id']]]).style('font-size: smaller')]],
                 cell_widths = "20% 80%")


def unique_identifiers(text):
    lines = text.splitlines()
    identifiers = flatten(re.split(r'\s+|,+|\.+', line) for line in lines)
    return unique(filter(None, identifiers))
