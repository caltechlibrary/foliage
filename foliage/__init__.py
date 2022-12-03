'''
__init__.py for foliage

Copyright
---------

Copyright (c) 2021-2022 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

# Package metadata
# .............................................................................
#
#  ╭────────────────────── Notice ── Notice ── Notice ─────────────────────╮
#  |    The following values are automatically updated at every release    |
#  |    by the Makefile. Manual changes to these values will be lost.      |
#  ╰────────────────────── Notice ── Notice ── Notice ─────────────────────╯

__version__     = '1.5.2'
__description__ = 'Foliage: a tool to do bulk changes in FOLIO using the OKAPI API'
__url__         = 'https://github.com/caltechlibrary/foliage'
__author__      = 'Mike Hucka'
__email__       = 'helpdesk@library.caltech.edu'
__license__     = 'BSD 3-clause license'


# Miscellaneous utilities.
# .............................................................................

def print_version():
    print(f'{__name__} version {__version__}')
    print(f'Authors: {__author__}')
    print(f'URL: {__url__}')
    print(f'License: {__license__}')
