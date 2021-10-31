'''
credentials.py: module for handling credentials for Foliage
'''

from   commonpy.interrupt import wait
import getpass
import keyring
from   pywebio.output import popup, close_popup, put_buttons
from   pywebio.pin import pin, put_input, put_actions, put_textarea
from   sidetrack import set_debug, log
import sys
import threading
from   validators.url import url as valid_url

if sys.platform.startswith('win'):
    import keyring.backends
    from keyring.backends.Windows import WinVaultKeyring
if sys.platform.startswith('darwin'):
    import keyring.backends
    from keyring.backends.OS_X import Keyring

from .ui import alert, warn, confirm


# Global constants.
# .............................................................................

_KEYRING = f'org.caltechlibrary.{__package__}'
'''The name of the keyring used to store server access credentials, if any.'''


# Main functions.
# .............................................................................

def credentials_from_file(creds_file):
    pass


def credentials_from_user(warn_empty = True, use_creds = None):
    event = threading.Event()
    confirmed_form = None

    def clk(val):
        nonlocal confirmed_form
        confirmed_form = val
        event.set()

    tenant_id = url = token = ''
    current_creds = use_creds or credentials_from_keyring()
    if current_creds:
        tenant_id = current_creds['tenant_id']
        url = current_creds['url']
        token = current_creds['token']

    log(f'asking user for credentials')
    pins = [
        put_input('tenant_id', label = 'Tenant id', value = tenant_id),
        put_input('url',       label = 'OKAPI URL', value = url),
        put_textarea('token',  label = 'OKAPI API token', value = token, rows = 4),
        put_buttons([
            {'label': 'Submit', 'value': True},
            {'label': 'Cancel', 'value': False, 'color': 'danger'},
        ], onclick = clk).style('float: right')
    ]
    popup(title = 'FOLIO credentials', content = pins, size = 'large', closable = False)

    event.wait()
    close_popup()
    wait(0.5)

    if not all([pin.tenant_id, pin.url, pin.token]):
        if not warn_empty:
            return None
        if confirm('Cannot proceed without all FOLIO credentials. Try again?'):
            return credentials_from_user()

    value_dict = {'tenant_id': pin.tenant_id, 'url': pin.url, 'token': pin.token}
    if not valid_url(pin.url):
        alert(f'Not a valid URL: {pin.url}')
        return credentials_from_user(use_creds = value_dict)

    return value_dict if all(value_dict.values()) else None


def credentials_from_keyring():
    creds = keyring_credentials()
    if all(creds):
        return {'url': creds[1], 'tenant_id': creds[0], 'token': creds[2]}
    else:
        return None


def save_credentials(creds):
    stored_creds = keyring_credentials()
    if stored_creds == (creds['url'], creds['tenant_id'], creds['token']):
        log(f'new credentials are the same as saved credentials')
        return
    log(f'saving credentials to keyring')
    save_keyring_credentials(creds['url'], creds['tenant_id'], creds['token'])


# Utility functions
# .............................................................................

# Explanation about the weird way this is done: the Python keyring module
# only offers a single function for setting a value; ostensibly, this is
# intended to store a password associated with an identifier (a user name),
# and this identifier is expected to be obtained some other way, such as by
# using the current user's computer login name.  But, in our situation, we
# have multiple pieces of information we have to store (a user id and an api
# key).  The hackacious solution taken here is to concatenate the values into
# a single string used as the actual value stored.  The individual values are
# separated by a character that is unlikely to be part of any user-typed value.

def keyring_credentials(ring = _KEYRING):
    '''Looks up the user's credentials.'''
    if sys.platform.startswith('win'):
        keyring.set_keyring(WinVaultKeyring())
    if sys.platform.startswith('darwin'):
        keyring.set_keyring(Keyring())
    value = keyring.get_password(ring, getpass.getuser())
    if __debug__: log(f'got "{value}" from keyring {_KEYRING}')
    return _decoded(value) if value else None


def save_keyring_credentials(url, tenant_id, token, ring = _KEYRING):
    '''Saves the user's credentials.'''
    if sys.platform.startswith('win'):
        keyring.set_keyring(WinVaultKeyring())
    if sys.platform.startswith('darwin'):
        keyring.set_keyring(Keyring())
    value = _encoded(url, tenant_id, token)
    if __debug__: log(f'storing "{value}" to keyring {_KEYRING}')
    keyring.set_password(ring, getpass.getuser(), value)


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
