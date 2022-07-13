'''
list_tab.py: implementation of the "List UUIDs" tab

Copyright
---------

Copyright (c) 2021-2022 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.data_utils import unique, pluralized, flattened
from   commonpy.exceptions import Interrupted
from   commonpy.file_utils import exists, readable
from   commonpy.interrupt import wait, interrupt, reset_interrupts
from   decouple import config
from   pprint import pformat
import pyperclip
from   pywebio.input import input, select, checkbox, radio
from   pywebio.input import NUMBER, TEXT, input_update, input_group
from   pywebio.output import put_text, put_markdown, put_row, put_html
from   pywebio.output import toast, popup, close_popup, put_buttons, put_button, put_error
from   pywebio.output import use_scope, set_scope, clear, remove, put_warning
from   pywebio.output import put_success, put_info, put_table, put_grid, span
from   pywebio.output import put_tabs, put_image, put_scrollable, put_code, put_link
from   pywebio.output import put_processbar, set_processbar, put_loading
from   pywebio.output import put_column, put_scope, clear_scope, get_scope
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
from   pywebio.pin import put_textarea, put_radio, put_checkbox, put_select
from   pywebio.session import eval_js
from   sidetrack import set_debug, log
import threading

from   foliage.base_tab import FoliageTab
from   foliage.export import export_data
from   foliage.folio import Folio, RecordKind, IdKind, TypeKind, Record
from   foliage.folio import unique_identifiers, back_up_record
from   foliage.ui import confirm, notify, stop_processbar
from   foliage.ui import note_info, note_warn, note_error
from   foliage.ui import tell_success, tell_failure, tell_warning, PROGRESS_BOX


# Tab definition class.
# .............................................................................

class CleanTab(FoliageTab):
    def contents(self):
        return {'title': 'Clean Records', 'content': tab_contents()}

    def pin_watchers(self):
        return {}


# Tab layout.
# .............................................................................

def tab_contents():
    log(f'generating list tab contents')
    return [
        put_markdown('### Phantom loans'),
        put_grid([[
            put_markdown("Input one or more **user barcodes** or **user id**'s"
                         ' below, or upload a file containing them. Click'
                         ' the button below to delete loans associated with'
                         ' those users for items that are no longer in FOLIO.'),
            put_button('Upload', outline = True,
                       onclick = lambda: load_file()).style(
                           'text-align: right'),
        ]], cell_widths = 'auto 100px'),
        put_textarea('textbox_users', rows = 4),
        put_row([
            put_button('Delete phantom loans',
                       onclick = lambda: do_delete()
                       ).style('text-align: left'),
            put_button('Clear', outline = True,
                       onclick = lambda: clear_tab()).style('text-align: right'),
        ])
    ]


# Implementation of tab functionality.
# .............................................................................

_interrupted = False
_running = False
_last_textbox = ''


def clear_tab():
    global _last_textbox
    log(f'clearing tab')
    clear('output')
    pin.textbox_users = ''
    _last_textbox = ''


def load_file():
    log(f'user requesting file upload')
    if (contents := user_file('Upload a file containing identifiers')):
        pin.textbox_users = contents


def stop():
    '''Stop an ongoing deletion by setting the _interrupted flag.'''
    global _interrupted
    global _last_textbox
    log(f'stopping')
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


def enable_delete_button(state):
    '''Enable the "delete phantom loans" button if True, disable if False.'''
    action = 'removeClass' if state else 'addClass'
    eval_js(f'''$("button:contains('Delete phantom loans')").{action}("disabled-button");''')


def wait_if_running():
    '''Check if the run state is running; if it is, wait until it changes.'''
    # The _running variable is set by do_find() when it's finished, and it's
    # set even if it gets interrupted. This is what we cue from.
    global _running
    if not _running:
        return
    enable_delete_button(False)
    stop()
    # Wait in case an ongoing delete is running, but don't wait forever.
    wait_count = 10
    while _running and wait_count > 0:
        # If the user clicks multiple times rapidly, the exception raised for
        # interrupts starts to cascade. Wrap with a try-except to avoid this.
        try:
            wait(1)
            wait_count -= 1
        except Interrupted:
            continue
    enable_delete_button(True)


_results = []

def clear_results():
    global _results
    _results = []


def record_result(record_or_id, success, notes):
    global _results
    id = record_or_id if isinstance(record_or_id, str) else record_or_id.id
    rec = record_or_id if isinstance(record_or_id, Record) else None
    _results.append({'id': id, 'success': success, 'notes': notes, 'record': rec})


def succeeded(record_or_id, msg, why = ''):
    comment = (' (' + why + ')') if why else ''
    record_result(record_or_id, True, msg + comment)
    tell_success('Success: ' + msg + comment + '.')


def failed(record_or_id, msg, why = ''):
    comment = (' (' + why + ')') if why else ''
    record_result(record_or_id, False, msg + comment)
    id = record_or_id if isinstance(record_or_id, str) else record_or_id.id
    tell_failure(f'Failed to delete **{id}**{comment}: ' + msg + '.')


def skipped(record_or_id, msg, why = ''):
    comment = (' (' + why + ')') if why else ''
    record_result(record_or_id, False, msg + comment)
    id = record_or_id if isinstance(record_or_id, str) else record_or_id.id
    tell_warning(f'Skipped **{id}**{comment}: ' + msg + '.')


def do_delete():
    global _last_textbox
    global _interrupted
    global _running
    log('do_delete invoked')
    wait_if_running()
    clear_results()
    reset()
    # Normally we'd want to find out if they input any identifiers, but I want
    # to detect *any* change to the input box, so this is a lower-level test.
    if not pin.textbox_users.strip():
        note_error('Please input at least one barcode or other id.')
        return
    identifiers = unique_identifiers(pin.textbox_users)
    if not identifiers:
        note_error('The input does not appear to contain identifiers or barcodes.')
        return
    _last_textbox = pin.textbox_users
    steps = len(identifiers) + 1
    folio = Folio()
    with use_scope('output', clear = True):
        put_grid([[
            put_scope('current_activity', [
                put_markdown(f'_This operation can take a long time. Please be patient._'
                             ).style('color: DarkOrange; margin-bottom: 0')]),
        ], [
            put_processbar('bar', init = 1/steps).style('margin-top: 11px'),
            put_button('Stop', outline = True, color = 'danger',
                       onclick = lambda: stop()).style('text-align: right'),
        ]], cell_widths = '85% 15%').style(PROGRESS_BOX)
        _running = True
        for count, user in enumerate(identifiers, start = 2):
            if _interrupted:
                break
            try:
                # Check that the kind of id we were given is really for users.
                id_kind = folio.id_kind(user)
                if id_kind is IdKind.UNKNOWN:
                    tell_failure(f'Unrecognized identifier: **{user}**.')
                    continue
                if id_kind not in [IdKind.USER_BARCODE, IdKind.USER_ID]:
                    tell_failure(f'Not a user identifier or barcode: **{user}**.')
                    continue
                deletions = []
                deletions_ids = set()
                for loan in folio.related_records(user, id_kind, RecordKind.LOAN,
                                                  open_loans_only = False):
                    if _interrupted:
                        raise Interrupted
                    item_id = loan.data['itemId']
                    item = folio.related_records(item_id, IdKind.ITEM_ID, RecordKind.ITEM)
                    if not item and item_id not in deletions_ids:
                        log(f'item {item_id} no longer exists; need delete loan {loan.id}')
                        deletions.append(loan)
                        deletions_ids.add(item_id)
                if not deletions:
                    put_warning('Did not find any loans on deleted items for'
                                f' user {user} – nothing to do.')
                    continue
                for loan in deletions:
                    if _interrupted:
                        raise Interrupted
                    delete(loan, loan.data['itemId'], user)
            except Interrupted as ex:
                log('stopping due to interruption')
                _interrupted = True
            except Exception as ex:
                import traceback
                log('Exception info: ' + str(ex) + '\n' + traceback.format_exc())
                tell_failure(f'Error: ' + str(ex))
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
            put_grid([[
                put_markdown('Done.'),
                put_button('Export', outline = True,
                           onclick = lambda: do_export(_last_results, kind_wanted),
                           ).style('text-align: right')
            ]]).style('margin: 1.5em 17px auto 17px')
        _running = False


def delete(record, item_id, user_id):
    '''Low-level function to delete the given record.'''
    why = f'for loan on nonexistent item {item_id} by user {user_id}'
    if config('DEMO_MODE', cast = bool):
        log(f'demo mode in effect – pretending to delete {record.id}')
    else:
        try:
            back_up_record(record)
            folio = Folio()
            folio.delete_record(record)
        except FolioOpFailed as ex:
            failed(record, str(ex), why)
            return False
    succeeded(record, f'deleted {record.kind} record **{record.id}**', why)
    return True


def do_export(file_name):
    global _results
    # Output fields requested
    #   id
    #   success
    #   notes
    values = []
    folio = Folio()
    for result in _results:
        entry = {'Loan ID'            : result['id'],
                 'Operation success'  : result['success'],
                 'Notes'              : result['notes']}
        values.append(entry)
    export_data(values, file_name)
