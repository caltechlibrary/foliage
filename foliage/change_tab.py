'''
change_tab.py: implementation of the "Change records" tab
'''

from   commonpy.data_utils import unique, pluralized, flattened
from   commonpy.file_utils import exists, readable
from   commonpy.interrupt import wait
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
import threading

from   .folio import Folio, RecordKind, RecordIdKind, TypeKind, NAME_KEYS
from   .folio import unique_identifiers
from   .ui import alert, warn, confirm, notify, user_file


# Tab creation function.
# .............................................................................

def change_tab():
    return [
        put_markdown('Input one or more item barcodes, item id\'s, or item'
                     + ' hrid\'s, then select the field to be changed, and'
                     + ' finally, select the new value for the field. Clicking'
                     + ' _Change values_ will change all items to have that'
                     + ' value for the field.').style('margin-bottom: 1em'),
        put_grid([[
            put_grid([
                [put_markdown('Identifiers of items to be changed:')],
                [put_textarea('chg_ids', rows = 5)],
                ]).style('margin-right: 10px'),
            put_grid([
                [put_text('Field to be changed:')],
                [put_row([
                    put_button('Select', onclick = lambda: select_field_name()
                               ).style('text-align: left; margin-right: 12px'),
                    put_textarea('chg_field', rows = 1),
                ], size = '85px auto').style('text-align: right')],
                [put_text('New field value:')],
                [put_row([
                    put_button('Select', onclick = lambda: select_field_value()
                               ).style('text-align: left; margin-right: 12px'),
                    put_textarea('chg_field_value', rows = 1),
                ], size = '85px auto').style('text-align: right')],
                ]).style('margin-left: 12px'),
            ]], cell_widths = '50% 50%'),
        put_grid([[
            put_button('Upload', color = 'primary', outline = True,
                       onclick = lambda: load_file()).style('text-align: left'),
            put_button('Change values', color = 'danger',
                       onclick = lambda: do_change()).style('text-align: right'),
            put_button(' Clear ', outline = True, onclick = lambda: clear_tab()
                       ).style('margin-left: 12px; text-align: right'),
        ]], cell_widths = 'auto 150px 90px'),
    ]


# Miscellaneous helper functions.
# .............................................................................

known_fields = {
    'Effective location'  : TypeKind.LOCATION,
    'Material type'       : TypeKind.MATERIAL,
    'Permanent loan type' : TypeKind.LOAN,
    'Permanent location'  : TypeKind.LOCATION,
    'Temporary location'  : TypeKind.LOCATION,
}

value_list = []

def load_file():
    if (contents := user_file('Upload a file containing identifiers')):
        pin.chg_ids = contents


def select_field_name():
    global value_list
    # Clear any previous values.
    value_list = []
    pin.chg_field_value = ''
    folio = Folio()
    # Ask the user to select something.
    if (answer := popup_selection('Select field to change', known_fields)):
        pin.chg_field = answer
        try:
            types = folio.types(known_fields[answer])
        except Exception as ex:
            log(f'exception requesting list of {requested}: ' + str(ex))
            alert(f'Unable to get type list -- please report this error.')
            return
        value_list = sorted(item['name'] for item in types)


def select_field_value():
    global value_list
    if not pin.chg_field:
        notify('Please first select the field to be changed.')
        return
    if not value_list:
        # If previous pop-up done quickly, update might not have happened.
        wait(0.5)
        if not value_list:
            # FIXME this is stupid
            wait(0.5)
    name = pin.chg_field.lower()
    if (val := popup_selection(f'Select a new value for the {name}', value_list)):
        pin.chg_field_value = val


def clear_tab():
    clear('output')
    pin.chg_ids = ''
    pin.chg_field_value = ''
    pin.chg_field = ''


def do_change():
    id_list = unique_identifiers(pin.chg_ids)
    change_record_fields(id_list, pin.chg_field, pin.chg_field_value)


def change_record_fields(identifiers, chg_field, new_value):
    if not identifiers:
        alert('Please input at least one barcode or other type of id.')
        return
    if not confirm('WARNING: you are about to change records in FOLIO'
                   + ' permanently. This cannot be undone.\\n\\nProceed?'):
        return
    folio = Folio()
    with use_scope('output', clear = True):
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
            try:
                records = folio.records(id, id_type, RecordKind.ITEM)
            except Exception as ex:
                log(f'exception trying to get records for {id}: ' + str(ex))
                put_error(f'Error: ' + str(ex))
                break
            if not records or len(records) == 0:
                put_error(f'No item record(s) found for {id_type} "{id}".')
                continue

            put_success(put_markdown(f'Changed item record **{id}**'
                                     + f' to have value **{new_value}** for'
                                     + f' field _{chg_field.lower()}_.'))


def popup_selection(title, values):
    event = threading.Event()
    clicked_ok = False

    def clk(val):
        nonlocal clicked_ok
        clicked_ok = val
        event.set()

    pins = [
        put_select('list_selection', options = values),
        put_buttons([
            {'label': 'Submit', 'value': True},
            {'label': 'Cancel', 'value': False, 'color': 'danger'},
        ], onclick = clk).style('float: right')
    ]
    popup(title = title, content = pins, closable = False)

    event.wait()
    close_popup()
    wait(0.5)                           # Give time for popup to go away.

    return pin.list_selection if clicked_ok else None
