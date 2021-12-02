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
from   commonpy.exceptions import Interrupted
from   commonpy.file_utils import exists, readable
from   commonpy.interrupt import wait, reset_interrupts, interrupt, interrupted
from   decouple import config
from   pywebio.input import input, select, checkbox, radio
from   pywebio.input import NUMBER, TEXT, input_update, input_group
from   pywebio.output import put_text, put_markdown, put_row, put_html
from   pywebio.output import toast, popup, close_popup, put_buttons, put_button
from   pywebio.output import use_scope, set_scope, clear, remove, put_warning
from   pywebio.output import put_info, put_table, put_grid, span, put_link
from   pywebio.output import put_tabs, put_image, put_scrollable, put_code
from   pywebio.output import put_processbar, set_processbar, put_loading
from   pywebio.output import put_column
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
from   pywebio.pin import put_textarea, put_radio, put_checkbox, put_select
from   pywebio.session import run_js, eval_js
from   sidetrack import set_debug, log
import sys
import threading

from   foliage.base_tab import FoliageTab
from   foliage.export import export_data
from   foliage.folio import Folio, RecordKind, RecordIdKind, TypeKind, NAME_KEYS
from   foliage.folio import unique_identifiers, back_up_record
from   foliage.ui import confirm, notify, user_file
from   foliage.ui import tell_success, tell_warning, tell_failure, stop_processbar
from   foliage.ui import note_info, note_warn, note_error, tell_success, tell_failure


# Tab definition class.
# .............................................................................

class ChangeTab(FoliageTab):
    def contents(self):
        return {'title': 'Change records', 'content': tab_contents()}

    def pin_watchers(self):
        return {'chg_op': lambda value: update_tab(value)}


# Tab creation function.
# .............................................................................

def tab_contents():
    log(f'generating change tab contents')
    # FIXME what causes these diffs on windows?
    textarea_rows = 11 if sys.platform.startswith('win') else 10
    margin_adjust = 'margin-top: -1em' if sys.platform.startswith('win') else ''
    return [
        put_grid([[
            put_markdown('Input one or more **item** barcodes, id\'s, or hrid\'s;'
                         + ' select a field to change; choose the action (add,'
                         + ' change, delete); and fill in the current '
                         + ' and/or new value. All items will'
                         + ' be changed the same way.'),
            put_button('Upload', outline = True,
                       onclick = lambda: load_file()).style('text-align: right'),
        ]], cell_widths = 'auto 100px'),
        put_grid([[
            put_grid([
                [put_markdown('Identifiers of items to be changed:')],
                [put_textarea('textbox_ids', rows = textarea_rows)],
            ]),
            put_grid([
                [put_text('Field to be changed:')],
                [put_row([
                    put_button('Select', onclick = lambda: select_field_name()
                               ).style('text-align: left'),
                    put_textarea('chg_field', rows = 1, readonly = True),
                ], size = '95px auto').style('text-align: right')],
                [put_radio('chg_op', inline = True,
                           options = [ ('Add value', 'add', True),
                                       ('Change value', 'change'),
                                       ('Delete value', 'delete')]
                           ).style(f'margin-bottom: 0.3em; {margin_adjust}')],
                [put_text('Current field value:').style('opacity: 0.3')],
                [put_row([
                    put_button('Select', onclick = lambda: select_field_value('old')),
                    put_textarea('old_value', rows = 1, readonly = True),
                ], size = '95px auto').style('z-index: 8; opacity: 0.3')],
                [put_text('New field value:')],
                [put_row([
                    put_button('Select', onclick = lambda: select_field_value('new')),
                    put_textarea('new_value', rows = 1, readonly = True),
                ], size = '95px auto').style('z-index: 9')],
                ]).style('margin-left: 12px'),
        ]], cell_widths = '50% 50%').style('margin-top: 1em'),
        put_row([
            put_button('Change records', color = 'danger',
                       onclick = lambda: do_change()),
            put_button('Clear', outline = True,
                       onclick = lambda: clear_tab()).style('text-align: right'),
        ])
    ]


# Implementation of tab functionality.
# .............................................................................

def update_tab(value):
    log(f'updating form in response to radio box selection: "{value}"')
    if value == 'add':
        eval_js('''$("p:contains('Current field value')").css("opacity", "0.3");''')
        eval_js('''$("div").filter((i, n) => $(n).css("z-index") == 8).css("opacity", "0.3");''')
        eval_js('''$("p:contains('New field value')").css("opacity", "1");''')
        eval_js('''$("div").filter((i, n) => $(n).css("z-index") == 9).css("opacity", "1");''')
    elif value == 'delete':
        eval_js('''$("p:contains('Current field value')").css("opacity", "1");''')
        eval_js('''$("p:contains('New field value')").css("opacity", "0.3");''')
        eval_js('''$("div").filter((i, n) => $(n).css("z-index") == 8).css("opacity", "1");''')
        eval_js('''$("div").filter((i, n) => $(n).css("z-index") == 9).css("opacity", "0.3");''')
    else:
        eval_js('''$("p:contains('Current field value')").css("opacity", "1");''')
        eval_js('''$("div").filter((i, n) => $(n).css("z-index") == 8).css("opacity", "1");''')
        eval_js('''$("p:contains('New field value')").css("opacity", "1");''')
        eval_js('''$("div").filter((i, n) => $(n).css("z-index") == 9).css("opacity", "1");''')


