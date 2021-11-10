'''
lookup_tab.py: implementation of the "Look up records" tab

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.data_utils import unique, pluralized, flattened
from   commonpy.file_utils import exists, readable
from   commonpy.interrupt import wait
import json
from   pprint import pformat
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
from   sidetrack import set_debug, log

from   .export import export
from   .folio import Folio, RecordKind, RecordIdKind, TypeKind, NAME_KEYS
from   .folio import unique_identifiers
from   .ui import alert, warn, confirm, notify, user_file


# Tab creation function.
# .............................................................................

def lookup_tab():
    return [
        put_grid([[
            put_markdown('Input one or more item barcode, item id, item hrid,'
                         + ' instance id, instance hrid, instance accession'
                         + ' number, user id, or user barcode in the field'
                         + ' below, or by uploading a text file.'),
            put_button('Upload', outline = True,
                       onclick = lambda: load_file()).style('text-align: right'),
        ]], cell_widths = 'auto 100px'),
        put_textarea('textbox_find', rows = 4),
        put_grid([[
            put_radio('select_kind_find', inline = True,
                      label = 'Type of record to retrieve:',
                      options = [ ('Item', RecordKind.ITEM, True),
                                  ('Instance', RecordKind.INSTANCE),
                                  ('Loan', RecordKind.LOAN),
                                  ('User', RecordKind.USER)]),
            put_markdown('_Note: loans found using item, instance, or user'
                         + ' identifiers are **open** loans only. Likewise,'
                         + ' user records found using item/instance/loan id\'s'
                         + ' are based on **open** loans only._'),
        ]], cell_widths = '47% 53%'),
        put_radio('show_raw', inline = True,
                  options = [('Summary format', 'summary', True),
                             ('Raw data format', 'json')]),
        put_row([
            put_button('Look up records', onclick = lambda: do_find()),
            put_text(''),    # Adds a column, pushing next item to the right.
            put_button(' Clear ', outline = True,
                       onclick = lambda: clear_tab()).style('text-align: right')
        ])
    ]


# Miscellaneous helper functions.
# .............................................................................

def clear_tab():
    clear('output')
    pin.textbox_find = ''


def load_file():
    if (file := user_file('Upload a file containing identifiers')):
        pin.textbox_find = file


def do_find():
    log(f'do_find invoked')
    folio = Folio()
    if not pin.textbox_find:
        alert('Please input at least one barcode or other id.')
        return
    with use_scope('output', clear = True):
        identifiers = unique_identifiers(pin.textbox_find)
        steps = len(identifiers) + 1
        put_processbar('bar', init = 1/steps);
        for index, id in enumerate(identifiers, start = 2):
            put_html('<br>')
            id_type = folio.record_id_type(id)
            if id_type == RecordIdKind.UNKNOWN:
                log(f'could not recognize type of {id}')
                put_error(f'Could not recognize the identifier type of {id}.')
                set_processbar('bar', index/steps)
                continue

            record_kind = pin.select_kind_find
            try:
                records = folio.records(id, id_type, record_kind)
            except Exception as ex:
                log(f'exception trying to get records for {id}: ' + str(ex))
                put_error(f'Error: ' + str(ex))
                break
            finally:
                set_processbar('bar', index/steps)
            if not records or len(records) == 0:
                put_error(f'No {record_kind} record(s) found for {id_type} "{id}".')
                continue
            this = pluralized(record_kind + " record", records, True)
            how = f'by searching for {id_type} **{id}**'
            put_success(put_markdown(f'Found {this} {how}')).style('text-align: center')
            show_index = (len(records) > 1)
            for index, record in enumerate(records, start = 1):
                print_record(record, record_kind, id, id_type,
                             index, show_index, pin.show_raw == 'json')
        put_html('<br>')
        put_button('Export', outline = True,
                   onclick = lambda: export(records, record_kind),
                   ).style('margin-left: 0').style('margin-left: 10px; float: right')


def print_record(record, record_kind, identifier, id_type, index, show_index, show_raw):
    if show_index:
        put_markdown(f'{record_kind.title()} record #{index}:')

    if show_raw:
        put_code(pformat(record, indent = 2))
    elif record_kind == 'item':
        # Caution: left-hand values contain nonbreaking spaces (invisible here).
        put_table([
            ['Title'                     , record['title']],
            ['Barcode'                   , record['barcode']],
            ['Call number'               , record['callNumber']],
            [f'{record_kind.title()} id' , record['id']],
            ['Effective location'        , record['effectiveLocation']['name']],
            ['Permanent location'        , record['permanentLocation']['name']],
            ['Status'                    , record['status']['name']],
            ['Tags'                      , ', '.join(t for t in record['tags']['tagList'])],
            ['Notes'                     , '\n'.join(record['notes'])],
            ['HRID'                      , record['hrid']],
            ['Created'                   , record['metadata']['createdDate']],
            ['Updated'                   , record['metadata']['updatedDate']],
        ]).style('margin-left: 2em; font-size: 90%')
    elif record_kind == 'instance':
        # Caution: left-hand values contain nonbreaking spaces (invisible here).
        put_table([
            ['Title'                     , record['title']],
            ['Call number'               , record['classifications'][0]['classificationNumber']],
            [f'{record_kind.title()} id' , record['id']],
            ['Tags'                      , ', '.join(t for t in record['tags']['tagList'])],
            ['HRID'                      , record['hrid']],
            ['Created'                   , record['metadata']['createdDate']],
            ['Updated'                   , record['metadata']['updatedDate']],
        ]).style('margin-left: 2em; font-size: 90%')
    elif record_kind == 'user':
        # Caution: left-hand values contain nonbreaking spaces (invisible here).
        put_table([
            ['Username'                  , record['username']],
            ['Barcode'                   , record['barcode']],
            [f'{record_kind.title()} id' , record['id']],
            ['Patron group'              , record['patronGroup']],
            ['Created'                   , record['metadata']['createdDate']],
            ['Updated'                   , record['metadata']['updatedDate']],
        ]).style('margin-left: 2em; font-size: 90%')
    elif record_kind == 'loan':
        put_table([
            [f'{record_kind.title()} id' , record['id']],
            ['User id'                   , record['userId']],
            ['Item id'                   , record['itemId']],
            ['Loan date'                 , record['loanDate']],
            ['Due date'                  , record['dueDate']],
            ['Created'                   , record['metadata']['createdDate']],
            ['Updated'                   , record['metadata']['updatedDate']],
        ]).style('margin-left: 2em; font-size: 90%')
