
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
from   pywebio.output import use_scope, set_scope, clear, remove
from   pywebio.output import put_tabs, put_image, put_scrollable, put_code
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
from   pywebio.pin import put_textarea, put_radio
from   pywebio.session import run_js, eval_js
import re

if __debug__:
    from sidetrack import set_debug, log

from .folio import folio_data
from .ui import quit_app, show_error, confirm


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

    log(f'page layout finished; waiting for user input')
    text = None
    record_type = 'items'
    while True:
        event = pin_wait_change('set_record_type_find', 'edit_barcodes_find',
                                'edit_barcodes_delete', 'do_find', 'do_delete')
        event_type = event['name']
        if event_type == 'set_record_type_find':
            record_type = event['value']
        elif event_type in ['edit_barcodes_find', 'edit_barcodes_delete']:
            text = event['value'].strip()
        elif event_type == 'do_find':
            if not text:
                toast('Please input at least one barcode.', color = 'error')
                continue
            clear('find_tab_output')
            with use_scope('find_tab_output'):
                barcodes = unique_barcodes(text)
                put_markdown(f'Looking up {pluralized("unique barcode", barcodes, True)} ...')
                for barcode in barcodes:
                    data = folio_data(barcode, record_type)
                    if data:
                        put_markdown(f'Raw FOLIO data for barcode **{barcode}**:')
                        put_code(pformat(data, indent = 2))
                    else:
                        put_error(f'No record for barcode {barcode} found.')
        elif event_type == 'do_delete':
            if not text:
                toast('Please input at least one barcode.', color = 'error')
                continue
            clear('delete_tab_output')
            clear('find_tab_output')
            if not confirm('Danger: this cannot be undone. Really delete the records?'):
                continue
            with use_scope('delete_tab_output'):
                barcodes = unique_barcodes(text)
                put_markdown(f'Deleting {pluralized("record", barcodes, True)} ...')
                for barcode in barcodes:
                    put_text(f'Deleting {record_type} record for {barcode}:')


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
        put_markdown('Given one or more barcode numbers, this will look up'
                     ' the FOLIO records corresponding to those numbers and'
                     ' display the raw FOLIO inventory record data. Write the'
                     ' barcode numbers below, one per line.'),
        put_textarea('edit_barcodes_find', rows = 4),
        put_radio('set_record_type_find', label = 'Type of record to retrieve:',
                  inline = True, options = [
                      ('Item', 'items', True),
                      ('Instance', 'instances'),
                      # ('Holdings', 'holdings')
                  ]),
        put_actions('do_find', buttons = ['Look up barcodes']),
    ]


def delete_records_tab():
    return [
        put_markdown('Given one or more barcode numbers, this will delete the'
                     ' corresponding FOLIO records to those numbers. Write the'
                     ' barcode numbers below, one per line.'),
        put_textarea('edit_barcodes_delete', rows = 4),
        put_radio('set_record_type_delete', label = 'Type of record to delete:',
                  inline = True, options = [
                      ('Item', 'items', True),
                      ('Instance', 'instances'),
                      # ('Holdings', 'holdings')
                  ]),
        put_actions('do_delete',
                    buttons = [dict(label = 'Delete FOLIO records',
                                    value = 'delete', color = 'danger')]),
    ]


def change_records_tab():
    return 'Forthcoming ...'


def unique_barcodes(barcodes):
    lines = barcodes.splitlines()
    items = flatten(re.split(r'\s+|,+|\.+', line) for line in lines)
    return unique(filter(None, items))
