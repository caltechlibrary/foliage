'''
lookup_tab.py: implementation of the "Look up records" tab

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.data_utils import unique, pluralized, flattened
from   commonpy.exceptions import Interrupted
from   commonpy.file_utils import exists, readable
from   commonpy.interrupt import wait, interrupt, interrupted, reset_interrupts
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
from   pywebio.session import run_js, eval_js
from   sidetrack import set_debug, log
import threading

from   foliage.base_tab import FoliageTab
from   foliage.export import export_records
from   foliage.folio import Folio, RecordKind, IdKind, TypeKind
from   foliage.folio import unique_identifiers
from   foliage.ui import confirm, notify, user_file, stop_processbar
from   foliage.ui import tell_success, tell_warning, tell_failure
from   foliage.ui import note_info, note_warn, note_error


# Tab definition class.
# .............................................................................

class LookupTab(FoliageTab):
    def contents(self):
        return {'title': 'Look up records', 'content': tab_contents()}

    def pin_watchers(self):
        return {}


# Tab body.
# .............................................................................

def tab_contents():
    log(f'generating lookup tab contents')
    return [
        put_grid([[
            put_markdown('Input one or more item barcode, item id, item hrid,'
                         + ' instance id, instance hrid, instance accession'
                         + ' number, loan id, loan hrid, user id, or user barcode'
                         + ' in the field below, or by uploading a text file.'),
            put_button('Upload', outline = True,
                       onclick = lambda: load_file()).style('text-align: right'),
        ]], cell_widths = 'auto 100px'),
        put_textarea('textbox_find', rows = 4),
        put_grid([[
            put_radio('select_kind', inline = True,
                      label = 'Kind of record to retrieve:',
                      options = [ ('Item', RecordKind.ITEM, True),
                                  ('Holdings', RecordKind.HOLDINGS),
                                  ('Instance', RecordKind.INSTANCE),
                                  ('Loan', RecordKind.LOAN),
                                  ('User', RecordKind.USER)]),
            put_checkbox("open_loans", inline = True,
                         options = [('Search open loans only', True, True)],
                         help_text = ('When searching for loans, selecting'
                                      + ' this option limits searches to loans'
                                      + ' marked "open".')),
        ]], cell_widths = '55% 45%'),
        put_grid([[
            put_grid([[
                put_text('Output format:'),
            ],[
                put_radio('show_raw', inline = True,
                          options = [('Summary format', 'summary', True),
                                     ('Raw data format', 'json')]),
            ]]),
            put_checkbox("inventory_api", inline = True,
                         options = [('Use inventory API for items and instances',
                                     True, True)],
                         help_text = 'When deselected, the FOLIO storage API is used.'),
        ]], cell_widths = '55% 45%'),
        put_row([
            put_button('Look up records', onclick = lambda: do_find()),
            put_text(''),    # Adds a column, pushing next item to the right.
            put_button('Clear', outline = True,
                       onclick = lambda: clear_tab()).style('text-align: right')
        ])
    ]


# Tab implementation.
# .............................................................................

_last_textbox = ''
_last_results = {}
_last_kind = None
_last_inventory_api = True
_last_open_loans = True


def clear_tab():
    global _last_textbox
    global _last_inventory_api
    log(f'clearing tab')
    clear('output')
    pin.textbox_find = ''
    pin.inventory_api = [True]
    _last_textbox = ''
    _last_inventory_api = [True]
    _last_open_loans = [True]


def stop():
    global _last_textbox
    log(f'stopping')
    interrupt()
    stop_processbar()
    _last_textbox = ''


def load_file():
    log(f'user requesting file upload')
    if (contents := user_file('Upload a file containing identifiers')):
        pin.textbox_find = contents


def do_find():
    global _last_results
    global _last_textbox
    global _last_kind
    global _last_inventory_api
    global _last_open_loans
    log(f'do_find invoked')
    # Normally we'd want to find out if they input any identifiers, but I want
    # to detect *any* change to the input box, so this is a lower-level test.
    if not pin.textbox_find.strip():
        note_error('Please input at least one barcode or other id.')
        return
    reuse_results = False
    if (pin.textbox_find == _last_textbox and pin.select_kind == _last_kind
        and pin.inventory_api == _last_inventory_api
        and pin.open_loans == _last_open_loans):
        if user_wants_reuse():
            reuse_results = True
        else:
            _last_results = {}
    _last_textbox = pin.textbox_find
    _last_kind = pin.select_kind
    _last_inventory_api = pin.inventory_api
    _last_open_loans = pin.open_loans
    kind_wanted = pin.select_kind
    identifiers = unique_identifiers(pin.textbox_find)
    steps = len(identifiers) + 1
    folio = Folio()
    reset_interrupts()
    with use_scope('output', clear = True):
        put_grid([[
            put_markdown(f'_Certain lookups can take a very long time. Please'
                     + ' be patient._').style('color: DarkOrange')
            ], [
            put_processbar('bar', init = 1/steps).style('margin-top: 11px'),
            put_button('Stop', outline = True, color = 'danger',
                       onclick = lambda: stop()).style('text-align: right')
            ]], cell_widths = '85% 15%').style('margin: auto 17px 1.5em 17px')
        for count, id in enumerate(identifiers, start = 2):
            try:
                # Figure out what kind of identifier we were given.
                id_kind = folio.id_kind(id)
                if id_kind is IdKind.UNKNOWN:
                    tell_failure(f'Unrecognized identifier kind: {id}.')
                    continue
                if reuse_results:
                    records = _last_results.get(id)
                else:
                    records = folio.related_records(id, id_kind, kind_wanted,
                                                    pin.inventory_api, pin.open_loans)
                    _last_results[id] = records
                if not records or len(records) == 0:
                    tell_failure(f'No {kind_wanted} record(s) found for {id_kind} "{id}".')
                    continue

                # Report the results & how we got them.
                source = 'storage'
                if pin.inventory_api and kind_wanted in ['item', 'instance']:
                    source = 'inventory'
                this = pluralized(kind_wanted + f' {source} record', records, True)
                how = f'by searching for {id_kind} **{id}**.'
                tell_success(f'Found {this} {how}')
                show_index = (len(records) > 1)
                for index, record in enumerate(records, start = 1):
                    print_record(record, id, index, show_index, pin.show_raw == 'json')
            except Interrupted as ex:
                log('stopping due to interruption')
                break
            except Exception as ex:
                import traceback
                log('Exception info: ' + str(ex) + '\n' + traceback.format_exc())
                tell_failure(f'Error: ' + str(ex))
                stop_processbar()
                return
            finally:
                if not interrupted():
                    set_processbar('bar', count/steps)
        stop_processbar()
        if interrupted():
            tell_warning('**Stopped**.')
        else:
            what = pluralized(f'{kind_wanted} identifier', identifiers, True)
            put_markdown(f'Finished looking up {what}.').style('text-align: center')
            put_button('Export', outline = True,
                       onclick = lambda: do_export(_last_results, kind_wanted),
                       ).style('float: right; margin: auto 17px auto 10px')


def print_record(record, identifier, index, show_index, show_raw):
    log(f'printing {record.kind} record {record.id}')
    if show_index:
        put_markdown(f'{record.kind.title()} record #{index}:')

    if show_raw:
        put_code(pformat(record.data, indent = 2))
    elif record.kind is RecordKind.ITEM:
        # Caution: left-hand values contain nonbreaking spaces (invisible here).
        if 'title' in record.data:
            # Inventory record version.
            put_table([
                ['Title'                     , record.data['title']],
                ['Barcode'                   , record.data['barcode']],
                ['Call number'               , record.data['callNumber']],
                [f'{record.kind.title()} id' , record.data['id']],
                ['Effective location'        , record.data['effectiveLocation']['name']],
                ['Permanent location'        , record.data['permanentLocation']['name']],
                ['Status'                    , record.data['status']['name']],
                ['Tags'                      , ', '.join(t for t in record.data['tags']['tagList'])],
                ['Notes'                     , '\n'.join(record.data['notes'])],
                ['HRID'                      , record.data['hrid']],
                ['Created'                   , record.data['metadata']['createdDate']],
                ['Updated'                   , record.data['metadata']['updatedDate']],
            ]).style('font-size: 90%; margin: auto 17px 1.5em 17px')
        else:
            # Storage record version.
            put_table([
                ['Barcode'                   , record.data['barcode']],
                ['Call number'               , record.data['itemLevelCallNumber']],
                [f'{record.kind.title()} id' , record.data['id']],
                ['Effective location'        , record.data['effectiveLocationId']],
                ['Permanent location'        , record.data['permanentLocationId']],
                ['Tags'                      , ', '.join(t for t in record.data['tags']['tagList'])],
                ['Notes'                     , '\n'.join(record.data['notes'])],
                ['HRID'                      , record.data['hrid']],
                ['Created'                   , record.data['metadata']['createdDate']],
                ['Updated'                   , record.data['metadata']['updatedDate']],
            ]).style('font-size: 90%; margin: auto 17px 1.5em 17px')
    elif record.kind is RecordKind.INSTANCE:
        # Caution: left-hand values contain nonbreaking spaces (invisible here).
        if record.data['classifications']:
            call_number = record.data['classifications'][0]['classificationNumber']
        else:
            call_number = ''
        put_table([
            ['Title'                     , record.data['title']],
            ['Call number'               , call_number],
            [f'{record.kind.title()} id' , record.data['id']],
            ['Tags'                      , ', '.join(t for t in record.data['tags']['tagList'])],
            ['HRID'                      , record.data['hrid']],
            ['Created'                   , record.data['metadata']['createdDate']],
            ['Updated'                   , record.data['metadata']['updatedDate']],
        ]).style('font-size: 90%; margin: auto 17px 1.5em 17px')
    elif record.kind is RecordKind.HOLDINGS:
        # Caution: left-hand values contain nonbreaking spaces (invisible here).
        put_table([
            [f'{record.kind.title()} id' , record.data['id']],
            ['HRID'                      , record.data['hrid']],
            ['Holdings type id'          , record.data['holdingsTypeId']],
            ['Instance id'               , record.data['instanceId']],
            ['Created'                   , record.data['metadata']['createdDate']],
            ['Updated'                   , record.data['metadata']['updatedDate']],
        ]).style('font-size: 90%; margin: auto 17px 1.5em 17px')
    elif record.kind is RecordKind.USER:
        # Caution: left-hand values contain nonbreaking spaces (invisible here).
        put_table([
            ['Username'                  , record.data['username']],
            ['Barcode'                   , record.data['barcode']],
            [f'{record.kind.title()} id' , record.data['id']],
            ['Patron group'              , record.data['patronGroup']],
            ['Created'                   , record.data['metadata']['createdDate']],
            ['Updated'                   , record.data['metadata']['updatedDate']],
        ]).style('font-size: 90%; margin: auto 17px 1.5em 17px')
    elif record.kind is RecordKind.LOAN:
        put_table([
            [f'{record.kind.title()} id' , record.data['id']],
            ['User id'                   , record.data['userId']],
            ['Item id'                   , record.data['itemId']],
            ['Loan date'                 , record.data['loanDate']],
            ['Due date'                  , record.data['dueDate']],
            ['Created'                   , record.data['metadata']['createdDate']],
            ['Updated'                   , record.data['metadata']['updatedDate']],
        ]).style('font-size: 90%; margin: auto 17px 1.5em 17px')


def user_wants_reuse():
    event = threading.Event()
    answer = False

    def clk(val):
        nonlocal answer
        answer = val
        event.set()

    pins = [
        put_text('The list of identifiers and the kind of record to retrieve'
                 + ' are unchanged from the previous lookup. Should the results'
                 + ' be reused, or should the identifiers be looked up again?'),
        put_html('<br>'),
        put_buttons([
            {'label': 'Reuse the results', 'value': True},
            {'label': 'Search again', 'value': False, 'color': 'secondary'},
        ], onclick = clk).style('float: left')
    ]
    popup(title = 'Should results be reused?', content = pins, closable = False)

    event.wait()
    close_popup()
    wait(0.5)                           # Give time for popup to go away.

    return answer


def do_export(results, record_kind):
    log(f'exporting {record_kind} {pluralized("record", results, True)}')
    # Results is a dictionary; each value is a list of records. Unwind it.
    all_records = [item for value in results.values() for item in value]
    export_records(all_records, record_kind)
