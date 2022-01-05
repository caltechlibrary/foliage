'''
delete_tab.py: implementation of the "Delete records" tab

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
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
from   foliage.export import export_data
from   foliage.folio import Folio, RecordKind, IdKind, TypeKind
from   foliage.folio import unique_identifiers, back_up_record
from   foliage.ui import confirm, notify, user_file, stop_processbar
from   foliage.ui import tell_success, tell_warning, tell_failure
from   foliage.ui import note_info, note_warn, note_error


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
            put_markdown('Input one or more item barcodes, id\'s, or hrid\'s,'
                         + ' then press the button'
                         + ' to delete the associated FOLIO records.'),
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
    identifiers = unique_identifiers(pin.textbox_delete)
    if not identifiers:
        note_error('Please input at least one barcode or other type of id.')
        return
    if not confirm('Warning: you are about to delete records from FOLIO'
                   + ' permanently. Proceed?', danger = True):
        log(f'user declined to proceed')
        return
    steps = len(identifiers) + 1
    folio = Folio()
    results = []
    reset_interrupts()
    with use_scope('output', clear = True):
        put_grid([[
            put_processbar('bar', init = 1/steps).style('margin-top: 11px'),
            put_button('Stop', outline = True, color = 'danger',
                       onclick = lambda: stop()).style('text-align: right')
            ]], cell_widths = '85% 15%').style('margin: auto 17px 1.5em 17px')
        for count, id in enumerate(identifiers, start = 2):
            try:
                record = folio.record(id)
                if not record:
                    failed(id, f'no item record(s) found for {id}.')
                    continue
                elif record.kind is not RecordKind.ITEM:
                    skipped(id, f'{id_kind} deletion is currently turned off.')
                    continue
                delete(record)
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
            what = pluralized('record', identifiers, True)
            put_grid([[
                put_markdown(f'Finished deleting {what}.').style('margin-top: 6px'),
                put_button('Export summary', outline = True,
                           onclick = lambda: export_data(results, 'deletion-results.csv'),
                           ).style('text-align: right')
            ]]).style('margin: 1.5em 17px auto 17px')


def delete(record, for_id = None):
    if config('DEMO_MODE', cast = bool):
        log(f'demo mode in effect – pretending to delete {record.id}')
        success = True
    else:
        back_up_record(record)
        folio = Folio()
        (success, msg) = folio.delete(record)
    why = ('for request to delete ' + for_id) if for_id else ''
    if success:
        succeeded(record.id, f'deleted item record {record.id}', why)
    else:
        failed(record.id, f'{msg}', why)


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
