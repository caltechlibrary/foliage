'''
change_tab.py: implementation of the "Change records" tab

Copyright
---------

Copyright (c) 2021-2022 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   collections import namedtuple
from   commonpy.data_utils import pluralized
from   commonpy.exceptions import Interrupted
from   commonpy.interrupt import wait, reset_interrupts, interrupt
from   decouple import config
from   pywebio.output import put_text, put_markdown, put_row
from   pywebio.output import popup, close_popup, put_buttons, put_button
from   pywebio.output import use_scope, clear, put_grid, put_scope, clear_scope
from   pywebio.output import put_processbar, set_processbar
from   pywebio.pin import pin, put_textarea, put_radio, put_select
from   pywebio.session import eval_js
from   sidetrack import log
import sys
import threading

from   foliage.base_tab import FoliageTab
from   foliage.exceptions import FolioOpFailed
from   foliage.export import export_data
from   foliage.folio import Folio, RecordKind, IdKind, TypeKind, Record
from   foliage.folio import unique_identifiers, back_up_record
from   foliage.ui import confirm, notify, user_file, note_error
from   foliage.ui import PROGRESS_BOX, PROGRESS_TEXT
from   foliage.ui import tell_success, tell_warning, tell_failure, stop_processbar


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
    log('generating change tab contents')
    # FIXME what causes these diffs on windows?
    textarea_rows = 14 if sys.platform.startswith('win') else 13
    margin_adjust = 'margin-top: -1.1em' if sys.platform.startswith('win') else ''
    return [
        put_grid([[
            put_markdown('Input item and/or holdings identifiers'
                         ' (i.e., barcodes, id\'s, or hrid\'s). All'
                         ' records will be changed the same way. Changing a'
                         ' holdings record will also change all its items.'),
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
                           options = [('Add value', 'add', True),
                                      ('Change value', 'change'),
                                      ('Delete value', 'delete')]
                           ).style(f'margin-bottom: 0.3em; {margin_adjust}')],
                [put_text('Current field value (records must match this):'
                          ).style('opacity: 0.3')],
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
            put_button('Change records', onclick = lambda: do_change()),
            put_button('Clear', outline = True,
                       onclick = lambda: clear_tab()).style('text-align: right'),
        ])
    ]


# Implementation of tab functionality.
# .............................................................................

# This next bit is an egregious and unobvious hack.  Here's the deal.  When
# the user selects different options using the radio buttons for the
# operation type (add value, change value, delete value), we want different
# buttons and fields to look visually "unavailable" as a clue to the user
# that they don't have to fill in those values.  However, PyWebIO doesn't
# provide a way to control the properties of the elements dynamically: there's
# PyWebIO API for changing a CSS attribute at run-time.
#
# One *can* do it using JavaScript using well-known methods, and PyWebIO
# *does* provide a function (eval_js) to execute JavaScript at run-time in
# the web page.  But, here we face a new challenge: how do do you refer to
# the things on the page whose CSS attributes you want to change?
#
# For some of the elements, it's possible to target them by searching for the
# element content.  That's the case for the text fields, where we can use a
# jQuery selector such as
#    $("p.contains('Current field value')")
# to get at the element, and from there, to change the CSS.  This is used in
# the code below for elements for which it's possible to do that.  But you
# can't do that for buttons -- you need to find another way to refer to them.
# Frustratingly, PyWebIO doesn't provide a way to put id attributes on
# elements; if you could do that, it would make it easy to target exactly the
# elements you need to change.  You also can't target CSS classes, because
# that would end up catching other elements with the same class on the page.
#
# So to get the other elements (the ones that can't be found using the jQuery
# "contains" operator mentioned above), I ended up using an insane hack:
#
#  1. Add distinguishing features to specific elements using one of the few
#     CSS/HTML controls that PyWebIO does provide, namely the style()
#     function, to add a property that we can uniquely find in the DOM at run
#     time.  I'm using the z-index, setting it specific numbers (8 and 9) in
#     tab_contents() above.  The z-index is not used for anything else on
#     this page so it's irrelevant as far as layout is concerned.
#
#  2. Invoke some JavaScript code in the web page that uses jQuery to look
#     for the elements that have the specific z-index values.  That's how the
#     specific elements are found.  Then it's easy to change the value of
#     desired CSS properties on those elements.
#
# Why use the numbers 8 and 9?  In case a future change ends up using a z-index
# value for something.  I hypothesized that a future developer who used z-index
# for a real purpose would use a value like 1, 2, or maybe 100, 1000, etc.
# The values 8 and 9 seemed off-beat enough that they wouldn't clash with
# something in the future, even if a future developer doesn't read this comment
# explaining what's going on.

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
    log('clearing tab')
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
    value_list = sorted(item.data['name'] for item in type_list)
    if (val := selected(f'Select the {old_new} value for {fname}', value_list)):
        field = old_new + '_value'
        setattr(pin, field, val)
        log(f'user selected {old_new} field value {val}')


def selected(title, values):
    log('showing list selection popup')
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
    log('user requesting file upload')
    if (contents := user_file('Upload a file containing identifiers')):
        pin.textbox_ids = contents


def stop():
    log('stopping')
    interrupt()
    stop_processbar()


_results = []


def clear_results():
    global _results
    _results = []


def record_result(record_or_id, success, notes):
    global _results
    id_ = record_or_id if isinstance(record_or_id, str) else record_or_id.id
    rec = record_or_id if isinstance(record_or_id, Record) else None
    _results.append({'id': id_, 'success': success, 'notes': notes, 'record': rec})


def succeeded(record_or_id, msg, context = ''):
    comment = (' (' + context + ')') if context else ''
    record_result(record_or_id, True, msg + comment)
    id_ = record_or_id if isinstance(record_or_id, str) else record_or_id.id
    tell_success(f'Success for **{id_}**{comment}: ' + msg + '.')


def failed(record_or_id, msg, context = ''):
    comment = (' (' + context + ')') if context else ''
    record_result(record_or_id, False, msg + comment)
    id_ = record_or_id if isinstance(record_or_id, str) else record_or_id.id
    tell_failure(f'Failure for **{id_}**{comment}: ' + msg + '.')


def skipped(record_or_id, msg, context = ''):
    comment = (' (' + context + ')') if context else ''
    record_result(record_or_id, False, msg + comment)
    id_ = record_or_id if isinstance(record_or_id, str) else record_or_id.id
    tell_warning(f'Skipped **{id_}**{comment}: ' + msg + '.')


_SUPPORTED_KINDS = [
    RecordKind.ITEM,
    RecordKind.HOLDINGS,
]


def do_change():
    log('do_change invoked')
    identifiers = unique_identifiers(pin.textbox_ids)
    if not identifiers:
        note_error('Please input at least one barcode or other type of id.')
        return
    if not all_selections_made():
        note_error('Missing selections – cannot proceed until form is filled out.')
        return
    if not confirm('Proceed with changes to records in FOLIO?', danger = True):
        log('user declined to proceed')
        return
    clear_results()
    reset_interrupts()
    steps = 2*len(identifiers)         # We need 2 passes => 2x number of items
    folio = Folio()
    with use_scope('output', clear = True):
        try:
            done = 0                    # noqa: SIM113
            put_grid([[
                put_scope('current_activity', [
                    put_markdown('_Gathering records ..._').style(PROGRESS_TEXT)]),
            ], [
                put_processbar('bar', init = done/steps).style('margin-top: 11px'),
                put_button('Stop', outline = True, color = 'danger',
                           onclick = lambda: stop()).style('text-align: right')
            ]], cell_widths = '85% 15%').style(PROGRESS_BOX)

            # Start by gathering all records & their types.
            records = []
            for id_ in identifiers:
                record = folio.record(id_)
                done += 1
                set_processbar('bar', done/steps)
                if not record:
                    failed(id_, f'unrecognized identifier **{id_}**')
                    continue
                if record.kind not in _SUPPORTED_KINDS:
                    skipped(id_, f'changing {record.kind} records is not supported')
                    continue
                records.append(record)

            # 1st pass: apply changes to holdings records in the input (if any).
            with use_scope('current_activity', clear = True):
                put_markdown('_Changing records ..._').style(PROGRESS_TEXT)
            holdings_done = []
            for record in filter(lambda r: r.kind is RecordKind.HOLDINGS, records):
                done += 1
                set_processbar('bar', done/steps)
                if not change_holdings(record):
                    log('couldn\'t change and/or save holdings rec. – skipping items')
                    continue
                for item in folio.related_records(record.id, IdKind.HOLDINGS_ID,
                                                  RecordKind.ITEM):
                    log(f'changing item {item.id} after changing holdings {record.id}')
                    context = f'an item associated with holdings record {record.id}'
                    # We changed the holdings rec. => we can change item directly.
                    change_item(item, record, context = context)
                holdings_done.append(record.id)

            # 2nd pass: apply changes to item records in the input. Some may
            # have been changed in 1st pass if the user provided holdings recs.
            for item in filter(lambda r: r.kind is RecordKind.ITEM, records):
                if item.data['holdingsRecordId'] in holdings_done:
                    log(f'skipping {item.id}, assuming it was done in holdings pass')
                change_item(item)
                done += 1
                set_processbar('bar', done/steps)
            set_processbar('bar', 1)
        except Interrupted:
            tell_warning('**Stopped**.')
            return
        except Exception as ex:         # noqa: PIE786
            import traceback
            log('Exception info: ' + str(ex) + '\n' + traceback.format_exc())
            tell_failure('Error: ' + str(ex))
            return
        finally:
            stop_processbar()
            clear_scope('current_activity')

        what = pluralized('record', identifiers, True)
        put_grid([[
            put_markdown(f'Finished changing {what}.').style('margin-top: 6px'),
            put_button('Export summary', outline = True,
                       onclick = lambda: do_export('foliage-changes.csv'),
                       ).style('text-align: right')
        ]]).style('margin: auto 17px auto 17px')


def change_holdings(record):
    if pin.chg_field == 'Permanent location' and pin.chg_op != 'change':
        # Holdings always have a perm loc., so can only change it.
        skipped(record.id, 'Cannot add or delete a permanent'
                ' location field on holdings records')
        return False
    return change_record(record) and save_changes(record)


def change_item(item, given_hrec = None, context = ''):
    '''Change the item and also update its parent holdings.'''

    # Try to change the item but without saving it yet. If we fail, bail.
    if not change_record(item, context):
        return False
    else:
        save_changes(item)

    # If the change is to a temporary location field or loan type, we can
    # make the change without having to change a holdings record.
    if pin.chg_field in ['Temporary location', 'Loan type']:
        return True

    # Not a temporary location change. Were we given the holdings record in the
    # input too? Then we should have done the change already.
    field_key = known_fields[pin.chg_field].key
    if given_hrec:
        if item.data[field_key] == given_hrec.data[field_key]:
            return True
        else:
            # This should not happen b/c the caller should have set its loc.
            failed(item.id, 'inconsistency in Foliage -- please report this.')
            return False

    # No holdings record has been changed so far. Here are the possible cases:
    # 1. Moving item from one holdings to another holdings on the instance.
    #    1a) Original holdings has other items => no deletion needed. Done.
    #    1b) Original holdings is empty => delete original holdings record.
    #
    # 2. Moving item to a location that has no holdings record on the instance
    #    2a) The instance has only one item => change the existing holdings rec.
    #    2b) The instance has other items => create new holdings record.
    location_id = item.data['permanentLocationId']
    folio = Folio()
    hrec = folio.record(item.data['holdingsRecordId'])
    if not hrec:
        # This should never happen, but we always want to check everything.
        failed(item.id, f'cannot update {field_key} of {item.id} because its holdings'
               f' record {item.data["holdingsRecordId"]} could not be retrieved')
        return False

    # In practice, the only way we get to this point is if the operation is not
    # a deletion -- so either an add or a change.
    inst_id = hrec.data['instanceId']
    all_hrecs = folio.related_records(inst_id, IdKind.INSTANCE_ID, RecordKind.HOLDINGS)
    hrec_items = None
    log(f'parent instance {inst_id} has {len(all_hrecs)} holdings records')
    for h in all_hrecs:
        log(f'checking location of holdings record {h.id}')
        if item.data[field_key] == h.data[field_key]:
            # Found a holdings record that has the new location => case 1.
            log(f'updating {item.id}\'s holdings record to be {h.id}')
            item.data['holdingsRecordId'] = h.id
            if config('DEMO_MODE', cast = bool):
                log(f'demo mode – pretending to save {item.id}')
            else:
                try:
                    folio.update_record(item)
                except FolioOpFailed as ex:
                    failed(item.id, str(ex), context)
                    return False
            context = 'updating item\'s holdings record pointer'
            succeeded(item.id, f'changed holdings record to be {h.id}', context)
            break
    else:
        log('none of the holdings record have the new location')
        # We have case 2. Next check: does the instance have any other items?
        if len(all_hrecs) == 1:
            hrec_items = folio.related_records(hrec.id, IdKind.HOLDINGS_ID, RecordKind.ITEM)
            if len(hrec_items) == 1:
                context = f'holdings record for {item.id}'
                # Case 2a: the instance has only 1 item.
                if change_holdings(hrec):
                    succeeded(hrec.id, f'field _{field_key}_ changed', context)
                    return True
                else:
                    failed(item.id, 'failed to change holdings record')
                    return False

        # Case 2b: the instance has other items. We must create a new holdings
        # record. Do it by copying the existing one & modifying it.
        log(f'need to create new holdings record for moving {item.id}')
        import copy
        new_holdings = copy.deepcopy(hrec)
        # These next fields are assigned automatically the Folio server.
        del new_holdings.data['id']
        del new_holdings.data['hrid']
        del new_holdings.data['metadata']
        # Update fields for the move.
        new_holdings.data['permanentLocationId'] = location_id
        # Create the record.
        context = f'moving item to new holdings record for location {location_id}'
        if config('DEMO_MODE', cast = bool):
            log('demo mode – pretending to create new holdings record')
            new_id = '[holdings id]'
        else:
            try:
                new_id = folio.new_record(new_holdings)
            except FolioOpFailed as ex:
                failed(item.id, str(ex), context = context)
                return False
        succeeded(item.id, f'created holdings record {new_id}', context)

        log(f'changing location of {item.id} to new holdings record {new_id}')
        item.data['holdingsRecordId'] = new_id
        if config('DEMO_MODE', cast = bool):
            log(f'demo mode – pretending to save {item.id}')
        else:
            try:
                back_up_record(item)
                folio.update_record(item)
            except FolioOpFailed as ex:
                failed(item.id, str(ex), context)
                return False
        succeeded(item.id, f'attached item to holdings record {new_id}', context)

    # We've moved the item. Do we need to delete the holdings record it came
    # from? Check if there are any other items on it.
    if hrec_items is None:
        hrec_items = folio.related_records(hrec.id, IdKind.HOLDINGS_ID, RecordKind.ITEM)
    for other in filter(lambda record: record.id != item.id, hrec_items):
        if other.id != item.id:
            log('holdings record has other items, therefore not deleting it')
            return True

    # It's 1b (orig holdings rec is now empty). Need delete the holdings rec.
    id_ = hrec.id
    context = 'moved last or only item to another holdings record'
    if config('DEMO_MODE', cast = bool):
        log(f'demo mode – pretending to delete {id_}')
    else:
        try:
            back_up_record(hrec)
            folio.delete_record(hrec)
        except FolioOpFailed as ex:
            failed(id_, str(ex), context = context)
            return False
    succeeded(item.id, f'deleted empty holdings record {id_}', context)
    return True


def change_record(record, context = ''):
    '''Adds, changes, or deletes a field value in the record.
    The change is determined by the current UI selections (via the "pins").
    Returns True if successful, False if couldn't make the change.
    Does not save the record; a save is assumed to be performed by the caller.
    '''
    folio = Folio()
    # Get the list of known values for this type (folio.py will have cached
    # it) and create a mapping of value names to value objects.
    value_type = known_fields[pin.chg_field].type
    values = {x.data['name']: x.data for x in folio.types(value_type)}

    field_key = known_fields[pin.chg_field].key
    if (current_value := record.data.get(field_key, None)):
        if pin.chg_op == 'add':
            skipped(record.id, f'item _{field_key}_ has an existing value', context)
            return False
        # We're doing change or delete. Existing value must match expected one.
        if current_value != values[pin.old_value]['id']:
            skipped(record.id, f'_{field_key}_ value is not "{pin.old_value}"', context)
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
                skipped(record.id, f'not allowed to delete field {field_key}'
                        ' on {record.kind} records', context)
                return False
    elif pin.chg_op == 'add':
        log(f'adding {field_key} value "{pin.new_value}" to item {record.id}')
        back_up_record(record)
        record.data[field_key] = values[pin.new_value]['id']
    else:
        # It doesn't have a value, and we're not doing an add.
        skipped(record.id, f'item **{record.id}** has no field _{field_key}_', context)
        return False
    log(f'changes made to {record.kind} record {record.id}')
    return True


def save_changes(record, context = ''):
    if config('DEMO_MODE', cast = bool):
        log(f'demo mode – pretending to save {record.id}')
    else:
        try:
            folio = Folio()
            folio.update_record(record)
        except FolioOpFailed as ex:
            failed(record.id, str(ex), context)
            return False

    # Report the outcome to the user.
    field = 'field _' + known_fields[pin.chg_field].key + '_'
    text = {'add': 'added to', 'change': 'changed in', 'delete': 'deleted from'}
    action = text[pin.chg_op]
    succeeded(record.id, f'{field} {action} {record.kind} record', context)
    return True


def do_export(file_name):
    global _results
    values = []
    # WIP need to add more fields, but that requires more changes.
    for result in _results:
        entry = {'Record ID'          : result['id'],
                 'Operation success'  : result['success'],
                 'Notes'              : result['notes']}
        values.append(entry)
    export_data(values, file_name)


Field = namedtuple('Field', 'type key delete_ok')

known_fields = {
    'Temporary location': Field(type = TypeKind.LOCATION,
                                key = 'temporaryLocationId',
                                delete_ok = [RecordKind.ITEM, RecordKind.HOLDINGS]),
    'Permanent location': Field(type = TypeKind.LOCATION,
                                key = 'permanentLocationId',
                                delete_ok = [RecordKind.ITEM]),
    'Loan type': Field(type = TypeKind.LOAN,
                       key = 'permanentLoanTypeId',
                       delete_ok = []),
}
