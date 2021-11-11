'''
credentials.py: module for handling credentials for Foliage

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   collections import namedtuple
from   commonpy.interrupt import wait
from   decouple import config
import getpass
import json
import keyring
import os
from   pywebio.output import popup, close_popup, put_buttons
from   pywebio.pin import pin, put_input, put_actions, put_textarea
from   sidetrack import set_debug, log
import sys
import threading

if sys.platform.startswith('win'):
    import keyring.backends
    from keyring.backends.Windows import WinVaultKeyring
if sys.platform.startswith('darwin'):
    import keyring.backends
    from keyring.backends.OS_X import Keyring

from .ui import alert, warn, confirm


# Private constants.
# .............................................................................

_KEYRING = f'org.caltechlibrary.{__package__}'
'''The name of the keyring used to store server access credentials, if any.'''


# Public data types.
# .............................................................................

Credentials = namedtuple('Credentials', 'url tenant_id token')


# Public functions.
# .............................................................................

def credentials_from_file(creds_file):
    try:
        with open(creds_file, 'r') as f:
            return json.loads(creds_file)
    except Exception as ex:
        log(f'unable to read creds file: ' + str(ex))
    return None


def credentials_from_env(partial_ok = False):
    url       = config('FOLIO_OKAPI_URL', default = None)
    tenant_id = config('FOLIO_OKAPI_TENANT_ID', default = None)
    token     = config('FOLIO_OKAPI_TOKEN', default = None)
    creds     = Credentials(url = url, tenant_id = tenant_id, token = token)
    if credentials_complete(creds):
        log(f'credentials via config are complete')
        return creds
    elif not any([creds.url, creds.tenant_id, creds.token]):
        log(f'no credentials found by config')
        return None
    elif partial_ok:
        log(f'credentials via config are not complete but partial_ok = True')
        return creds
    return None


def credentials_from_user(warn_empty = True, initial_creds = None):
    event = threading.Event()
    clicked_ok = False

    def clk(val):
        nonlocal clicked_ok
        clicked_ok = val
        event.set()

    log(f'asking user for credentials')
    current = initial_creds or Credentials('', '', '')
    pins = [
        put_input('url',       label = 'OKAPI URL', value = current.url),
        put_input('tenant_id', label = 'Tenant id', value = current.tenant_id),
        put_textarea('token',  label = 'API token', value = current.token, rows = 4),
        put_buttons([
            {'label': 'Submit', 'value': True},
            {'label': 'Cancel', 'value': False, 'color': 'danger'},
        ], onclick = clk).style('float: right')
    ]
    popup(title = 'FOLIO credentials', content = pins, size = 'large', closable = False)

    event.wait()
    close_popup()
    wait(0.5)                           # Give time for popup to go away.

    if not clicked_ok:
        log(f'user cancelled out of credentials dialog')
        return initial_creds

    new_creds = Credentials(url = pin.url, tenant_id = pin.tenant_id, token = pin.token)
    if not credentials_complete(new_creds) and warn_empty:
        log(f'user provided incomplete credentials')
        if confirm('Cannot proceed without all credentials. Try again?'):
            return credentials_from_user(initial_creds = new_creds)

    log(f'got credentials from user')
    return new_creds


# Explanation about the weird way this is done: the Python keyring module
# only offers a single function for setting a value; ostensibly, this is
# intended to store a password associated with an identifier (a user name),
# and this identifier is expected to be obtained some other way, such as by
# using the current user's computer login name.  But, in our situation, we
# have multiple pieces of information we have to store (a user id and an api
# key).  The hackacious solution taken here is to concatenate the values into
# a single string used as the actual value stored.  The individual values are
# separated by a character that is unlikely to be part of any user-typed value.

def credentials_from_keyring(partial_ok = False, ring = _KEYRING):
    '''Look up the user's credentials.
    If partial_ok is False, return None if the keyring value is incomplete.'''
    if sys.platform.startswith('win'):
        keyring.set_keyring(WinVaultKeyring())
    if sys.platform.startswith('darwin'):
        keyring.set_keyring(Keyring())
    value = keyring.get_password(ring, getpass.getuser())
    if __debug__: log(f'got "{value}" from keyring {_KEYRING}')
    if value:
        parts = _decoded(value)
        if all(parts) or partial_ok:
            return Credentials(url = parts[0], tenant_id = parts[1], token = parts[2])
    return None


def save_credentials(creds, ring = _KEYRING):
    '''Save the user's credentials.'''
    if sys.platform.startswith('win'):
        keyring.set_keyring(WinVaultKeyring())
    if sys.platform.startswith('darwin'):
        keyring.set_keyring(Keyring())
    value = _encoded(creds.url, creds.tenant_id, creds.token)
    if __debug__: log(f'storing "{value}" to keyring {_KEYRING}')
    keyring.set_password(ring, getpass.getuser(), value)


def credentials_complete(creds):
    '''Return True if the given credentials are complete.'''
    return (creds and creds.url and creds.tenant_id and creds.token)


def use_credentials(creds):
    '''Set global environment variables for the credentials as given.'''
    os.environ['FOLIO_OKAPI_URL']       = creds.url
    os.environ['FOLIO_OKAPI_TENANT_ID'] = creds.tenant_id
    os.environ['FOLIO_OKAPI_TOKEN']     = creds.token


# Utility functions
# .............................................................................

_SEP = ''
'''Character used to separate multiple actual values stored as a single
encoded value string.  This character is deliberately chosen to be something
very unlikely to be part of a legitimate string value typed by user at a
shell prompt, because control-c is normally used to interrupt programs.
'''

def _encoded(url, tenant_id, token):
    return f'{url}{_SEP}{tenant_id}{_SEP}{token}'


def _decoded(value_string):
    return tuple(value_string.split(_SEP))