def clear_tab():
    log(f'clearing tab')
    clear('output')
    pin.textbox_ids = ''
    pin.chg_op = 'add'
    pin.chg_field = ''
    pin.old_value = ''
    pin.new_value = ''
    update_tab('add')


def select_field_name():
    # Clear any previous value.
    pin.new_value = ''
    if (answer := list_selection('Select field to change', known_fields)):
        # Show the selected value.
        pin.chg_field = answer
        log(f'user selected field {answer}')
    else:
        log(f'user canceled field selection')


def select_field_value(old_new):
    # No way to prevent clicks when the op is not valid, so just ignore them.
    # Setting an old field value is only valid for change and delete.
    # Setting a new field value is only valid for add and change.
    if ((old_new == 'old' and pin.chg_op == 'add')
        or (old_new == 'new' and pin.chg_op == 'delete')):
        return

    if not pin.chg_field:
        notify('Please first select the field to be changed.')
        return

    fname = pin.chg_field.lower()
    log(f'getting list of values for {fname}')
    type_list = Folio().types(known_fields[pin.chg_field].type)
    if not type_list:
        note_error(f'Could not retrieve the list of possible {fname} values')
        return
    value_list = sorted(item['name'] for item in type_list)
    if (val := list_selection(f'Select the {old_new} value for {fname}', value_list)):
        field = old_new + '_value'
        setattr(pin, field, val)
        log(f'user selected {old_new} field value {val}')
    else:
        log(f'user canceled value selection')


def list_selection(title, values):
    log(f'showing list selection popup')
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
            {'label': 'Cancel', 'value': False, 'color': 'secondary'},
        ], onclick = clk).style('float: right')
    ]
    popup(title = title, content = pins, closable = False)
    event.wait()
    close_popup()
    wait(0.5)                           # Give time for popup to go away.

    log(f'user {"made a selection" if clicked_ok else "cancelled"}')
    return pin.list_selection if clicked_ok else None


def all_selections_made():
    return (pin.chg_field
            and ((pin.chg_op == 'add' and pin.new_value)
                 or (pin.chg_op == 'delete' and pin.old_value)
                 or (pin.chg_op == 'change' and pin.new_value and pin.old_value)))


def load_file():
    log(f'user requesting file upload')
    if (contents := user_file('Upload a file containing identifiers')):
        pin.textbox_ids = contents


def stop():
    log(f'stopping')
    interrupt()
    stop_processbar()


results = []

def succeeded(id, msg):
    global results
    results.append({'id': id, 'success': True, 'notes': msg})
    tell_success(f'Successfully changed **{id}**: ' + msg + '.')


def failed(id, msg):
    global results
    results.append({'id': id, 'success': False, 'notes': msg})
    tell_failure(f'Failed to change **{id}**: ' + msg + '.')


def skipped(id, msg):
    global results
    results.append({'id': id, 'success': False, 'notes': msg})
    tell_warning(f'Skipped **{id}**: ' + msg + '.')


def do_change():
    log(f'do_change invoked')
    global results
    identifiers = unique_identifiers(pin.textbox_ids)
    if not identifiers:
        note_error('Please input at least one barcode or other type of id.')
        return
    if not all_selections_made():
        note_error('Missing selections – cannot proceed until form is filled out.')
        return
    if not confirm('Warning: you are about to change records in FOLIO'
                   + ' permanently. Proceed?', danger = True):
        log(f'user declined to proceed')
        return
    reset_interrupts()
    results = []
    with use_scope('output', clear = True):
        steps = len(identifiers) + 1
        put_grid([[
            put_processbar('bar', init = 1/steps).style('margin-top: 11px'),
            put_button('Stop', outline = True, color = 'danger',
                       onclick = lambda: stop()).style('text-align: right')
            ]], cell_widths = '85% 15%').style('margin: auto 17px auto 17px')
        folio = Folio()
        for count, id in enumerate(identifiers, start = 2):
            put_html('<br>')
            try:
                id_kind = folio.record_id_kind(id)
                if id_kind == RecordIdKind.UNKNOWN:
                    failed(id, f'could not recognize this type of id')
                    continue
                # FIXME update this when we support other record types.
                elif id_kind not in [RecordIdKind.ITEM_ID, RecordIdKind.ITEM_HRID,
                                     RecordIdKind.ITEM_BARCODE]:
                    skipped(id, f'not an item record')
                    continue
                records = folio.records(id, id_kind, RecordKind.ITEM)
                if interrupted():
                    break
                if not records or len(records) == 0:
                    failed(id, f'no item record(s) found for {id_kind} {id}.')
                    continue
                # FIXME update this when support other record types.
                known_fields[pin.chg_field].change(records[0])
            except Interrupted as ex:
                log('stopping due to interruption')
                break
            except Exception as ex:
                tell_failure(f'Error: ' + str(ex))
                stop_processbar()
                return
            finally:
                set_processbar('bar', count/steps)
        stop_processbar()
        put_html('<br>')
        if interrupted():
            tell_warning('**Stopped**.')
        else:
            what = pluralized('item record', identifiers, True)
            put_grid([[
                put_markdown(f'Finished changing {what}.').style('margin-top: 6px'),
                put_button('Export summary', outline = True,
                           onclick = lambda: export_data(results, 'change-results.csv'),
                           ).style('text-align: right')
            ]]).style('margin: auto 17px auto 17px')


