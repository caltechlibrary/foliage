'''
delete_tab.py: implementation of the "Delete records" tab

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

from   .base_tab import FoliageTab
from   .folio import Folio, RecordKind, RecordIdKind, TypeKind, NAME_KEYS
from   .folio import unique_identifiers, back_up_record
from   .ui import confirm, notify, user_file
from   .ui import tell_success, tell_warning, tell_failure
from   .ui import note_info, note_warn, note_error


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
            put_markdown('Input one or more barcodes, item id\'s, hrid\'s,'
                         + ' or instance id\'s, then press the button'
                         + ' to delete the associated FOLIO records. Note that'
                         + ' **deleting instance records will cause multiple'
                         + ' holdings and item records to be deleted**. Handle'
                         + ' with extreme caution!'),
            put_button('Upload', outline = True,
                       onclick = lambda: load_file()).style('text-align: right'),
        ]], cell_widths = 'auto 100px'),
        put_textarea('textbox_delete', rows = 4),
        put_row([
            put_button('Delete FOLIO records', color = 'danger',
                       onclick = lambda: do_delete()),
            put_text(''),    # Adds a column, pushing next item to the right.
            put_button('Clear', outline = True,
                       onclick = lambda: clear_tab()).style('text-align: right')
        ])
    ]


# Miscellaneous helper functions.
# .............................................................................

def clear_tab():
    log(f'clearing tab')
    clear('output')
    pin.textbox_delete = ''

def load_file():
    log(f'user requesting file upload')
    if (file := user_file('Upload a file containing identifiers')):
        pin.textbox_delete = file

def do_delete():
    log(f'do_delete invoked')
    folio = Folio()
    if not pin.textbox_delete:
        note_error('Please input at least one barcode or other type of id.')
        return
    if not confirm('WARNING: you are about to delete records in FOLIO'
                   + ' permanently. This cannot be undone.\\n\\nProceed?'):
        return
    with use_scope('output', clear = True):
        identifiers = unique_identifiers(pin.textbox_delete)
        steps = len(identifiers) + 1
        put_processbar('bar', init = 1/steps);
        for index, id in enumerate(identifiers, start = 2):
            put_html('<br>')
            id_type = folio.record_id_type(id)
            if id_type == RecordIdKind.UNKNOWN:
                tell_failure(f'Could not recognize the identifier type of {id}.')
                set_processbar('bar', index/steps)
                continue
            try:
                records = folio.records(id, id_type)
                record = records[0] if records else None
            except Exception as ex:
                note_error(f'Error: ' + str(ex))
                break
            finally:
                set_processbar('bar', index/steps)
            if not record:
                tell_failure(f'Could not find a record for {id_type} {id}.')
                continue
            back_up_record(record)
            if id_type in [RecordIdKind.ITEM_ID, RecordIdKind.ITEM_BARCODE]:
                if demo_mode:
                    tell_success(f'Deleted item record **{id}**')
                else:
                    delete_item(folio, record, id)
            else:
                tell_warning('Instance record deletion is currently turned off.')
                # delete_instance(folio, record, id)


def delete_item(folio, record, for_id = None):
    id = record['id']
    (success, msg) = folio.operation('delete', f'/inventory/items/{id}')
    if success:
        why = " (for request to delete " + (for_id if for_id else '') + ")"
        tell_success(f'Deleted item record {id}{why}')
    else:
        tell_failure(f'Error: {msg}')


def delete_holdings(folio, record, for_id = None):
    id = record['id']
    (success, msg) = folio.operation('delete', f'/holdings-storage/holdings/{id}')
    if success:
        why = " (for request to delete " + (for_id if for_id else '') + ")"
        tell_success(f'Deleted holdings record {id}{why}.')
    else:
        tell_failure(f'Error: {msg}')


# The following is based on
# https://github.com/FOLIO-FSE/shell-utilities/blob/master/instance-delete

def delete_instance(folio, record, for_id = None):
    inst_id = record['id']

    # Starting at the bottom, delete the item records.
    items = folio.records(inst_id, RecordIdKind.INSTANCE_ID, RecordKind.ITEM)
    tell_warning(f'Deleting {pluralized("item record", items, True)} due to'
                 + f' the deletion of instance record {inst_id}.')
    for item in items:
        delete_item(folio, item, for_id)

    # Now delete the holdings records.
    holdings = folio.records(inst_id, RecordIdKind.INSTANCE_ID, RecordKind.HOLDINGS)
    tell_warning(f'Deleting {pluralized("holdings record", holdings, True)} due to'
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
            tell_failure(f'Error: {msg}')
    else:
        tell_failure(f'Error: {msg}')

    # FIXME
    # Need to deal with EDS update.
