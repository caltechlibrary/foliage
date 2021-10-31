
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
from   pywebio.output import toast, popup, close_popup, put_buttons, put_button, put_error
from   pywebio.output import use_scope, set_scope, clear, remove, put_warning
from   pywebio.output import put_success, put_info, put_table, put_grid, span
from   pywebio.output import put_tabs, put_image, put_scrollable, put_code, put_link
from   pywebio.output import put_processbar, set_processbar, put_loading, span
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
from   pywebio.pin import put_textarea, put_radio, put_checkbox, put_select
from   pywebio.session import run_js, eval_js
import re
import threading
import webbrowser

if __debug__:
    from sidetrack import set_debug, log

from .folio import Folio, RecordKind, RecordIdKind, TypeKind
from .ui import quit_app, reload_page, alert, warn, confirm, image_data


# Overall main page structure
# .............................................................................

def foliage_main_page(log_file, backup_dir, demo_mode):
    log(f'creating index page')
    if demo_mode:
        put_warning('Demo mode in effect').style(
            'position: absolute; left: calc(50% - 5.5em); width: 11em;'
            + 'height: 25px; padding: 0 10px; top: 0; z-index: 2')
    put_image(image_data('foliage-icon-r.png'), width='90px').style('float: left')
    put_image(image_data('foliage-icon.png'), width='90px').style('float: right')
    put_html('<h1 class="text-center">Foliage</h1>')
    put_html('<div class="font-italic text-muted font-weight-light text-center mx-auto">'
             ' Foliage ("FOLIo chAnGe Editor") is an app that runs'
             ' on your computer and lets you perform FOLIO operations over'
             ' the network. This web page is its user interface.'
             '</div>').style('width: 85%')
    put_tabs([
        {'title': 'Show IDs', 'content': list_types_tab()},
        {'title': 'Look up records', 'content': find_records_tab()},
        {'title': 'Delete records', 'content': delete_records_tab()},
#        {'title': 'Change records', 'content': change_records_tab()},
        {'title': 'Other', 'content': other_tab()},
        ])

    put_actions('quit',
                buttons = [dict(label = 'Quit Foliage', value = 'quit',
                                color = 'warning')]
                ).style('position: absolute; bottom: -10px;'
                        + 'left: calc(50% - 3.5em); z-index: 2')

    # Start the infinite loop for processing user input.
    run_main_loop(log_file, backup_dir, demo_mode)


def run_main_loop(log_file, backup_dir, demo_mode):
    log(f'running main loop')
    folio = Folio()
    while True:
        event = pin_wait_change('do_list_types', 'do_find', 'do_delete',
                                'clear_list', 'clear_find', 'clear_delete',
                                'quit', 'show_log', 'show_backups')
        event_type = event['name']

        if event_type.startswith('clear'):  # catches all clear_* buttons.
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


        elif event_type == 'do_list_types':
            log(f'listing id types')
            with use_scope('output', clear = True):
                put_processbar('bar', init = 1/2)
                requested = pin.list_type
                try:
                    types = folio.types(requested)
                except Exception as ex:
                    put_html('<br>')
                    put_error('Error: ' + str(ex))
                    continue
                finally:
                    set_processbar('bar', 2/2)
                put_html('<br>')
                cleaned_name = requested.split('/')[-1].replace("-", " ")
                put_markdown(f'Found {len(types)} values for {cleaned_name}:')
                contents = []
                for item in types:
                    name, id = item[0], item[1]
                    title = f'Data for {cleaned_name} value "{name.title()}"'
                    action = lambda: show_record(title, folio.records(id, RecordIdKind.TYPE_ID, requested))
                    contents.append([name, link(id, action)])
                put_table(sorted(contents, key = lambda x: x[0]), header = ['Type', 'Id'])

        elif event_type == 'do_find':
            log(f'do_find invoked')
            if not pin.textbox_find:
                alert('Please input at least one barcode or other id.')
                continue
            with use_scope('output', clear = True):
                identifiers = unique_identifiers(pin.textbox_find)
                steps = len(identifiers) + 1
                put_processbar('bar', init = 1/steps);
                for index, id in enumerate(identifiers, start = 2):
                    put_html('<br>')
                    id_type = folio.record_id_type(id)
                    if id_type == RecordIdKind.UNKNOWN:
                        put_error(f'Could not recognize the identifier type of {id}.')
                        set_processbar('bar', index/steps)
                        continue

                    record_kind = pin.select_kind_find
                    try:
                        records = folio.records(id, id_type, record_kind)
                    except Exception as ex:
                        put_error(f'Error: {antiformat(str(ex))}')
                        break
                    finally:
                        set_processbar('bar', index/steps)
                    if not records or len(records) == 0:
                        put_error(f'No record(s) for {id_type.value} "{id}".')
                        continue
                    this = pluralized(record_kind + " record", records, True)
                    how = f'by searching for {id_type.value} **{id}**'
                    put_success(put_markdown(f'Found {this} {how}')).style('text-align: center')
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
                put_processbar('bar', init = 1/steps);
                for index, id in enumerate(identifiers, start = 2):
                    put_html('<br>')
                    id_type = folio.record_id_type(id)
                    if id_type == RecordIdKind.UNKNOWN:
                        put_error(f'Could not recognize the identifier type of {id}.')
                        set_processbar('bar', index/steps)
                        continue
                    try:
                        records = folio.records(id, id_type)
                        record = records[0] if records else None
                    except Exception as ex:
                        alert(f'Error: {antiformat(str(ex))}')
                        break
                    finally:
                        set_processbar('bar', index/steps)
                    if not record:
                        put_error(f'Could not find a record for {id_type.value} {id}.')
                        continue
                    backup_record(record, backup_dir)
                    if id_type in [RecordIdKind.ITEM_ID, RecordIdKind.ITEM_BARCODE]:
                        if demo_mode:
                            put_success(put_markdown(f'Deleted item record **{id}**'))
                        else:
                            delete_item(folio, record, id)
                    else:
                        put_warning('Instance record deletion is currently turned off.')
                        # delete_instance(folio, record, id)


