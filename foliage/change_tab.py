'''
change_tab.py: implementation of the "Change records" tab

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   collections import namedtuple, defaultdict
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
from   foliage.folio import Folio, RecordKind, IdKind, TypeKind
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
    textarea_rows = 14 if sys.platform.startswith('win') else 13
    margin_adjust = 'margin-top: -1.1em' if sys.platform.startswith('win') else ''
    return [
        put_grid([[
            put_markdown('Input item and/or holdings identifiers'
                         + ' (i.e., barcodes, id\'s, or hrid\'s). All'
                         + ' records will be changed the same way. Changing a'
                         + ' holdings record will also change all its items.'),
            put_button('Upload', outline = True,
                       onclick = lambda: load_file()).style('text-align: right'),
        ]], cell_widths = 'auto 100px'),
        put_grid([[
            put_grid([
                [put_textarea('textbox_ids', rows = textarea_rows)],
            ]),
            put_grid([
                [put_text('Select the field to be changed:').style('margin-top: -0.5em')],
                [put_row([
                    put_button('Select', onclick = lambda: select_field_name()
                               ).style('text-align: left'),
                    put_textarea('chg_field', rows = 1, readonly = True),
                ], size = '95px auto').style('text-align: right')],
                [put_text('Select the action to perform:')],
                [put_radio('chg_op', inline = True,
                           options = [ ('Add value', 'add', True),
                                       ('Change value', 'change'),
                                       ('Delete value', 'delete')]
                           ).style(f'margin-bottom: 0.3em; {margin_adjust}')],
                [put_text('Current field value (records must match this):').style('opacity: 0.3')],
                [put_row([
                    put_button('Select', onclick = lambda: select_field_value('old')),
                    put_textarea('old_value', rows = 1, readonly = True),
                ], size = '95px auto').style('z-index: 8; opacity: 0.3')],
                [put_text('New value (field will be set to this):')],
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
    if (answer := selected('Select field to change', known_fields)):
        # Show the selected value.
        pin.chg_field = answer
        log(f'user selected field {answer}')


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
    if (val := selected(f'Select the {old_new} value for {fname}', value_list)):
        field = old_new + '_value'
        setattr(pin, field, val)
        log(f'user selected {old_new} field value {val}')


def selected(title, values):
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

def succeed(id, msg, context = ''):
    global results
    comment = (' (' + context + ')') if context else ''
    results.append({'id': id, 'success': True, 'notes': msg + comment})
    tell_success(f'Successfully changed **{id}**{comment}: ' + msg + '.')


def fail(id, msg, context = ''):
    global results
    comment = (' (' + context + ')') if context else ''
    results.append({'id': id, 'success': False, 'notes': msg + comment})
    tell_failure(f'Failed to change **{id}**{comment}: ' + msg + '.')


def skip(id, msg, context = ''):
    global results
    comment = (' (' + context + ')') if context else ''
    results.append({'id': id, 'success': False, 'notes': msg + comment})
    tell_warning(f'Skipped **{id}**{comment}: ' + msg + '.')


_UNSUPPORTED_KINDS = [
    IdKind.INSTANCE_ID,
    IdKind.INSTANCE_HRID,
    IdKind.ACCESSION,
    IdKind.USER_ID,
    IdKind.USER_BARCODE,
    IdKind.LOAN_ID,
    IdKind.TYPE_ID,
]

def do_change():
    log(f'do_change invoked')
    global results
    results = []
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
    steps = 2*len(identifiers)          # 2 passes => 2x number of items
    folio = Folio()
    with use_scope('output', clear = True):
        try:
            done = 0
            with use_scope('progress'):
                put_grid([[put_markdown(f'_Gathering records ..._')]]
                         ).style('margin: auto 17px auto 17px')
            put_grid([[
                put_processbar('bar', init = done/steps).style('margin-top: 11px'),
                put_button('Stop', outline = True, color = 'danger',
                           onclick = lambda: stop()).style('text-align: right')
            ]], cell_widths = '85% 15%').style('margin: auto 17px 1.5em 17px')

            # Start by gathering all records & their types.
            records = []
            for id in identifiers:
                record = folio.record(id)
                done += 1
                set_processbar('bar', done/steps)
                if not record:
                    fail(id, f'unrecognized identifier **{id}**.')
                    continue
                if record.kind in _UNSUPPORTED_KINDS:
                    skip(id, 'changing this kind of record is not supported.')
                    continue
                records.append(record)

            # 1st pass: apply changes to holdings records in the input (if any).
            #  * temporary location: all ops allowed, & change holdings' items.
            #
            #  * permanent location: "add"/"delete" permanent loc. on holdings
            #    is not allowed b/c they have only 1 perm. loc & always have a
            #    loc. "Change" allowed; changes all items & the holdings rec.
            with use_scope('progress', clear = True):
                put_grid([[put_markdown(f'_Changing records ..._')]]
                         ).style('margin: auto 17px auto 17px')
            holdings_done = []
            for record in filter(lambda r: r.kind is RecordKind.HOLDINGS, records):
                done += 1
                set_processbar('bar', done/steps)
                if not (change_holdings(record) and save_record(record)):
                    log(f'couldn\'t change and/or save holdings rec. – skipping items')
                    continue
                for item in folio.related_records(record.id, IdKind.HOLDINGS_ID,
                                                  RecordKind.ITEM):
                    log(f'changing item {item.id} after changing holdings {record.id}')
                    context = f'an item associated with holdings record {record.id}'
                    # We changed the holdings rec. => we can change item directly.
                    if change_item(item, record, context = context):
                        save_record(item, context = context)
                holdings_done.append(record.id)

            # 2nd pass: apply changes to item records in the input. We may have
            # changed some already if there were holdings records in the input.
            for item in filter(lambda r: r.kind is RecordKind.ITEM, records):
                if item.data['holdingsRecordId'] in holdings_done:
                    log(f'skipping {item.id}, assuming it was done in holdings pass')
                elif change_item(item):
                    save_record(item)
                done += 1
                set_processbar('bar', done/steps)
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
            put_markdown(f'Finished changing {what}.').style('margin-top: 6px'),
            put_button('Export summary', outline = True,
                       onclick = lambda: export_data(results, 'change-results.csv'),
                       ).style('text-align: right')
        ]]).style('margin: auto 17px auto 17px')


def change_record(record, context = ''):
    '''Returns True if successful, False if couldn't make the change.'''
    folio = Folio()
    # Get the list of known values for this type (folio.py will have cached
    # it) and create a mapping of value names to value objects.
    value_type = known_fields[pin.chg_field].type
    values = {x['name']:x for x in folio.types(value_type)}

    field_key = known_fields[pin.chg_field].key
    if (current_value := record.data.get(field_key, None)):
        if pin.chg_op == 'add':
            skip(record.id, f'item _{field_key}_ has an existing value', context)
            return False
        # We're doing change or delete. Existing value must match expected one.
        if current_value != values[pin.old_value]['id']:
            skip(record.id, f'_{field_key}_ value is not "{pin.old_value}"', context)
            return False
        # We can proceed.
        back_up_record(record)
        if pin.chg_op == 'change':
            log(f'changing field {field_key} in item {record.id} to {pin.new_value}')
            record.data[field_key] = values[pin.new_value]['id']
        elif pin.chg_op == 'delete':
            # Some fields on some record kinds must always exist.
            if record.kind in known_fields[pin.chg_field].delete_ok:
                log(f'deleting field {field_key} from item {record.id}')
                del record.data[field_key]
            else:
                skip(record.id, f'not allowed to delete field {field_key}'
                     + ' on {record.kind} records', context)
                return False
    elif pin.chg_op == 'add':
        log(f'adding {field_key} value "{pin.new_value}" to item {record.id}')
        back_up_record(record)
        record.data[field_key] = values[pin.new_value]['id']
    else:
        # It doesn't have a value, and we're not doing an add.
        skip(record.id, f'item **{record.id}** has no field _{field_key}_', context)
        return False
    log(f'changes made to {record.kind} record {record.id}')
    return True