def change_location(record):
    # Get the list of known types again (folio.py will have cached it) and
    # create a mapping of value names to type objects.
    folio = Folio()
    types = {}
    for item in folio.types(known_fields[pin.chg_field].type):
        types[item['name']] = item

    id = record['id']
    field_key = known_fields[pin.chg_field].key
    if (current_value := record.get(field_key, None)):
        if pin.chg_op == 'add':
            skipped(id, f'item has an existing value for _{field_key}_')
            return
        # We're doing change or delete. Existing value must match expected one.
        if current_value != types[pin.old_value]['id']:
            skipped(id, f'value of field _{field_key}_ is not "{pin.old_value}"')
            return
        back_up_record(record)
        if pin.chg_op == 'change':
            log(f'changing field {field_key} in item {id} to {pin.new_value}')
            record[field_key] = types[pin.new_value]['id']
        elif pin.chg_op == 'delete':
            log(f'deleting field {field_key} from item {id}')
            del record[field_key]
    elif pin.chg_op == 'add':
        log(f'adding {field_key} value "{pin.new_value}" to item {id}')
        back_up_record(record)
        record[field_key] = types[pin.new_value]['id']
    else:
        # It doesn't have a value, and we're not doing an add.
        skipped(id, f'item **{id}** has no field _{field_key}_')
        return

    if pin.chg_field == 'Permanent location':
        # The item's permanent location should match the holdings location.
        # If an item is moved to a different place, its holdings field value
        # should be updated, which may require creating a new holdings record.
        # At the moment, the following does NOT create new holdings records.

        holdings_id = record['holdingsRecordId']
        if (holdings := folio.records(holdings_id, RecordIdKind.HOLDINGS_ID)):
            holdings_record = holdings[0]
        else:
            failed(id, f'cannot update permanent its location because its'
                   + f' holdings record {holdings_id} could not be retrieved')
            return

        new_location_id = record['permanentLocation']['id']
        new_location_name = record['permanentLocation']['name']
        if holdings_record['permanentLocationId'] != new_location_id:
            log(f'holdings location is not the same as new location')
            # See if the instance has another holdings record with the loc.
            # We can get the instance id from this holdings b/c it's the same.
            inst_id = holdings_record['instanceId']
            for rec in folio.records(inst_id, RecordIdKind.INSTANCE_ID, 'holdings'):
                if rec['permanentLocationId'] == new_location_id:
                    new_holdings_id = rec['id']
                    log(f'updating {id}\'s holdings record to be {new_holdings_id}')
                    record['holdingsRecordId'] = new_holdings_id
                    break
            else:
                # No holdings records found with the new location. Currently not
                # handled. FIXME: support creating new holdings record.
                failed(id, f'the parent instance {inst_id} has no holdings record'
                       + f' with a permanent location of {new_location_name}.'
                       + f' One will need to be created before item {id}\'s'
                       + f' permanent location can be set there.')
                return

    # If we made it this far, send the updated record to Folio.
    if config('DEMO_MODE', cast = bool):
        log(f'demo mode in effect – pretending to change {id}')
        success = True
    else:
        success, error = folio.write(record, f'/item-storage/items/{id}')

    # Report the outcome to the user.
    text = {'add': 'added to', 'change': 'changed in', 'delete': 'deleted from'}
    act  = text[pin.chg_op]
    if success:
        succeeded(id, f'field _{field_key}_ {act} item record')
    else:
        failed(id, str(error))


Field = namedtuple('Field', 'type key change')

known_fields = {
    'Temporary location': Field(type = TypeKind.LOCATION,
                                key = 'temporaryLocationId',
                                change = change_location),
    'Permanent location': Field(type = TypeKind.LOCATION,
                                key = 'permanentLocationId',
                                change = change_location),
}