def list_types_tab():
    return [
        put_grid([[
            put_markdown('Select a FOLIO type to list:').style('margin-top: 6px'),
            put_select('list_type', options = [
                {'label': 'Acquisition units', 'value': TypeKind.ACQUISITION_UNIT},
                {'label': 'Address types', 'value': TypeKind.ADDRESS},
                {'label': 'Alternative title types', 'value': TypeKind.ALT_TITLE},
                {'label': 'Call number types', 'value': TypeKind.CALL_NUMBER},
                {'label': 'Classification types', 'value': TypeKind.CLASSIFICATION},
                {'label': 'Contributor types', 'value': TypeKind.CONTRIBUTOR},
                {'label': 'Contributor name types', 'value': TypeKind.CONTRIBUTOR_NAME},
                {'label': 'Department types', 'value': TypeKind.DEPARTMENT},
                {'label': 'Expense classes', 'value': TypeKind.EXPENSE_CLASS},
                {'label': 'Fixed due date schedules', 'value': TypeKind.FIXED_DUE_DATE_SCHED},
                {'label': 'Group types', 'value': TypeKind.GROUP},
                {'label': 'Holdings types', 'value': TypeKind.HOLDINGS},
                {'label': 'Holdings note types', 'value': TypeKind.HOLDINGS_NOTE},
                {'label': 'Holdings source types', 'value': TypeKind.HOLDINGS_SOURCE},
                {'label': 'Identifier types', 'value': TypeKind.ID},
                {'label': 'ILL policy types', 'value': TypeKind.ILL_POLICY},
                {'label': 'Instance types', 'value': TypeKind.INSTANCE},
                {'label': 'Instance format types', 'value': TypeKind.INSTANCE_FORMAT},
                {'label': 'Instance note types', 'value': TypeKind.INSTANCE_NOTE},
                {'label': 'Instance relationship types', 'value': TypeKind.INSTANCE_REL},
                {'label': 'Instance status types', 'value': TypeKind.INSTANCE_STATUS},
                {'label': 'Item note types', 'value': TypeKind.ITEM_NOTE},
                {'label': 'Item damaged status types', 'value': TypeKind.ITEM_DAMAGED_STATUS},
                {'label': 'Loan types', 'value': TypeKind.LOAN},
                {'label': 'Loan policy types', 'value': TypeKind.LOAN_POLICY},
                {'label': 'Location types', 'value': TypeKind.LOCATION},
                {'label': 'Material types', 'value': TypeKind.MATERIAL},
                {'label': 'Nature of content term types', 'value': TypeKind.NATURE_OF_CONTENT},
#                {'label': 'Order lines', 'value': TypeKind.ORDER_LINE},
                {'label': 'Organizations', 'value': TypeKind.ORGANIZATION},
                {'label': 'Service point types', 'value': TypeKind.SERVICE_POINT},
                {'label': 'Shelf location types', 'value': TypeKind.SHELF_LOCATION},
                {'label': 'Statistical code types', 'value': TypeKind.STATISTICAL_CODE},
            ]).style('margin-left: 10px'),
            put_actions('do_list_types',
                        buttons = ['Get list']).style('margin-left: 10px; text-align: left'),
            put_actions('clear_list',
                        buttons = [dict(label = 'Clear', value = 'clear',
                                        color = 'secondary')]).style('margin-left: 10px; text-align: right')
        ]])
    ]


