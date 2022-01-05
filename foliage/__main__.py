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
from   commonpy.exceptions import Interrupted
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

import foliage
from   foliage import __version__
from   foliage.change_tab import ChangeTab
from   foliage.credentials import credentials_from_user, credentials_from_keyring
from   foliage.credentials import use_credentials, credentials_complete
from   foliage.credentials import credentials_from_file, credentials_from_env
from   foliage.delete_tab import DeleteTab
from   foliage.enum_utils import MetaEnum, ExtendedEnum
from   foliage.folio import Folio
from   foliage.list_tab import ListTab
from   foliage.lookup_tab import LookupTab
from   foliage.other_tab import OtherTab
from   foliage.system_widget import SystemWidget
from   foliage.ui import quit_app, reload_page, confirm, notify, inside_pyinstaller_app
from   foliage.ui import note_info, note_warn, note_error, tell_success, tell_failure
from   foliage.ui import image_data, user_file, JS_CODE, CSS_CODE
from   foliage.ui import close_splash_screen


# Internal constants.
# .............................................................................

_DIRS = AppDirs('Foliage', 'CaltechLibrary')
'''Platform-specific directories for Foliage data.'''

_TABS = [LookupTab(), ChangeTab(), DeleteTab(), ListTab(), OtherTab()]
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
    no_widget  = ('don\'t run the taskbar/system tray widget',  'flag',   'W'),
    debug      = ('log debug output to "OUT" ("-" is console)', 'option', '@'),
)

