'''
__main__.py: main function for %PROJECT_NAME%.

Copyright
---------

Copyright (c) %CREATION_YEAR% by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

import sys
from   sys import exit as exit
if sys.version_info <= (3, 8):
    print('%PROJECT_NAME% requires Python version 3.8 or higher,')
    print('but the current version of Python is ' +
          str(sys.version_info.major) + '.' + str(sys.version_info.minor) + '.')
    exit(1)

if __debug__:
    from sidetrack import set_debug, log


# Main program.
# .............................................................................

# For more info about how plac works see https://plac.readthedocs.io/en/latest/
@plac.annotations(
    version    = ('print version info and exit',                'flag',   'V'),
    debug      = ('log debug output to "OUT" ("-" is console)', 'option', '@'),
)

def main(version = False, debug = 'OUT'):
    '''%PROJECT_DESCRIPTION%'''

    # Set up debug logging as soon as possible, if requested ------------------

    if debug != 'OUT':
        if __debug__: set_debug(True, debug)
        import faulthandler
        faulthandler.enable()
        if not sys.platform.startswith('win'):
            import signal
            from boltons.debugutils import pdb_on_signal
            pdb_on_signal(signal.SIGUSR1)

    # Preprocess arguments and handle early exits -----------------------------

    if version:
        from %PROJECT_NAME% import print_version
        print_version()
        exit()

    # See the
    # for information about how to work with the command-line arguments.


   # Do the real work --------------------------------------------------------




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
