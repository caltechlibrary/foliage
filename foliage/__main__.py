'''
__main__.py: main function for foliage.

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

import sys
from   sys import exit as exit
if sys.version_info <= (3, 8):
    print('foliage requires Python version 3.8 or higher,')
    print('but the current version of Python is ' +
          str(sys.version_info.major) + '.' + str(sys.version_info.minor) + '.')
    exit(1)

from   appdirs import AppDirs
from   collections import ChainMap
from   commonpy.data_utils import timestamp, pluralized
from   commonpy.file_utils import writable
from   commonpy.interrupt import config_interrupt
from   commonpy.network_utils import network_available
from   commonpy.string_utils import antiformat
from   decouple import config
from   getpass import getuser
from   fastnumbers import isint
import faulthandler
from   functools import partial
from   itertools import chain
import os
from   os import makedirs
from   os.path import exists, dirname, join, basename, abspath, realpath, isdir
import plac
import pywebio
# Default server is tornado, and tornado mucks with logging.
# aiohttp server does not.  Unfortunately, only tornado auto-reloads.
# from   pywebio.platform.aiohttp import start_server
from   pywebio import start_server
from   pywebio.input import input, select, checkbox, radio
from   pywebio.input import NUMBER, TEXT, input_update, input_group
from   pywebio.output import put_text, put_markdown, put_row, put_html
from   pywebio.output import toast, popup, close_popup, put_buttons, put_button, put_error
from   pywebio.output import use_scope, set_scope, clear, remove, put_warning
from   pywebio.output import put_success, put_info, put_table, put_grid, span
from   pywebio.output import put_tabs, put_image, put_scrollable, put_code, put_link
from   pywebio.output import put_processbar, set_processbar, put_loading
from   pywebio.output import put_column
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
from   pywebio.pin import put_textarea, put_radio, put_checkbox, put_select
from   pywebio.session import run_js, eval_js, download
from   sidetrack import set_debug, log
from   tornado.template import Template

from   .change_tab import ChangeTab
from   .credentials import credentials_from_user, credentials_from_keyring
from   .credentials import use_credentials, save_credentials, credentials_complete
from   .credentials import credentials_from_file, credentials_from_env
from   .delete_tab import DeleteTab
from   .enum_utils import MetaEnum, ExtendedEnum
from   .folio import Folio
from   .list_tab import ListTab
from   .lookup_tab import LookupTab
from   .other_tab import OtherTab
from   .ui import quit_app, reload_page, tell, alert, warn, confirm, notify
from   .ui import image_data, user_file, JS_CODE, CSS_CODE, alert, warn


# Internal constants.
# .............................................................................

_DIRS = AppDirs('Foliage', 'CaltechLibrary')
'''Platform-specific directories for Foliage data.'''

_TABS = [ListTab(), LookupTab(), ChangeTab(), DeleteTab(), OtherTab()]
'''List of tabs making up the Foliage application.'''


# Main program.
# .............................................................................

@plac.annotations(
    backup_dir = ('back up records to folder B before changes', 'option', 'b'),
    creds_file = ('read FOLIO credentials from .ini file C',    'option', 'c'),
    demo_mode  = ('demo mode: don\'t perform destructive ops',  'flag',   'd'),
    no_keyring = ('don\'t use keyring for credentials',         'flag',   'K'),
    port       = ('open browser on port P (default: 8080)',     'option', 'p'),
    version    = ('print program version info and exit',        'flag',   'V'),
    debug      = ('log debug output to "OUT" ("-" is console)', 'option', '@'),
)

def main(backup_dir = 'B', creds_file = 'C', demo_mode = False,
         no_keyring = False, port = 'P', version = False, debug = 'OUT'):
    '''Foliage: FOLIo chAnGe Editor, a tool to do bulk changes in FOLIO.

Credentials for FOLIO OKAPI access can be provided in a number of ways. The
sequence of methods it uses are as follows:

  1. If the --creds-file argument is used, and the given file contains
     complete credentials (OKAPI URL, tenant id, and OKAPI API token), then
     those credentials are used and nothing more is tried. (In other words,
     credentials given via --creds-file override everything else.) If the
     given file cannot be read or does not contain complete credentials, then
     it is an error and Foliage will quit.

  2. Else, if all three of the environment variables FOLIO_OKAPI_URL,
     FOLIO_OKAPI_TENANT_ID and FOLIO_OKAPI_TOKEN are set, it uses those
     credentials and nothing more is tried.

  3. Else, the credentials are looked up in the user's system keyring/keychain.
     If all 3 pieces of info are found (i.e., OKAPI URL, tenant id, and OKAPI
     API token), then those credentials are used.

  4. Else, it asks the user for the FOLIO_OKAPI_URL, FOLIO_OKAPI_TENANT_ID, a
     FOLIO login, and a password, and uses that combination to request an API
     token from FOLIO. Unless the --no-keyring argument is given, Foliage also
     stores the URL, tenant id, and token in the user's keyring/keychain so
     that it doesn't have to ask again in future runs. (The user's login and
     password are not stored.)

