'''
delete_tab.py: implementation of the "Delete records" tab

Copyright
---------

Copyright (c) 2021-2022 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.exceptions import Interrupted
from   commonpy.interrupt import reset_interrupts, interrupt
from   decouple import config
import json
from   pywebio.output import put_markdown, put_row, put_button, use_scope
from   pywebio.output import put_grid, clear
from   pywebio.output import put_processbar, set_processbar
from   pywebio.output import put_scope, clear_scope
from   pywebio.pin import pin, put_textarea
from   sidetrack import log

from   foliage.base_tab import FoliageTab
from   foliage.exceptions import FolioOpFailed
from   foliage.export import export_data
from   foliage.folio import Folio, RecordKind, IdKind, TypeKind, Record
from   foliage.folio import unique_identifiers, back_up_record
from   foliage.ui import confirm, user_file, stop_processbar
from   foliage.ui import tell_success, tell_warning, tell_failure
from   foliage.ui import note_error, PROGRESS_BOX, PROGRESS_TEXT


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
    log('generating delete tab contents')
    return [
        put_grid([[
            put_markdown('Input one or more item, holdings, or instance'
                         ' identifiers (in the form of id\'s, barcodes, hrid\'s,'
                         ' or accession numbers), or upload a file containing'
                         ' the identifiers. **Warning**: Deleting holdings'
                         ' **will delete all their items**, and deleting'
                         ' instances **will delete all their holdings _and_ items**.'),
            put_button('Upload', outline = True,
                       onclick = lambda: load_file()).style('text-align: right'),
        ]], cell_widths = 'auto 100px'),
        put_textarea('textbox_delete', rows = 4),
        put_row([
            put_button('Delete records', onclick = lambda: do_delete()),
            put_button('Clear', outline = True,
                       onclick = lambda: clear_tab()).style('text-align: right')
        ])
    ]


# Implementation of tab functionality.
# .............................................................................

def clear_tab():
    log('clearing tab')
    clear('output')
    pin.textbox_delete = ''


def load_file():
    log('user requesting file upload')
    if (file := user_file('Upload a file containing identifiers')):
        pin.textbox_delete = file


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


def succeeded(record_or_id, msg, why = ''):
    comment = (' (' + why + ')') if why else ''
    record_result(record_or_id, True, msg + comment)
    tell_success('Success: ' + msg + comment + '.')


def failed(record_or_id, msg, why = ''):
    comment = (' (' + why + ')') if why else ''
    record_result(record_or_id, False, msg + comment)
    id_ = record_or_id if isinstance(record_or_id, str) else record_or_id.id
    tell_failure(f'Failed to delete **{id_}**{comment}: ' + msg + '.')


def skipped(record_or_id, msg, why = ''):
    comment = (' (' + why + ')') if why else ''
    record_result(record_or_id, False, msg + comment)
    id_ = record_or_id if isinstance(record_or_id, str) else record_or_id.id
    tell_warning(f'Skipped **{id_}**{comment}: ' + msg + '.')


def flagged(record_or_id, msg, why = ''):
    comment = (' (' + why + ')') if why else ''
    id_ = record_or_id if isinstance(record_or_id, str) else record_or_id.id
    tell_warning(f'Note about **{id_}**{comment}: ' + msg + '.')


def do_delete():
    log('do_delete invoked')
    identifiers = unique_identifiers(pin.textbox_delete)
    if not identifiers:
        note_error('Please input at least one barcode or other type of id.')
        return
    if not confirm('Warning: if the deletions include holdings and/or instance'
                   ' records, all their associated items and holdings will'
                   ' also be deleted. Only do this if you have verified the'
                   ' implications first. Proceed?', danger = True):
        log('user declined to proceed')
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
            for id_ in identifiers:
                with use_scope('current_activity', clear = True):
                    put_markdown(f'_Looking up {id_} ..._').style(PROGRESS_TEXT)
                record = folio.record(id_)
                if not record:
                    failed(id_, f'unrecognized identifier **{id_}**')
                    continue
                done += 1
                set_processbar('bar', done/steps)
                if record.kind not in _HANDLERS.keys():
                    skipped(id_, f'deleting {record.kind} records is not supported')
                    continue
                with use_scope('current_activity', clear = True):
                    text = '_Deleting '
                    if record.kind is RecordKind.ITEM:
                        text += f'item {id_} ..._'
                    elif record.kind is RecordKind.HOLDINGS:
                        text += f'holdings {id_} and associated items ..._'
                    elif record.kind is RecordKind.INSTANCE:
                        text += f'instance {id_} and associated holdings and items ..._'
                    elif record.kind is RecordKind.USER:
                        text += f'user {id_} and associated holdings and items ..._'
                    put_markdown(text).style(PROGRESS_TEXT)
                _HANDLERS[record.kind](record)
                done += 1
                set_processbar('bar', done/steps)
            set_processbar('bar', 1)
            clear_scope('current_activity')
        except Interrupted:
            tell_warning('**Stopped**.')
            return
        except Exception as ex:         # noqa: PIE786
            import traceback
            log('Exception: ' + str(ex) + '\n' + traceback.format_exc())
            tell_failure('Error: ' + str(ex))
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
    why = f'for request to delete FOLIO instance record {instance.id}'
    folio = Folio()

    # Deletions must be done in two separate places: source storage (SRS), and
    # the regular instance/holdings/items storage APIs. Kyle Banerjee said in
    # personal communication of 2022-07-27 that SRS should be done first.

    def srs_response_converter(response):
        if not response or not response.text:
            log('no response received from FOLIO')
            return None
        if response.status_code == 404:
            # Assume this is a case of an instance lacking a Marc record.
            log('No SRS record found')
            return None
        return json.loads(response.text)

    srsget = f'/source-storage/records/{instance.id}/formatted?idType=INSTANCE'
    data_json = folio.request(srsget, converter = srs_response_converter)
    if not data_json:
        flagged(instance, ("FOLIO SRS lacks a corresponding record, therefore"
                           " only the instance record will be deleted"))
    elif 'matchedId' not in data_json:
        failed(instance, 'unexpected data from FOLIO SRS – please report this')
        return
    else:
        srs_id = data_json["matchedId"]
        if config('DEMO_MODE', cast = bool):
            log(f'demo mode in effect – pretending to delete {srs_id} from SRS')
        else:
            try:
                log(f'deleting {instance.id} from SRS, where its id is {srs_id}')
                srsdel = f'/source-storage/records/{srs_id}'
                folio.request(srsdel, op = 'delete')
            except FolioOpFailed as ex:
                failed(instance, str(ex), why)
                return False
        succeeded(instance, f'removed SRS instance record **{srs_id}**', why)

    # Deletions on instances are not recursive regardless of which API you use.
    # You have to manually remove items, then holdings, then instances.
    # The following is based on Kyle Banerjee's script dated 2021-11-11 at
    # https://github.com/FOLIO-FSE/shell-utilities/blob/master/instance-delete.

    # Start by using delete_holdings(), which will delete items too.
    folio = Folio()
    for holdings in folio.related_records(instance.id, IdKind.INSTANCE_ID,
                                          RecordKind.HOLDINGS):
        if not delete_holdings(holdings, for_id = instance.id):
            failed(instance, 'unable to delete all holdings records')
            return False

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
        _location_map = {x.data['id']: x.data['name']
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
    export_data(values, file_name, sort = False)


_HANDLERS = {
    RecordKind.ITEM     : delete,       # The generic function suffices.
    RecordKind.HOLDINGS : delete_holdings,
    RecordKind.INSTANCE : delete_instance,
    RecordKind.USER     : delete_user,
}
