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
from   pywebio.output import put_column, put_scope, clear_scope, put_loading
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
from   pywebio.pin import put_textarea, put_radio, put_checkbox, put_select
from   sidetrack import set_debug, log

from   foliage.base_tab import FoliageTab
from   foliage.exceptions import *
from   foliage.export import export_data
from   foliage.folio import Folio, RecordKind, IdKind, TypeKind, Record
from   foliage.folio import unique_identifiers, back_up_record
from   foliage.ui import confirm, notify, user_file, stop_processbar
from   foliage.ui import tell_success, tell_warning, tell_failure
from   foliage.ui import note_info, note_warn, note_error
from   foliage.ui import PROGRESS_BOX, PROGRESS_TEXT


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
            put_markdown('Input one or more item, holdings, or instance'
                         + ' identifiers (in the form of id\'s, barcodes, hrid\'s,'
                         + ' or accession numbers), or upload a file containing'
                         + ' the identifiers. **Warning**: Deleting holdings'
                         + ' **will delete all their items**, and deleting'
                         + ' instances **will delete all their holdings _and_ items**.'),
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
    log(f'do_delete invoked')
    identifiers = unique_identifiers(pin.textbox_delete)
    if not identifiers:
        note_error('Please input at least one barcode or other type of id.')
        return
    if not confirm('Warning: if the deletions include holdings and/or instance'
                   ' records, all their associated items and holdings will'
                   ' also be deleted. Only do this if you have verified the'
                   ' implications first. Proceed?', danger = True):
        log(f'user declined to proceed')
        return
    clear_results()
    reset_interrupts()
    steps = 2*len(identifiers)       # Count getting records, for more action.
    folio = Folio()
    with use_scope('output', clear = True):
        put_grid([[
            put_scope('current_activity', [
                put_markdown('_Getting records ..._').style(PROGRESS_TEXT)]),
        ], [
            put_processbar('bar', init = 0/steps).style('margin-top: 11px'),
            put_button('Stop', outline = True, color = 'danger',
                       onclick = lambda: stop()).style('text-align: right')
        ]], cell_widths = '85% 15%').style(PROGRESS_BOX)
        try:
            done = 0
            for id in identifiers:
                with use_scope('current_activity', clear = True):
                    put_markdown(f'_Looking up {id} ..._').style(PROGRESS_TEXT)
                record = folio.record(id)
                if not record:
                    failed(id, f'unrecognized identifier **{id}**')
                    continue
                done += 1
                set_processbar('bar', done/steps)
                if record.kind not in _HANDLERS.keys():
                    skipped(id, f'deleting {record.kind} records is not supported')
                    continue
                with use_scope('current_activity', clear = True):
                    text = '_Deleting '
                    if record.kind is RecordKind.ITEM:
                        text += f'item {id} ..._'
                    elif record.kind is RecordKind.HOLDINGS:
                        text += f'holdings {id} and associated items ..._'
                    elif record.kind is RecordKind.INSTANCE:
                        text += f'instance {id} and associated holdings and items ..._'
                    elif record.kind is RecordKind.USER:
                        text += f'user {id} and associated holdings and items ..._'
                    put_markdown(text).style(PROGRESS_TEXT)
                _HANDLERS[record.kind](record)
                done += 1
                set_processbar('bar', done/steps)
            set_processbar('bar', 1)
            clear_scope('current_activity')
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

        put_grid([[
            put_markdown('Finished deletions.').style('margin-top: 6px'),
            put_button('Export summary', outline = True,
                       onclick = lambda: do_export('foliage-deletions.csv'),
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
            failed(record, str(ex), why)
            return False
    succeeded(record, f'deleted {record.kind} record **{record.id}**', why)
    return True


def delete_holdings(holdings, for_id = None):
    '''Delete the given holdings record and all its items.'''
    # Deletions on holdings are not recursive. The items have to be deleted 1st
    # and FOLIO will give a 400 error if you try to delete a holdings record
    # while there's still an item somewhere pointing to it.
    why = 'deleting item attached to holdings record {holdings.id}'
    folio = Folio()
    # Start at the bottom: delete its items 1st.
    for item in folio.related_records(holdings.id, IdKind.HOLDINGS_ID, RecordKind.ITEM):
        if not delete(item, for_id = holdings.id):
            failed(holdings, f'unable to delete item {item.id} – stopping')
            return False
    # If we get this far, delete the holdings record.
    return delete(holdings, for_id)


def delete_instance(instance, for_id = None):
    '''Delete the given instance record.'''
    # Deletions on instances are not recursive regardless of which API you use.
    # The following is based on Kyle Banerjee's script dated 2021-11-11 at
    # https://github.com/FOLIO-FSE/shell-utilities/blob/master/instance-delete
    # but whereas that script uses the instance-storage API endpoint, this uses
    # the inventory API. (I'm told the latter will simply forward the request
    # to the instance storage API, but I decided to use the inventory API in
    # case it does more in the future.) Note that this also uses the source
    # storage API, which is a 3rd API besides the inventory API and storage
    # API used elsewhere in Foliage. (That part comes from Banerjee's script.)

    # Start by using delete_holdings(), which will delete items too.
    why = 'deleting all records attached to instance record {instance.id}'
    folio = Folio()
    for holdings in folio.related_records(instance.id, IdKind.INSTANCE_ID,
                                          RecordKind.HOLDINGS):
        if not delete_holdings(holdings, for_id = instance.id):
            failed(instance, f'unable to delete all holdings records')
            return False

    # Next, get the matched id from source storage & delete the instance there.
    def response_converter(response):
        if not response or not response.text:
            log('no response received from FOLIO')
            return None
        return json.loads(response.text)

    folio = Folio()
    srsget = f'/source-storage/records/{instance.id}/formatted?idType=INSTANCE'
    data_json = folio.request(srsget, converter = response_converter)
    if not data_json:
        failed(instance, 'unable to retrieve instance data from FOLIO SRS')
        return
    elif 'matchedId' not in data_json:
        failed(instance, 'unexpected data from FOLIO SRS – please report this')
        return
    srs_id = data_json["matchedId"]
    log(f'SRS id for {instance.id} is {srs_id}')
    srsdel = f'/source-storage/records/{srs_id}'
    folio.request(srsdel)

    # If we didn't get an exception, finally delete the instance from inventory.
    return delete(instance, for_id)


def delete_user(record, for_id = None):
    '''Delete the given user record.'''
    failed(record, 'user records cannot be deleted at this time')


_location_map = None

def init_location_map():
    global _location_map
    if _location_map is None:
        folio = Folio()
        _location_map = {x.data['id']:x.data['name']
                         for x in folio.types(TypeKind.LOCATION)}


def location(location_data):
    global _location_map
    if isinstance(location_data, dict):
        if 'name' in location_data:
            return f'{location_data["name"]} ({location_data["id"]})'
        else:
            return location_data["id"]
    elif location_data and location_data in _location_map:
        return f'{_location_map[location_data]} ({location_data})'
    return '(unknown location)'


def do_export(file_name):
    global _results
    init_location_map()
    # Output fields requested
    #   id
    #   success
    #   notes
    #   record hrid
    #   record barcode (if present)
    #   record location
    #   record title
    #   record publication year
    #   record publisher

    # People want to see titles, dates, locations. We need to do lookups to
    # get them.
    values = []
    folio = Folio()
    for result in _results:
        entry = {'Record ID'          : result['id'],
                 'Operation success'  : result['success'],
                 'Notes'              : result['notes'],
                 'Effective location' : '',
                 'Permanent location' : ''}
        if result['record']:
            rec = result['record']
            if rec.kind == RecordKind.ITEM:
                entry['Permanent location'] = location(rec.data['permanentLocationId'])
                if 'effectiveLocationId' in rec.data:
                    entry['Effective location'] = location(rec.data['effectiveLocationId'])
        values.append(entry)
    export_data(values, file_name)


_HANDLERS = {
    RecordKind.ITEM     : delete,       # The generic function suffices.
    RecordKind.HOLDINGS : delete_holdings,
    RecordKind.INSTANCE : delete_instance,
    RecordKind.USER     : delete_user,
}