def find_records_tab():
    return [
        put_markdown('Input one or more item barcode, item id, instance id,'
                     + ' hrid, accession number, user id or user barcode in the'
                     + ' field below, then press the button to look up records.'
                     + ' (Searching for items by instance records may return'
                     + ' multiple results.)'),
        put_textarea('textbox_find', rows = 4),
        put_radio('select_kind_find', inline = True,
                  label = 'Type of record to retrieve:',
                  options = [ ('Item', RecordKind.ITEM.value, True),
                              ('Instance', RecordKind.INSTANCE.value),
                              ('User', RecordKind.USER.value),
                              ('Loan', RecordKind.LOAN.value)]),
        put_text(''), # Adds a column, pushing next item to the right.
        put_checkbox('show_raw', options = ['Show raw data from FOLIO']),
        put_row([
            put_actions('do_find', buttons = ['Look up records']),
            put_text(''),    # Adds a column, pushing next item to the right.
            put_actions('clear_find',
                        buttons = [dict(label = 'Clear', value = 'clear',
                                        color = 'secondary')]).style('text-align: right')
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
            put_actions('clear_delete',
                        buttons = [dict(label = 'Clear', value = 'clear',
                                        color = 'secondary')]).style('text-align: right')
        ])
    ]


def other_tab():
    return [
        put_grid([[
            put_markdown('When performing destructive operations, Foliage'
                         + ' saves a copy of records before modifying them.'
                         + ' Click this button to open the folder containing'
                         + ' the files. A given record may have multiple backup'
                         + ' files with different time stamps.'),
            put_actions('show_backups',
                        buttons = [dict(label = 'Show backups',
                                        value = 'show_backups',
                                        color = 'info')]
                        ).style('margin-left: 10px; text-align: left'),
        ], [
            put_markdown('The debug log file contains a detailed trace of'
                         + ' every action that Foliage takes. This can be'
                         + ' useful when trying to resolve bugs and other'
                         + ' problems.'),
            put_actions('show_log',
                        buttons = [dict(label = 'Show log file', value = 'show_log',
                                        color = 'info')]
                        ).style('margin-left: 10px; text-align: left'),
        ]], cell_widths = 'auto 150px'),
    ]


def print_record(record, record_kind, identifier, id_type, index, show_index, show_raw):
    if show_index:
        put_markdown(f'{record_kind.title()} record #{index}:')

    if show_raw:
        put_code(pformat(record, indent = 2))
    elif record_kind == 'item':
        # Caution: left-hand values contain nonbreaking spaces (invisible here).
        put_table([
            ['Title'                     , record['title']],
            ['Call number'               , record['callNumber']],
            [f'FOLIO {record_kind.title()} id' , record['id']],
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
            [f'FOLIO {record_kind.title()} id' , record['id']],
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
            [f'FOLIO {record_kind.title()} id' , record['id']],
            ['Patron group'              , record['patronGroup']],
            ['Created'                   , record['metadata']['createdDate']],
            ['Updated'                   , record['metadata']['updatedDate']],
        ]).style('margin-left: 2em; font-size: 90%')
    elif record_kind == 'loan':
        put_table([
            [f'FOLIO {record_kind.title()} id' , record['id']],
            ['User id'                   , record['userId']],
            ['Item id'                   , record['itemId']],
            ['Loan date'                 , record['loanDate']],
            ['Due date'                  , record['dueDate']],
            ['Created'                   , record['metadata']['createdDate']],
            ['Updated'                   , record['metadata']['updatedDate']],
        ]).style('margin-left: 2em; font-size: 90%')


def unique_identifiers(text):
    lines = text.splitlines()
    identifiers = flatten(re.split(r'\s+|,+', line) for line in lines)
    identifiers = [id.replace('"', '') for id in identifiers]
    return unique(filter(None, identifiers))


def link(name, action):
    return put_button(name, onclick = action, link_style = True)


def show_record(title, data):
    event = threading.Event()

    def clk(val):
        event.set()

    data = data[0] if isinstance(data, list) and len(data) > 0 else data
    pins = [
        put_scrollable(put_code(pformat(data, indent = 2)), height = 400),
        put_buttons([{'label': 'Close', 'value': 1}], onclick = clk).style('float: right'),
    ]
    popup(title = title, content = pins, closable = False, size = 'large')

    event.wait()
    close_popup()


def test():
    put_markdown('foo')
    put_buttons([
        {'label': 'Close', 'value': True},
    ], onclick = onclick).style('float: right')


def backup_record(record, backup_dir):
    timestamp = dt.now(tz = tz.tzlocal()).strftime('%Y%m%d-%H%M%S%f')[:-3]
    id = record['id']
    file = join(backup_dir, id + '.' + timestamp + '.json')
    with open(file, 'w') as f:
        log(f'backing up record {id} to {file}')
        json.dump(record, f, indent = 2)


def delete_item(folio, record, for_id = None):
    import pdb; pdb.set_trace()
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
    items = folio.records(inst_id, RecordIdKind.INSTANCE_ID, RecordKind.ITEM.value)
    put_warning(f'Deleting {pluralized("item record", items, True)} due to'
                + f' the deletion of instance record {inst_id}.')
    for item in items:
        delete_item(folio, item, for_id)

    # Now delete the holdings records.
    holdings = folio.records(inst_id, RecordIdKind.INSTANCE_ID, RecordKind.HOLDINGS.value)
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
