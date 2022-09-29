'''
credentials.py: module for handling credentials for Foliage

Reading credentials
-------------------

This module implements storage and retrieval of credentials needed for the user
to interact with FOLIO.  It supports multiple ways of reading the creds:

- from environment variables
- from a .ini style file
- from a user interface dialog

Storing credentials
-------------------

The Foliage code only stores credentials outside of itself in one way: by
writing a combination of the FOLIO token, FOLIO tenant id, and FOLIO OKAPI URL
under the key "org.caltechlibrary.foliage" in the user's system keyring.
The values are never written to a file by Foliage.

Passing credentials around within Foliage
-----------------------------------------

The way credentials are communicated to the FOLIO functions (in folio.py) is
slightly unobvious.  The credentials are set via environment variables in the
Foliage process (see use_credentials() below) so that they're available to
the folio.py functions without having to pass around a variable holding them.
It's also a simpler alternative to keeping a singleton global object to hold
the credentials data.

When other functions below need to pass credentials around (e.g., when first
reading them in __main__.py), they're generally passed around in the form of a
named tuple, called (in a very imaginative fashion) "Credentials".  That's
done because while credentials are being configured or changed, the flow of
information is more clear when it's done point-to-point, via arguments.

Copyright
---------

Copyright (c) 2021-2022 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   collections import namedtuple
from   commonpy.interrupt import wait
from   decouple import Config, RepositoryIni, RepositoryEmpty, config
import getpass
import keyring
import os
from   pywebio.output import popup, close_popup, put_buttons, put_markdown
from   pywebio.output import put_loading
from   pywebio.pin import pin, put_input
from   sidetrack import log
import sys
import threading

if sys.platform.startswith('win'):
    import keyring.backends
    from keyring.backends.Windows import WinVaultKeyring
if sys.platform.startswith('darwin'):
    import keyring.backends
    from keyring.backends.OS_X import Keyring

from foliage.folio import Folio
from foliage.ui import confirm, note_info, notify


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
    '''Return a Credentials object created from values in creds_file.

    The credentials file must be in ".ini" format, like this:

    [settings]
    FOLIO_OKAPI_URL = .....
    FOLIO_OKAPI_TENANT_ID = .....
    FOLIO_OKAPI_TOKEN = .....
    '''
    try:
        config_file = Config(RepositoryIni(source = creds_file))
    except Exception as ex:             # noqa: PIE786
        log('unable to read given creds file: ' + str(ex))
        return None
    return _creds_from_source(config_file, str(creds_file))


def credentials_from_env():
    '''Return a Credentials object created from environment variables.

    This checks for the following environment variables:

      FOLIO_OKAPI_URL
      FOLIO_OKAPI_TENANT_ID
      FOLIO_OKAPI_TOKEN
    '''
    return _creds_from_source(Config(RepositoryEmpty()), 'environment')


def credentials_from_user(warn_empty = True, initial_creds = None):
    '''Ask user for info needed to create a token & return a Credentials obj.'''

    event = threading.Event()
    clicked_ok = False

    def clk(val):
        nonlocal clicked_ok
        clicked_ok = val
        event.set()

    log('asking user for credentials')
    current = initial_creds or Credentials('', '', '')
    pins = [
        put_markdown('_This information is needed to create a FOLIO API token.'
                     ' Your FOLIO login & password will_'
                     ' **not** _be stored after this form disappears; only'
                     ' the token, URL and tenant id will be stored._'),
        put_input('user',      label = 'FOLIO user name'),
        put_input('password',  label = 'FOLIO password', type = 'password'),
        put_input('url',       label = 'OKAPI URL', value = current.url),
        put_input('tenant_id', label = 'Tenant id', value = current.tenant_id),
        put_buttons([
            {'label': 'Submit', 'value': True},
            {'label': 'Cancel', 'value': False, 'color': 'danger'},
        ], onclick = clk).style('float: right')
    ]
    popup(title = 'FOLIO credentials', content = pins, size = 'medium',
          closable = False)

    event.wait()
    close_popup()
    wait(0.5)                           # Give time for popup to go away.

    if not clicked_ok:
        log('user cancelled out of credentials dialog')
        return initial_creds

    if pin.url:                         # Remove '/' if the user included it.
        pin.url = pin.url.rstrip('/')

    if not all([pin.url, pin.tenant_id, pin.user, pin.password]):
        if warn_empty:
            log('user provided incomplete credentials')
            if confirm('Cannot proceed without all credentials. Try again?'):
                tmp = Credentials(url = pin.url, tenant_id = pin.tenant_id, token = None)
                return credentials_from_user(initial_creds = tmp)
        else:
            return None

    with put_loading():
        token, error = Folio.new_token(url = pin.url, tenant_id = pin.tenant_id,
                                       user = pin.user, password = pin.password)

    if error:
        notify('Failed to get a token: ' + error + '.')
        return None
    else:
        note_info('New FOLIO API token obtained.')

    log('got credentials from user')
    return Credentials(url = pin.url, tenant_id = pin.tenant_id, token = token)


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
        log('using windows keyring vault')
        keyring.set_keyring(WinVaultKeyring())
    if sys.platform.startswith('darwin'):
        log('using macos keyring')
        keyring.set_keyring(Keyring())
    log(f'trying to read value from {ring}')
    try:
        value = keyring.get_password(ring, getpass.getuser())
    except Exception as ex:             # noqa: PIE786
        log('exception trying to get password from keyring: ' + str(ex))
        return None
    if value:
        log(f'got credentials from keyring {ring}')
        parts = _decoded(value)
        if all(parts) or partial_ok:
            return Credentials(url = parts[0], tenant_id = parts[1], token = parts[2])
    log(f'did not find a value in keyring {ring}')
    return None


def use_credentials(creds):
    '''Set run-time environment credentials and save them to the keyring.'''
    log('setting environment variables for credentials')
    os.environ['FOLIO_OKAPI_URL']       = creds.url
    os.environ['FOLIO_OKAPI_TENANT_ID'] = creds.tenant_id
    os.environ['FOLIO_OKAPI_TOKEN']     = creds.token
    if config('USE_KEYRING', cast = bool):
        keyring_creds = credentials_from_keyring()
        if creds != keyring_creds:
            _store_credentials(creds)


def current_credentials():
    url       = config('FOLIO_OKAPI_URL', default = None)
    tenant_id = config('FOLIO_OKAPI_TENANT_ID', default = None)
    token     = config('FOLIO_OKAPI_TOKEN', default = None)
    return Credentials(url = url, tenant_id = tenant_id, token = token)


def credentials_complete(creds):
    '''Return True if the given credentials are complete.'''
    return (creds and creds.url and creds.tenant_id and creds.token)


# Private helper functions.
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


def _creds_from_source(source = None, where = ''):
    if not source:
        return None
    url       = source.get('FOLIO_OKAPI_URL', default = None)
    tenant_id = source.get('FOLIO_OKAPI_TENANT_ID', default = None)
    token     = source.get('FOLIO_OKAPI_TOKEN', default = None)
    if not any([url, tenant_id, token]):
        log(f'no credentials found in {where}')
        return None
    creds = Credentials(url = url, tenant_id = tenant_id, token = token)
    complete = 'complete' if credentials_complete(creds) else 'not complete'
    log(f'credentials in {where} are {complete}')
    return creds


def _store_credentials(creds, ring = _KEYRING):
    '''Save the user's credentials.'''
    if sys.platform.startswith('win'):
        keyring.set_keyring(WinVaultKeyring())
    if sys.platform.startswith('darwin'):
        keyring.set_keyring(Keyring())
    value = _encoded(creds.url, creds.tenant_id, creds.token)
    log(f'storing credentials to keyring {_KEYRING}')
    keyring.set_password(ring, getpass.getuser(), value)
