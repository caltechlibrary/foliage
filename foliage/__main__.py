'''
__main__.py: main function for foliage.

User interface design
---------------------

Foliage runs locally as a Python application, but it opens a web page in the
user's default web browser to use as a user interface.  Foliage does this via
PyWebIO, a framework for building browser-based synchronous GUI applications.
The page has familiar GUI elements like page tabs, buttons, and input forms.

The main Foliage application also starts a separate graphical interface written
in PyQT to put a widget in the taskbar (on Windows) or system tray (on macOS),
This widget provides a visual indication to the user that Foliage is still
running, and also provides a single menu item, "Quit", that allows the user to
quit Foliage.  It's an alternative to using the "Quit" button in the main
Foliage window or closing the window, in case the user has done something to
hide or lose track of the Window.  On Windows, the PyQT widget runs in a thread
but on macOS, it must run as a separate process spawned by Foliage.  The macOS
requirement is a result of how macOS's graphical framework works; the issues
are explained in the file "system_widget.py" in this directory.

The PyWebIO framework does its magic by running a web server on the user's
machine.  Foliage uses Tornado as the web server, mainly because Tornado
supports a useful feature during development: auto-reloading Foliage files
when they've been edited.  However, the PyWebIO interface to Tornado lacks a
critical feature needed by Foliage to implement a proper "Quit" capability
(which is a significant problem, because being able to quit the app is kind
of an important thing). The copy of PyWebIO currently used by Foliage is a
modified version PyWebIO 1.5.2; the modification solves a problem I was having
in which PyWebIO could not detect that the user has closed the application
window.  I'm submitting a pull request to PyWebIO that I hope will mean future
versions of PyWebIO will provide the feature and Foliage won't have to use a
fork in the future.

The main event loop for user interaction is implemented in the Foliage function
foliage_page() in this file.  This function populates the web page (calling
on functions in other files to create the elements on the various tabs) and
then ends with a "while True" loop.  The loop periodically checks whether
certain GUI elements have changed state (such as certain buttons being pressed)
and if not, goes back to waiting for a change in state.  Most of the tabs in
Foliage actually don't need to be engaged in this loop, because they set up
buttons to trigger functions if the user presses the button.  However, not
everything can be done that way, plus we need to check the state of the widget
mentioned above and that needs to be done by polling.

FOLIO user credentials
----------------------

The typical scenario expected for Foliage is that the first time the user
starts it, it will ask the user for credentials, store a token in the user's
private system keychain, and then on subsequent starts, Foliage will read the
token the keychain instead of asking the user again.  The information Foliage
needs is a FOLIO tenant id, FOLIO URL, and (once only to create a token) the
user's FOLIO login and password; it does not store the user login and password
because it only needs the token, tenant id and URL.

For flexibility and to support other scenarios, Foliage actually supports
multiple ways of providing the credentials:

  1. If the command line argument --creds-file is used, and the given file
     contains the credentials (OKAPI URL, tenant id, and OKAPI API token), then
     those credentials are used and nothing more is tried. (In other words,
     credentials given via --creds-file override everything else.) If the
     given file cannot be read or does not contain complete credentials, then
     it is an error and Foliage will quit.

  2. Else, if all three of the environment variables FOLIO_OKAPI_URL,
     FOLIO_OKAPI_TENANT_ID and FOLIO_OKAPI_TOKEN are set, it uses those
     credentials and nothing more is tried.

  3. Else, it looks up the credentials in the user's system keyring/keychain.
     If all 3 pieces of info are found (i.e., OKAPI URL, tenant id, and OKAPI
     API token), then those credentials are used.

  4. Else, it asks the user for the FOLIO_OKAPI_URL, FOLIO_OKAPI_TENANT_ID, a
     FOLIO login, and a password, and uses that combination to request an API
     token from FOLIO. Unless the --no-keyring argument is given, Foliage also
     stores the URL, tenant id, and token in the user's keyring/keychain so
     that it doesn't have to ask again in future runs. (The user's login and
     password are not stored.)

FOLIO API
---------

Calls to the FOLIO API are encapsulated in folio.py and credentials.py.
This main function doesn't interact directly with FOLIO except during the
initial startup when it deals with user credentials.  The calls to FOLIO are
mostly all made by the various tab functions.

Debug log
---------

Unlike some other applications I've written, Foliage always writes a log file.
The file can be accessed by the user from the "Other" tab.  The location of
the file is set to a default application-specific location unless the user
sets it explicitly to another destination using the command-line argument
--debug.  Using the command-line argument is the only way to set it; the GUI
does not provide a way to change the location.  (This is done on purpose;
changing the log destination is something only advanced users or developers
should do.  For normal users, we want the output to go to a known and reliable
location, so that it's findable in case it's needed to help solve problems
that users may be experiencing.)

Backup directory
----------------

Before destructive operations are made on records in FOLIO, Foliage saves a
copy of the record as it existed before the change is performed.  It saves it
in an application-specific directory.  Similar to the case of the debug log
destination, the backup directory can also be changed via a command-line
argument, --backup-dir.  For similar reasons to those discussed above for the
debug flag, there is no GUI facility to change the location of the backup dir.
It can only be done via the command line interface.

Copyright
---------

Copyright (c) 2021-2022 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

import sys
if sys.version_info <= (3, 8):
    print('foliage requires Python version 3.8 or higher,')
    print('but the current version of Python is '
          + str(sys.version_info.major) + '.' + str(sys.version_info.minor) + '.')
    sys.exit(1)

from   appdirs import AppDirs
from   collections import ChainMap
from   commonpy.data_utils import timestamp
from   commonpy.exceptions import Interrupted
from   commonpy.file_utils import writable, readable
from   commonpy.interrupt import config_interrupt, wait
from   commonpy.network_utils import network_available
from   commonpy.string_utils import antiformat
from   decouple import config
from   fastnumbers import isint
import faulthandler
from   functools import partial
import os
from   os import makedirs
from   os.path import exists, dirname, join, realpath, isdir
import plac
import pywebio
# PyWebIO's default is tornado, and tornado mucks with logging, so I would
# have preferred to use aiohttp (which doesn't muck with logging).
# Unfortunately, only tornado provides an auto-reload feature.  IMPORTANT:
# the copy of PyWebIO used by Foliage is a fork where I've modified an
# important function for detecting when the user has closed the app window.
from   pywebio import start_server
from   pywebio.output import put_html, put_warning, put_tabs, put_image
from   pywebio.pin import pin_wait_change, put_actions
from   pywebio.session import run_js
from   sidetrack import set_debug, log
from   tornado.template import Template

from   foliage import __version__
from   foliage.change_tab import ChangeTab
from   foliage.credentials import credentials_from_user, credentials_from_keyring
from   foliage.credentials import use_credentials, credentials_complete
from   foliage.credentials import credentials_from_file, credentials_from_env
from   foliage.delete_tab import DeleteTab
from   foliage.folio import Folio
from   foliage.list_tab import ListTab
from   foliage.lookup_tab import LookupTab
from   foliage.other_tab import OtherTab
from   foliage.clean_tab import CleanTab
from   foliage.system_widget import SystemWidget
from   foliage.ui import quit_app, confirm, notify, inside_pyinstaller_app
from   foliage.ui import note_info, note_warn, note_error
from   foliage.ui import image_data, JS_CODE, CSS_CODE
from   foliage.ui import close_splash_screen


# Internal constants.
# .............................................................................

_DIRS = AppDirs('Foliage', 'CaltechLibrary')
'''Platform-specific directories for Foliage data.'''

_TABS = [LookupTab(), ChangeTab(), DeleteTab(), CleanTab(), ListTab(), OtherTab()]
'''List of tabs making up the Foliage application.'''


# Main program.
# .............................................................................

@plac.annotations(
    backup_dir = ('back up records to folder B before changes', 'option', 'b'),
    creds_file = ('read FOLIO credentials from .ini file C'   , 'option', 'c'),
    demo_mode  = ('demo mode: don\'t perform destructive ops' , 'flag'  , 'd'),
    no_keyring = ('don\'t use keyring for credentials'        , 'flag'  , 'K'),
    port       = ('open browser on port P (default: 8080)'    , 'option', 'p'),
    version    = ('print program version info and exit'       , 'flag'  , 'V'),
    no_widget  = ('don\'t run the taskbar/system tray widget' , 'flag'  , 'W'),
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
web page as its user interface -- it opens a page in a browser on your
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
        sys.exit()

    config_debug(debug)                # Set up debugging before going further.

    log('='*8 + f' started {timestamp()} ' + '='*8)
    log('command line: ' + str(sys.argv))
    os.environ['FOLIAGE_GUI_STARTED'] = 'False'      # Used by ui.py functions.

    config_signals()
    config_backup_dir(None if backup_dir == 'B' else backup_dir)
    config_credentials(None if creds_file == 'C' else creds_file, not no_keyring)
    config_port(port if (port != 'P' and isint(port)) else 8080)
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
    except KeyboardInterrupt:
        # Catch it, but don't treat it as an error; just stop execution.
        log('keyboard interrupt received')
        pass
    except SystemExit:
        # Thrown by quit_app() during a normal exit.
        log('exit requested')
    except Exception as ex:             # noqa: PIE786
        exception = ex
        exception_info = sys.exc_info()

    # Try to deal with exceptions gracefully ----------------------------------

    if widget:
        # Stop the widget explicitly now, in case have an exception and end up
        # calling os._exit, b/c doing *that* would not kill the widget subproc.
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
        except Exception:               # noqa: PIE786
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
    '''Main page creation function and main loop for Foliage.
    This is handed to the PyWebIO start_server() function in our main().
    '''
    os.environ['FOLIAGE_GUI_STARTED'] = 'True'   # Used by ui.py functions.
    log('generating main Foliage page')
    put_image(image_data('foliage-icon.png'), width='70px').style('float: left')
    put_image(image_data('foliage-icon-r.png'), width='70px').style('float: right')
    put_html('<h1 class="text-center">Foliage</h1>')
    put_html('<div class="font-italic text-muted font-weight-light text-center mx-auto">'
             '<b>FOLIo chAnGe Editor</b> runs on your computer and interacts'
             ' with FOLIO over the network.').style('width: 85%')
    put_tabs([tab.contents() for tab in _TABS]).style('padding-bottom: 16px')
    put_actions('quit',
                buttons = [{'label': 'Quit', 'value': True, 'color': 'warning'}]
                ).style('position: absolute; bottom: 0px;'
                        'left: calc(50% - 3em); z-index: 2')
    warn_if_demo_mode()
    close_splash_screen()

    # Make sure we have a working network before trying to test Folio creds.
    if not network_available():
        notify('No network -- cannot proceed.')
        quit_app(ask_confirm = False)

    # Make sure we have valid FOLIO credentials.
    check_credentials()

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
    '''Takes the value of the --debug flag & configures debugging accordingly.'''

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
                    sys.exit()
            faulthandler.enable()
            if os.name != 'nt':         # Can't use next part on Windows.
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
                  ' -- debug log will not be written.')
    except FileNotFoundError:
        note_warn(f'Cannot write log file {antiformat(log_file)}'
                  ' -- debug log will not be written.')
    except KeyboardInterrupt:
        # Need to catch this separately or else it will end up ignored by
        # virtue of the next clause catching all Exceptions.
        os._exit()
    except Exception as ex:             # noqa: PIE786
        log(str(ex))
        note_warn(f'Unable to create log file {antiformat(log_file)}'
                  ' -- debug log will not be written.')

    # Make settings accessible in other parts of the program.
    os.environ['DEBUG'] = str(debug_arg != 'OUT')
    os.environ['LOG_FILE'] = (log_file or '-')


def config_signals():
    '''Configure process signal handling.'''
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
    '''Configure the directory used for backing up FOLIO records.'''
    if not backup_dir:
        default_backups = join(_DIRS.user_data_dir, 'Backups')
        backup_dir = config('BACKUP_DIR', default = default_backups)
    if exists(backup_dir) and not isdir(backup_dir):
        note_error(f'Not a directory: {antiformat(backup_dir)}')
        sys.exit(1)
    if not exists(backup_dir):
        log(f'creating backup directory {antiformat(backup_dir)}')
        try:
            makedirs(backup_dir)
        except OSError:
            note_error(f'Unable to create backup directory {antiformat(backup_dir)}')
            sys.exit(1)
    if not writable(backup_dir):
        note_error(f'Cannot write in backup directory: {antiformat(backup_dir)}')
        sys.exit(1)
    log('backup dir is ' + backup_dir)
    os.environ['BACKUP_DIR'] = backup_dir


def config_credentials(creds_file, use_keyring):
    '''Takes credentials-related command line options and processes them.'''
    os.environ['USE_KEYRING'] = str(use_keyring)
    os.environ['CREDS_FILE'] = creds_file or 'None'

    creds = None
    if creds_file:
        log('creds file supplied on command line')
        if not exists(creds_file):
            note_error(f'Credentials file does not exist: {creds_file}')
            sys.exit(1)
        if not readable(creds_file):
            note_error(f'Credentials file not readable: {creds_file}')
            sys.exit(1)
        creds = credentials_from_file(creds_file)
        if not creds:
            note_error(f'Failed to read credentials from {creds_file}')
            sys.exit(1)
        if not credentials_complete(creds):
            # Consider it an error to be told to use a file and it's incomplete
            note_error(f'Incomplete credentials in {creds_file}')
            sys.exit(1)
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
    '''Takes the --demo-mode option and handles it.'''
    os.environ['DEMO_MODE'] = str(demo_mode)
    if demo_mode:
        note_warn('Demo mode is on -- changes to FOLIO will NOT be made')


def config_port(port):
    '''Takes the --port option and changes the Foliage port if needed.'''
    if not isint(port):
        note_error(f'Port number value is not an integer: {antiformat(port)}')
        sys.exit(1)
    os.environ['PORT'] = str(port)


def log_config():
    '''Write the configuration to the log file.'''
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


def warn_if_demo_mode():
    '''Put a marker on the Foliage GUI to indicate that demo mode is in effect.'''
    if config('DEMO_MODE', cast = bool):
        put_warning('Demo mode in effect').style(
            'position: absolute; left: calc(50% - 5.5em); width: 11em;'
            'height: 25px; padding: 0 10px; top: 0; z-index: 2')
    else:
        log('Demo mode not in effect')


def check_credentials():
    '''Check that the credentials we have are complete and valid.
    If they are not, ask the user if they want to edit them.
    '''
    def edit_and_use_credentials():
        creds = credentials_from_user(initial_creds = credentials_from_env())
        if not credentials_complete(creds):
            notify('Unable to proceed without complete credentials. Quitting.')
            quit_app(ask_confirm = False)
        use_credentials(creds)

    if not credentials_complete(credentials_from_env()):
        edit_and_use_credentials()
    if not Folio().credentials_valid():
        # FOLIO might have invalidated users' tokens.
        if confirm('The FOLIO token may have expired, or else the given '
                   ' credentials are invalid. Click "OK" to review the '
                   ' credentials and try to regenerate the token, or click '
                   ' "Cancel" to quit Foliage now.'):
            edit_and_use_credentials()
        else:
            notify('Invalid FOLIO credentials, or expired token.')
            quit_app(ask_confirm = False)


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
