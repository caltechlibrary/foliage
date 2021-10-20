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

RECORD_ENDPOINTS = {
    'items'     : '/inventory/items?query=barcode%3D%3D{}',
    'instances' : '/inventory/instances?query=item.barcode%3D%3D{}',
#    'holdings'  : '/inventory/holdings?query=item.barcode%3D%3D{}',
}


# Exported functions
# .............................................................................

def folio(operation, endpoint, result_parser, retry = 0):
    '''Do a GET on "endpoint" & return result of calling result_parser on it.'''
    headers = {
        "x-okapi-token": config('FOLIO_OKAPI_TOKEN'),
        "x-okapi-tenant": config('FOLIO_OKAPI_TENANT_ID'),
        "content-type": "application/json",
    }

    request_url = config('FOLIO_OKAPI_URL') + endpoint
    (response, error) = net(operation, request_url, headers = headers)
    if not error:
        log(f'got result from {request_url}')
        return result_parser(response)
    elif isinstance(error, NoContent):
        log(f'got empty content from {request_url}')
        return result_parser(None)
    elif isinstance(error, RateLimitExceeded):
        retry += 1
        if retry > 3:
            raise FolioError(f'Rate limit exceeded for {request_url}')
        else:
            # Wait and then call ourselves recursively.
            log(f'hit rate limit; pausing 2s')
            wait(2)
            return folio(operation, endpoint, result_parser, retry = retry)
    else:
        raise RuntimeError(f'Problem contacting {endpoint}: {antiformat(error)}')


def json_for_barcode(barcode, record_type):
    if record_type not in RECORD_ENDPOINTS:
        raise RuntimeError(f'Unrecognzied record_type value {record_type}')

    def parser(resp):
        if not resp or not resp.text:
            log(f'FOLIO returned no result for {barcode}')
            return None
        data_dict = json.loads(resp.text)
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

    return folio('get', RECORD_ENDPOINTS[record_type].format(barcode), parser)
