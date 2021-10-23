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

from   commonpy.data_utils import timestamp
from   commonpy.interrupt import config_interrupt
from   commonpy.string_utils import antiformat
from   fastnumbers import isint
import plac
import pywebio
# Default server is tornado, and tornado mucks with logging.
# aiohttp server does not.  Unfortunately, only tornado auto-reloads.
# from   pywebio.platform.aiohttp import start_server
from   pywebio import start_server

if __debug__:
    from sidetrack import set_debug, log

from .foliage import foliage
from .ui import JS_CODE, CSS_CODE, alert, warn


# Main program.
# .............................................................................

@plac.annotations(
    port       = ('open browser on port "P" (default: 8080)',   'option', 'p'),
    version    = ('print version info and exit',                'flag',   'V'),
    debug      = ('log debug output to "OUT" ("-" is console)', 'option', '@'),
)

def main(port = 'P', version = False, debug = 'OUT'):
    '''Foliage: FOLIo chAnGe Editor, a tool to do bulk changes in FOLIO.'''

    # Set up debug logging as soon as possible, if requested ------------------

    if debug != 'OUT':
        set_debug(True, debug)
        import faulthandler
        faulthandler.enable()
        if not sys.platform.startswith('win'): # This part doesn't work on win.
            import signal
            from boltons.debugutils import pdb_on_signal
            pdb_on_signal(signal.SIGUSR1)
            warn('Debug mode on. Use "kill -USR1 pid" to drop into pdb.', False)

    # Preprocess arguments and handle early exits -----------------------------

    if version:
        from foliage import print_version
        print_version()
        exit()

    if port != 'P' and not isint(port):
        alert(f'Port number value for option -p must be an integer.', False)
        exit(1)
    port = 8080 if port == 'P' else int(port)

    # Do the real work --------------------------------------------------------

    log('='*8 + f' started {timestamp()} ' + '='*8)
    exception = None
    try:
        pywebio.config(title = 'Foliage', js_code = JS_CODE, css_style = CSS_CODE)
        start_server(foliage, port = port, auto_open_webbrowser = True,
                     debug = (debug != 'OUT'))
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