In normal situations, the first time a user runs Foliage, they will end up in
case #4 above (i.e., being asked for credentials so that Foliage can create
and store an API token), and then on subsequent runs, Foliage will not ask for
the credentials again.
'''

    # Process arguments and handle early exits --------------------------------

    if version:
        from foliage import print_version
        print_version()
        exit()

    config_debug(debug)                # Set up debugging before anything else.
    config_backup_dir(None if backup_dir == 'B' else backup_dir)
    config_credentials(None if creds_file == 'C' else creds_file, not no_keyring)
    config_port(8080 if port == 'P' else port)
    config_demo_mode(demo_mode)

    # Do the real work --------------------------------------------------------

    log('='*8 + f' started {timestamp()} ' + '='*8)
    log_config()
    exception = None
    try:
        pywebio.config(title = 'Foliage', js_code = JS_CODE, css_style = CSS_CODE)

        # This uses a custom index page template created by copying the PyWebIO
        # default and modifying it.
        here = realpath(dirname(__file__))
        with open(join(here, 'data', 'index.tpl')) as index_tpl:
            index_page_template = Template(index_tpl.read())
        pywebio.platform.utils._index_page_tpl = index_page_template

        # cdn parameter makes it load PyWebIO JS code from our local copy.
        start_server(foliage, auto_open_webbrowser = True, cdn = False,
                     port = os.environ['PORT'], debug = os.environ['DEBUG'])
    except KeyboardInterrupt as ex:
        # Catch it, but don't treat it as an error; just stop execution.
        log(f'keyboard interrupt received')
        pass
    except Exception as ex:
        exception = sys.exc_info()

    # Try to deal with exceptions gracefully ----------------------------------

    if exception:
        from traceback import format_exception
        summary = antiformat(exception[1])
        details = antiformat(''.join(format_exception(*exception)))
        log(f'Exception: {summary}\n{details}')
        alert('Error: ' + summary, False)
        # This is a sledgehammer, but it kills everything, including ongoing
        # network get/post. I have not found a more reliable way to interrupt.
        os._exit(1)

    # And exit ----------------------------------------------------------------

    log('Exiting normally.')
    log('_'*8 + f' stopped {timestamp()} ' + '_'*8)


# Main page creation function.
# .............................................................................

def foliage():
    log(f'generating main Foliage page')
    put_image(image_data('foliage-icon.png'), width='85px').style('float: left')
    put_image(image_data('foliage-icon-r.png'), width='85px').style('float: right')
    put_html('<h1 class="text-center">Foliage</h1>')
    put_html('<div class="font-italic text-muted font-weight-light text-center mx-auto">'
             ' Foliage ("FOLIo chAnGe Editor") is an app that runs'
             ' on your computer and lets you perform FOLIO operations over'
             ' the network. This web page is its user interface.'
             '</div>').style('width: 85%')
    put_tabs([tab.contents() for tab in _TABS]).style('padding-bottom: 16px')
    put_button('Quit Foliage', color = 'warning', onclick = lambda: quit_app()
               ).style('position: absolute; bottom: 20px;'
                       + 'left: calc(50% - 3.5em); z-index: 2')
    if config('DEMO_MODE', cast = bool):
        put_warning('Demo mode in effect').style(
            'position: absolute; left: calc(50% - 5.5em); width: 11em;'
            + 'height: 25px; padding: 0 10px; top: 0; z-index: 2')

    # Make sure we have a network before trying to test Folio creds.
    if not network_available:
        notify('No network -- cannot proceed.')
        quit_app(ask_confirm = False)

    creds = credentials_from_env()
    if not credentials_complete(creds):
        creds = credentials_from_user(initial_creds = creds)
        if not credentials_complete(creds):
            notify('Unable to proceed without complete credentials. Quitting.')
            quit_app(ask_confirm = False)
        if config('USE_KEYRING', cast = bool):
            save_credentials(creds)
            tell('FOLIO credentials obtained and stored.')
    use_credentials(creds)
    if not Folio.validated_credentials():
        notify('Invalid FOLIO credentials. Quitting.')
        quit_app(ask_confirm = False)

    watchers  = dict(ChainMap(*[tab.pin_watchers() for tab in _TABS]))
    pin_names = list(watchers.keys())
    log(f'entering pin handler loop for pins {pin_names}')
    while True:
        # Block, waiting for a change event on any of the pins being watched.
        changed = pin_wait_change(pin_names)
        # Find handler associated w/ pin name & call it with value from event.
        name = changed["name"]
        log(f'invoking pin callback for {name}')
        watchers[name](changed['value'])


# Miscellaneous utilities local to this module.
# .............................................................................

def config_debug(debug_arg):
    '''Takes the value of the --debug flag & returns a tuple (bool, log_file).
    The tuple values represent whether --debug was given a value other than
    the default, and the destination log file for debug output.
    '''

    log_file = None
    try:
        if debug_arg == 'OUT':
            # The --debug flag was not given, so turn on only basic logging.
            # Store the debug log in user's log directory.
            log_dir = _DIRS.user_log_dir
            log_file = join(log_dir, 'log.txt')
            if not exists(log_dir):
                makedirs(log_dir)
            with open(log_file, 'w'):
                # Empty out the file for each new run.
                pass
        else:
            # We were given --debug explicitly.  Turn on all debug features.
            if debug_arg != '-':
                log_file = debug_arg
                log_dir = dirname(log_file)
                if not writable(log_dir):
                    alert(f'Can\'t write debug ouput in {log_dir}', False)
                    exit()
            faulthandler.enable()
            if not sys.platform.startswith('win'): # Can't use next part on Win
                import signal
                from boltons.debugutils import pdb_on_signal
                pdb_on_signal(signal.SIGUSR1)

            warn('Debug & auto-reload are on. "kill -USR1 pid" for pdb.', False)

            # Turn on debug logging in PyWebIO & Tornado. That ends up enabling
            # logging in hpack, which is too much, so turn that off separately.
            import logging
            logging.root.setLevel(logging.DEBUG)
            logging.getLogger('hpack').setLevel(logging.INFO)

        # Turn on debug tracing to the destination we ended up deciding to use.
        set_debug(True, log_file or '-')
    except PermissionError:
        warn(f'Permission denied creating log file {antiformat(log_file)}', False)
    except FileNotFoundError:
        warn(f'Cannot write log file {antiformat(log_file)}', False)
    except KeyboardInterrupt:
        # Need to catch this separately or else it will end up ignored by
        # virtue of the next clause catching all Exceptions.
        exit()
    except Exception as ex:
        warn(f'Unable to create log file {antiformat(log_file)}', False)

    # Make settings accessible in other parts of the program.
    os.environ['DEBUG'] = str(debug_arg != 'OUT')
    os.environ['LOG_FILE'] = (log_file or '-')


def config_backup_dir(backup_dir):
    if not backup_dir:
        backup_dir = config('BACKUP_DIR', default = _DIRS.user_log_dir)
    if exists(backup_dir) and not isdir(backup_dir):
        alert(f'Not a directory: {antiformat(backup_dir)}', False)
        exit(1)
    elif not writable(backup_dir):
        alert(f'Cannot write in backup directory: {antiformat(backup_dir)}', False)
        exit(1)
    if not exists(backup_dir):
        log(f'creating backup directory {antiformat(backup_dir)}')
        try:
            makedirs(backup_dir)
        except OSError as ex:
            log(f'failed to create {antiformat(backup_dir)}: ' + str(ex))
            alert(f'Unable to create backup directory {backup_dir}', False)
            exit(1)
    os.environ['BACKUP_DIR'] = backup_dir


def config_credentials(creds_file, use_keyring):
    creds = None
    if creds_file:
        if not exists(creds_file):
            alert(f'Credentials file does not exist: {creds_file}', False)
            exit(1)
        if not readable(creds_file):
            alert(f'Credentials file not readable: {creds_file}', False)
            exit(1)
        creds = credentials_from_file(creds_file)
        if not creds:
            alert(f'Failed to read credentials from {creds_file}', False)
            exit(1)
        if not credentials_complete(creds):
            # Consider it an error to be told to use a file and it's incomplete
            alert(f'Incomplete credentials in {creds_file}', False)
            exit(1)
    if not creds:
        creds = credentials_from_env()
    keyring_creds = None
    if (not creds or not credentials_complete(creds)) and use_keyring:
        keyring_creds = credentials_from_keyring(partial_ok = True)
        if credentials_complete(keyring_creds):
            creds = keyring_creds
    if creds:
        use_credentials(creds)
        # We got credentials but not from the keyring. Save them.
        if not keyring_creds and use_keyring:
            save_credentials(creds)
    os.environ['USE_KEYRING'] = str(use_keyring)
    os.environ['CREDS_FILE'] = creds_file or 'None'


def config_demo_mode(demo_mode):
    os.environ['DEMO_MODE'] = str(demo_mode)
    if demo_mode:
        warn('Demo mode is on -- changes to FOLIO will NOT be made', False)


def config_port(port):
    if not isint(port):
        alert(f'Port number value is not an integer: antiformat(port)', False)
        exit(1)
    os.environ['PORT'] = str(port)


def log_config():
    log(f'backup_dir  = {config("BACKUP_DIR")}')
    log(f'log_file    = {config("LOG_FILE")}')
    log(f'creds_file  = {config("CREDS_FILE")}')
    log(f'use_keyring = {config("USE_KEYRING")}')
    log(f'port        = {config("PORT")}')
    log(f'demo_mode   = {config("DEMO_MODE")}')


# Main entry point.
# .............................................................................

# The following entry point definition is for the console_scripts keyword
# option to setuptools.  The entry point for console_scripts has to be a
# function that takes zero arguments.
def console_scripts_main():
    plac.call(main)

# The following allows users to invoke this using "python3 -m handprint".
if __name__ == '__main__':
    plac.call(main)
