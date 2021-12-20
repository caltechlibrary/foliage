'''
export.py: let the user export records and save them to a file

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.data_utils import unique, pluralized, flattened
from   commonpy.interrupt import wait
import csv
from   io import BytesIO, StringIO
import json
from   pywebio.input import input, select, checkbox, radio
from   pywebio.input import NUMBER, TEXT, input_update, input_group
from   pywebio.output import put_text, put_markdown, put_row, put_html
from   pywebio.output import toast, popup, close_popup, put_buttons, put_button, put_error
from   pywebio.output import use_scope, set_scope, clear, remove, put_warning
from   pywebio.output import put_success, put_info, put_table, put_grid, span
from   pywebio.output import put_tabs, put_image, put_scrollable, put_code, put_link
from   pywebio.output import put_processbar, set_processbar, put_loading
from   pywebio.output import put_column
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
from   pywebio.pin import put_textarea, put_radio, put_checkbox, put_select
from   pywebio.session import run_js, eval_js, download
from   sidetrack import set_debug, log
from   slugify import slugify
import threading

from   foliage.folio import Folio, RecordKind, IdKind, TypeKind
from   foliage.ui import quit_app, reload_page, confirm, notify


# Main functions.
# .............................................................................

def export_records(records, kind):
    log(f'exporting {pluralized(kind + " record", records, True)}')
    if not records:
        note_error('Nothing to export')
        return

    event = threading.Event()
    clicked_ok = False

    def clk(val):
        nonlocal clicked_ok
        clicked_ok = val
        event.set()

    log(f'asking user for output format')
    pins = [
        put_radio('file_fmt', options = [('CSV', 'csv', True), ('JSON', 'json')]),
        put_buttons([
            {'label': 'Cancel', 'value': False, 'color': 'secondary'},
            {'label': 'OK', 'value': True},
        ], onclick = clk).style('float: right; vertical-align: center')
    ]
    popup(title = 'Select the format for the exported records:', content = pins)

    event.wait()
    close_popup()
    wait(0.5)                           # Give time for popup animation.

    if not clicked_ok:
        log('user clicked cancel')
        return

    if pin.file_fmt == 'csv':
        log('user selected CSV format')
        export_records_csv(records, kind)
    else:
        log('user selected JSON format')
        export_records_json(records, kind)


def export_data(data_list, filename):
    if not data_list:
        return

    # Assume all the items have the same structure and it is flat.
    columns = [name.lower() for name in data_list[0].keys()]
    # Try to find a good sort key, else default to 1st key found.
    if 'id' in columns:
        sort_key = 'id'
    elif 'name' in columns:
        sort_key = 'name'
    else:
        sort_key = data_list[0].keys()[0]

    # Write into an in-memory, file-like object & tell PyWebIO to download it.
    with StringIO() as tmp:
        writer = csv.DictWriter(tmp, fieldnames = columns)
        writer.writeheader()
        for item_dict in sorted(data_list, key = lambda d: d[sort_key]):
            writer.writerow(item_dict)
        tmp.seek(0)
        bytes = BytesIO(tmp.read().encode('utf8')).getvalue()
        download(filename, bytes)


# Miscellaneous helper functions.
# .............................................................................

def export_records_csv(records, kind):
    log(f'exporting {pluralized("record", records, True)} to CSV')
    # We have nested dictionaries, which can't be stored directly in CSV, so
    # first we have to flatten the dictionaries inside the list.
    records = [flattened(r.data) for r in records]

    # Next, we need a list of column names to pass to the CSV function.  This
    # is complicated by the fact that JSON dictionaries can have fields that
    # themselves have JSON dictionaries for values, and any given record (1)
    # may not have values for all those fields, and (2) may have values that
    # are lists, but with different numbers of elements. So we can't just
    # look at one record to figure out all the columns we need: we have to
    # look at _all_ records and create a maximal set before we write the CSV.
    columns = set(flattened(record.keys() for record in records))

    # Sort the column names to move the name & id fields to the front.
    name_key = RecordKind.name_key(kind)
    def name_id_key(column_name):
        return (column_name != name_key, column_name != 'id', column_name)
    columns = sorted(list(columns), key = lambda x: name_id_key(x))

    # Write into an in-memory, file-like object & tell PyWebIO to download it.
    with StringIO() as tmp:
        writer = csv.DictWriter(tmp, fieldnames = columns)
        writer.writeheader()
        for item_dict in sorted(records, key = lambda d: d[name_key]):
            writer.writerow(item_dict)
        tmp.seek(0)
        bytes = BytesIO(tmp.read().encode('utf8')).getvalue()
        download(f'{slugify(kind)}-records.csv', bytes)


def export_records_json(records, kind):
    log(f'exporting {pluralized("record", records, True)} to JSON')
    records_json = [r.data for r in records]
    with StringIO() as tmp:
        json.dump(records_json, tmp)
        tmp.seek(0)
        bytes = BytesIO(tmp.read().encode('utf8')).getvalue()
        download(f'{slugify(kind)}-records.json', bytes)
