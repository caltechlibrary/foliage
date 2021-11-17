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
from   commonpy.interrupt import wait, interrupted
from   commonpy.string_utils import antiformat
from   commonpy.network_utils import net
from   datetime import datetime as dt
from   dateutil import tz
from   decouple import config
from   enum import Enum, EnumMeta
from   functools import partial
from   fastnumbers import isint
import json
from   os.path import exists, dirname, join, basename, abspath, realpath, isdir
import re
from   sidetrack import set_debug, log
from   validators.url import url as valid_url

from   .enum_utils import MetaEnum, ExtendedEnum


# Public data types.
# .............................................................................

class RecordKind(ExtendedEnum):
    ITEM     = 'item'
    INSTANCE = 'instance'
    HOLDINGS = 'holdings'
    USER     = 'user'
    LOAN     = 'loan'
    TYPE     = 'type'


class RecordIdKind(ExtendedEnum):
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


# maybe call this ValueKind?

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

# The equivalent of the name field in record lists, when the field is not 'name'
NAME_KEYS = {
    TypeKind.ADDRESS    : 'addressType',
    TypeKind.GROUP      : 'group',
    RecordKind.ITEM     : 'title',
    RecordKind.INSTANCE : 'title',
    RecordKind.HOLDINGS : 'id',
    RecordKind.USER     : 'username',
    RecordKind.LOAN     : 'id',
    RecordKind.TYPE     : 'name',
}


# Internal constants.
# .............................................................................

# Number of times we retry an api call that return an HTTP error.
_MAX_RETRY = 3