def main(backup_dir = 'B', creds_file = 'C', demo_mode = False,
         no_keyring = False, port = 'P', version = False, no_widget = False,
         debug = 'OUT'):
    '''
Foliage (FOLIo chAnGe Editor) is a tool to do bulk changes in FOLIO. It allows
a user to look up records of various kinds, perform bulk changes in the values
of record fields, delete records, and more. It communicates with a FOLIO server
using the OKAPI network API.

FOLIO credentials
~~~~~~~~~~~~~~~~~

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

The form of the interface
~~~~~~~~~~~~~~~~~~~~~~~~~

Although Foliage is a desktop application and not a web service, it uses a
web page as its user interface &ndash; it opens a page in a browser on your
computer, letting you interact with the program through the familiar elements
of a web page. All the while, Foliage runs locally on your computer. When you
start Foliage normally (or after it shows the one-time credentials screen,
described below), your browser should present a page that has the title
"Foliage" and is organized into five areas of functionality accessed by
clicking on the row of tabs near the top: (1) "Look up records" (the first
one shown when Foliage starts up), (2) "Change records", (3) "Delete
records", (4) "List UUIDs", and (5) "Other".

Taskbar/menubar widget
~~~~~~~~~~~~~~~~~~~~~~

When Foliage starts up, it provides an icon in the Windows taskbar or the
macOS system tray (depending on your operating system). The icon serves as a
reminder that Foliage is running, and offers a single menu option (for
quitting Foliage). The menu is accssed by right-clicking the widget on
Windows or left-clicking it on macOS.

To prevent the startup of the widget process, run Foliage with the --no-widget
command-line option.

Additional command-line arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The default port for the local web server started by Foliage is 8080.  To
change this port, you can use the option --port followed by a port number.

If given the -V option, this program will print the version and other
information, and exit without doing anything else.

If given the -@ argument, this program will output a detailed trace of what it
is doing. The debug trace will be sent to the given destination, which can
be '-' to indicate console output, or a file path to send the output to a file.

Command-line arguments summary
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

    # Process arguments -------------------------------------------------------

    if version:
        from foliage import print_version
        print_version()
        exit()

    config_debug(debug)                # Set up debugging before going further.

    log('='*8 + f' started {timestamp()} ' + '='*8)
    os.environ['FOLIAGE_GUI_STARTED'] = 'False'

    config_signals()
    config_backup_dir(None if backup_dir == 'B' else backup_dir)
    config_credentials(None if creds_file == 'C' else creds_file, not no_keyring)
    config_port(8080 if port == 'P' else port)
    config_demo_mode(demo_mode)

    log_config()

    # Do the real work --------------------------------------------------------

    exception = exception_info = widget = None
    try:
        log('configuring PyWebIO server')
        pywebio.config(title = 'Foliage', description = 'FOLIo chAnGe Editor',
                       js_code = JS_CODE, css_style = CSS_CODE)

        # This uses a custom index page template that was created by copying
        # the PyWebIO default and modifying it.
        here = realpath(dirname(__file__))
        index_tpl = join(here, 'data', 'index.tpl')
        with open(index_tpl, encoding = 'utf-8') as index_tpl:
            log(f'reading index page template {index_tpl}')
            index_page_template = Template(index_tpl.read())
        pywebio.platform.utils._index_page_tpl = index_page_template

        # Start the widget outside the PyWebIO app so we can stop it later.
        widget = SystemWidget() if not no_widget else None

        # cdn = False makes it load PyWebIO JS code from our local copy.
        log('starting PyWebIO server')
        foliage = partial(foliage_page, widget)
        start_server(foliage, auto_open_webbrowser = True, cdn = False,
                     port = os.environ['PORT'], debug = os.environ['DEBUG'])
    except KeyboardInterrupt as ex:
        # Catch it, but don't treat it as an error; just stop execution.
        log('keyboard interrupt received')
        pass
    except SystemExit as ex:
        # Thrown by quit_app() during a normal exit.
        log('exit requested')
    except Exception as ex:
        exception = ex
        exception_info = sys.exc_info()

    # Try to deal with exceptions gracefully ----------------------------------

    if widget:
        # Do this first, in case we need to handle an exception and end up
        # calling os._exit, b/c that would not kill the widget subprocess.
        widget.stop()

    if exception:
        log('Main caught exception: ' + str(exception))
        from traceback import format_exception
        summary = str(exception_info[1])
        details = ''.join(format_exception(*exception_info))
        log('Exception info: ' + summary + '\n' + details)
        # Try to tell the user what happened, if we can.
        try:
            note_error('Error: ' + summary)
            wait(2)
            log('closing application window')
            run_js('close_window()')
        except:
            pass
        log('exiting forcefully with error code')
        # This is a sledgehammer, but it kills everything, including network
        # get/post and the Qt widget thread (on Windows).
        os._exit(1)
    else:
        log('exiting normally')

    # And exit ----------------------------------------------------------------

    log('_'*8 + f' stopped {timestamp()} ' + '_'*8)



# Main page creation function.
# .............................................................................

def foliage_page(widget):
    os.environ['FOLIAGE_GUI_STARTED'] = 'True'
    log('generating main Foliage page')
    put_image(image_data('foliage-icon.png'), width='85px').style('float: left')
    put_image(image_data('foliage-icon-r.png'), width='85px').style('float: right')
    put_html('<h1 class="text-center">Foliage</h1>')
    put_html('<div class="font-italic text-muted font-weight-light text-center mx-auto">'
             ' Foliage ("FOLIo chAnGe Editor") is an app that runs'
             ' on your computer and lets you perform FOLIO operations over'
             ' the network. This web page is its user interface.'
             '</div>').style('width: 85%')
    put_tabs([tab.contents() for tab in _TABS]).style('padding-bottom: 16px')
    put_actions('quit',
                buttons = [{'label': 'Quit', 'value': True, 'color': 'warning'}]
                ).style('position: absolute; bottom: 0px;'
                        + 'left: calc(50% - 3em); z-index: 2')
    advise_demo_mode()
    close_splash_screen()

    # Make sure we have a network before trying to test Folio creds.
    if not network_available:
        notify('No network -- cannot proceed.')
        quit_app(ask_confirm = False)

    if not credentials_complete(credentials_from_env()):
        creds = credentials_from_user(initial_creds = credentials_from_env())
        if not credentials_complete(creds):
            notify('Unable to proceed without complete credentials. Quitting.')
            quit_app(ask_confirm = False)
        use_credentials(creds)
    if not Folio.credentials_valid():
        notify('Invalid FOLIO credentials. Quitting.')
        quit_app(ask_confirm = False)

    # Create a single dict from all the separate pin_watchers dicts.
    watchers  = dict(ChainMap(*[tab.pin_watchers() for tab in _TABS]))
    pin_names = ['quit'] + list(watchers.keys())
    log(f'entering pin handler loop for pins {pin_names}')
    while True:
        # Block, waiting for a change event on any of the pins being watched.
        # The timeout is so we can check if the user quit the taskbar widget.
        changed = pin_wait_change(pin_names, timeout = 1)
        if (not widget or widget.running()) and not changed:
             continue
        if (widget and not widget.running()):
            log('widget has exited')
            quit_app(ask_confirm = False)
        if changed and changed['name'] == 'quit':
            log('user clicked the Quit button')
            quit_app(ask_confirm = True)
            continue                    # In case the user cancels the exit.
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
                    note_error(f'Can\'t write debug ouput in {log_dir}')
                    exit()
            faulthandler.enable()
            if not os.name == 'nt':     # Can't use next part on Windows.
                import signal
                from boltons.debugutils import pdb_on_signal
                pdb_on_signal(signal.SIGUSR1)

            note_info('Debug & auto-reload are on. "kill -USR1 pid" for pdb.')

            # Turn on debug logging in PyWebIO & Tornado. That ends up enabling
            # logging in hpack, which is too much, so turn that off separately.
            import logging
            logging.root.setLevel(logging.DEBUG)
            logging.getLogger('hpack').setLevel(logging.INFO)

        # Turn on debug tracing to the destination we ended up deciding to use.
        set_debug(True, log_file or '-')
        log('debug_arg = ' + debug_arg)
    except PermissionError:
        note_warn(f'Permission denied creating log file {antiformat(log_file)}'
                  + ' -- debug log will not be written.')
    except FileNotFoundError:
        note_warn(f'Cannot write log file {antiformat(log_file)}'
                  + ' -- debug log will not be written.')
    except KeyboardInterrupt:
        # Need to catch this separately or else it will end up ignored by
        # virtue of the next clause catching all Exceptions.
        os._exit()
    except Exception as ex:
        note_warn(f'Unable to create log file {antiformat(log_file)}'
                  + ' -- debug log will not be written.')

    # Make settings accessible in other parts of the program.
    os.environ['DEBUG'] = str(debug_arg != 'OUT')
    os.environ['LOG_FILE'] = (log_file or '-')


def config_signals():
    if os.name == 'nt' and inside_pyinstaller_app():
        # Our PyQt taskbar widget is problematic because PyQt uses signals
        # and when you exit the widget, the signal it sends causes the main
        # thread to terminate, which in turn means the main thread never gets
        # a chance to close the application window.  I couldn't solve this by
        # catching the signals, maybe because I just don't know how to do
        # that on Windows.  Instead, this causes them to be ignored.  IMHO it's
        # OK when running as a GUI app b/c it's hard for the user to ^C it.
        import signal
        import win32api
        import ctypes
        log('configuring signals to be ignored on Windows')
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        win32api.SetConsoleCtrlHandler(None, True)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(None, True)
    else:
        config_interrupt(raise_exception = Interrupted)


def config_backup_dir(backup_dir):
    if not backup_dir:
        default_backups =  join(_DIRS.user_data_dir, 'Backups')
        backup_dir = config('BACKUP_DIR', default = default_backups)
    if exists(backup_dir) and not isdir(backup_dir):
        note_error(f'Not a directory: {antiformat(backup_dir)}')
        exit(1)
    if not exists(backup_dir):
        log(f'creating backup directory {antiformat(backup_dir)}')
        try:
            makedirs(backup_dir)
        except OSError as ex:
            note_error(f'Unable to create backup directory {antiformat(backup_dir)}')
            exit(1)
    if not writable(backup_dir):
        note_error(f'Cannot write in backup directory: {antiformat(backup_dir)}')
        exit(1)
    log('backup dir is ' + backup_dir)
    os.environ['BACKUP_DIR'] = backup_dir


def config_credentials(creds_file, use_keyring):
    os.environ['USE_KEYRING'] = str(use_keyring)
    os.environ['CREDS_FILE'] = creds_file or 'None'

    creds = None
    if creds_file:
        log('creds file supplied on command line')
        if not exists(creds_file):
            note_error(f'Credentials file does not exist: {creds_file}')
            exit(1)
        if not readable(creds_file):
            note_error(f'Credentials file not readable: {creds_file}')
            exit(1)
        creds = credentials_from_file(creds_file)
        if not creds:
            note_error(f'Failed to read credentials from {creds_file}')
            exit(1)
        if not credentials_complete(creds):
            # Consider it an error to be told to use a file and it's incomplete
            note_error(f'Incomplete credentials in {creds_file}')
            exit(1)
    if not creds:
        log('no creds supplied on command line; looking in env')
        creds = credentials_from_env()
    keyring_creds = None
    if (not creds or not credentials_complete(creds)) and use_keyring:
        log('no creds found in env; looking in keyring')
        keyring_creds = credentials_from_keyring(partial_ok = True)
        if credentials_complete(keyring_creds):
            creds = keyring_creds
    if creds:
        log('found creds and using them')
        use_credentials(creds)
    else:
        log('no creds found')


def config_demo_mode(demo_mode):
    os.environ['DEMO_MODE'] = str(demo_mode)
    if demo_mode:
        note_warn('Demo mode is on -- changes to FOLIO will NOT be made')


def config_port(port):
    if not isint(port):
        note_error(f'Port number value is not an integer: antiformat(port)')
        exit(1)
    os.environ['PORT'] = str(port)


def log_config():
    import platform
    log(f'Foliage version = {__version__}')
    log(f'system          = {platform.system()}')
    if platform.system() == 'Darwin':
        log(f'version         = {platform.mac_ver()[0]}')
    else:
        log(f'version         = {platform.version()}')
    log(f'debug           = {os.environ["DEBUG"]}')
    log(f'backup_dir      = {config("BACKUP_DIR")}')
    log(f'log_file        = {config("LOG_FILE")}')
    log(f'creds_file      = {config("CREDS_FILE")}')
    log(f'use_keyring     = {config("USE_KEYRING")}')
    log(f'port            = {config("PORT")}')
    log(f'demo_mode       = {config("DEMO_MODE")}')


def advise_demo_mode():
    if config('DEMO_MODE', cast = bool):
        put_warning('Demo mode in effect').style(
            'position: absolute; left: calc(50% - 5.5em); width: 11em;'
            + 'height: 25px; padding: 0 10px; top: 0; z-index: 2')
    else:
        log('Demo mode not in effect')


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
