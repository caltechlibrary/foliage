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
from   enum import Enum, EnumMeta
from   functools import partial
from   fastnumbers import isint
import json

if __debug__:
    from sidetrack import set_debug, log


# Public data types.
# .............................................................................

# The following class was based in part on the posting by user "Pierre D" at
# https://stackoverflow.com/a/65225753/743730 made on 2020-12-09.

class MetaEnum(EnumMeta):
    '''Meta class for enums that implements "contain" test ability.'''
    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        return True


class ExtendedEnum(Enum, metaclass = MetaEnum):
    '''Extend Enum class with a function allowing a test for containment.'''
    pass


class RecordKind(ExtendedEnum):
    ITEM     = 'item'
    INSTANCE = 'instance'
    HOLDINGS = 'holdings'
    USER     = 'user'
    LOAN     = 'loan'


class RecordIdKind(ExtendedEnum):
    UNKNOWN      = 'unknown'
    ITEM_BARCODE = 'item barcode'
    ITEM_ID      = 'item id'
    HRID         = 'hrid'
    INSTANCE_ID  = 'instance id'
    HOLDINGS_ID  = 'holdings id'
    ACCESSION    = 'accession number'
    USER_ID      = 'user id'
    USER_BARCODE = 'user barcode'
    LOAN_ID      = 'loan id'


class TypeKind(ExtendedEnum):
    ADDRESS             = 'addresstypes'
    ALT_TITLE           = 'alternative-title-types'
    CALL_NUMBER         = 'call-number-types'
    CLASSIFICATION      = 'classification-types'
    CONTRIBUTOR         = 'contributor-types'
    CONTRIBUTOR_NAME    = 'contributor-name-types'
    DEPARTMENT          = 'departments'
    GROUP               = 'groups'
    HOLDINGS            = 'holdings-types'
    HOLDINGS_NOTE       = 'holdings-note-types'
    HOLDINGS_SOURCE     = 'holdings-sources'
    ID                  = 'identifier-types'
    ILL_POLICY          = 'ill-policies'
    INSTANCE            = 'instance-types'
    INSTANCE_FORMAT     = 'instance-formats'
    INSTANCE_NOTE       = 'instance-note-types'
    INSTANCE_REL        = 'instance-relationship-types'
    INSTANCE_STATUS     = 'instance-statuses'
    ITEM_NOTE           = 'item-note-types'
    ITEM_DAMAGED_STATUS = 'item-damaged-statuses'
    LOAN                = 'loan-types'
    LOCATION            = 'locations'
    MATERIAL            = 'material-types'
    MODE_OF_ISSUANCE    = 'mode-of-issuance'
    NATURE_OF_CONTENT   = 'nature-of-content-terms'
    ORGANIZATION        = 'organizations/organizations'
    PROXYFOR            = 'proxiesfor'
    SERVICE_POINT       = 'service-points'
    SHELF_LOCATION      = 'shelf-locations'
    STATISTICAL_CODE    = 'statistical-code-types'


# Internal constants.
# .............................................................................

# Number of times we retry an api call that return an HTTP error.
_MAX_RETRY = 3

# Time between retries, multiplied by retry number.
_RETRY_TIME_FACTOR = 2