# Time between retries, multiplied by retry number.
_RETRY_TIME_FACTOR = 2


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
            return None
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
                return token
            elif error:
                log(f'FOLIO returned error: ' + str(error))
            else:
                log(f'FOLIO returned unrecognized code {str(resp.status_code)}')
        except Interrupted as ex:
            log(f'interrupted')
        except Exception as ex:
            log(f'FOLIO rejected request for creating API token: ' + str(ex))
        return None


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
            return response if convert is None else convert(response)
        elif isinstance(error, NoContent):
            log(f'got empty content from {request_url}')
            return None if convert is None else convert(None)
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


    def record_id_kind(self, id):
        '''Infer the type of id given.'''
        if id in self._kind_cache:
            return self._kind_cache[id]

        id_kind = RecordIdKind.UNKNOWN
        if isint(id) and len(id) > 7 and id.startswith('350'):
            log(f'recognized {id} as an item barcode')
            id_kind = RecordIdKind.ITEM_BARCODE
        elif id.startswith('clc') and '.' in id:
            log(f'recognized {id} as an accession number')
            id_kind = RecordIdKind.ACCESSION
        elif id.count('-') > 2:
            # Given a uuid, there's no way to ask Folio what kind it is, b/c
            # of Folio's microarchitecture & the lack of a central coordinating
            # authority.  So we have to ask different modules in turn.
            record_endpoints = [
                ('/item-storage/items',         RecordIdKind.ITEM_ID),
                ('/instance-storage/instances', RecordIdKind.INSTANCE_ID),
                ('/holdings-storage/holdings',  RecordIdKind.HOLDINGS_ID),
                ('/loan-storage/loans',         RecordIdKind.LOAN_ID),
                ('/users',                      RecordIdKind.USER_ID),
            ]
            for base, kind in record_endpoints:
                if (response := self._folio('get', f'{base}/{id}?limit=0')):
                    if response.status_code == 200:
                        log(f'recognized {id} as {kind}')
                        id_kind = kind
                    elif response.status_code >= 500:
                        raise RuntimeError('FOLIO server error')
        else:
            # We have a value that's more ambiguous. Try some searches.
            folio_searches = [
                (f'/users?query=barcode=',                   RecordIdKind.USER_BARCODE),
                (f'/item-storage/items?query=hrid=',         RecordIdKind.ITEM_HRID),
                (f'/instance-storage/instances?query=hrid=', RecordIdKind.INSTANCE_HRID),
                (f'/holdings-storage/holdings?query=hrid=',  RecordIdKind.HOLDINGS_HRID),
            ]
            for query, kind in folio_searches:
                if (response := self._folio('get', f'{query}{id}&limit=0')):
                    if response.status_code == 200:
                        # The endpoint always return a value, even when there
                        # are no hits, so we have to look inside.
                        data = json.loads(response.text)
                        if data and int(data.get('totalRecords', 0)) > 0:
                            log(f'recognized {id} as {kind}')
                            id_kind = kind
                    elif response.status_code >= 500:
                        raise RuntimeError('FOLIO server error')

        if id_kind != RecordIdKind.UNKNOWN:
            self._kind_cache[id] = id_kind
        return id_kind


    def records(self, id, id_kind, requested = None):

        def record_list(key, response):
            if not response or not response.text:
                log(f'FOLIO returned no result for {id}')
                return []
            data_dict = json.loads(response.text)
            if key:
                if not 'totalRecords' in data_dict:
                    if 'title' in data_dict:
                        # It's a record directly and not a list of records.
                        return [data_dict]
                    else:
                        raise RuntimeError('Unexpected data returned by FOLIO')
                log(f'got {data_dict["totalRecords"]} records for {id}')
                return data_dict[key]
            else:
                return [data_dict]

        # If we not given an explicit record type to retrieve, return the same
        # kind implied by the id type.
        if not requested:
            if id_kind in [RecordIdKind.ITEM_ID, RecordIdKind.ITEM_BARCODE,
                           RecordIdKind.ITEM_HRID]:
                requested = 'item'
            elif id_kind in [RecordIdKind.USER_ID, RecordIdKind.USER_BARCODE]:
                requested = 'user'
            elif id_kind in [RecordIdKind.HOLDINGS_ID, RecordIdKind.HOLDINGS_HRID]:
                requested = 'holdings'
            elif id_kind == RecordIdKind.LOAN_ID:
                requested = 'loan'
            elif id_kind == RecordIdKind.TYPE_ID:
                requested = 'type'
            else:
                requested = 'instance'

        # Figure out the appropriate API endpoint.
        if id_kind == RecordIdKind.TYPE_ID:
            data_extractor = partial(record_list, None)
            endpoint = f'/{requested}/{id}'

        elif requested == 'item':
            data_extractor = partial(record_list, 'items')
            if id_kind == RecordIdKind.ITEM_ID:
                endpoint = f'/inventory/items/{id}'
            elif id_kind == RecordIdKind.ITEM_BARCODE:
                endpoint = f'/inventory/items?query=barcode=={id}'
            elif id_kind == RecordIdKind.ITEM_HRID:
                endpoint = f'/inventory/items?query=hrid=={id}&limit=10000'
            elif id_kind == RecordIdKind.INSTANCE_ID:
                endpoint = f'/inventory/items?query=instance.id=={id}&limit=10000'
            elif id_kind == RecordIdKind.INSTANCE_HRID:
                endpoint = f'/inventory/items?query=instance.hrid=={id}&limit=10000'
            elif id_kind == RecordIdKind.ACCESSION:
                inst_id = instance_id_from_accession(id)
                endpoint = f'/inventory/items?query=instance.id=={inst_id}&limit=10000'
            elif id_kind == RecordIdKind.HOLDINGS_ID:
                endpoint = f'/inventory/items?query=holdingsRecordId=={id}&limit=10000'
            elif id_kind == RecordIdKind.HOLDINGS_HRID:
                holdings = self.records(id, RecordIdKind.HOLDINGS_HRID, 'holdings')
                if not holdings:
                    return []
                holdings_id = holdings[0]['id']
                return self.records(holdings_id, RecordIdKind.HOLDINGS_ID, 'item')
            elif id_kind == RecordIdKind.USER_ID:
                # Can't get items for a user directly.
                log(f'need to find loans for user {id}')
                loans = self.records(id, RecordIdKind.USER_ID, 'loan')
                if not loans:
                    return []
                # Look for active loans only.
                active = [loan for loan in loans if loan['status']['name'] == 'Open']
                # The loans have item itemId's. Use that to retrieve item recs.
                items = []
                for loan in active:
                    if interrupted():
                        return []
                    item_id = loan['itemId']
                    items += self.records(item_id, RecordIdKind.ITEM_ID, 'item')
                return items
            elif id_kind == RecordIdKind.USER_BARCODE:
                # Do the lookup using the user id.
                records = self.records(id, RecordIdKind.USER_BARCODE)
                if not records:
                    return []
                user_id = records[0]['id']
                return self.records(user_id, RecordIdKind.USER_ID, 'item')
            elif id_kind == RecordIdKind.LOAN_ID:
                # Have to use loan-storage and extract the item id.
                records = self.records(id, id_kind, 'loan')
                if not records:
                    return []
                item_id = records[0]['itemId']
                return self.records(item_id, RecordIdKind.ITEM_ID, 'item')
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested} by {id_kind.value}')

        elif requested == 'instance':
            data_extractor = partial(record_list, 'instances')
            if id_kind == RecordIdKind.INSTANCE_ID:
                endpoint = f'/inventory/instances/{id}'
            elif id_kind == RecordIdKind.ITEM_BARCODE:
                endpoint = f'/inventory/instances?query=item.barcode=={id}'
            elif id_kind == RecordIdKind.ITEM_ID:
                endpoint = f'/inventory/instances?query=item.id=={id}'
            elif id_kind == RecordIdKind.ITEM_HRID:
                endpoint = f'/inventory/instances?query=item.hrid=={id}'
            elif id_kind == RecordIdKind.INSTANCE_HRID:
                endpoint = f'/inventory/instances?query=hrid=={id}'
            elif id_kind == RecordIdKind.ACCESSION:
                inst_id = instance_id_from_accession(id)
                endpoint = f'/inventory/instances/{inst_id}'
            elif id_kind == RecordIdKind.HOLDINGS_ID:
                holdings = self.records(id, RecordIdKind.HOLDINGS_ID)
                if not holdings:
                    return []
                instance_id = holdings[0]['instanceId']
                return self.records(instance_id, RecordIdKind.INSTANCE_ID)
            elif id_kind == RecordIdKind.HOLDINGS_HRID:
                holdings = self.records(id, RecordIdKind.HOLDINGS_HRID)
                if not holdings:
                    return []
                instance_id = holdings[0]['instanceId']
                return self.records(instance_id, RecordIdKind.INSTANCE_ID)
            elif id_kind == RecordIdKind.LOAN_ID:
                loans = self.records(id, RecordIdKind.LOAN_ID)
                if not loans:
                    return []
                item_id = loans[0]['itemId']
                return self.records(item_id, RecordIdKind.ITEM_ID, 'instance')
            elif id_kind == RecordIdKind.USER_ID:
                loans = self.records(id, RecordIdKind.USER_ID, 'loan')
                if not loans:
                    return []
                active = [loan for loan in loans if loan['status']['name'] == 'Open']
                item_ids = [loan['itemId'] for loan in active]
                instances = []
                for id in item_ids:
                    if interrupted():
                        return []
                    instances += self.records(id, RecordIdKind.ITEM_ID, 'instance')
                return instances
            elif id_kind == RecordIdKind.USER_BARCODE:
                loans = self.records(id, RecordIdKind.USER_BARCODE, 'loan')
                if not loans:
                    return []
                active = [loan for loan in loans if loan['status']['name'] == 'Open']
                item_ids = [loan['itemId'] for loan in active]
                instances = []
                for id in item_ids:
                    if interrupted():
                        return []
                    instances += self.records(id, RecordIdKind.ITEM_ID, 'instance')
                return instances
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested} by {id_kind.value}')

        elif requested == 'loan':
            if id_kind == RecordIdKind.LOAN_ID:
                endpoint = f'/loan-storage/loans/{id}'
                data_extractor = partial(record_list, None)
            elif id_kind == RecordIdKind.USER_ID:
                endpoint = f'/loan-storage/loans?query=userId=={id}&limit=10000'
                data_extractor = partial(record_list, 'loans')
                loans = self._folio('get', endpoint, data_extractor)
                if not loans:
                    return []
                return [loan for loan in loans if loan['status']['name'] == 'Open']
            elif id_kind == RecordIdKind.USER_BARCODE:
                # Can't do this one directly, so get a user id.
                user_records = self.records(id, RecordIdKind.USER_BARCODE, 'user')
                if not user_records:
                    return []
                user_id = user_records[0]['id']
                return self.records(user_id, RecordIdKind.USER_ID, 'loan')
            elif id_kind == RecordIdKind.ITEM_ID:
                endpoint = f'/loan-storage/loans?query=itemId=={id}&limit=10000'
                data_extractor = partial(record_list, 'loans')
                loans = self._folio('get', endpoint, data_extractor)
                if not loans:
                    return []
                return [loan for loan in loans if loan['status']['name'] == 'Open']
            elif id_kind == RecordIdKind.ITEM_BARCODE:
                # Can't seem to use barcodes directly in loan-storage.
                log(f'need to find item id for item barcode {id}')
                records = self.records(id, RecordIdKind.ITEM_BARCODE)
                if not records:
                    return []
                item_id = records[0]['id']
                return self.records(item_id, RecordIdKind.ITEM_ID, 'loan')
            elif id_kind == RecordIdKind.ITEM_HRID:
                log(f'need to find item id for item hrid {id}')
                records = self.records(id, RecordIdKind.ITEM_HRID)
                if not records:
                    return []
                item_id = records[0]['id']
                return self.records(item_id, RecordIdKind.ITEM_ID, 'loan')
            elif id_kind == RecordIdKind.INSTANCE_ID:
                # We have to get the item id's, and look up loans on each.
                records = self.records(id, RecordIdKind.INSTANCE_ID, 'item')
                loans = []
                for item in records:
                    loans += self.records(item['id'], RecordIdKind.ITEM_ID, 'loan')
                if not loans:
                    return []
                return [loan for loan in loans if loan['status']['name'] == 'Open']
            elif id_kind == RecordIdKind.INSTANCE_HRID:
                # Get the instance record & do this again with the instance id.
                records = self.records(id, RecordIdKind.INSTANCE_HRID, 'instance')
                if not records:
                    return []
                instance_id = records[0]['id']
                return self.records(instance_id, RecordIdKind.INSTANCE_ID, 'loan')
            elif id_kind == RecordIdKind.ACCESSION:
                # Get the instance record & do this again with the instance id.
                records = self.records(id, RecordIdKind.ACCESSION, 'instance')
                if not records:
                    return []
                instance_id = records[0]['id']
                return self.records(instance_id, RecordIdKind.INSTANCE_ID, 'loan')
            elif id_kind == RecordIdKind.HOLDINGS_ID:
                holdings = self.records(id, RecordIdKind.HOLDINGS_ID)
                if not holdings:
                    return []
                instance_id = holdings[0]['instanceId']
                return self.records(instance_id, RecordIdKind.INSTANCE_ID, 'loan')
            elif id_kind == RecordIdKind.HOLDINGS_HRID:
                holdings = self.records(id, RecordIdKind.HOLDINGS_HRID)
                if not holdings:
                    return []
                instance_id = holdings[0]['instanceId']
                return self.records(instance_id, RecordIdKind.INSTANCE_ID, 'loan')
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested} by {id_kind.value}')

        elif requested == 'user':
            if id_kind == RecordIdKind.USER_ID:
                endpoint = f'/users/{id}'
                data_extractor = partial(record_list, None)
            elif id_kind == RecordIdKind.USER_BARCODE:
                endpoint = f'/users?query=barcode={id}'
                data_extractor = partial(record_list, 'users')
            elif id_kind == RecordIdKind.ITEM_ID:
                records = self.records(id, RecordIdKind.ITEM_ID, 'loan')
                if not records:
                    return []
                user_id = records[0]['userId']
                return self.records(user_id, RecordIdKind.USER_ID, 'user')
            elif id_kind == RecordIdKind.ITEM_HRID:
                records = self.records(id, RecordIdKind.ITEM_HRID, 'item')
                if not records:
                    return []
                item_id = records[0]['id']
                return self.records(item_id, RecordIdKind.ITEM_ID, 'user')
            elif id_kind == RecordIdKind.ITEM_BARCODE:
                records = self.records(id, RecordIdKind.ITEM_BARCODE, 'item')
                if not records:
                    return []
                item_id = records[0]['id']
                return self.records(item_id, RecordIdKind.ITEM_ID, 'user')
            elif id_kind == RecordIdKind.INSTANCE_ID:
                loans = self.records(id, RecordIdKind.INSTANCE_ID, 'loan')
                if not loans:
                    return []
                active = [loan for loan in loans if loan['status']['name'] == 'Open']
                user_ids = [loan['userId'] for loan in active]
                user_records = []
                for id in user_ids:
                    if interrupted():
                        return []
                    user_records += self.records(id, RecordIdKind.USER_ID, 'user')
                return user_records
            elif id_kind == RecordIdKind.INSTANCE_HRID:
                records = self.records(id, RecordIdKind.INSTANCE_HRID, 'instance')
                if not records:
                    return []
                record_id = records[0]['id']
                return self.records(record_id, RecordIdKind.INSTANCE_ID, 'user')
            elif id_kind == RecordIdKind.ACCESSION:
                records = self.records(id, RecordIdKind.ACCESSION, 'instance')
                if not records:
                    return []
                record_id = records[0]['id']
                return self.records(record_id, RecordIdKind.INSTANCE_ID, 'user')
            elif id_kind == RecordIdKind.LOAN_ID:
                records = self.records(id, RecordIdKind.LOAN_ID, 'loan')
                if not records:
                    return []
                user_id = records[0]['userId']
                return self.records(user_id, RecordIdKind.USER_ID, 'user')
            elif id_kind == RecordIdKind.HOLDINGS_ID:
                records = self.records(id, RecordIdKind.HOLDINGS_ID)
                if not records:
                    return []
                instance_id = records[0]['instanceId']
                return self.records(instance_id, RecordIdKind.INSTANCE_ID, 'user')
            elif id_kind == RecordIdKind.HOLDINGS_HRID:
                records = self.records(id, RecordIdKind.HOLDINGS_HRID)
                if not records:
                    return []
                instance_id = records[0]['instanceId']
                return self.records(instance_id, RecordIdKind.INSTANCE_ID, 'user')
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested} by {id_kind.value}')

        elif requested == 'holdings':
            if id_kind == RecordIdKind.HOLDINGS_ID:
                data_extractor = partial(record_list, None)
                endpoint = f'/holdings-storage/holdings/{id}'
            elif id_kind == RecordIdKind.HOLDINGS_HRID:
                data_extractor = partial(record_list, 'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=hrid=={id}&limit=10000'
            elif id_kind == RecordIdKind.INSTANCE_ID:
                data_extractor = partial(record_list, 'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=instanceId=={id}&limit=10000'
            elif id_kind == RecordIdKind.ITEM_BARCODE:
                data_extractor = partial(record_list, 'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=item.barcode=={id}&limit=10000'
            elif id_kind == RecordIdKind.ITEM_ID:
                data_extractor = partial(record_list, 'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=item.id=={id}&limit=10000'
            elif id_kind == RecordIdKind.ITEM_HRID:
                data_extractor = partial(record_list, 'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=item.hrid=={id}&limit=10000'
            elif id_kind == RecordIdKind.INSTANCE_HRID:
                data_extractor = partial(record_list, 'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=hrid=={id}&limit=10000'
            elif id_kind == RecordIdKind.ACCESSION:
                data_extractor = partial(record_list, 'holdingsRecords')
                inst_id = instance_id_from_accession(id)
                endpoint = f'/holdings-storage/holdings?query=instanceId=={inst_id}&limit=10000'
            elif id_kind == RecordIdKind.LOAN_ID:
                records = self.records(id, RecordIdKind.LOAN_ID, 'loan')
                if not records:
                    return []
                item_id = records[0]['itemId']
                return self.records(item_id, RecordIdKind.ITEM_ID, 'holdings')
            elif id_kind == RecordIdKind.USER_ID:
                loans = self.records(id, RecordIdKind.USER_ID, 'loan')
                if not loans:
                    return []
                loan_ids = [loan['id'] for loan in loans]
                holdings_records = []
                for id in loan_ids:
                    if interrupted():
                        return []
                    holdings_records += self.records(id, RecordIdKind.LOAN_ID, 'holdings')
                return holdings_records
            elif id_kind == RecordIdKind.USER_BARCODE:
                user = self.records(id, RecordIdKind.USER_BARCODE, 'user')
                if not user:
                    return []
                return self.records(user['id'], RecordIdKind.USER_ID, 'holdings')
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
                return {}
            elif 200 <= response.status_code < 300:
                data_dict = json.loads(response.text)
                if 'totalRecords' in data_dict:
                    key = set(set(data_dict.keys()) - {'totalRecords'}).pop()
                    return data_dict[key]
                else:
                    raise RuntimeError('Unexpected data returned by FOLIO')
            else:
                raise RuntimeError('Problem retrieving list of types')

        endpoint = '/' + type_kind + '?limit=1000'
        type_list = self._folio('get', endpoint, result_parser)
        if type_list:
            self._type_list_cache[type_kind] = type_list
        return type_list


    # https://s3.amazonaws.com/foliodocs/api/mod-inventory/p/inventory.html

    def operation(self, op, endpoint):
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
    if config('DEMO_MODE', cast = bool):
        log(f'demo mode in effect -- not backing up record')
        return
    backup_dir = config('BACKUP_DIR')
    timestamp = dt.now(tz = tz.tzlocal()).strftime('%Y%m%d-%H%M%S%f')[:-3]
    id = record['id']
    file = join(backup_dir, id + '.' + timestamp + '.json')
    with open(file, 'w') as f:
        log(f'backing up record {id} to {file}')
        json.dump(record, f, indent = 2)
