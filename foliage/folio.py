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
import json

if __debug__:
    from sidetrack import set_debug, log


# Internal constants
# .............................................................................

_RECORD_ENDPOINTS = {
    'items'     : '/inventory/items?query=barcode%3D%3D{}',
    'instances' : '/inventory/instances?query=item.barcode%3D%3D{}',
#    'holdings'  : '/inventory/holdings?query=item.barcode%3D%3D{}',
}

# Number of times we retry an api call that return an HTTP error.
_MAX_RETRY = 3

# Time between retries, multiplied by retry number.
_RETRY_TIME_FACTOR = 2


# Class definition.
# .............................................................................

class Folio():
    '''Interface to a FOLIO server using Okapi.'''

    def __init__(self):
        '''Create an interface to the FOLIO server.'''

        self.okapi_base_url = config('FOLIO_OKAPI_URL')
        self.okapi_token = config('FOLIO_OKAPI_TOKEN')
        self.tenant_id = config('FOLIO_OKAPI_TENANT_ID')


    def _folio(self, op, endpoint, convert, retry = 0):
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
            return convert(response)
        elif isinstance(error, NoContent):
            log(f'got empty content from {request_url}')
            return convert(None)
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


    def record(self, barcode, record_type):
        if record_type not in _RECORD_ENDPOINTS:
            raise RuntimeError(f'Unrecognized record_type value {record_type}')

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
            return data_dict[record_type][0]

        endpoint = _RECORD_ENDPOINTS[record_type].format(barcode)
        return self._folio('get', endpoint, record_as_dict)
