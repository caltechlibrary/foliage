'''
folio.py: functions for interacting with FOLIO over the network API

How FOLIO credentials are supplied
----------------------------------

Almost all of the methods in this file that need FOLIO credentials get them
from three environment variables:

- FOLIO_OKAPI_TOKEN
- FOLIO_OKAPI_TENANT_ID
- FOLIO_OKAPI_URL

These environmewnt variables are set only by one function in Foliage:
use_credentials() in credentials.py.  The credentials may be gathered from the
user in a variety of ways, but as far as this module is concerned, the values
are only read from the environment variables.  This simplifies the calls here
and makes it possible to easily update the credentials at run time.

The exception in the code below is the method new_token(...), which takes
parameters that include the user's login and password.  This method is called
by the functions that ask the user for the credentials when first getting a
token from FOLIO, which happens at a time when none of the environment
variables are set.  Using parameters in this case is simpler than having the
caller set four environment variables prior to calling new_token(...) and then
having new_token(...) have to read four environment variables.

Copyright
---------

Copyright (c) 2021-2022 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.data_utils import unique, flattened
from   commonpy.exceptions import NoContent, RateLimitExceeded
from   commonpy.exceptions import Interrupted, NetworkFailure
from   commonpy.file_utils import writable
from   commonpy.interrupt import wait, raise_for_interrupts
from   commonpy.network_utils import net, network_available
from   dataclasses import dataclass
from   datetime import datetime as dt
from   dateutil import tz
from   decouple import config
from   functools import partial
import json
import os
from   os.path import exists, join
import re
from   sidetrack import log
from   validators.url import url as valid_url

from   foliage.enum_utils import ExtendedEnum
from   foliage.exceptions import FoliageException, FolioError, FolioOpFailed


# Internal constants.
# .............................................................................

# Accession number prefix for this site.
_AN_PREFIX = 'cit.oai'

# Number of times we retry an api call that return an HTTP error.
_MAX_RETRY = 3

# Time between retries, multiplied by retry number.
_RETRY_TIME_FACTOR = 2

# Regex to identify item barcodes.
_ITEM_BARCODE_REGEX = re.compile(r'\A('
                                 + '|'.join([
                                     r'350\d+',
                                     r'\d{1,3}',
                                     r'nobarcode\d+',
                                     r'temp-\w+',
                                     r'tmp-\w+',
                                     r'SFL-\w+',
                                 ]) + r')\Z',
                                 re.IGNORECASE)


# Public data types.
# .............................................................................

class RecordKind(ExtendedEnum):
    '''Class representing a kind of record in FOLIO.

    "Kind" in this case means the distinction between an item, versus an
    instance, versus a loan, versus other records.
    '''

    UNKNOWN  = 'unknown'
    ITEM     = 'item'
    INSTANCE = 'instance'
    HOLDINGS = 'holdings'
    LOAN     = 'loan'
    USER     = 'user'
    TYPE     = 'type'

    @staticmethod
    def name_key(kind):
        '''Return the JSON key to use as the equivalen of a "name" field.
        The value is used mainly when sorting lists of records.
        '''
        mapping = {
            RecordKind.ITEM     : 'title',
            RecordKind.INSTANCE : 'title',
            RecordKind.HOLDINGS : 'id',
            RecordKind.LOAN     : 'id',
            RecordKind.USER     : 'username',
        }
        return mapping[kind] if kind in mapping else 'name'


    @staticmethod
    def creation_endpoint(kind):
        '''FOLIO API endpoint for creating the given kind of record.'''
        mapping = {
            RecordKind.HOLDINGS : '/holdings-storage/holdings',
        }
        return mapping[kind] if kind in mapping else None


    @staticmethod
    def update_endpoint(kind):
        '''FOLIO API endpoint for updating the given kind of record.'''
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
        '''FOLIO API endpoint for deleting the given kind of record.'''
        mapping = {
            RecordKind.ITEM     : '/item-storage/items',
            RecordKind.INSTANCE : '/instance-storage/instances',
            RecordKind.HOLDINGS : '/holdings-storage/holdings',
            RecordKind.LOAN     : '/loan-storage/loans',
            RecordKind.USER     : '/users',
        }
        return mapping[kind] if kind in mapping else None


class IdKind(ExtendedEnum):
    '''Enumeration representing what kind of record an id corresponds to.'''

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
        '''Return a RecordKind corresponding to a given IdKind.'''
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
    '''Enumeration of data types (e.g., for location types).'''

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
    id   : str                          # The UUID.  # noqa: A003
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
            log('given incomplete set of parameters -- can\'t proceed.')
            return None, 'Incomplete parameters for credentials'
        try:
            log('asking FOLIO for new API token')
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
        except Interrupted:
            log('interrupted')
            return None, 'Operation was interrupted before a new token was obtained'
        except Exception as ex:         # noqa: PIE786
            log('exception trying to get new FOLIO token: ' + str(ex))
            return None, 'Encountered error trying to get token – please report this'


    @staticmethod
    def credentials_valid():
        '''Return True if the current FOLIO credentials are valid.
        This reads the environment variables for the credentials and tries to
        call a FOLIO API endpoint to test whether the creds are valid.
        '''
        url       = config('FOLIO_OKAPI_URL', default = None)
        tenant_id = config('FOLIO_OKAPI_TENANT_ID', default = None)
        token     = config('FOLIO_OKAPI_TOKEN', default = None)
        if not all([url, tenant_id, token]):
            log('credentials are incomplete; cannot validate credentials')
            return False
        if not valid_url(url):
            log('FOLIO_OKAPI_URL value is not a valid URL')
            return False
        try:
            log('testing if FOLIO credentials appear valid')
            headers = {
                "x-okapi-token": token,
                "x-okapi-tenant": tenant_id,
                "content-type": "application/json",
            }
            request_url = url + '/instance-statuses?limit=0'
            (resp, _) = net('get', request_url, headers = headers)
            return (resp and resp.status_code < 400)
        except Exception as ex:         # noqa: PIE786
            log('FOLIO credentials test failed with ' + str(ex))
            return False


    def request(self, api, op = 'get', data = None, converter = None, retry = 0):
        '''Invoke 'op' on 'api', call 'converter' on it, return result.
        This method reads the FOLIO credentials from environment variables.
        In case of rate limits being hit, this will retry the operation.
        '''
        headers = {
            "x-okapi-token":  config('FOLIO_OKAPI_TOKEN'),
            "x-okapi-tenant": config('FOLIO_OKAPI_TENANT_ID'),
            "content-type":   "application/json",
        }

        url = config('FOLIO_OKAPI_URL') + api
        if data is not None:
            (response, error) = net(op, url, headers = headers, data = data)
        else:
            (response, error) = net(op, url, headers = headers)

        if not error:
            log(f'got result from {url}')
            return converter(response) if converter is not None else response
        elif isinstance(error, NoContent):
            log(f'got empty content from {url}')
            return converter(response) if converter is not None else response
        elif isinstance(error, RateLimitExceeded):
            retry += 1
            if retry > _MAX_RETRY:
                raise FolioError(f'Rate limit exceeded for {url}')
            else:
                # Wait and then call ourselves recursively.
                wait_time = retry * _RETRY_TIME_FACTOR
                log(f'hit rate limit; pausing {wait_time}s')
                wait(wait_time)
                return self.request(api, op, data, converter, retry = retry)
        # Error from net() may be an exception object, but we have special
        # understanding of FOLIO return codes, so handle most cases ourselves.
        self._finish(response, error, 'HTTP get ' + url)


    def _finish(self, response, error, what):
        '''Interpret FOLIO HTTP response & log + raise errors if appropriate.'''
        if isinstance(error, Interrupted):
            # Propagate interruptions to callers.
            raise error
        elif isinstance(error, NetworkFailure):
            raise FolioOpFailed('Network error')
        elif not response:
            # Could we have lost the network?
            if not network_available():
                log('lost network connection')
                raise FolioOpFailed('Network connection appears to be down')
            else:
                # Something is really wonky.
                log('got empty or None response for ' + what)
                raise FolioError('Network API call produced no response')
        elif 200 <= response.status_code < 300:
            log('success for ' + what)
            return
        elif response.status_code == 400:
            # "Bad request, e.g. malformed request body or query parameter.
            # Details of the error (e.g. name of the parameter or line/character
            # number with malformed data) provided in the response."
            log('FOLIO response code 400 details: ' + response.text)
            raise FolioOpFailed('Error in API call to FOLIO – please report this')
        elif response.status_code in [401, 403]:
            # "Not authorized to perform requested action"
            log(f'FOLIO response code {response.status_code}: ' + response.text)
            raise FolioOpFailed('FOLIO permissions error: not authorized for action')
        elif response.status_code == 404:
            # "Item not found" etc.
            log('FOLIO response code 404 details: ' + response.text)
            raise FolioOpFailed('FOLIO returned an error: ' + response.text)
        elif response.status_code in [409, 500, 501]:
            # "internal server error"
            log(f'FOLIO response {response.status_code} details: ' + response.text)
            raise FolioError('FOLIO server error: ' + response.text)
        elif response.status_code == 422:
            # Schema validation error, probably in JSON we tried to upload.
            # 1st get the JSON 'errors' field; it's a list, ea w/ 'message'.
            response_dict = json.loads(response.text)
            if 'errors' in response_dict:
                error_list = response_dict['errors']
                log('code 422: schema errors')
                for index, error in enumerate(error_list):
                    log(f'error #{index}:' + error)
            else:
                log('got code 422 but response did not include errors')
            raise FolioOpFailed('Foliage data format error – please report this')
        else:
            # A code that I didn't see in the FOLIO API documentation.
            log(f'Unrecognized FOLIO response code {response.status_code}'
                ' details: ' + response.text)
            raise FoliageException('Unexpected FOLIO response – please report this')


    def types(self, type_kind):
        '''Return a list of types of type_kind, as Record objects.'''
        if type_kind not in TypeKind:
            raise RuntimeError(f'Unknown type kind {type_kind}')
        if type_kind in self._type_list_cache:
            log(f'returning cached value of types {type_kind}')
            return self._type_list_cache[type_kind]

        def result_parser(response):
            if not response or not response.text:
                log('no response received from FOLIO')
                return []
            elif 200 <= response.status_code < 300:
                data_dict = json.loads(response.text)
                if 'totalRecords' in data_dict:
                    log(f'successfully got list of {type_kind} types from FOLIO')
                    key = set(set(data_dict.keys()) - {'totalRecords'}).pop()
                    return [Record(id = item['id'], kind = type_kind, data = item)
                            for item in data_dict[key]]
                else:
                    raise RuntimeError('Unexpected data returned by FOLIO')
            elif response.status_code == 401:
                log(f'user lacks authorization to get a {type_kind} list')
                return []
            else:
                raise RuntimeError('Problem retrieving list of types')

        endpoint = '/' + type_kind + '?limit=10000'
        type_list = self.request(endpoint, converter = result_parser)
        if type_list:
            self._type_list_cache[type_kind] = type_list
        return type_list


    def id_kind(self, id_):
        '''Infer the type of id given.

        This is currently limited to non-"type" records, i.e., items, holdings,
        instances, etc., and not the TypeKind kinds of records.
        '''
        if id_ in self._kind_cache:
            return self._kind_cache[id_]

        id_kind = IdKind.UNKNOWN
        id_ = id_.strip(r' \\')  # Strip backslashes that got into some barcodes
        if (_ITEM_BARCODE_REGEX.match(id_)):
            log(f'recognized {id_} as an item barcode')
            id_kind = IdKind.ITEM_BARCODE
        elif id_.startswith('it') and id_[2].isdigit():
            log(f'recognized {id_} as an item hrid')
            id_kind = IdKind.ITEM_HRID
        elif id_.startswith('ho') and id_[2].isdigit():
            log(f'recognized {id_} as an holdings hrid')
            id_kind = IdKind.HOLDINGS_HRID
        elif id_.startswith(_AN_PREFIX):
            log(f'recognized {id_} as an accession number')
            id_kind = IdKind.ACCESSION
        elif id_.count('-') > 2:
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
                if (response := self.request(f'{base}/{id_}')):
                    if response.status_code == 200:
                        log(f'recognized {id_} as {kind}')
                        id_kind = kind
                        break
                    elif response.status_code >= 500:
                        raise RuntimeError('FOLIO server error')
        else:
            # We have a value that's more ambiguous. Try some searches.
            # Most hrid's will follow the pattern above, so try other cases 1st.
            folio_searches = [
                ('/users?query=barcode=',                   IdKind.USER_BARCODE),
                # Caltech ID's are same as user barcodes with a leading 000.
                # Let's try to help people who type in a CITUID without the 0's.
                ('/users?query=barcode=000',                IdKind.USER_BARCODE),
                ('/instance-storage/instances?query=hrid=', IdKind.INSTANCE_HRID),
                ('/item-storage/items?query=hrid=',         IdKind.ITEM_HRID),
                ('/holdings-storage/holdings?query=hrid=',  IdKind.HOLDINGS_HRID),
            ]
            for query, kind in folio_searches:
                if (response := self.request(f'{query}{id_}&limit=0')):
                    if response.status_code == 200:
                        # These endpoints always return a value, even when
                        # there are no hits, so we have to look inside.
                        data = json.loads(response.text)
                        if data and int(data.get('totalRecords', 0)) > 0:
                            log(f'recognized {id_} as {kind}')
                            id_kind = kind
                            break
                    elif response.status_code >= 500:
                        raise RuntimeError('FOLIO server error')

        if id_kind != IdKind.UNKNOWN:
            log(f'caching id kind value for {id_}')
            self._kind_cache[id_] = id_kind
        return id_kind


    def record(self, id_, id_kind = None):
        '''Return the record corresponding to the given id.  If the id kind
        is known, setting parameter id_kind will save multiple API calls.

        This is currently limited to non-"type" records, i.e., items, holdings,
        instances, etc., and not the TypeKind kinds of records.
        '''
        if not id_kind:
            id_kind = self.id_kind(id_)
        log(f'id {id_} has kind {id_kind}')
        if id_kind == IdKind.UNKNOWN:
            return None
        record_kind = IdKind.to_record_kind(id_kind)
        if (records_list := self.related_records(id_, id_kind, record_kind)):
            if len(records_list) > 1:
                raise RuntimeError(f'Expected 1 record for {id_} but got'
                                   ' {len(records_list)}.')
            return records_list[0]
        return None


    def related_records(self, id_, id_kind, requested,
                        use_inventory = False, open_loans_only = True):
        '''Returns a list of records found by searching for "id_kind" records
        associated with "id_".
        '''
        use_inv = 'using inventory API' if use_inventory else ''
        log(f'getting {requested} record(s) for {id_kind} {id_} {use_inv}')

        def record_list(kind, key, response):
            if not response or not response.text or response.status_code == 404:
                log(f'FOLIO returned no result searching for {id_} and {kind}')
                return []
            try:
                data = json.loads(response.text)
            except json.decoder.JSONDecodeError:
                raise RuntimeError('Unexpected response format returned by FOLIO')
            if key:
                if 'totalRecords' in data:
                    log(f'got {data["totalRecords"]} records for {id_}')
                    return [Record(id = rec['id'], kind = kind, data = rec)
                            for rec in data[key]]
                else:
                    if 'title' in data:
                        # It's a record directly and not a list of records.
                        log(f'got 1 record for {id_}')
                        return [Record(id = data['id'], kind = kind, data = data)]
                    else:
                        raise RuntimeError('Unexpected data returned by FOLIO')
            else:
                log(f'got 1 record for {id_}')
                return [Record(id = data['id'], kind = kind, data = data)]


        # Figure out the appropriate API endpoint and return the value(s).
        if id_kind == IdKind.TYPE_ID:
            data_extractor = partial(record_list, RecordKind.TYPE, None)
            endpoint = f'/{requested}/{id_}'

        elif requested == RecordKind.ITEM:
            # Default data extractor, but this gets overriden in some cases.
            data_extractor = partial(record_list, RecordKind.ITEM, 'items')
            module = 'inventory' if use_inventory else 'item-storage'

            # Given an item identifier.
            if id_kind == IdKind.ITEM_ID:
                endpoint = f'/{module}/items/{id_}'
                if not use_inventory:
                    data_extractor = partial(record_list, RecordKind.ITEM, None)
            elif id_kind == IdKind.ITEM_BARCODE:
                endpoint = f'/{module}/items?query=barcode={id_}'
            elif id_kind == IdKind.ITEM_HRID:
                endpoint = f'/{module}/items?query=hrid={id_}'

            # Given an instance identifier.
            elif id_kind == IdKind.INSTANCE_ID:
                endpoint = f'/{module}/items?query=instance.id={id_}&limit=10000'
            elif id_kind == IdKind.INSTANCE_HRID:
                endpoint = f'/{module}/items?query=instance.hrid={id_}&limit=10000'
            elif id_kind == IdKind.ACCESSION:
                inst_id = instance_id_from_accession(id_)
                endpoint = f'/{module}/items?query=instance.id={inst_id}&limit=10000'

            # Given a holdings identifier.
            elif id_kind == IdKind.HOLDINGS_ID:
                endpoint = f'/{module}/items?query=holdingsRecordId={id_}&limit=10000'
            elif id_kind == IdKind.HOLDINGS_HRID:
                holdings = self.related_records(id_, IdKind.HOLDINGS_HRID,
                                                'holdings', False, open_loans_only)
                if not holdings:
                    return []
                return self.related_records(holdings[0].id, IdKind.HOLDINGS_ID,
                                            'item', use_inventory, open_loans_only)

            # Given a user identifier.
            elif id_kind == IdKind.USER_ID:
                # Can't get items for a user directly.
                log(f'need to find loans for user {id_}')
                loans = self.related_records(id_, IdKind.USER_ID, 'loan',
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
                records = self.related_records(id_, IdKind.USER_BARCODE, 'user',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                user_id = records[0].id
                return self.related_records(user_id, IdKind.USER_ID, 'item',
                                            use_inventory, open_loans_only)

            # Given a loan identifier.
            elif id_kind == IdKind.LOAN_ID:
                # Have to use loan-storage and extract the item id.
                records = self.related_records(id_, id_kind, 'loan',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                item_id = records[0].data['itemId']
                return self.related_records(item_id, IdKind.ITEM_ID, 'item',
                                            use_inventory, open_loans_only)
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested}'
                                   f' by {id_kind.value}')

        elif requested == RecordKind.INSTANCE:
            # Default data extractor, but this gets overriden in some cases.
            data_extractor = partial(record_list, RecordKind.INSTANCE, 'instances')
            module = 'inventory' if use_inventory else 'instance-storage'

            # Given an instance identifier.
            if id_kind == IdKind.INSTANCE_ID:
                endpoint = f'/{module}/instances/{id_}'
                if not use_inventory:
                    data_extractor = partial(record_list, RecordKind.INSTANCE, None)
            elif id_kind == IdKind.INSTANCE_HRID:
                endpoint = f'/{module}/instances?query=hrid={id_}'
            elif id_kind == IdKind.ACCESSION:
                inst_id = instance_id_from_accession(id_)
                endpoint = f'/{module}/instances/{inst_id}'
                if not use_inventory:
                    data_extractor = partial(record_list, RecordKind.INSTANCE, None)

            # Given an item identifier.
            elif id_kind == IdKind.ITEM_BARCODE:
                endpoint = f'/{module}/instances?query=item.barcode=={id_}'
            elif id_kind == IdKind.ITEM_ID:
                endpoint = f'/{module}/instances?query=item.id=={id_}'
            elif id_kind == IdKind.ITEM_HRID:
                endpoint = f'/{module}/instances?query=item.hrid=={id_}'

            # Given a holdings identifier.
            elif id_kind == IdKind.HOLDINGS_ID:
                holdings = self.related_records(id_, IdKind.HOLDINGS_ID, 'holdings',
                                                use_inventory, open_loans_only)
                if not holdings:
                    return []
                instance_id = holdings[0].data['instanceId']
                return self.related_records(instance_id, IdKind.INSTANCE_ID, 'instance',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.HOLDINGS_HRID:
                holdings = self.related_records(id_, IdKind.HOLDINGS_HRID, 'holdings',
                                                use_inventory, open_loans_only)
                if not holdings:
                    return []
                instance_id = holdings[0].data['instanceId']
                return self.related_records(instance_id, IdKind.INSTANCE_ID, 'instance',
                                            use_inventory, open_loans_only)

            # Given a loan identifier.
            elif id_kind == IdKind.LOAN_ID:
                loans = self.related_records(id_, IdKind.LOAN_ID, 'loan',
                                             use_inventory, open_loans_only)
                if not loans:
                    return []
                item_id = loans[0].data['itemId']
                return self.related_records(item_id, IdKind.ITEM_ID, 'instance',
                                            use_inventory, open_loans_only)

            # Given a user identifier.
            elif id_kind == IdKind.USER_ID:
                loans = self.related_records(id_, IdKind.USER_ID, 'loan',
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
                loans = self.related_records(id_, IdKind.USER_BARCODE, 'loan',
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
                raise RuntimeError(f'Unsupported combo: searching for {requested}'
                                   f' by {id_kind.value}')

        elif requested == RecordKind.LOAN:
            if id_kind == IdKind.LOAN_ID:
                endpoint = f'/loan-storage/loans/{id_}'
                data_extractor = partial(record_list, RecordKind.LOAN, None)
            elif id_kind == IdKind.USER_ID:
                endpoint = f'/loan-storage/loans?query=userId=={id_}&limit=10000'
                data_extractor = partial(record_list, RecordKind.LOAN, 'loans')
                loans = self.request(endpoint, converter = data_extractor)
                if not loans:
                    return []
                if open_loans_only:
                    loans = [ln for ln in loans if ln.data['status']['name'] == 'Open']
                return loans
            elif id_kind == IdKind.USER_BARCODE:
                # Can't do this one directly, so get a user id.
                user_records = self.related_records(id_, IdKind.USER_BARCODE, 'user',
                                                    use_inventory, open_loans_only)
                if not user_records:
                    return []
                user_id = user_records[0].id
                return self.related_records(user_id, IdKind.USER_ID, 'loan',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.ITEM_ID:
                endpoint = f'/loan-storage/loans?query=itemId=={id_}&limit=10000'
                data_extractor = partial(record_list, RecordKind.LOAN, 'loans')
                loans = self.request(endpoint, converter = data_extractor)
                if not loans:
                    return []
                if open_loans_only:
                    loans = [ln for ln in loans if ln.data['status']['name'] == 'Open']
                return loans
            elif id_kind in [IdKind.ITEM_BARCODE, IdKind.ITEM_HRID]:
                log(f'need to find item id for {id_kind} {id_}')
                records = self.related_records(id_, id_kind, 'item',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                item_id = records[0].id
                return self.related_records(item_id, IdKind.ITEM_ID, 'loan',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.INSTANCE_ID:
                # We have to get the item id's, and look up loans on each.
                records = self.related_records(id_, IdKind.INSTANCE_ID, 'item',
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
            elif id_kind in [IdKind.INSTANCE_HRID, IdKind.ACCESSION]:
                # Get the instance record & do this again with the instance id,
                # because we solved that case in the code above.
                records = self.related_records(id_, id_kind, 'instance',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                instance_id = records[0].id
                return self.related_records(instance_id, IdKind.INSTANCE_ID, 'loan',
                                            use_inventory, open_loans_only)
            elif id_kind in [IdKind.HOLDINGS_ID, IdKind.HOLDINGS_HRID]:
                # Can't go straight from holdings records to loans. Get items
                # under this holdings record, then get loans on those items.
                items = self.related_records(id_, id_kind, 'item',
                                             use_inventory, open_loans_only)
                loans = []
                for item in items:
                    loans += self.related_records(item.id, IdKind.ITEM_ID, 'loan',
                                                  use_inventory, open_loans_only)
                return loans
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested}'
                                   f' by {id_kind.value}')

        elif requested == RecordKind.USER:
            if id_kind == IdKind.USER_ID:
                endpoint = f'/users/{id_.zfill(10)}'
                data_extractor = partial(record_list, RecordKind.USER, None)
            elif id_kind == IdKind.USER_BARCODE:
                endpoint = f'/users?query=barcode={id_.zfill(10)}'
                data_extractor = partial(record_list, RecordKind.USER, 'users')
            elif id_kind == IdKind.ITEM_ID:
                records = self.related_records(id_, IdKind.ITEM_ID, 'loan',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                if 'userId' in records[0].data:
                    user_id = records[0].data['userId']
                    return self.related_records(user_id, IdKind.USER_ID, 'user',
                                                use_inventory, open_loans_only)
                else:
                    return []
            elif id_kind == IdKind.ITEM_HRID:
                records = self.related_records(id_, IdKind.ITEM_HRID, 'item',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                item_id = records[0].id
                return self.related_records(item_id, IdKind.ITEM_ID, 'user',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.ITEM_BARCODE:
                records = self.related_records(id_, IdKind.ITEM_BARCODE, 'item',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                item_id = records[0].id
                return self.related_records(item_id, IdKind.ITEM_ID, 'user',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.INSTANCE_ID:
                loans = self.related_records(id_, IdKind.INSTANCE_ID, 'loan',
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
                records = self.related_records(id_, IdKind.INSTANCE_HRID, 'instance',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                record_id = records[0].id
                return self.related_records(record_id, IdKind.INSTANCE_ID, 'user',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.ACCESSION:
                records = self.related_records(id_, IdKind.ACCESSION, 'instance',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                record_id = records[0].id
                return self.related_records(record_id, IdKind.INSTANCE_ID, 'user',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.LOAN_ID:
                records = self.related_records(id_, IdKind.LOAN_ID, 'loan',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                user_id = records[0].data['userId']
                return self.related_records(user_id, IdKind.USER_ID, 'user',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.HOLDINGS_ID:
                records = self.related_records(id_, IdKind.HOLDINGS_ID, 'holdings',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                instance_id = records[0].data['instanceId']
                return self.related_records(instance_id, IdKind.INSTANCE_ID, 'user',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.HOLDINGS_HRID:
                records = self.related_records(id_, IdKind.HOLDINGS_HRID, 'holdings',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                instance_id = records[0].data['instanceId']
                return self.related_records(instance_id, IdKind.INSTANCE_ID, 'user',
                                            use_inventory, open_loans_only)
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested}'
                                   f' by {id_kind.value}')

        elif requested == RecordKind.HOLDINGS:
            if id_kind == IdKind.HOLDINGS_ID:
                data_extractor = partial(record_list, RecordKind.HOLDINGS, None)
                endpoint = f'/holdings-storage/holdings/{id_}'
            elif id_kind == IdKind.HOLDINGS_HRID:
                data_extractor = partial(record_list, RecordKind.HOLDINGS,
                                         'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=hrid=={id_}&limit=10000'
            elif id_kind == IdKind.INSTANCE_ID:
                data_extractor = partial(record_list, RecordKind.HOLDINGS,
                                         'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=instanceId=={id_}&limit=10000'
            elif id_kind == IdKind.ITEM_BARCODE:
                data_extractor = partial(record_list, RecordKind.HOLDINGS,
                                         'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=item.barcode=={id_}&limit=10000'
            elif id_kind == IdKind.ITEM_ID:
                data_extractor = partial(record_list, RecordKind.HOLDINGS,
                                         'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=item.id=={id_}&limit=10000'
            elif id_kind == IdKind.ITEM_HRID:
                data_extractor = partial(record_list, RecordKind.HOLDINGS,
                                         'holdingsRecords')
                endpoint = f'/holdings-storage/holdings?query=item.hrid=={id_}&limit=10000'
            elif id_kind == IdKind.ACCESSION:
                data_extractor = partial(record_list, RecordKind.HOLDINGS,
                                         'holdingsRecords')
                inst_id = instance_id_from_accession(id_)
                endpoint = f'/holdings-storage/holdings?query=instanceId=={inst_id}&limit=10000'
            elif id_kind == IdKind.INSTANCE_HRID:
                records = self.related_records(id_, IdKind.INSTANCE_HRID, 'instance',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                record_id = records[0].id
                return self.related_records(record_id, IdKind.INSTANCE_ID, 'holdings',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.LOAN_ID:
                records = self.related_records(id_, IdKind.LOAN_ID, 'loan',
                                               use_inventory, open_loans_only)
                if not records:
                    return []
                item_id = records[0].data['itemId']
                return self.related_records(item_id, IdKind.ITEM_ID, 'holdings',
                                            use_inventory, open_loans_only)
            elif id_kind == IdKind.USER_ID:
                loans = self.related_records(id_, IdKind.USER_ID, 'loan',
                                             use_inventory, open_loans_only)
                if not loans:
                    return []
                holdings_records = []
                for loan in loans:
                    raise_for_interrupts()
                    holdings_records += self.related_records(loan.id, IdKind.LOAN_ID,
                                                             'holdings', use_inventory,
                                                             open_loans_only)
                return holdings_records
            elif id_kind == IdKind.USER_BARCODE:
                user = self.related_records(id_, IdKind.USER_BARCODE, 'user',
                                            use_inventory, open_loans_only)
                if not user:
                    return []
                return self.related_records(user.id, IdKind.USER_ID, 'holdings',
                                            use_inventory, open_loans_only)
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested}'
                                   f' by {id_kind.value}')

        else:
            raise RuntimeError(f'Unrecognized record type value {requested}')

        return self.request(endpoint, converter = data_extractor)


    def new_record(self, record):
        '''Create a new record using the data in 'record' & return the new id.
        This method reads the FOLIO credentials from environment variables.
        It will raise an exception with an error message if it fails.
        '''
        response = self._do('create', record)
        data = json.loads(response.text)
        if 'id' in data:
            log(f'newly created record has id {data["id"]}')
            return data['id']
        log('data returned for creation lacks an id: ' + response.text)
        raise FolioOpFailed('Unexpected data returned by FOLIO')


    def update_record(self, record):
        '''Update the given record.
        This method reads the FOLIO credentials from environment variables.
        It will raise an exception with an error message if it fails.
        '''
        self._do('update', record)


    def delete_record(self, record):
        '''Delete the given record.
        This method reads the FOLIO credentials from environment variables.
        It will raise an exception with an error message if it fails.
        '''
        self._do('delete', record)


    def _do(self, what, record):
        '''Do something to a record: create, update, or delete.
        This method reads the FOLIO credentials from environment variables.
        It will raise an exception with an error message if it fails.
        '''
        headers = {
            "x-okapi-token":  config('FOLIO_OKAPI_TOKEN'),
            "x-okapi-tenant": config('FOLIO_OKAPI_TENANT_ID'),
            "content-type":   "application/json",
        }
        log(f'requesting Folio to {what} record: ' + str(record))
        if what == 'create':
            endpoint = RecordKind.creation_endpoint(record.kind)
            url = config('FOLIO_OKAPI_URL') + endpoint
            op = 'post'
            data = json.dumps(record.data)
            (response, error) = net(op, url, headers = headers, data = data)
        elif what == 'update':
            endpoint = RecordKind.update_endpoint(record.kind)
            url = config('FOLIO_OKAPI_URL') + endpoint + '/' + record.id
            op = 'put'
            data = json.dumps(record.data)
            (response, error) = net(op, url, headers = headers, data = data)
        elif what == 'delete':
            endpoint = RecordKind.deletion_endpoint(record.kind)
            url = config('FOLIO_OKAPI_URL') + endpoint + '/' + record.id
            op = 'delete'
            (response, error) = net(op, url, headers = headers)
        else:
            log(f'unrecognized record actio {what}')
            raise FoliageException('Internal error – please report this')

        if not error and what == 'create':
            # Creation returns a record; other actions don't return anything.
            return response
        # Error from net() may be an exception object, but we have special
        # understanding of FOLIO return codes, so handle most cases ourselves.
        self._finish(response, error, f'{what}d record {record.id} using {url}')


# Misc. utilities
# .............................................................................

def instance_id_from_accession(accession_number):
    '''Return an instance id constructed from an accession number.'''
    # ANs end with a UUID where the dashes are replaced with periods. E.g.:
    # cit.oai.caltech.folio.ebsco.com.fs00001057.17c5c348.8796.4b11.90a8.6b31ff9509ed
    # UUID are 32 hex chars with 4 separators (= 36 chars total).
    return accession_number[-36:].replace('.', '-')


def unique_identifiers(text):
    '''Return a list of identifiers found in the text after some cleanup.'''
    lines = text.splitlines()
    ids = flattened(re.split(r'\s+|,+|;+|:+', line) for line in lines)
    ids = [id_.strip(r'''.'":?!/''') for id_ in ids]
    ids = [id_ for id_ in ids if not any(c in id_ for c in r'!@#$%^&*=\/')]
    ids = [id_ for id_ in ids if any(c.isnumeric() for c in id_)]
    return unique(filter(None, ids))


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
