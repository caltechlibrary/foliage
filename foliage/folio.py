'''
folio.py: functions for interacting with FOLIO over the network API

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.data_utils import unique, pluralized, flattened
from   commonpy.exceptions import NoContent, ServiceFailure, RateLimitExceeded
from   commonpy.exceptions import Interrupted
from   commonpy.file_utils import writable
from   commonpy.interrupt import wait, interrupted, raise_for_interrupts
from   commonpy.string_utils import antiformat
from   commonpy.network_utils import net
from   dataclasses import dataclass
from   datetime import datetime as dt
from   dateutil import tz
from   decouple import config
from   enum import Enum, EnumMeta
from   functools import partial
from   fastnumbers import isint
import json
import os
from   os.path import exists, dirname, join
import re
from   sidetrack import set_debug, log
from   validators.url import url as valid_url

from   foliage.enum_utils import MetaEnum, ExtendedEnum
from   foliage.exceptions import FolioError


# Internal constants.
# .............................................................................

# Number of times we retry an api call that return an HTTP error.
_MAX_RETRY = 3

# Time between retries, multiplied by retry number.
_RETRY_TIME_FACTOR = 2


# Public data types.
# .............................................................................

class RecordKind(ExtendedEnum):
    UNKNOWN  = 'unknown'
    ITEM     = 'item'
    INSTANCE = 'instance'
    HOLDINGS = 'holdings'
    LOAN     = 'loan'
    USER     = 'user'
    TYPE     = 'type'

    @staticmethod
    def name_key(kind):
        mapping = {
            RecordKind.ITEM     : 'title',
            RecordKind.INSTANCE : 'title',
            RecordKind.HOLDINGS : 'id',
            RecordKind.LOAN     : 'id',
            RecordKind.USER     : 'username',
        }
        return mapping[kind] if kind in mapping else 'name'


    @staticmethod
    def storage_endpoint(kind):
        mapping = {
            RecordKind.ITEM     : '/item-storage/items',
            RecordKind.INSTANCE : '/instance-storage/instances',
            RecordKind.HOLDINGS : '/holdings-storage/holdings',
            RecordKind.LOAN     : '/loan-storage/loans',
            RecordKind.USER     : '/users',
        }
        return mapping[kind] if kind in mapping else None


    @staticmethod
    def deletion_endpoint(kind):
        mapping = {
            RecordKind.ITEM     : '/inventory/items',
            RecordKind.INSTANCE : '/inventory/instances',
            RecordKind.HOLDINGS : '/holdings-storage/holdings',
            RecordKind.LOAN     : '/loan-storage/loans',
            RecordKind.USER     : '/users',
        }
        return mapping[kind] if kind in mapping else None


class IdKind(ExtendedEnum):
    UNKNOWN       = 'unknown'
    ITEM_BARCODE  = 'item barcode'
    ITEM_ID       = 'item id'
    ITEM_HRID     = 'item hrid'
    INSTANCE_ID   = 'instance id'
    INSTANCE_HRID = 'instance hrid'
    ACCESSION     = 'accession number'
    HOLDINGS_ID   = 'holdings id'
    HOLDINGS_HRID = 'holdings hrid'
    USER_ID       = 'user id'
    USER_BARCODE  = 'user barcode'
    LOAN_ID       = 'loan id'
    TYPE_ID       = 'type id'

    @staticmethod
    def to_record_kind(id_kind):
        mapping = {
            IdKind.UNKNOWN       : RecordKind.UNKNOWN,
            IdKind.ITEM_BARCODE  : RecordKind.ITEM,
            IdKind.ITEM_ID       : RecordKind.ITEM,
            IdKind.ITEM_HRID     : RecordKind.ITEM,
            IdKind.INSTANCE_ID   : RecordKind.INSTANCE,
            IdKind.INSTANCE_HRID : RecordKind.INSTANCE,
            IdKind.ACCESSION     : RecordKind.INSTANCE,
            IdKind.HOLDINGS_ID   : RecordKind.HOLDINGS,
            IdKind.HOLDINGS_HRID : RecordKind.HOLDINGS,
            IdKind.USER_ID       : RecordKind.USER,
            IdKind.USER_BARCODE  : RecordKind.USER,
            IdKind.LOAN_ID       : RecordKind.LOAN,
            IdKind.TYPE_ID       : RecordKind.TYPE,
        }
        return mapping[id_kind] if id_kind in mapping else RecordKind.UNKNOWN


class TypeKind(ExtendedEnum):
    ACQUISITION_UNIT     = 'acquisitions-units/units'
    ADDRESS              = 'addresstypes'
    ALT_TITLE            = 'alternative-title-types'
    CALL_NUMBER          = 'call-number-types'
    CLASSIFICATION       = 'classification-types'
    CONTRIBUTOR          = 'contributor-types'
    CONTRIBUTOR_NAME     = 'contributor-name-types'
    DEPARTMENT           = 'departments'
    EXPENSE_CLASS        = 'finance/expense-classes'
    FIXED_DUE_DATE_SCHED = 'fixed-due-date-schedule-storage/fixed-due-date-schedules'
    GROUP                = 'groups'
    HOLDINGS             = 'holdings-types'
    HOLDINGS_NOTE        = 'holdings-note-types'
    HOLDINGS_SOURCE      = 'holdings-sources'
    ID                   = 'identifier-types'
    ILL_POLICY           = 'ill-policies'
    INSTANCE             = 'instance-types'
    INSTANCE_FORMAT      = 'instance-formats'
    INSTANCE_NOTE        = 'instance-note-types'
    INSTANCE_REL         = 'instance-relationship-types'
    INSTANCE_STATUS      = 'instance-statuses'
    ITEM_NOTE            = 'item-note-types'
    ITEM_DAMAGED_STATUS  = 'item-damaged-statuses'
    LOAN                 = 'loan-types'
    LOAN_POLICY          = 'loan-policy-storage/loan-policies'
    LOCATION             = 'locations'
    MATERIAL             = 'material-types'
    MODE_OF_ISSUANCE     = 'mode-of-issuance'
    NATURE_OF_CONTENT    = 'nature-of-content-terms'
    ORDER_LINE           = 'orders/order-lines'
    ORGANIZATION         = 'organizations/organizations'
    PROXYFOR             = 'proxiesfor'
    SERVICE_POINT        = 'service-points'
    SHELF_LOCATION       = 'shelf-locations'
    STATISTICAL_CODE     = 'statistical-code-types'

    @staticmethod
    def name_key(kind):
        if kind == TypeKind.ADDRESS:
            return 'addressType'
        elif kind == TypeKind.GROUP:
            return 'group'
        else:
            return 'name'


# Class used by Foliage to store FOLIO records --------------------------------

@dataclass
class Record():
    '''Data class for storing a single FOLIO record.'''
    id   : str                          # The UUID.
    kind : RecordKind                   # The kind of record it is.
    data : dict                         # The JSON data from FOLIO.


# Public class definitions.
# .............................................................................

class Folio():
    '''Interface to a FOLIO server using Okapi.'''

    _type_list_cache = {}
    _kind_cache = {}

    def __new__(cls, *args, **kwds):
        '''Construct object instance as a singleton.'''

        # This implements a Singleton pattern by storing the object we create
        # and returning the same one if the class constructor is called again.
        existing_instance = cls.__dict__.get("__folio_instance__")
        if existing_instance is not None:
            log(f'Using previously-created FOLIO object {str(cls)}')
            return existing_instance

        cls.__folio_instance__ = existing_instance = object.__new__(cls)
        return existing_instance


    @staticmethod
    def new_token(url, tenant_id, user, password):
        '''Ask FOLIO to create a token for the given url, tenant & user.'''
        if not all([url, tenant_id, user, password]):
            log(f'given incomplete set of parameters -- can\'t proceed.')
            return None, 'Incomplete parameters for credentials'
        try:
            log(f'asking FOLIO for new API token')
            headers = {
                'x-okapi-tenant': tenant_id,
                'content-type': 'application/json',
            }
            data = json.dumps({
                'tenant': tenant_id,
                'username': user,
                'password': password
            })
            request_url = url + '/authn/login'
            (resp, error) = net('post', request_url, headers = headers, data = data)
            if resp.status_code == 201:
                token = resp.headers['x-okapi-token']
                log(f'got new token from FOLIO: {token}')
                return token, None
            elif resp.status_code == 422:
                return None, 'FOLIO rejected the information given'
            elif isinstance(error, Interrupted):
                raise_for_interrupts()
            elif error:
                return None, 'FOLIO returned an error: ' + str(error)
            else:
                return None, f'FOLIO returned unknown code {str(resp.status_code)}'
        except Interrupted as ex:
            log(f'interrupted')
            return None, 'Operation was interrupted before a new token was obtained'
        except Exception as ex:
            log('exception trying to get new FOLIO token: ' + str(ex))
            return None, 'Encountered error trying to get token – please report this'


    @staticmethod
    def credentials_valid():
        url       = config('FOLIO_OKAPI_URL', default = None)
        tenant_id = config('FOLIO_OKAPI_TENANT_ID', default = None)
        token     = config('FOLIO_OKAPI_TOKEN', default = None)
        if not all([url, tenant_id, token]):
            log(f'credentials are incomplete; cannot validate credentials')
            return False
        if not valid_url(url):
            log(f'FOLIO_OKAPI_URL value is not a valid URL')
            return False
        try:
            log(f'testing if FOLIO credentials appear valid')
            headers = {
                "x-okapi-token": token,
                "x-okapi-tenant": tenant_id,
                "content-type": "application/json",
            }
            request_url = url + '/instance-statuses?limit=0'
            (resp, _) = net('get', request_url, headers = headers)
            return (resp and resp.status_code < 400)
        except Exception as ex:
            log(f'FOLIO credentials test failed with ' + str(ex))
            return False


    def _folio(self, op, endpoint, convert = None, retry = 0):
        '''Invoke 'op' on 'endpoint', call 'convert' on it, return result.'''

        headers = {
            "x-okapi-token":  config('FOLIO_OKAPI_TOKEN'),
            "x-okapi-tenant": config('FOLIO_OKAPI_TENANT_ID'),
            "content-type":   "application/json",
        }

        request_url = config('FOLIO_OKAPI_URL') + endpoint
        (response, error) = net(op, request_url, headers = headers)
        if not error:
            log(f'got result from {request_url}')
            return convert(response) if convert is not None else response
        elif isinstance(error, Interrupted):
            log('request interrupted: ' + request_url)
        elif isinstance(error, NoContent):
            log(f'got empty content from {request_url}')
            return convert(response) if convert is not None else response
        elif isinstance(error, RateLimitExceeded):
            retry += 1
            if retry > _MAX_RETRY:
                raise FolioError(f'Rate limit exceeded for {request_url}')
            else:
                # Wait and then call ourselves recursively.
                wait_time = retry * _RETRY_TIME_FACTOR
                log(f'hit rate limit; pausing {wait_time}s')
                wait(wait_time)
                return self._folio(op, endpoint, convert, retry = retry)
        raise error


    def id_kind(self, id):
        '''Infer the type of id given.

        This is currently limited to non-"type" records, i.e., items, holdings,
        instances, etc., and not the TypeKind kinds of records.
        '''
        if id in self._kind_cache:
            return self._kind_cache[id]

        id_kind = IdKind.UNKNOWN
        if isint(id) and len(id) > 7 and id.startswith('350'):
            log(f'recognized {id} as an item barcode')
            id_kind = IdKind.ITEM_BARCODE
        elif id.startswith('it') and id[2].isdigit():
            log(f'recognized {id} as an item hrid')
            id_kind = IdKind.ITEM_HRID
        elif id.startswith('clc') and '.' in id:
            log(f'recognized {id} as an accession number')
            id_kind = IdKind.ACCESSION
        elif id.startswith('ho') and id[2].isdigit():
            log(f'recognized {id} as an holdings hrid')
            id_kind = IdKind.HOLDINGS_HRID
        elif id.count('-') > 2:
            # Given a uuid, there's no way to ask Folio what kind it is, b/c
            # of Folio's microarchitecture & the lack of a central coordinating
            # authority.  So we have to ask different modules in turn.
            record_endpoints = [
                ('/item-storage/items',         IdKind.ITEM_ID),
                ('/instance-storage/instances', IdKind.INSTANCE_ID),
                ('/holdings-storage/holdings',  IdKind.HOLDINGS_ID),
                ('/loan-storage/loans',         IdKind.LOAN_ID),
                ('/users',                      IdKind.USER_ID),
            ]
            for base, kind in record_endpoints:
                if (response := self._folio('get', f'{base}/{id}')):
                    if response.status_code == 200:
                        log(f'recognized {id} as {kind}')
                        id_kind = kind
                        break
                    elif response.status_code >= 500:
                        raise RuntimeError('FOLIO server error')
        else:
            # We have a value that's more ambiguous. Try some searches.
            folio_searches = [
                ('/instance-storage/instances?query=hrid=', IdKind.INSTANCE_HRID),
                ('/item-storage/items?query=hrid=',         IdKind.ITEM_HRID),
                ('/holdings-storage/holdings?query=hrid=',  IdKind.HOLDINGS_HRID),
                ('/users?query=barcode=',                   IdKind.USER_BARCODE),
            ]
            for query, kind in folio_searches:
                if (response := self._folio('get', f'{query}{id}&limit=0')):
                    if response.status_code == 200:
                        # These endpoints always return a value, even when
                        # there are no hits, so we have to look inside.
                        data = json.loads(response.text)
                        if data and int(data.get('totalRecords', 0)) > 0:
                            log(f'recognized {id} as {kind}')
                            id_kind = kind
                            break
                    elif response.status_code >= 500:
                        raise RuntimeError('FOLIO server error')

        if id_kind != IdKind.UNKNOWN:
            log(f'caching id kind value for {id}')
            self._kind_cache[id] = id_kind
        return id_kind


    def record(self, id, id_kind = None):
        '''Return the record corresponding to the given id.  If the id kind
        is known, setting parameter id_kind will save multiple API calls.

        This is currently limited to non-"type" records, i.e., items, holdings,
        instances, etc., and not the TypeKind kinds of records.
        '''
        if not id_kind:
            id_kind = self.id_kind(id)
        log(f'id {id} has kind {id_kind}')
        if id_kind == IdKind.UNKNOWN:
            return None
        record_kind = IdKind.to_record_kind(id_kind)
        if (records_list := self.related_records(id, id_kind, record_kind)):
            if len(records_list) > 1:
                raise RuntimeError(f'Expected 1 record for {id} but got'
                                   + ' {len(records_list)}.')
            return records_list[0]
        return None


    def related_records(self, id, id_kind, requested,
                        use_inventory = False, open_loans_only = True):
        '''Returns a list of records found by searching for "id_kind" records
        associated with "id".
        '''
        use_inv = 'using inventory API' if use_inventory else ''
        log(f'getting {requested} record(s) for {id_kind} id {id} {use_inv}')

        def record_list(kind, key, response):
            if not response or not response.text:
                log(f'FOLIO returned no result searching for {id} and {kind}')
                return []
            data = json.loads(response.text)
            if key:
                if 'totalRecords' in data:
                    log(f'got {data["totalRecords"]} records for {id}')
                    return [Record(id = rec['id'], kind = kind, data = rec)
                            for rec in data[key]]
                else:
                    if 'title' in data:
                        # It's a record directly and not a list of records.
                        log(f'got 1 record for {id}')
                        return [Record(id = data['id'], kind = kind, data = data)]
                    else:
                        raise RuntimeError('Unexpected data returned by FOLIO')
            else:
                log(f'got 1 record for {id}')
                return [Record(id = data['id'], kind = kind, data = data)]


        # Figure out the appropriate API endpoint and return the value(s).
        if id_kind == IdKind.TYPE_ID:
            data_extractor = partial(record_list, RecordKind.TYPE, None)
            endpoint = f'/{requested}/{id}'

        elif requested == RecordKind.ITEM:
            # Default data extractor, but this gets overriden in some cases.
            data_extractor = partial(record_list, RecordKind.ITEM, 'items')
            module = 'inventory' if use_inventory else 'item-storage'

            # Given an item identifier.
            if id_kind == IdKind.ITEM_ID:
                endpoint = f'/{module}/items/{id}'
                if not use_inventory:
                    data_extractor = partial(record_list, RecordKind.ITEM, None)
            elif id_kind == IdKind.ITEM_BARCODE:
                endpoint = f'/{module}/items?query=barcode={id}'
            elif id_kind == IdKind.ITEM_HRID:
                endpoint = f'/{module}/items?query=hrid={id}'

            # Given an instance identifier.
            elif id_kind == IdKind.INSTANCE_ID:
                endpoint = f'/{module}/items?query=instance.id={id}&limit=10000'
            elif id_kind == IdKind.INSTANCE_HRID:
                endpoint = f'/{module}/items?query=instance.hrid={id}&limit=10000'
            elif id_kind == IdKind.ACCESSION:
                inst_id = instance_id_from_accession(id)
                endpoint = f'/{module}/items?query=instance.id={inst_id}&limit=10000'

            # Given a holdings identifier.
            elif id_kind == IdKind.HOLDINGS_ID:
                endpoint = f'/{module}/items?query=holdingsRecordId={id}&limit=10000'
            elif id_kind == IdKind.HOLDINGS_HRID:
                holdings = self.related_records(id, IdKind.HOLDINGS_HRID,
                                                'holdings', False, open_loans_only)
                if not holdings:
                    return []
                return self.related_records(holdings[0].id, IdKind.HOLDINGS_ID,
                                            'item', use_inventory, open_loans_only)

            # Given a user identifier.
            elif id_kind == IdKind.USER_ID:
                # Can't get items for a user directly.
                log(f'need to find loans for user {id}')
                loans = self.related_records(id, IdKind.USER_ID, 'loan',
                                             use_inventory, open_loans_only)
                if not loans:
                    return []
                if open_loans_only:
                    loans = [ln for ln in loans if ln.data['status']['name'] == 'Open']
                # The loans have item itemId's. Use that to retrieve item recs.
                items = []
                for loan in loans:
                    raise_for_interrupts()
                    item_id = loan.data['itemId']
                    items += self.related_records(item_id, IdKind.ITEM_ID, 'item',
                                                  use_inventory, open_loans_only)
                return items
            elif id_kind == IdKind.USER_BARCODE:
                # Do the lookup using the user id.
                records = self.related_records(id, IdKind.USER_BARCODE, 'user',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                user_id = records[0].id
                return self.related_records(user_id, IdKind.USER_ID, 'item',
                                            use_inventory, open_loans_only)

            # Given a loan identifier.
            elif id_kind == IdKind.LOAN_ID:
                # Have to use loan-storage and extract the item id.
                records = self.related_records(id, id_kind, 'loan',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                item_id = records[0].data['itemId']
                return self.related_records(item_id, IdKind.ITEM_ID, 'item',
                                            use_inventory, open_loans_only)
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested} by {id_kind.value}')

        elif requested == RecordKind.INSTANCE:
            # Default data extractor, but this gets overriden in some cases.
            data_extractor = partial(record_list, RecordKind.INSTANCE, 'instances')
            module = 'inventory' if use_inventory else 'instance-storage'

            # Given an instance identifier.
            if id_kind == IdKind.INSTANCE_ID:
                endpoint = f'/{module}/instances/{id}'
                if not use_inventory:
                    data_extractor = partial(record_list, RecordKind.INSTANCE, None)
            elif id_kind == IdKind.INSTANCE_HRID:
                endpoint = f'/{module}/instances?query=hrid={id}'
            elif id_kind == IdKind.ACCESSION:
                inst_id = instance_id_from_accession(id)
                endpoint = f'/{module}/instances/{inst_id}'
                if not use_inventory:
                    data_extractor = partial(record_list, RecordKind.INSTANCE, None)

            # Given an item identifier.
            elif id_kind == IdKind.ITEM_BARCODE:
                endpoint = f'/{module}/instances?query=item.barcode=={id}'
            elif id_kind == IdKind.ITEM_ID:
                endpoint = f'/{module}/instances?query=item.id=={id}'
            elif id_kind == IdKind.ITEM_HRID:
                endpoint = f'/{module}/instances?query=item.hrid=={id}'

            # Given a holdings identifier.
            elif id_kind == IdKind.HOLDINGS_ID:
                holdings = self.related_records(id, IdKind.HOLDINGS_ID, 'holdings',
                                                use_inventory, open_loans_only)
                if not holdings:
                    return []
                instance_id = holdings[0].data['instanceId']
                return self.related_records(instance_id, IdKind.INSTANCE_ID, 'instance',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.HOLDINGS_HRID:
                holdings = self.related_records(id, IdKind.HOLDINGS_HRID, 'holdings',
                                                use_inventory, open_loans_only)
                if not holdings:
                    return []
                instance_id = holdings[0].data['instanceId']
                return self.related_records(instance_id, IdKind.INSTANCE_ID, 'instance',
                                            use_inventory, open_loans_only)

            # Given a loan identifier.
            elif id_kind == IdKind.LOAN_ID:
                loans = self.related_records(id, IdKind.LOAN_ID, 'loan',
                                             use_inventory, open_loans_only)
                if not loans:
                    return []
                item_id = loans[0].data['itemId']
                return self.related_records(item_id, IdKind.ITEM_ID, 'instance',
                                            use_inventory, open_loans_only)

            # Given a user identifier.
            elif id_kind == IdKind.USER_ID:
                loans = self.related_records(id, IdKind.USER_ID, 'loan',
                                             use_inventory, open_loans_only)
                if not loans:
                    return []
                if open_loans_only:
                    loans = [ln for ln in loans if ln.data['status']['name'] == 'Open']
                instances = []
                for item_id in [loan.data['itemId'] for loan in loans]:
                    raise_for_interrupts()
                    instances += self.related_records(item_id, IdKind.ITEM_ID, 'instance',
                                                      use_inventory, open_loans_only)
                return instances
            elif id_kind == IdKind.USER_BARCODE:
                loans = self.related_records(id, IdKind.USER_BARCODE, 'loan',
                                             use_inventory, open_loans_only)
                if not loans:
                    return []
                if open_loans_only:
                    loans = [ln for ln in loans if ln.data['status']['name'] == 'Open']
                instances = []
                for item_id in [loan.data['itemId'] for loan in loans]:
                    raise_for_interrupts()
                    instances += self.related_records(item_id, IdKind.ITEM_ID, 'instance',
                                                      use_inventory, open_loans_only)
                return instances
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested} by {id_kind.value}')

        elif requested == RecordKind.LOAN:
            if id_kind == IdKind.LOAN_ID:
                endpoint = f'/loan-storage/loans/{id}'
                data_extractor = partial(record_list, RecordKind.LOAN, None)
            elif id_kind == IdKind.USER_ID:
                endpoint = f'/loan-storage/loans?query=userId=={id}&limit=10000'
                data_extractor = partial(record_list, RecordKind.LOAN, 'loans')
                loans = self._folio('get', endpoint, data_extractor)
                if not loans:
                    return []
                if open_loans_only:
                    loans = [ln for ln in loans if ln.data['status']['name'] == 'Open']
                return loans
            elif id_kind == IdKind.USER_BARCODE:
                # Can't do this one directly, so get a user id.
                user_records = self.related_records(id, IdKind.USER_BARCODE, 'user',
                                                    use_inventory, open_loans_only)
                if not user_records:
                    return []
                user_id = user_records[0].id
                return self.related_records(user_id, IdKind.USER_ID, 'loan',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.ITEM_ID:
                endpoint = f'/loan-storage/loans?query=itemId=={id}&limit=10000'
                data_extractor = partial(record_list, RecordKind.LOAN, 'loans')
                loans = self._folio('get', endpoint, data_extractor)
                if not loans:
                    return []
                if open_loans_only:
                    loans = [ln for ln in loans if ln.data['status']['name'] == 'Open']
                return loans
            elif id_kind == IdKind.ITEM_BARCODE:
                # Can't seem to use barcodes directly in loan-storage.
                log(f'need to find item id for item barcode {id}')
                records = self.related_records(id, IdKind.ITEM_BARCODE, 'item',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                item_id = records[0].id
                return self.related_records(item_id, IdKind.ITEM_ID, 'loan',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.ITEM_HRID:
                log(f'need to find item id for item hrid {id}')
                records = self.related_records(id, IdKind.ITEM_HRID, 'item',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                item_id = records[0].id
                return self.related_records(item_id, IdKind.ITEM_ID, 'loan',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.INSTANCE_ID:
                # We have to get the item id's, and look up loans on each.
                records = self.related_records(id, IdKind.INSTANCE_ID, 'item',
                                               use_inventory, open_loans_only)
                loans = []
                for item in records:
                    loans += self.related_records(item.id, IdKind.ITEM_ID, 'loan',
                                                  use_inventory, open_loans_only)
                if not loans:
                    return []
                if open_loans_only:
                    loans = [ln for ln in loans if ln.data['status']['name'] == 'Open']
                return loans
            elif id_kind == IdKind.INSTANCE_HRID:
                # Get the instance record & do this again with the instance id.
                records = self.related_records(id, IdKind.INSTANCE_HRID, 'instance',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                instance_id = records[0].id
                return self.related_records(instance_id, IdKind.INSTANCE_ID, 'loan',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.ACCESSION:
                # Get the instance record & do this again with the instance id.
                records = self.related_records(id, IdKind.ACCESSION, 'instance',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                instance_id = records[0].id
                return self.related_records(instance_id, IdKind.INSTANCE_ID, 'loan',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.HOLDINGS_ID:
                holdings = self.related_records(id, IdKind.HOLDINGS_ID, 'holdings',
                                                use_inventory, open_loans_only)
                if not holdings:
                    return []
                instance_id = holdings[0].data['instanceId']
                return self.related_records(instance_id, IdKind.INSTANCE_ID, 'loan',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.HOLDINGS_HRID:
                holdings = self.related_records(id, IdKind.HOLDINGS_HRID, 'holdings',
                                                use_inventory, open_loans_only)
                if not holdings:
                    return []
                instance_id = holdings[0].data['instanceId']
                return self.related_records(instance_id, IdKind.INSTANCE_ID, 'loan',
                                            use_inventory, open_loans_only)
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested} by {id_kind.value}')

        elif requested == RecordKind.USER:
            if id_kind == IdKind.USER_ID:
                endpoint = f'/users/{id}'
                data_extractor = partial(record_list, RecordKind.USER, None)
            elif id_kind == IdKind.USER_BARCODE:
                endpoint = f'/users?query=barcode={id}'
                data_extractor = partial(record_list, RecordKind.USER, 'users')
            elif id_kind == IdKind.ITEM_ID:
                records = self.related_records(id, IdKind.ITEM_ID, 'loan',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                user_id = records[0].data['userId']
                return self.related_records(user_id, IdKind.USER_ID, 'user',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.ITEM_HRID:
                records = self.related_records(id, IdKind.ITEM_HRID, 'item',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                item_id = records[0].id
                return self.related_records(item_id, IdKind.ITEM_ID, 'user',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.ITEM_BARCODE:
                records = self.related_records(id, IdKind.ITEM_BARCODE, 'item',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                item_id = records[0].id
                return self.related_records(item_id, IdKind.ITEM_ID, 'user',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.INSTANCE_ID:
                loans = self.related_records(id, IdKind.INSTANCE_ID, 'loan',
                                             use_inventory, open_loans_only)
                if not loans:
                    return []
                if open_loans_only:
                    loans = [ln for ln in loans if ln.data['status']['name'] == 'Open']
                user_records = []
                for user_id in [loan.data['userId'] for loan in loans]:
                    raise_for_interrupts()
                    user_records += self.related_records(user_id, IdKind.USER_ID, 'user',
                                                         use_inventory, open_loans_only)
                return user_records
            elif id_kind == IdKind.INSTANCE_HRID:
                records = self.related_records(id, IdKind.INSTANCE_HRID, 'instance',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                record_id = records[0].id
                return self.related_records(record_id, IdKind.INSTANCE_ID, 'user',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.ACCESSION:
                records = self.related_records(id, IdKind.ACCESSION, 'instance',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                record_id = records[0].id
                return self.related_records(record_id, IdKind.INSTANCE_ID, 'user',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.LOAN_ID:
                records = self.related_records(id, IdKind.LOAN_ID, 'loan',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                user_id = records[0].data['userId']
                return self.related_records(user_id, IdKind.USER_ID, 'user',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.HOLDINGS_ID:
                records = self.related_records(id, IdKind.HOLDINGS_ID, 'holdings',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                instance_id = records[0].data['instanceId']
                return self.related_records(instance_id, IdKind.INSTANCE_ID, 'user',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.HOLDINGS_HRID:
                records = self.related_records(id, IdKind.HOLDINGS_HRID, 'holdings',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                instance_id = records[0].data['instanceId']
                return self.related_records(instance_id, IdKind.INSTANCE_ID, 'user',
                                            use_inventory, open_loans_only)
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested} by {id_kind.value}')

        elif requested == RecordKind.HOLDINGS:
            if id_kind == IdKind.HOLDINGS_ID:
                data_extractor = partial(record_list, RecordKind.HOLDINGS, None)
                endpoint = f'/holdings-storage/holdings/{id}'
            elif id_kind == IdKind.HOLDINGS_HRID:
                data_extractor = partial(record_list, RecordKind.HOLDINGS, 'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=hrid=={id}&limit=10000'
            elif id_kind == IdKind.INSTANCE_ID:
                data_extractor = partial(record_list, RecordKind.HOLDINGS, 'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=instanceId=={id}&limit=10000'
            elif id_kind == IdKind.ITEM_BARCODE:
                data_extractor = partial(record_list, RecordKind.HOLDINGS, 'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=item.barcode=={id}&limit=10000'
            elif id_kind == IdKind.ITEM_ID:
                data_extractor = partial(record_list, RecordKind.HOLDINGS, 'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=item.id=={id}&limit=10000'
            elif id_kind == IdKind.ITEM_HRID:
                data_extractor = partial(record_list, RecordKind.HOLDINGS, 'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=item.hrid=={id}&limit=10000'
            elif id_kind == IdKind.INSTANCE_HRID:
                data_extractor = partial(record_list, RecordKind.HOLDINGS, 'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=hrid=={id}&limit=10000'
            elif id_kind == IdKind.ACCESSION:
                data_extractor = partial(record_list, RecordKind.HOLDINGS, 'holdingsRecords')
                inst_id = instance_id_from_accession(id)
                endpoint = f'/holdings-storage/holdings?query=instanceId=={inst_id}&limit=10000'
            elif id_kind == IdKind.LOAN_ID:
                records = self.related_records(id, IdKind.LOAN_ID, 'loan',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                item_id = records[0].data['itemId']
                return self.related_records(item_id, IdKind.ITEM_ID, 'holdings',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.USER_ID:
                loans = self.related_records(id, IdKind.USER_ID, 'loan',
                                             use_inventory, open_loans_only)
                if not loans:
                    return []
                holdings_records = []
                for loan in loans:
                    raise_for_interrupts()
                    holdings_records += self.related_records(loan.id, IdKind.LOAN_ID, 'holdings',
                                                             use_inventory, open_loans_only)
                return holdings_records
            elif id_kind == IdKind.USER_BARCODE:
                user = self.related_records(id, IdKind.USER_BARCODE, 'user',
                                            use_inventory, open_loans_only)
                if not user:
                    return []
                return self.related_records(user.id, IdKind.USER_ID, 'holdings',
                                            use_inventory, open_loans_only)
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested} by {id_kind.value}')

        else:
            raise RuntimeError(f'Unrecognized record type value {requested}')

        return self._folio('get', endpoint, data_extractor)


    def types(self, type_kind):
        '''Return a list of types of type_kind.'''
        if type_kind not in TypeKind:
            raise RuntimeError(f'Unknown type kind {type_kind}')
        if type_kind in self._type_list_cache:
            log(f'returning cached value of types {type_kind}')
            return self._type_list_cache[type_kind]

        def result_parser(response):
            if not response:
                log('no response received from FOLIO')
                return {}
            elif 200 <= response.status_code < 300:
                data_dict = json.loads(response.text)
                if 'totalRecords' in data_dict:
                    log(f'successfully got list of {type_kind} types from FOLIO')
                    key = set(set(data_dict.keys()) - {'totalRecords'}).pop()
                    return data_dict[key]
                else:
                    raise RuntimeError('Unexpected data returned by FOLIO')
            elif response.status_code == 401:
                log(f'user lacks authorization to get a {type_kind} list')
                return {}
            else:
                raise RuntimeError('Problem retrieving list of types')

        endpoint = '/' + type_kind + '?limit=10000'
        type_list = self._folio('get', endpoint, result_parser)
        if type_list:
            self._type_list_cache[type_kind] = type_list
        return type_list


    def write(self, record, endpoint):
        '''Write a record to the given endpoint.'''

        headers = {
            "x-okapi-token":  config('FOLIO_OKAPI_TOKEN'),
            "x-okapi-tenant": config('FOLIO_OKAPI_TENANT_ID'),
            "content-type":   "application/json",
        }

        request_url = config('FOLIO_OKAPI_URL') + endpoint
        data = json.dumps(record.data)
        (response, error) = net('put', request_url, headers = headers, data = data)
        if response and response.status_code == 204:
            log(f'successfully wrote record to {request_url}')
            return True, ''
        else:
            log(f'failed to write record to {request_url}: ' + str(error))
            return False, error


    def delete(self, record):
        '''Delete a record.'''

        headers = {
            "x-okapi-token":  config('FOLIO_OKAPI_TOKEN'),
            "x-okapi-tenant": config('FOLIO_OKAPI_TENANT_ID'),
            "content-type":   "application/json",
        }

        # Some deletions are done via the inventory api & some via storage api.
        endpoint = RecordKind.deletion_endpoint(record.kind)
        request_url = config('FOLIO_OKAPI_URL') + endpoint + '/' + record.id
        (response, error) = net('delete', request_url, headers = headers)
        if response and response.status_code == 204:
            log(f'successfully deleted record {record.id} from {request_url}')
            return True, ''
        else:
            log(f'failed to delete record {record.id}: ' + str(error))
            return False, error


    # https://s3.amazonaws.com/foliodocs/api/mod-inventory/p/inventory.html

    def operation(self, op, endpoint, data = None):
        '''Do 'op' on 'endpoint' and return a tuple (success, response text).'''

        def result_parser(response):
            if not response:
                return (False, '')
            elif 200 <= response.status_code < 300:
                return (True, response.text)
            elif response.status_code == 400:
                # "Bad request, e.g. malformed request body or query
                # parameter. Details of the error (e.g. name of the parameter
                # or line/character number with malformed data) provided in
                # the response."
                return (False, response.text)
            elif response.status_code == 401:
                # "Not authorized to perform requested action"
                return (False, response.text)
            elif response.status_code == 404:
                # "Item with a given ID not found"
                return (False, response.text)
            elif response.status_code == 422:
                # "Validation error"
                return (False, response.text)
            elif response.status_code in [409, 500]:
                # "internal server error"
                return (False, response.text)

        # return self._folio(op, endpoint, result_parser)
        log(f'issuing operation {op} on {endpoint}')
        return self._folio(op, endpoint, result_parser)


# Misc. utilities
# .............................................................................

def instance_id_from_accession(an):
    start = an.find('.')
    id_part = an[start + 1:]
    return id_part.replace('.', '-')


def unique_identifiers(text):
    lines = text.splitlines()
    identifiers = flattened(re.split(r'\s+|,+|;+|:+', line) for line in lines)
    identifiers = [id.replace('"', '') for id in identifiers]
    identifiers = [id.replace("'", '') for id in identifiers]
    identifiers = [id.replace(':', '') for id in identifiers]
    return unique(filter(None, identifiers))


def back_up_record(record):
    '''Write the record in JSON format to the backup directory.

    Backups are organized using a separate directory for every record uuid,
    then in a time-stamped file for the json file within that directory.
    '''
    if config('DEMO_MODE', cast = bool):
        log(f'demo mode in effect -- not backing up record {record.id}')
        return

    backup_dir = join(config('BACKUP_DIR'), record.id)
    if not exists(backup_dir):
        try:
            os.makedirs(backup_dir)
        except OSError as ex:
            log('unable to create backup directory {backup_dir}: ' + str(ex))
            raise
    elif not writable(backup_dir):
        log('backup directory is not writable: {backup_dir}')
        raise RuntimeError(f'Unable to write to backup directory {backup_dir}')

    timestamp = dt.now(tz = tz.tzlocal()).isoformat(timespec = 'seconds')
    # Can't use colon characters in Windows file names. This next change makes
    # the result not ISO 8601 or RFC 3339 compliant, but we don't need to be.
    timestamp = timestamp.replace(':', '')
    file = join(backup_dir, timestamp + '.json')
    with open(file, 'w') as f:
        log(f'backing up record {record.id} to {file}')
        json.dump(record.data, f, indent = 2)
