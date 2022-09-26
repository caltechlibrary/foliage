'''
export.py: let the user export records and save them to a file

Copyright
---------

Copyright (c) 2021-2022 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.data_utils import pluralized, flattened
from   commonpy.interrupt import wait
import csv
from   io import BytesIO, StringIO
import json
from   pywebio.output import popup, close_popup, put_buttons
from   pywebio.pin import pin, put_radio
from   pywebio.session import download
from   sidetrack import log
from   slugify import slugify
import threading

from   foliage.folio import RecordKind
from   foliage.ui import note_error, note_warn


# Main functions.
# .............................................................................

def export_records(records, kind):
    log(f'exporting {pluralized(kind + " record", records, True)}')
    if not records:
        note_error('No results – nothing to export.')
        return

    event = threading.Event()
    clicked_ok = False

    def clk(val):
        nonlocal clicked_ok
        clicked_ok = val
        event.set()

    log('asking user for output format')
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


def export_data(data_list, filename, sort = True):
    if not data_list:
        return

    # Assume all the items have the same structure and it is flat.
    columns = list(data_list[0].keys())
    if sort:
        # Try to find a good sort key, else default to 1st key found.
        if 'id' in columns:
            sort_key = 'id'
        elif 'record id' in columns:
            sort_key = 'Record ID'
        elif 'name' in columns:
            sort_key = 'name'
        else:
            sort_key = list(data_list[0].keys())[0]
        data_list = sorted(data_list, key = lambda d: d[sort_key])

    # Write into an in-memory, file-like object & tell PyWebIO to download it.
    with StringIO() as tmp:
        writer = csv.DictWriter(tmp, fieldnames = columns)
        writer.writeheader()
        for item_dict in data_list:
            writer.writerow(item_dict)
        tmp.seek(0)
        bytes_ = BytesIO(tmp.read().encode('utf8')).getvalue()
        download(filename, bytes_)


# Miscellaneous helper functions.
# .............................................................................

def export_records_csv(records, kind):
    log(f'exporting {pluralized("record", records, True)} to CSV')
    if len(records) == 0:
        note_warn('List of records is empty.')

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
    # FIXME storage records don't have the same fields as inventory records.
    # RecordKind.name_key needs a way to make that distinction.
    if name_key not in records[0]:
        name_key = 'id'

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
        bytes_ = BytesIO(tmp.read().encode('utf8')).getvalue()
        download(f'{slugify(kind)}-records.csv', bytes_)


def export_records_json(records, kind):
    log(f'exporting {pluralized("record", records, True)} to JSON')
    if len(records) == 0:
        note_warn('List of records is empty.')
    records_json = [r.data for r in records]
    with StringIO() as tmp:
        json.dump(records_json, tmp)
        tmp.seek(0)
        bytes_ = BytesIO(tmp.read().encode('utf8')).getvalue()
        download(f'{slugify(kind)}-records.json', bytes_)