# Keys to look up the name field in id lists.
NAME_KEYS = {
    TypeKind.ADDRESS.value             : 'addressType',
    TypeKind.ALT_TITLE.value           : 'name',
    TypeKind.CALL_NUMBER.value         : 'name',
    TypeKind.CLASSIFICATION.value      : 'name',
    TypeKind.CONTRIBUTOR.value         : 'name',
    TypeKind.CONTRIBUTOR_NAME.value    : 'name',
    TypeKind.DEPARTMENT.value          : 'name',
    TypeKind.GROUP.value               : 'group',
    TypeKind.HOLDINGS.value            : 'name',
    TypeKind.HOLDINGS_NOTE.value       : 'name',
    TypeKind.HOLDINGS_SOURCE.value     : 'name',
    TypeKind.ID.value                  : 'name',
    TypeKind.ILL_POLICY.value          : 'name',
    TypeKind.INSTANCE.value            : 'name',
    TypeKind.INSTANCE_FORMAT.value     : 'name',
    TypeKind.INSTANCE_NOTE.value       : 'name',
    TypeKind.INSTANCE_REL.value        : 'name',
    TypeKind.INSTANCE_STATUS.value     : 'name',
    TypeKind.ITEM_NOTE.value           : 'name',
    TypeKind.ITEM_DAMAGED_STATUS.value : 'name',
    TypeKind.LOAN.value                : 'name',
    TypeKind.LOCATION.value            : 'name',
    TypeKind.MATERIAL.value            : 'name',
    TypeKind.MODE_OF_ISSUANCE.value    : 'name',
    TypeKind.NATURE_OF_CONTENT.value   : 'name',
    TypeKind.ORGANIZATION              : 'name',
    TypeKind.PROXYFOR.value            : 'name',
    TypeKind.SERVICE_POINT.value       : 'name',
    TypeKind.SHELF_LOCATION.value      : 'name',
    TypeKind.STATISTICAL_CODE.value    : 'name',
}


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
        raise error


    def record_id_type(self, identifier):
        '''Infer the type of identifier given.'''
        if isint(identifier) and len(identifier) > 7 and identifier.startswith('350'):
            log(f'recognized {identifier} as an item barcode')
            return RecordIdKind.ITEM_BARCODE
        elif identifier.startswith('clc') and '.' in identifier:
            log(f'recognized {identifier} as an accession number')
            return RecordIdKind.ACCESSION
        else:
            # Given a uuid, there's no way to ask Folio what kind it is, b/c
            # of Folio's microarchitecture & the lack of a central coordinating
            # authority.  So we have to ask different modules in turn.
            response = self._folio('get', f'/item-storage/items/{identifier}?limit=0')
            if response:
                if response.status_code == 200:
                    log(f'recognized {identifier} as an item id')
                    return RecordIdKind.ITEM_ID
                elif response.status_code >= 500:
                    raise RuntimeError('FOLIO server error')

            response = self._folio('get', f'/instance-storage/instances/{identifier}?limit=0')
            if response:
                if response.status_code == 200:
                    log(f'recognized {identifier} as an instance id')
                    return RecordIdKind.INSTANCE_ID
                elif response.status_code >= 500:
                    raise RuntimeError('FOLIO server error')

            response = self._folio('get', f'/holdings-storage/holdings/{identifier}?limit=0')
            if response:
                if response.status_code == 200:
                    log(f'recognized {identifier} as a holdings id')
                    return RecordIdKind.HOLDINGS_ID
                elif response.status_code >= 500:
                    raise RuntimeError('FOLIO server error')

            response = self._folio('get', f'/users/{identifier}?limit=0')
            if response:
                if response.status_code == 200:
                    log(f'recognized {identifier} as a user id')
                    return RecordIdKind.USER_ID
                elif response.status_code >= 500:
                    raise RuntimeError('FOLIO server error')

            response = self._folio('get', f'/users?query=barcode={identifier}&limit=0')
            if response:
                if response.status_code == 200:
                    # This endpoint always return a value, even when there are
                    # no hits, so we have to look inside.
                    data_dict = json.loads(response.text)
                    if 'totalRecords' in data_dict and int(data_dict['totalRecords']) > 0:
                        log(f'recognized {identifier} as a user barcode')
                        return RecordIdKind.USER_BARCODE
                elif response.status_code >= 500:
                    raise RuntimeError('FOLIO server error')

            response = self._folio('get', f'/loan-storage/loans/{identifier}?limit=0')
            if response:
                if response.status_code == 200:
                    log(f'recognized {identifier} as a loan id')
                    return RecordIdKind.LOAN_ID
                elif response.status_code >= 500:
                    raise RuntimeError('FOLIO server error')

            response = self._folio('get', f'/instance-storage/instances?query=hrid={identifier}&limit=0')
            if response:
                if response.status_code == 200:
                    log(f'recognized {identifier} as an hrid')
                    return RecordIdKind.HRID
                elif response.status_code >= 500:
                    raise RuntimeError('FOLIO server error')

            # We're out of ideas.
            return RecordIdKind.UNKNOWN


    def records(self, identifier, id_type, requested = None):
        def record_list(key, response):
            if not response or not response.text:
                log(f'FOLIO returned no result for {identifier}')
                return []
            data_dict = json.loads(response.text)
            if key:
                if not 'totalRecords' in data_dict:
                    if 'title' in data_dict:
                        # It's a record directly and not a list of records.
                        return [data_dict]
                    else:
                        raise RuntimeError('Unexpected data returned by FOLIO')
                log(f'got {data_dict["totalRecords"]} records for {identifier}')
                return data_dict[key]
            else:
                return [data_dict]

        # If we not given an explicit record type to retrieve, return the same
        # kind implied by the id type.
        if not requested:
            if id_type in [RecordIdKind.ITEM_ID, RecordIdKind.ITEM_BARCODE]:
                requested = 'item'
            elif id_type == RecordIdKind.HOLDINGS_ID:
                requested = 'holdings'
            elif id_type in [RecordIdKind.USER_ID, RecordIdKind.USER_BARCODE]:
                requested = 'user'
            else:
                requested = 'instance'

        # Figure out the appropriate API endpoint.
        if requested == 'item':
            data_extractor = partial(record_list, 'items')
            if id_type == RecordIdKind.ITEM_ID:
                endpoint = f'/inventory/items/{identifier}'
            elif id_type == RecordIdKind.ITEM_BARCODE:
                endpoint = f'/inventory/items?query=barcode=={identifier}'
            elif id_type == RecordIdKind.INSTANCE_ID:
                endpoint = f'/inventory/items?query=instance.id=={identifier}&limit=10000'
            elif id_type == RecordIdKind.HRID:
                endpoint = f'/inventory/items?query=instance.hrid=={identifier}&limit=10000'
            elif id_type == RecordIdKind.ACCESSION:
                inst_id = instance_id_from_accession(identifier)
                endpoint = f'/inventory/items?query=instance.id=={inst_id}&limit=10000'
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested} by {id_type.value}')
        elif requested == 'instance':
            data_extractor = partial(record_list, 'instances')
            if id_type == RecordIdKind.INSTANCE_ID:
                endpoint = f'/inventory/instances/{identifier}'
            elif id_type == RecordIdKind.ITEM_BARCODE:
                endpoint = f'/inventory/instances?query=item.barcode=={identifier}'
            elif id_type == RecordIdKind.ITEM_ID:
                endpoint = f'/inventory/instances?query=item.id=={identifier}'
            elif id_type == RecordIdKind.HRID:
                endpoint = f'/inventory/instances?query=hrid=={identifier}'
            elif id_type == RecordIdKind.ACCESSION:
                inst_id = instance_id_from_accession(identifier)
                endpoint = f'/inventory/instances/{inst_id}'
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested} by {id_type.value}')
        elif requested == 'holdings':
            data_extractor = partial(record_list, 'holdingsRecords')
            if id_type == RecordIdKind.HOLDINGS_ID:
                endpoint = f'/holdings-storage/holdings/{identifier}'
            elif id_type == RecordIdKind.INSTANCE_ID:
                endpoint = f'/holdings-storage/holdings?query=instanceId=={identifier}&limit=10000'
            elif id_type == RecordIdKind.ITEM_BARCODE:
                endpoint = f'/holdings-storage/holdings?query=item.barcode=={identifier}'
            elif id_type == RecordIdKind.ITEM_ID:
                endpoint = f'/holdings-storage/holdings?query=item.id=={identifier}'
            elif id_type == RecordIdKind.HRID:
                endpoint = f'/holdings-storage/holdings?query=hrid=={identifier}'
            elif id_type == RecordIdKind.ACCESSION:
                inst_id = instance_id_from_accession(identifier)
                endpoint = f'/holdings-storage/holdings?query=instanceId=={inst_id}&limit=10000'
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested} by {id_type.value}')
        elif requested == 'user':
            if id_type == RecordIdKind.USER_ID:
                endpoint = f'/users/{identifier}'
                data_extractor = partial(record_list, None)
            elif id_type == RecordIdKind.USER_BARCODE:
                endpoint = f'/users?query=barcode={identifier}'
                data_extractor = partial(record_list, 'users')

            # FIXME this returns loan records, which is not user records
            # elif id_type == RecordIdKind.ITEM_ID:
            #     endpoint = f'/circulation/loans?query=itemId={identifier}'
            #     data_extractor = partial(record_list, 'loans')

            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested} by {id_type.value}')
        elif requested == 'loan':
            if id_type == RecordIdKind.LOAN_ID:
                endpoint = f'/loan-storage/loans/{identifier}'
                data_extractor = partial(record_list, None)
            elif id_type == RecordIdKind.USER_ID:
                endpoint = f'/circulation/loans?query=userId=={identifier}'
                data_extractor = partial(record_list, 'loans')
            else:
                raise RuntimeError(f'Unsupported combo: searching for {requested} by {id_type.value}')
        else:
            raise RuntimeError(f'Unrecognized record type value {requested}')

        return self._folio('get', endpoint, data_extractor)


    def types(self, type_kind):
        '''Return a list of (name, id) tuples.'''
        if type_kind not in TypeKind:
            raise RuntimeError(f'Unknown type kind {type_kind}')

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
        name_key = NAME_KEYS[type_kind] if type_kind in NAME_KEYS else 'name'
        return [(item[name_key], item['id']) for item in type_list]


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
