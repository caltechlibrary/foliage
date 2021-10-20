
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

if __debug__:
    from sidetrack import set_debug, log

from .folio import folio_data
from .ui import quit_app, show_error


# Overall main page structure
# .............................................................................

def foliage():
    put_image(logo_image(), width='90px').style('float: right')
    put_html('<h1 class="text-center">Foliage</h1>')
    put_markdown('_Foliage ("FOLIo chAnGe Editor") is an application that runs'
                 ' on your computer and lets you perform bulk operations in'
                 ' FOLIO over the network. Foliage uses this web page as a way'
                 ' of implementing its user interface._')

    put_tabs([
        {'title': 'Look up records', 'content': find_records_tab()},
        {'title': 'Delete records', 'content': delete_records_tab()},
        {'title': 'Change records', 'content': change_records_tab()},
        ])

    log(f'page layout finished; waiting for user input')
    barcodes = None
    record_type = 'items'
    while True:
        event = pin_wait_change('set_record_type', 'set_barcodes', 'do_find')
        event_type = event['name']
        if event_type == 'set_record_type':
            record_type = event['value']
        elif event_type == 'set_barcodes':
            barcodes = event['value']
        elif event_type == 'do_find':
            if not barcodes:
                toast('Please input at least one barcode.', color = 'error')
            else:
                clear('output')
                with use_scope('output'):
                    given = unique(list_from_string(barcodes))
                    put_markdown(f'Found {pluralized("unique barcode", given, True)}.')
                    for barcode in given:
                        data = folio_data(barcode, record_type)
                        put_markdown(f'Raw FOLIO data for barcode **{barcode}**:')
                        put_code(pformat(data, indent = 2))


def logo_image():
    here = dirname(__file__)
    image_file = join(here, 'data', 'foliage-icon.png')
    if exists(image_file):
        with open(image_file, 'rb') as f:
            return f.read()
    else:
        log(f'could not find logo image in {here}')


def delete_items(button, barcodes = []):
    if button == 'cancel':
        put_markdown('**Cancelled**')
    elif eval_js('confirm_action("This cannot be undone. Confirm deletions?")'):
        put_markdown('**Proceeding with deletions ...**')
        for barcode in barcodes:
            put_text(f'Deleting {barcode}')
        put_markdown('**Done.**')
    else:
        put_markdown('**Cancelled**')


def find_records_tab():
    return [
        put_markdown('Given one or more barcode numbers, this will look up'
                     ' the FOLIO records corresponding to those numbers and'
                     ' display the raw FOLIO inventory record data. Write the'
                     ' barcode numbers below, one per line.'),
        put_textarea('set_barcodes', rows = 4),
        put_radio('set_record_type', label = 'Type of record to retrieve:',
                  inline = True, options = [
                      ('Item', 'items', True),
                      ('Instance', 'instances'),
                      # ('Holdings', 'holdings')
                  ]),
        put_actions('do_find', buttons = ['Look up barcodes']),
    ]


def change_records_tab():
    return 'Forthcoming ...'


def delete_records_tab():
    return 'Forthcoming ...'


def list_from_string(barcodes):
    return [number.strip(',.') for number in barcodes.splitlines()]
