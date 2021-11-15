'''
change_tab.py: implementation of the "Change records" tab

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   collections import namedtuple
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
from   pywebio.session import run_js, eval_js
from   sidetrack import set_debug, log
import threading

from   .base_tab import FoliageTab
from   .folio import Folio, RecordKind, RecordIdKind, TypeKind, NAME_KEYS
from   .folio import unique_identifiers, back_up_record
from   .ui import alert, warn, confirm, notify, user_file


# Tab definition class.
# .............................................................................

class ChangeTab(FoliageTab):
    def contents(self):
        return {'title': 'Change records', 'content': tab_contents()}

    def pin_watchers(self):
        return {'chg_action': lambda value: update_tab(value)}


# Tab creation function.
# .............................................................................

def tab_contents():
    log(f'generating change tab contents')
    return [
        put_markdown('Input one or more item barcodes, item id\'s, or item'
                     + ' hrid\'s, then select the field to be changed, and'
                     + ' finally, select the new value for the field. Clicking'
                     + ' _Change values_ will change all items to have that'
                     + ' value for the field.').style('margin-bottom: 1em'),
        put_grid([[
            put_grid([
                [put_markdown('Identifiers of items to be changed:')],
                [put_textarea('chg_ids', rows = 7)],
                ]),
            put_grid([
                [put_text('Field to be changed:')],
                [put_row([
                    put_button('Select', onclick = lambda: select_field_name()
                               ).style('text-align: left'),
                    put_textarea('chg_field', rows = 1, readonly = True),
                ], size = '85px auto').style('text-align: right')],
                [put_radio('chg_action', inline = True,
                          options = [ ('Change field value', 'change', True),
                                      ('Delete field value', 'delete')]
                           ).style('margin-bottom: 0.3em')],
                [put_text('New field value:')],
                [put_row([
                    put_button('Select', onclick = lambda: select_field_value()),
                    put_textarea('chg_field_value', rows = 1, readonly = True),
                ], size = '85px auto').style('z-index: 9')],
                ]).style('margin-left: 12px'),
            ]], cell_widths = '50% 50%'),
        put_grid([[
            put_button('Upload', outline = True,
                       onclick = lambda: load_file()).style('text-align: left'),
            put_button('Change records', color = 'danger',
                       onclick = lambda: do_change()).style('text-align: right'),
            put_button(' Clear ', outline = True,
                       onclick = lambda: clear_tab()).style('text-align: right'),
        ]], cell_widths = 'auto 150px 90px'),
    ]


# Miscellaneous helper functions.
# .............................................................................

Field = namedtuple('Field', 'type key')

known_fields = {
    'Effective location'  : Field(type = TypeKind.LOCATION, key = 'effectiveLocation'),
    'Material type'       : Field(type = TypeKind.MATERIAL, key = 'materialType'),
    'Permanent loan type' : Field(type = TypeKind.LOAN,     key = 'permanentLoanType'),
    'Permanent location'  : Field(type = TypeKind.LOCATION, key = 'permanentLocation'),
    'Temporary location'  : Field(type = TypeKind.LOCATION, key = 'temporaryLocation'),
}


def update_tab(value):
    if value == 'delete':
        eval_js('''$("p:contains('New field value')").css("opacity", "0.4");''')
        eval_js('''$("div").filter((i, n) => $(n).css("z-index") == 9).css("opacity", "0.4");''')
    else:
        eval_js('''$("p:contains('New field value')").css("opacity", "1");''')
        eval_js('''$("div").filter((i, n) => $(n).css("z-index") == 9).css("opacity", "1");''')


def clear_tab():
    log(f'clearing tab')
    clear('output')
    pin.chg_ids = ''
    pin.chg_field_value = ''
    pin.chg_field = ''
    pin.chg_action = 'change'
    update_tab('change')


def load_file():
    log(f'user requesting file upload')
    if (contents := user_file('Upload a file containing identifiers')):
        pin.chg_ids = contents


def select_field_name():
    # Clear any previous value.
    pin.chg_field_value = ''
    if (answer := popup_selection('Select field to change', known_fields)):
        # Show the selection in the text field.
        pin.chg_field = answer


def select_field_value():
    if pin.chg_action == 'delete':
        # Ignore clicks when the action is to delete.
        return
    if not pin.chg_field:
        notify('Please first select the field to be changed.')
        return

    log(f'getting list of values for {pin.chg_field}')
    folio = Folio()
    try:
        types = folio.types(known_fields[pin.chg_field].type)
    except Exception as ex:
        log(f'exception requesting list of {requested}: ' + str(ex))
        alert(f'Unable to get type list -- please report this error.')
        return
    value_list = sorted(item['name'] for item in types)
    name = pin.chg_field.lower()
    if (val := popup_selection(f'Select a new value for the {name}', value_list)):
        pin.chg_field_value = val


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
        put_processbar('bar', init = 1/steps)
        for index, id in enumerate(identifiers, start = 2):
            put_html('<br>')
            set_processbar('bar', index/steps)
            try:
                id_type = folio.record_id_type(id)
                if id_type == RecordIdKind.UNKNOWN:
                    log(f'could not recognize type of {id}')
                    put_error(f'Could not recognize the identifier type of {id}.')
                    continue
                records = folio.records(id, id_type, RecordKind.ITEM)
            except Exception as ex:
                log(f'exception getting records for {id}: ' + str(ex))
                put_error(f'Error: ' + str(ex))
                continue
            if not records or len(records) == 0:
                put_error(f'No item record(s) found for {id_type} "{id}".')
                continue
            # FIXME this is only okay for item records.
            record = records[0]
            field_key = known_fields[chg_field].key
            if record.get(field_key, None):
                put_warn(put_markdown(f'Item record **{id}** has no value'
                                      + f' for field _{field_key}_ – skipping'))
                continue

            holdings_id = record['holdingsRecordId']
            try:
                holdings = folio.records(holdings_id, RecordIdKind.HOLDINGS_ID)
            except Exception as ex:
                log(f'exception getting holdings record {holdings_id}: ' + str(ex))
                put_error(f'Failed to get holdings record for {id} -- skipping')
                continue

            holdings_record = holdings[0]
            if pin.chg_action == 'delete':
                # back_up_record(record)
                log(f'deleting field {field_key} from item {id}')
                del record[field_key]
                folio.update(record)

                put_success(put_markdown(f'Deleted _{chg_field.lower()}_ field'
                                         + f' from record **{id}**.'))

                # if holdings_record.get(field_key, None):
                #     log(f'deleting field {field_key} from holdings {holdings_id}')
            else:
                # Have to update both the item record and the holdings record
                import pdb; pdb.set_trace()


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
