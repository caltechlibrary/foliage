'''
folio.py: functions for interacting with FOLIO over the network API

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.exceptions import NoContent, ServiceFailure, RateLimitExceeded
from   commonpy.interrupt import wait
from   commonpy.string_utils import antiformat
from   commonpy.network_utils import net
from   decouple import config
from   enum import Enum
from   fastnumbers import isint
import json

if __debug__:
    from sidetrack import set_debug, log


# Internal constants.
# .............................................................................

# Number of times we retry an api call that return an HTTP error.
_MAX_RETRY = 3

# Time between retries, multiplied by retry number.
_RETRY_TIME_FACTOR = 2

# Endpoints for getting data.
_RECORD_ENDPOINTS = {
    'item'     : ('items', '/inventory/items?query=barcode%3D%3D{}'),
    'instance' : ('instances', '/inventory/instances?query=item.barcode%3D%3D{}'),
}


# Public data types.
# .............................................................................

class IdType(Enum):
    UNKNOWN    = 'unknown'
    BARCODE    = 'barcode'
    HRID       = 'hrid'
    ITEMID     = 'item id'
    INSTANCEID = 'instance id'
    HOLDINGSID = 'holdings id'


# Public class definitions.
# .............................................................................

class Folio():
    '''Interface to a FOLIO server using Okapi.'''

    def __init__(self):
        '''Create an interface to the FOLIO server.'''

        self.okapi_base_url = config('FOLIO_OKAPI_URL')
        self.okapi_token = config('FOLIO_OKAPI_TOKEN')
        self.tenant_id = config('FOLIO_OKAPI_TENANT_ID')


    def _folio(self, op, endpoint, convert = None, retry = 0):
        '''Invoke 'op' on 'endpoint', call 'convert' on it, return result.'''
        headers = {
            "x-okapi-token": self.okapi_token,
            "x-okapi-tenant": self.tenant_id,
            "content-type": "application/json",
        }

        request_url = self.okapi_base_url + endpoint
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
        raise RuntimeError(f'Problem contacting {endpoint}: {antiformat(error)}')


    def id_type(self, identifier):
        '''Infer the type of identifier given.'''
        if isint(identifier):
            return IdType.BARCODE
        elif '-' not in identifier:
            return IdType.HRID
        else:
            # Id's look the same. Try different cases to see if they exist
            # using the storage API, which is the fastest/lowest-level API.
            response = self._folio('get', f'/item-storage/items/{identifier}')
            if response:
                if response.status_code == 200:
                    return IdType.ITEMID
                elif response.status_code >= 500:
                    raise RuntimeError('FOLIO server error')

            response = self._folio('get', f'/instance-storage/instances/{identifier}')
            if response:
                if response.status_code == 200:
                    return IdType.INSTANCEID
                elif response.status_code >= 500:
                    raise RuntimeError('FOLIO server error')

            response = self._folio('get', f'/holdings-storage/holdings/{identifier}')
            if response:
                if response.status_code == 200:
                    return IdType.HOLDINGSID
                elif response.status_code >= 500:
                    raise RuntimeError('FOLIO server error')

            # We're out of ideas.
            return IdType.UNKNOWN


    def record(self, barcode, record_type):
        if record_type not in _RECORD_ENDPOINTS:
            raise RuntimeError(f'Unrecognized record_type value {record_type}')
        key = _RECORD_ENDPOINTS[record_type][0]
        endpoint = _RECORD_ENDPOINTS[record_type][1].format(barcode)

        def record_as_dict(response):
            if not response or not response.text:
                log(f'FOLIO returned no result for {barcode}')
                return None
            data_dict = json.loads(response.text)
            # Depending on the way we're getting it, the record might be
            # directly provided or it might be in a list of records.
            if not 'totalRecords' in data_dict:
                if 'title' in data_dict:
                    # It's a record directly and not a list of records.
                    return data_dict
                else:
                    raise RuntimeError('Unexpected data returned by FOLIO')
            elif data_dict['totalRecords'] == 0:
                log(f'got 0 records for {barcode}')
                return None
            elif data_dict['totalRecords'] > 1:
                total = data_dict['totalRecords']
                log(f'got {total} records for {barcode}')
                log(f'using only first value')
            return data_dict[key][0]

        result_dict = self._folio('get', endpoint, record_as_dict)
        if result_dict and 'id' not in result_dict:
            # Something's wrong if what we get back doesn't have an 'id' field.
            raise RuntimeError(f'No id in record returned from {endpoint}')
        return result_dict


    # https://s3.amazonaws.com/foliodocs/api/mod-inventory/p/inventory.html

    def operation(self, op, endpoint):
        '''Do 'op' on 'endpoint' and return a tuple (success, error_msg).'''

        def result_parser(response):
            if not response:
                return (False, '')
            elif 200 <= response.status_code < 300:
                return (True, None)
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
        return self._folio('get', endpoint, result_parser)