def save_record(record, context = ''):
    if config('DEMO_MODE', cast = bool):
        log(f'demo mode in effect – pretending to save {record.id}')
        success = True
    else:
        folio = Folio()
        endpoint = RecordKind.storage_endpoint(record.kind)
        success, error = folio.write(record, endpoint + '/' + record.id)
    # Report the outcome to the user.
    field = 'field _' + known_fields[pin.chg_field].key + '_'
    text = {'add': 'added to', 'change': 'changed in', 'delete': 'deleted from'}
    action = text[pin.chg_op]
    if success:
        succeed(record.id, f'{field} {action} {record.kind} record', context)
        return True
    else:
        fail(record.id, str(error), context)
        return False


def change_holdings(record):
    if pin.chg_field == 'Permanent location' and pin.chg_op != 'change':
        # Holdings always have a perm loc., so can only change it.
        skip(record.id, 'Cannot add or delete a permanent'
                + ' location field on holdings records')
        return False
    return change_record(record)


def change_item(item, holdings_record = None, context = ''):
    # Try to change the item but without saving them yet. If we fail, bail.
    if not change_record(item, context):
        return False

    # If the change is to a temporary location field, we can make the change
    # without having to change a holdings record, and we're done.
    if pin.chg_field == 'Temporary location':
        return True

    # Not a temporary location change. Are we making this change together with
    # changing the holdings record? If so and the results match, we're done.
    field_key = known_fields[pin.chg_field].key
    if holdings_record:
        if item.data[field_key] == holdings_record.data[field_key]:
            return True
        else:
            # This should not happen.
            import pdb; pdb.set_trace()

    # No holdings record has been changed so far. Here are the possible cases:
    # 1. Moving item from one holdings to another holdings on the instance.
    #    1a) Original holdings has other items => no deletion needed. Done.
    #    1b) Original holdings is empty => delete original holdings record.
    #
    # 2. Moving item to a location that has no holdings record on the instance
    #    => must create new holdings record on the instance.
    folio = Folio()
    current_holdings = folio.record(item.data['holdingsRecordId'])
    if not current_holdings:
        # This should never happen, but we always want to check everything.
        fail(id, f'cannot update {field_key} of {item.id} because its holdings'
               + f' record {item.data["holdingsRecordId"]} could not be retrieved')
        return False

    instance_id = current_holdings['instanceId']
    instance = folio.record(instance_id)
    if not instance:
        # This should never happen, but we always want to check everything.
        fail(id, f'cannot update {field_key} of {item.id} because its'
               + f' instance record {instance_id} could not be retrieved')
        return False

    # In practice, the only way we get to this point is if the operation is not
    # a deletion -- so either an add or a change.
    for holdings in folio.related_records(instance_id, IdKind.INSTANCE_ID, 'holdings'):
        if item.data[field_key] == holdings.data[field_key]:
            # Found a holdings record that has the new location => case 1.
            log(f'updating {item.id}\'s holdings record to be {holdings.id}')
            item.data['holdingsRecordId'] = holdings.id
            break
    else:
        # No other existing holdings record has the new location => case 2.
        # FIXME create new holdings rec.
        new_location_id = item['permanentLocation']['id']
        new_location_name = item['permanentLocation']['name']
        fail(id, f'the parent instance {instance_id} has no holdings record'
             + f' with a permanent location of {new_location_name}.'
             + f' One will need to be created before item {item.id}\'s'
             + f' permanent location can be set there.')
        return False

    # If we get here, we have a case 1a or 1b. To figure out which, check if
    # there are any other items on the current holdings record.
    for other in folio.related_records(current_holdings.id, IdKind.HOLDINGS_ID, 'items'):
        if other.id != item.id:
            # The holdings rec has another item => case 1a. We're done.
            return True
    else:
        # We have case 1b and we need to delete the old holdings record.
        if config('DEMO_MODE', cast = bool):
            log(f'demo mode in effect – pretending to delete {current_holdings.id}')
            success = True
        else:
            back_up_record(current_holdings)
            success, error = folio.delete(current_holdings)
        context = 'moving its last or only item ({record.id}) to another holdings record'
        if success:
            succeed(current_holdings.id, f'deleted holdings record {current_holdings.id}',
                    context = context)
            return True
        else:
            fail(current_holdings.id, str(error), context = context)
            return False



Field = namedtuple('Field', 'type key delete_ok')

known_fields = {
    'Temporary location': Field(type = TypeKind.LOCATION,
                                key = 'temporaryLocationId',
                                delete_ok = [RecordKind.ITEM, RecordKind.HOLDINGS]),
    'Permanent location': Field(type = TypeKind.LOCATION,
                                key = 'permanentLocationId',
                                delete_ok = [RecordKind.ITEM]),
}
