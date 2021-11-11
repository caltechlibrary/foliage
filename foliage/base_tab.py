'''
base_tab.py: base class for tabs

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

class FoliageTab():
    def contents(self):
        '''Return a dict of elements {'title': '...', 'content': [objects]}.'''
        pass

    def pin_watchers(self):
        '''Return a dict of elements {'pin_name': callback_function}.'''
        pass
