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
from   commonpy.data_utils import timestamp
from   commonpy.file_utils import writable
from   commonpy.interrupt import config_interrupt
from   commonpy.string_utils import antiformat
from   getpass import getuser
from   fastnumbers import isint
import faulthandler
from   functools import partial
from   os import makedirs
from   os.path import exists, dirname, join, basename, abspath, realpath, isdir
import plac
import pywebio
# Default server is tornado, and tornado mucks with logging.
# aiohttp server does not.  Unfortunately, only tornado auto-reloads.
# from   pywebio.platform.aiohttp import start_server
from   pywebio import start_server
from   tornado.template import Template

if __debug__:
    from sidetrack import set_debug, log

from .foliage import foliage_main_page
from .ui import JS_CODE, CSS_CODE, alert, warn


# Internal constants.
# .............................................................................

_APP_DIRS = AppDirs('Foliage', 'CaltechLibrary')


# Main program.
# .............................................................................

@plac.annotations(
    backup_dir = ('save copies of records in directory "B"',    'option', 'b'),
    port       = ('open browser on port "P" (default: 8080)',   'option', 'p'),
    version    = ('print version info and exit',                'flag',   'V'),
    debug      = ('log debug output to "OUT" ("-" is console)', 'option', '@'),
)

def main(backup_dir = 'B', port = 'P', version = False, debug = 'OUT'):
    '''Foliage: FOLIo chAnGe Editor, a tool to do bulk changes in FOLIO.'''

    # Set up debug logging as soon as possible --------------------------------

    log_file = None
    try:
        if debug == 'OUT':
            # Store debug log in user's log directory.
            log_dir = _APP_DIRS.user_log_dir
            log_file = join(log_dir, 'log.txt')
            if not exists(log_dir):
                makedirs(log_dir)
            with open(log_file, 'w'):
                # Empty out the file for each new run.
                pass
        else:
            if debug != '-':
                log_file = debug
                if not writable(dirname(log_file)):
                    alert(f'Can\'t write debug ouput file in {dirname(debug)}', False)
                    exit()
            faulthandler.enable()
            if not sys.platform.startswith('win'): # This part doesn't work on win.
                import signal
                from boltons.debugutils import pdb_on_signal
                pdb_on_signal(signal.SIGUSR1)
            warn('Debug & auto-reload are on. "kill -USR1 pid" invokes pdb.', False)
        set_debug(True, log_file or '-')
    except PermissionError:
        warn(f'Permission denied trying to create log file {log_file}', False)
    except FileNotFoundError:
        warn(f'Cannot write debug output file {log_file}', False)
    except KeyboardInterrupt:
        # Need to catch this separately or else it will end up ignored by
        # virtue of the next clause catching any Exception.
        exit()
    except Exception as ex:
        warn(f'Unable to create log file {log_file}', False)

    # Preprocess arguments and handle early exits -----------------------------

    if version:
        from foliage import print_version
        print_version()
        exit()

    if backup_dir != 'B':
        if not exists(backup_dir) or not isdir(backup_dir):
            alert(f'Directory for -b does not exist: {backup_dir}')
            exit(1)
        elif not writable(backup_dir):
            alert(f'Cannot write in backup directory: {backup_dir}')
            exit(1)
    else:
        backup_dir = _APP_DIRS.user_log_dir

    if port != 'P' and not isint(port):
        alert(f'Port number value for option -p must be an integer.', False)
        exit(1)
    port = 8080 if port == 'P' else int(port)

    # Do the real work --------------------------------------------------------

    log('='*8 + f' started {timestamp()} ' + '='*8)
    exception = None
    try:
        pywebio.config(title = 'Foliage', js_code = JS_CODE, css_style = CSS_CODE)

        # This uses a custom index page template created by copying the PyWebIO
        # default and modifying it. Among other things, the following were
        # removed because Foliage doesn't need them: Plotly, Codemirror.
        here = realpath(dirname(__file__))
        with open(join(here, 'data', 'index.tpl')) as index_tpl:
            index_page_template = Template(index_tpl.read())
        pywebio.platform.utils._index_page_tpl = index_page_template

        if not exists(backup_dir):
            makedirs(backup_dir)

        log(f'using {backup_dir} for backing up records')
        log(f'debug log output is going to {log_file if log_file else "stdout"}')
        log(f'starting server')

        foliage = partial(foliage_main_page, log_file, backup_dir)
        start_server(foliage, port = port, auto_open_webbrowser = True,
                     debug = (debug != 'OUT'))
    except KeyboardInterrupt as ex:
        pass
    except Exception as ex:
        exception = sys.exc_info()

    # Try to deal with exceptions gracefully ----------------------------------

    if exception:
        if isinstance(exception[0], KeyboardInterrupt):
            log(f'received {exception.__class__.__name__}')
        else:
            from traceback import format_exception
            summary = antiformat(exception[1])
            details = antiformat(''.join(format_exception(*exception)))
            log(f'Exception: {summary}\n{details}')
            alert(summary, False)

    # And exit ----------------------------------------------------------------

    log('Exiting normally.')
    log('_'*8 + f' stopped {timestamp()} ' + '_'*8)


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
