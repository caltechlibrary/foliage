'''
delete_tab.py: implementation of the "Delete records" tab

Copyright
---------

Copyright (c) 2021-2022 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.data_utils import unique, pluralized, flattened
from   commonpy.exceptions import Interrupted
from   commonpy.file_utils import exists, readable
from   commonpy.interrupt import wait, reset_interrupts, interrupt, interrupted
from   decouple import config
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
from   sidetrack import set_debug, log

from   foliage.base_tab import FoliageTab
from   foliage.exceptions import *
from   foliage.export import export_data
from   foliage.folio import Folio, RecordKind, IdKind, TypeKind
from   foliage.folio import unique_identifiers, back_up_record
from   foliage.ui import confirm, notify, user_file, stop_processbar
from   foliage.ui import tell_success, tell_warning, tell_failure
from   foliage.ui import note_info, note_warn, note_error, STATUS_BOX_STYLE


# Tab definition class.
# .............................................................................

class DeleteTab(FoliageTab):
    def contents(self):
        return {'title': 'Delete records', 'content': tab_contents()}

    def pin_watchers(self):
        return {}


# Tab creation function.
# .............................................................................

def tab_contents():
    log(f'generating delete tab contents')
    return [
        put_grid([[
            put_markdown('Input one or more item or holdings identifiers'
                         + ' (which can be id\'s, barcodes, or hrid\'s),'
                         + ' then press the button to delete the records.'),
            put_button('Upload', outline = True,
                       onclick = lambda: load_file()).style('text-align: right'),
        ]], cell_widths = 'auto 100px'),
        put_textarea('textbox_delete', rows = 4),
        put_row([
            put_button('Delete records', color = 'danger',
                       onclick = lambda: do_delete()),
            put_button('Clear', outline = True,
                       onclick = lambda: clear_tab()).style('text-align: right')
        ])
    ]


# Implementation of tab functionality.
# .............................................................................

def clear_tab():
    log(f'clearing tab')
    clear('output')
    pin.textbox_delete = ''


def load_file():
    log(f'user requesting file upload')
    if (file := user_file('Upload a file containing identifiers')):
        pin.textbox_delete = file


def stop():
    log(f'stopping')
    interrupt()
    stop_processbar()


results = []

def succeeded(id, msg, why = ''):
    global results
    comment = (' (' + why + ')') if why else ''
    results.append({'id': id, 'success': True, 'notes': msg + comment})
    tell_success(f'Succeeded: ' + msg + comment + '.')


def failed(id, msg, why = ''):
    global results
    comment = (' (' + why + ')') if why else ''
    results.append({'id': id, 'success': False, 'notes': msg + comment})
    tell_failure(f'Failed to delete **{id}**{comment}: ' + msg + '.')


def skipped(id, msg, why = ''):
    global results
    comment = (' (' + why + ')') if why else ''
    results.append({'id': id, 'success': False, 'notes': msg + comment})
    tell_warning(f'Skipped **{id}**{comment}: ' + msg + '.')


def do_delete():
    log(f'do_delete invoked')
    global results
    results = []
    identifiers = unique_identifiers(pin.textbox_delete)
    if not identifiers:
        note_error('Please input at least one barcode or other type of id.')
        return
    if not confirm('Proceed with deleting records from FOLIO?', danger = True):
        log(f'user declined to proceed')
        return
    reset_interrupts()
    steps = len(identifiers) + 1
    folio = Folio()
    with use_scope('output', clear = True):
        put_grid([[
            put_markdown(f'_Performing deletions_ ...').style('margin-bottom: 0')
        ], [
            put_processbar('bar', init = 1/steps).style('margin-top: 11px'),
            put_button('Stop', outline = True, color = 'danger',
                       onclick = lambda: stop()).style('text-align: right')
        ]], cell_widths = '85% 15%').style(STATUS_BOX_STYLE)
        try:
            for count, id in enumerate(identifiers, start = 2):
                record = folio.record(id)
                if not record:
                    failed(id, f'unrecognized identifier **{id}**')
                    continue
                if record.kind not in _HANDLERS.keys():
                    skipped(id, f'deleting {record.kind} records is not supported')
                    continue
                _HANDLERS[record.kind](record)
                set_processbar('bar', count/steps)
        except Interrupted as ex:
            tell_warning('**Stopped**.')
            return
        except Exception as ex:
            import traceback
            log('Exception info: ' + str(ex) + '\n' + traceback.format_exc())
            tell_failure(f'Error: ' + str(ex))
            return
        finally:
            stop_processbar()

        what = pluralized('record', identifiers, True)
        put_grid([[
            put_markdown(f'Finished deleting {what}.').style('margin-top: 6px'),
            put_button('Export summary', outline = True,
                       onclick = lambda: export_data(results, 'foliage-deletions.csv'),
                       ).style('text-align: right')
        ]]).style('margin: 1.5em 17px auto 17px')


def delete(record, for_id = None):
    '''Generic low-level function to delete the given record.'''
    why = ('for request to delete ' + for_id) if for_id else ''
    if config('DEMO_MODE', cast = bool):
        log(f'demo mode in effect – pretending to delete {record.id}')
    else:
        try:
            back_up_record(record)
            folio = Folio()
            folio.delete_record(record)
        except FolioOpFailed as ex:
            failed(record.id, str(ex), why)
            return
    succeeded(record.id, f'deleted {record.kind} record {record.id}', why)


def delete_holdings(record, for_id = None):
    '''Delete the given holdings record.'''
    # Does the holdings record have any items?
    folio = Folio()
    if folio.related_records(record.id, IdKind.HOLDINGS_ID, RecordKind.ITEM):
        failed(record.id, 'nonempty holdings records cannot be deleted at this time')
        return
    delete(record, for_id)


def delete_instance(record, for_id = None):
    '''Delete the given instance record.'''
    failed(record.id, 'instance records cannot be deleted at this time')


def delete_user(record, for_id = None):
    '''Delete the given user record.'''
    failed(record.id, 'user records cannot be deleted at this time')


_HANDLERS = {
    RecordKind.ITEM     : delete,       # The generic function suffices.
    RecordKind.HOLDINGS : delete_holdings,
    RecordKind.INSTANCE : delete_instance,
    RecordKind.USER     : delete_user,
}

# The following is based on
# https://github.com/FOLIO-FSE/shell-utilities/blob/master/instance-delete

# def delete_instance(folio, record, for_id = None):
#     inst_id = record['id']

#     # Starting at the bottom, delete the item records.
#     items = folio.records(inst_id, IdKind.INSTANCE_ID, RecordKind.ITEM)
#     for item in items:
#         delete_item(folio, item, inst_id)

#     # Now delete the holdings records.
#     holdings = folio.records(inst_id, IdKind.INSTANCE_ID, RecordKind.HOLDINGS)
#     for hr in holdings:
#         delete_holdings(folio, hr, inst_id)

#     # Finally, the instance record. There are two parts to this.
#     (success, msg) = folio.operation('delete', f'/instance-storage/instances/{inst_id}/source-record')
#     if success:
#         if config('DEMO_MODE', cast = bool):
#             log(f'demo mode in effect – pretending to delete {inst_id}')
#             success = True
#         else:
#             (success, msg) = folio.operation('delete', f'/instance-storage/instances/{inst_id}')
#         if success:
#             why = " for request to delete " + for_id
#             succeeded(inst_id, f'deleted instance record {inst_id}', why)
#         else:
#             failed(inst_id, f'error: {msg}')
#     else:
#         failed(inst_id, f'error: {msg}')

    # FIXME
    # Need to deal with EDS update.
