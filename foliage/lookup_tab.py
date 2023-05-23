'''
lookup_tab.py: implementation of the "Look up records" tab

Copyright
---------

Copyright (c) 2021-2022 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.data_utils import pluralized
from   commonpy.exceptions import Interrupted
from   commonpy.interrupt import wait, interrupt, reset_interrupts
from   pprint import pformat
from   pywebio.output import put_text, put_markdown, put_row, put_html
from   pywebio.output import popup, close_popup, put_buttons, put_button
from   pywebio.output import use_scope, clear, put_table, put_grid, put_scope
from   pywebio.output import put_code, put_processbar, set_processbar
from   pywebio.output import clear_scope
from   pywebio.pin import pin, put_textarea, put_radio, put_checkbox
from   pywebio.session import eval_js
from   sidetrack import log
import threading

from   foliage.base_tab import FoliageTab
from   foliage.export import export_records
from   foliage.folio import Folio, RecordKind, IdKind, TypeKind
from   foliage.folio import unique_identifiers, Record
from   foliage.ui import user_file, stop_processbar
from   foliage.ui import tell_success, tell_warning, tell_failure
from   foliage.ui import note_error, PROGRESS_BOX


# Tab definition class.
# .............................................................................

class LookupTab(FoliageTab):
    def contents(self):
        return {'title': 'Look up records', 'content': tab_contents()}

    def pin_watchers(self):
        return {}


# Tab layout.
# .............................................................................

column_widths = '54% 46%'

def tab_contents():
    log('generating lookup tab contents')
    return [
        put_grid([[
            put_markdown('Input one or more item barcode, item id, item hrid,'
                         ' instance id, instance hrid, instance accession'
                         ' number, loan id, loan hrid, user id, or user'
                         ' barcode below, or upload a file containing them.'),
            put_button('Upload', outline = True,
                       onclick = lambda: load_file()).style('text-align: right'),
        ]], cell_widths = 'auto 100px'),
        put_textarea('textbox_find', rows = 4),
        put_grid([[
            put_radio('select_kind', inline = True,
                      label = 'Kind of record to retrieve:',
                      options = [('Item', RecordKind.ITEM, True),
                                 ('Holdings', RecordKind.HOLDINGS),
                                 ('Instance', RecordKind.INSTANCE),
                                 ('Loan', RecordKind.LOAN),
                                 ('User', RecordKind.USER)]),
            put_checkbox("open_loans", inline = True,
                         options = [('Search open loans only', True, True)],
                         help_text = ('When searching for loans (and users,'
                                      ' based on loans), limit searches to'
                                      ' open loans only. Deselect'
                                      ' to search all loans.')),
        ]], cell_widths = column_widths),
        put_grid([[
            put_grid([[
                put_text('Format in which to display records:'),
            ], [
                put_radio('show_raw', inline = True,
                          options = [('Summary', 'summary', True),
                                     ('Enhanced summary', 'enhanced'),
                                     ('Raw data', 'json')]),
            ]]),
            put_checkbox("inventory_api", inline = True,
                         options = [('Use FOLIO "inventory" API',
                                     True, True)],
                         help_text = ("FOLIO's Inventory API shows more fields but"
                                      ' some values are computed. Deselect to'
                                      ' get pure records from the storage API.')),
        ]], cell_widths = column_widths),
        put_row([
            put_button('Look up records', onclick = lambda: do_find()),
            put_text(''),    # Adds a column, pushing next item to the right.
            put_button('Clear', outline = True,
                       onclick = lambda: clear_tab()).style('text-align: right')
        ])
    ]


# Tab implementation.
# .............................................................................

_interrupted = False
_running = False
_last_textbox = ''
_last_results = {}
_last_kind = None
_last_inventory_api = True
_last_open_loans = True
_location_map = None
_loan_map = None


def load_file():
    log('user requesting file upload')
    if (contents := user_file('Upload a file containing identifiers')):
        pin.textbox_find = contents


def init_location_map():
    global _location_map
    if _location_map is None:
        log('building map of location names')
        folio = Folio()
        _location_map = {x.data['id']: x.data['name']
                         for x in folio.types(TypeKind.LOCATION)}


def init_loan_map():
    global _loan_map
    if _loan_map is None:
        log('building map of loan types')
        folio = Folio()
        _loan_map = {x.data['id']: x.data['name']
                     for x in folio.types(TypeKind.LOAN)}


def inputs_are_unchanged():
    global _last_textbox
    global _last_kind
    global _last_inventory_api
    global _last_open_loans
    unchanged = (pin.textbox_find == _last_textbox
                 and pin.select_kind == _last_kind
                 and pin.inventory_api == _last_inventory_api
                 and pin.open_loans == _last_open_loans)
    log(f'field values are considered {"unchanged" if unchanged else "changed"}')
    return unchanged


def clear_tab():
    global _last_textbox
    global _last_inventory_api
    global _last_open_loans
    log('clearing tab')
    clear('output')
    pin.textbox_find = ''
    pin.inventory_api = [True]
    _last_textbox = ''
    _last_inventory_api = [True]
    _last_open_loans = [True]


def stop():
    '''Stop an ongoing lookup by setting the _interrupted flag.'''
    global _interrupted
    global _last_textbox
    log('stopping')
    _interrupted = True
    _last_textbox = ''
    stop_processbar()
    interrupt()
    with use_scope('output'):
        tell_warning('**Stopping** ...')


def reset():
    # Reset to state where we can run new operations.
    global _interrupted
    _interrupted = False
    reset_interrupts()


def enable_lookup_button(state):
    '''Enable the "look up records" button if True, disable if False.'''
    action = 'removeClass' if state else 'addClass'
    eval_js(f'''$("button:contains('Look up records')").{action}("disabled-button");''')


def wait_if_running():
    '''Check if the run state is running; if it is, wait until it changes.'''
    # The _running variable is set by do_find() when it's finished, and it's
    # set even if it gets interrupted. This is what we cue from.
    global _running
    if not _running:
        return
    enable_lookup_button(False)
    stop()
    # Wait in case an ongoing lookup is running, but don't wait forever.
    wait_count = 10
    while _running and wait_count > 0:
        # If the user clicks multiple times rapidly, the exception raised for
        # interrupts starts to cascade. Wrap with a try-except to avoid this.
        try:
            wait(1)
            wait_count -= 1
        except Interrupted:
            continue
    enable_lookup_button(True)


def nonexistent_record_stub(id_, id_kind):
    data = {'id': ''}

    if id_kind in [IdKind.ITEM_BARCODE, IdKind.USER_BARCODE]:
        data['barcode'] = id_
    elif id_kind in [IdKind.ITEM_ID, IdKind.HOLDINGS_ID, IdKind.INSTANCE_ID,
                     IdKind.USER_ID, IdKind.LOAN_ID, IdKind.TYPE_ID,
                     IdKind.ACCESSION]:
        data['id'] = id_
    elif id_kind in [IdKind.ITEM_HRID, IdKind.HOLDINGS_HRID, IdKind.INSTANCE_HRID]:
        data['hrid'] = id_

    if id_kind in [IdKind.INSTANCE_ID, IdKind.INSTANCE_HRID]:
        data['title'] = ''
    # Item records from the storage API don't have 'title', so we don't add it
    # unless we're using the inventory API.
    if pin.inventory_api and id_kind in [IdKind.ITEM_BARCODE, IdKind.ITEM_ID,
                                         IdKind.ITEM_HRID]:
        data['title'] = ''

    return Record(id_, id_kind, data)


# Summary of the basic flow of control:
#
# User clicks "look up records", thus invoking do_find().
# We show progress bar & stop button while lookup is running.
# Possible scenarios:
#   1) process finishes normally
#   2) user clicks stop button
#   3) user clicks "look up records" button while lookup is running

def do_find():
    global _last_results
    global _last_textbox
    global _last_kind
    global _last_inventory_api
    global _last_open_loans
    global _location_map
    global _interrupted
    global _running
    log('do_find invoked')
    wait_if_running()
    reset()
    # Normally we'd want to find out if they input any identifiers, but I want
    # to detect *any* change to the input box, so this is a lower-level test.
    if not pin.textbox_find.strip():
        note_error('Please input at least one barcode or other id.')
        return
    identifiers = unique_identifiers(pin.textbox_find)
    if not identifiers:
        note_error('The input does not appear to contain FOLIO identifiers.')
        return
    reuse_results = False
    if inputs_are_unchanged() and user_wants_reuse():
        reuse_results = True
    else:
        _last_results = {}
    _last_textbox = pin.textbox_find
    _last_kind = pin.select_kind
    _last_inventory_api = pin.inventory_api
    _last_open_loans = pin.open_loans
    kind_wanted = pin.select_kind
    steps = len(identifiers) + 1
    folio = Folio()
    total_found = 0
    with use_scope('output', clear = True):
        put_grid([[
            put_scope('current_activity', [
                put_markdown('_Certain lookups take a long time. Please be patient._'
                             ).style('color: DarkOrange; margin-bottom: 0')]),
        ], [
            put_processbar('bar', init = 1/steps).style('margin-top: 11px'),
            put_button('Stop', outline = True, color = 'danger',
                       onclick = lambda: stop()).style('text-align: right'),
        ]], cell_widths = '85% 15%').style(PROGRESS_BOX)
        # The staff want to see location names, so we need to get the mapping.
        _running = True
        for count, id_ in enumerate(identifiers, start = 2):
            if _interrupted:
                break
            try:
                # Figure out what kind of identifier we were given.
                id_kind = folio.id_kind(id_)
                if id_kind is IdKind.UNKNOWN:
                    tell_failure(f'Unrecognized identifier: **{id_}**.')
                    continue
                if reuse_results:
                    records = _last_results.get(id_)
                else:
                    records = folio.related_records(id_, id_kind, kind_wanted,
                                                    pin.inventory_api, pin.open_loans)
                    if not records or len(records) == 0:
                        tell_failure(f'No {kind_wanted} record(s) found for'
                                     f' {id_kind} **{id_}**.')
                        _last_results[id_] = [nonexistent_record_stub(id_, id_kind)]
                        continue
                    else:
                        _last_results[id_] = records

                # Report the results & how we got them.
                source = 'storage'
                if pin.inventory_api and kind_wanted in ['item', 'instance']:
                    source = 'inventory'
                this = pluralized(kind_wanted + f' {source} record', records, True)
                how = f'by searching for {id_kind} **{id_}**.'
                tell_success(f'Found {this} {how}')
                show_index = (len(records) > 1)
                for index, record in enumerate(records, start = 1):
                    print_record(record, id_, index, show_index, pin.show_raw)
                total_found += len(records)
            except Interrupted:
                log('stopping due to interruption')
                _interrupted = True
            except Exception as ex:     # noqa: PIE786
                import traceback
                log('Exception info: ' + str(ex) + '\n' + traceback.format_exc())
                tell_failure('Error: ' + str(ex))
                stop_processbar()
                return
            finally:
                if not _interrupted:
                    set_processbar('bar', count/steps)
        stop_processbar()
        clear_scope('current_activity')
        if _interrupted:
            tell_warning('**Stopped**.')
        else:
            summary = (f'Found {total_found} {kind_wanted} records by looking up '
                       + pluralized('unique identifier', identifiers, True)
                       + '.')
            put_grid([[
                put_markdown(summary).style('margin-top: 6px'),
                put_button('Export', outline = True,
                           onclick = lambda: do_export(_last_results, kind_wanted),
                           ).style('text-align: right')
            ]]).style('margin: 1.5em 17px auto 17px')
        _running = False


def field(record, field_name, subfield_name = None, list_joiner = ', '):
    if field_name not in record.data:
        return ''
    if subfield_name:
        if subfield_name not in record.data[field_name]:
            return ''
        value = record.data[field_name][subfield_name]
    else:
        value = record.data[field_name]
    if isinstance(value, list) and list_joiner:
        return list_joiner.join(str(x) for x in value)
    else:
        return str(value)


def location(record, field_name, include_id=True):
    if field_name not in record.data:
        return ''
    location_data = record.data[field_name]
    if isinstance(location_data, dict):
        if 'name' in location_data:
            id_info = f' ({location_data["id"]})' if include_id else ''
            return f'{location_data["name"]}{id_info}'
        else:
            return location_data["id"]
    elif location_data:
        global _location_map
        init_location_map()
        if location_data in _location_map:
            id_info = f' ({location_data})' if include_id else ''
            return f'{_location_map[location_data]}{id_info}'
    return '(unknown location)'


def notes(record, field_name):
    if field_name not in record.data:
        return ''
    notes = record.data[field_name]
    if isinstance(notes, str):
        return notes
    elif isinstance(notes, list):
        if len(notes) == 0:
            return ''
        elif isinstance(notes[0], dict):
            return '\n'.join(filter(None, [n.get('note', '') for n in notes]))
        else:
            return '\n'.join(str(note) for note in notes)
    else:
        return notes


def loan_type(record, field_name):
    if field_name not in record.data:
        return ''
    loan_type = record.data[field_name]
    if isinstance(loan_type, dict):
        if 'name' in loan_type:
            return f'{loan_type["name"]}  ({loan_type["id"]})'
        else:
            return loan_type["id"]
    elif loan_type:
        global _loan_map
        init_loan_map()
        if loan_type in _loan_map:
            return f'{_loan_map[loan_type]}  ({loan_type})'
    return '(unknown loan type)'


def print_record(record, identifier, index, show_index, format):
    log(f'printing {record.kind} record {record.id}')
    if show_index:
        put_markdown(f'{record.kind.title()} record #{index}:')
    if format == 'json':
        put_code(pformat(record.data, indent = 2))
        return
    # Caution: left-hand values contain nonbreaking spaces (invisible here).
    if record.kind is RecordKind.ITEM:
        if 'title' in record.data:
            # Inventory record version.
            table = [
                ['Title'                     , field(record, 'title')],
                ['Barcode'                   , field(record, 'barcode')],
                ['Call number'               , field(record, 'callNumber')],
                [f'{record.kind.title()} id' , field(record, 'id')],
                ['Effective location'        , location(record, 'effectiveLocation')],
                ['Permanent location'        , location(record, 'permanentLocation')],
                ['Loan type'                 , loan_type(record, 'permanentLoanType')],
                ['Status'                    , field(record, 'status', 'name')],
                ['Tags'                      , field(record, 'tags', 'tagsList')],
                ['Notes'                     , notes(record, 'notes')],
                ['HRID'                      , field(record, 'hrid')],
                ['Created'                   , field(record, 'metadata', 'createdDate')],
                ['Updated'                   , field(record, 'metadata', 'updatedDate')],
            ]
        else:
            # Storage record version.
            table = [
                ['Barcode'                   , field(record, 'barcode')],
                ['Call number'               , field(record, 'itemLevelCallNumber')],
                [f'{record.kind.title()} id' , field(record, 'id')],
                ['Effective location'        , location(record, 'effectiveLocationId')],
                ['Permanent location'        , location(record, 'permanentLocationId')],
                ['Loan type'                 , loan_type(record, 'permanentLoanTypeId')],
                ['Tags'                      , field(record, 'tags', 'tagsList')],
                ['Notes'                     , notes(record, 'notes')],
                ['HRID'                      , field(record, 'hrid')],
                ['Created'                   , field(record, 'metadata', 'createdDate')],
                ['Updated'                   , field(record, 'metadata', 'updatedDate')],
            ]
    elif record.kind is RecordKind.INSTANCE:
        call_number = ''
        if field(record, 'classifications'):
            call_number = record.data['classifications'][0]['classificationNumber']
        if 'tags' in record.data:
            table = [
                ['Title'                     , field(record, 'title')],
                ['Call number'               , call_number],
                [f'{record.kind.title()} id' , field(record, 'id')],
                ['Tags'                      , field(record, 'tags', 'tagsList')],
                ['Notes'                     , notes(record, 'notes')],
                ['HRID'                      , field(record, 'hrid')],
                ['Created'                   , field(record, 'metadata', 'createdDate')],
                ['Updated'                   , field(record, 'metadata', 'updatedDate')],
            ]
        else:
            table = [
                ['Title'                     , field(record, 'title')],
                ['Call number'               , call_number],
                [f'{record.kind.title()} id' , field(record, 'id')],
                ['HRID'                      , field(record, 'hrid')],
                ['Notes'                     , notes(record, 'notes')],
                ['Created'                   , field(record, 'metadata', 'createdDate')],
                ['Updated'                   , field(record, 'metadata', 'updatedDate')],
            ]
    elif record.kind is RecordKind.HOLDINGS:
        if 'effectiveLocationId' in record.data:
            table = [
                [f'{record.kind.title()} id' , field(record, 'id')],
                ['HRID'                      , field(record, 'hrid')],
                ['Holdings type id'          , field(record, 'holdingsTypeId')],
                ['Instance id'               , field(record, 'instanceId')],
                ['Effective location'        , location(record, 'effectiveLocationId')],
                ['Permanent location'        , location(record, 'permanentLocationId')],
                ['Created'                   , field(record, 'metadata', 'createdDate')],
                ['Updated'                   , field(record, 'metadata', 'updatedDate')],
            ]
        else:
            table = [
                [f'{record.kind.title()} id' , field(record, 'id')],
                ['HRID'                      , field(record, 'hrid')],
                ['Holdings type id'          , field(record, 'holdingsTypeId')],
                ['Instance id'               , field(record, 'instanceId')],
                ['Effective location'        , ''],
                ['Permanent location'        , location(record, 'permanentLocationId')],
                ['Created'                   , field(record, 'metadata', 'createdDate')],
                ['Updated'                   , field(record, 'metadata', 'updatedDate')],
            ]
    elif record.kind is RecordKind.USER:
        table = [
            ['Username'                  , field(record, 'username')],
            ['Barcode'                   , field(record, 'barcode')],
            [f'{record.kind.title()} id' , field(record, 'id')],
            ['Patron group'              , field(record, 'patronGroup')],
            ['Created'                   , field(record, 'metadata', 'createdDate')],
            ['Updated'                   , field(record, 'metadata', 'updatedDate')],
        ]
    elif record.kind is RecordKind.LOAN:
        if 'userId' in record.data:
            table = [
                [f'{record.kind.title()} id' , field(record, 'id')],
                ['Status'                    , field(record, 'status', 'name')],
                ['User id'                   , field(record, 'userId')],
                ['Item id'                   , field(record, 'itemId')],
                ['Loan date'                 , field(record, 'loanDate')],
                ['Due date'                  , field(record, 'dueDate')],
                ['Created'                   , field(record, 'metadata', 'createdDate')],
                ['Updated'                   , field(record, 'metadata', 'updatedDate')],
            ]
        else:
            table = [
                [f'{record.kind.title()} id' , field(record, 'id')],
                ['Status'                    , field(record, 'status', 'name')],
                ['User id'                   , ''],
                ['Item id'                   , field(record, 'itemId')],
                ['Loan date'                 , field(record, 'loanDate')],
                ['Due date'                  , field(record, 'dueDate')],
                ['Created'                   , field(record, 'metadata', 'createdDate')],
                ['Updated'                   , field(record, 'metadata', 'updatedDate')],
            ]

    # Define some helpers for the enhanced format.
    def item_info(hid):
        folio = Folio()
        items = folio.related_records(hid, IdKind.HOLDINGS_ID, RecordKind.ITEM)
        num_items = len(items)
        text = str(num_items)
        if num_items > 1:
            if record.kind == RecordKind.ITEM:
                text += ' (including this item)'
        else:
            if record.kind == RecordKind.ITEM:
                text += ' (this is the only item on the holdings record)'
        return text

    def holdings_info(iid):
        folio = Folio()
        holdings = folio.related_records(iid, IdKind.INSTANCE_ID, RecordKind.HOLDINGS)
        num_holdings = len(holdings)
        if num_holdings > 1:
            prefix = '<br>&nbsp;&nbsp;&bull;&nbsp;'
            holdings_list = []
            for h in holdings:
                if 'effectiveLocationId' in h.data:
                    loc = location(h, 'effectiveLocationId', False)
                else:
                    loc = location(h, 'permanentLocationId', False)
                holdings_list.append(loc + f' (holdings record: {h.id})')
            locations = prefix + prefix.join(holdings_list)
            return put_html(f'{num_holdings} holdings records in total:{locations}')
        else:
            if record.kind == RecordKind.HOLDINGS:
                return '1 (there are no other holdings records on the instance)'
            else:
                return '1 (including this holdings record)'

    # Add additional info when doing an enhanced summary.
    if format == 'enhanced' and record.kind == RecordKind.ITEM:
        folio = Folio()
        hid = record.data['holdingsRecordId']
        instances = folio.related_records(hid, IdKind.HOLDINGS_ID, RecordKind.INSTANCE)
        instance = instances[0]
        iid = instance.id
        total_items = item_info(hid)
        total_holdings = holdings_info(iid)

        table.append(['Parent holdings record'             , hid])
        table.append(['Total items on the holdings record' , total_items])
        table.append(['Parent instance record'             , iid])
        table.append(['Total holdings records on the instance', total_holdings])

        additions = {'parentHoldingsRecord'                 : hid,
                     'totalItemsOnHoldingsRecord'           : total_items,
                     'parentInstanceRecord'                 : iid,
                     'totalHoldingsRecordsOnParentInstance' : total_holdings}
        record.data['computedByFoliage'] = additions
    elif format == 'enhanced' and record.kind == RecordKind.HOLDINGS:
        folio = Folio()
        hid = record.id
        iid = record.data['instanceId']
        total_items = item_info(hid)
        total_holdings = holdings_info(iid)

        # The summary table for holdings already has the holdings & instance id's.
        table.append(['Total items on this holdings record'   , total_items])
        table.append(['Total holdings records on the instance', total_holdings])

        additions = {'totalItemsOnThisHoldingsRecord': total_items,
                     'totalHoldingsRecordsOnParentInstance': total_holdings}
        record.data['computedByFoliage'] = additions
    put_table(table).style('font-size: 90%; margin: auto 17px 1.5em 17px')


def user_wants_reuse():
    event = threading.Event()
    answer = False

    def clk(val):
        nonlocal answer
        answer = val
        event.set()

    pins = [
        put_text('The list of identifiers and the kind of record to retrieve'
                 ' are unchanged from the previous lookup. Should the results'
                 ' be reused, or should the identifiers be looked up again?'),
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
