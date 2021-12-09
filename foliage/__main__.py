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
from   foliage.ui import quit_app, reload_page, confirm, notify, pyinstaller_app
from   foliage.ui import note_info, note_warn, note_error, tell_success, tell_failure
from   foliage.ui import image_data, user_file, JS_CODE, CSS_CODE
from   foliage.ui import close_splash_screen


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

    # Process arguments -------------------------------------------------------

    if version:
        from foliage import print_version
        print_version()
        exit()

    log('='*8 + f' started {timestamp()} ' + '='*8)
    os.environ['FOLIAGE_GUI_STARTED'] = 'False'

    config_debug(debug)                # Set up debugging before anything else.
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

        # cdn = False makes it load PyWebIO JS code from our local copy.
        log('starting PyWebIO server')
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
        # This is a sledgehammer, but it kills everything, including ongoing
        # network get/post. I have not found a more reliable way to interrupt.
        os._exit(1)

    # And exit ----------------------------------------------------------------

    log('exiting normally')
    if widget:
        widget['app'].quit()
    log('_'*8 + f' stopped {timestamp()} ' + '_'*8)


# Main page creation function.
# .............................................................................

def foliage():
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
    widget = taskbar_widget()

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
        if not changed and widget['running']:
            continue
        if not widget['running'] or changed['name'] == 'quit':
            log('detected quit action')
            quit_app(ask_confirm = widget['running'])
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
    if os.name == 'nt' and pyinstaller_app():
        # Our PyQt taskbar widget is problematic because PyQt uses signals
        # and when you exit the widget, the signal it sends causes the
        # main thread to terminate.  I couldn't solve this by catching
        # signals, maybe because I just don't know how to do that properly
        # on Windows.  Instead, this causes them to be ignored.  IMHO tha's
        # OK when running as a GUI app b/c it's hard for the user to ^C it.
        import signal
        import win32api
        import ctypes
        log('configuring signals to be ignored')
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


def taskbar_widget():
    # The use of a PyQt widget is the simplest way I found to create a
    # taskbar widget.  Our widget is minimal and only has a single
    # right-click action, for "exit".  Still, the most frustrating part of
    # this scheme is that the PyQt widget must run in a thread because the
    # app.exec_() is a blocking call.  That leads to a problem about how to
    # exit Foliage if the user quits the taskbar widget.  The PyQt thread
    # cannot issue PyWebIO calls because those can only be issued from the
    # PyWebIO thread, so the widget itself can't call our quit_app().  The
    # widget function also can't throw SystemExit because it won't end up in
    # the main thread.  After considerable time and many rabbit holes, I hit
    # on the approach of (1) making the quit button in the UI use a PyWebIO
    # pin object, so that testing for quit is part of the main event loop;
    # (2) making the widget function set a value in a substructured object
    # when the user exits the widget, so that the caller can test it; and (3)
    # using a timeout on the PyWebIO wait in the main foliage() "while True"
    # loop, so it can periodically test the value of the structured object.

    # We return a structured type, because the value needs to be set inside a
    # thread but we need to have a handle on it from the outside.
    widget_info = {'running': True}

    # The taskbar is not currently relevant on macOS.  The caller only cares
    # about when the widget exits, so on macOS, pretend it's always running.
    if sys.platform.startswith('darwin'):
        return widget_info

    # The taskbar widget is implemented using PyQt and runs in a subthread.
    def show_widget():
        from PyQt5 import QtGui, QtWidgets, QtCore
        from PyQt5.QtCore import Qt

        log('creating Qt app for producing taskbar icon')
        app = QtWidgets.QApplication([])
        icon = QtGui.QIcon()
        data_dir = join(dirname(__file__), 'foliage', 'data')
        icon.addFile(join(data_dir, 'foliage-icon-256x256.png'), QtCore.QSize(256,256))
        icon.addFile(join(data_dir, 'foliage-icon-128x128.png'), QtCore.QSize(128,128))
        icon.addFile(join(data_dir, 'foliage-icon-64x64.png'),   QtCore.QSize(64,64))
        app.setWindowIcon(icon)
        mw = QtWidgets.QMainWindow()
        mw.setWindowIcon(icon)
        mw.setWindowTitle('Foliage')
        mw.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowMinimizeButtonHint)
        mw.showMinimized()

        nonlocal widget_info
        log('exec\'ing Qt app')
        # The following call will block until the widget is exited (by the user
        # right-clicking on the widget and selecting "exit").
        app.exec_()

        # If the user right-clicks on the widget in the taskbar and chooses
        # exit, we end up here. Set a flag to tell the main loop what happened.
        log('taskbar widget returned from exec_()')
        widget_info['running'] = False

    from threading import Thread
    log(f'starting thread for creating taskbar icon widget')
    thread = Thread(target = show_widget, args = ())
    thread.start()
    # Note that we never join() the thread, because that would block.  We start
    # the widget thread & return so the caller can proceed to its own event loop.
    return widget_info


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
