'''
base_tab.py: base class for tabs

The tabs in Foliage are conceptually pretty simple: there's a function to
create the tab contents, and another function to set up optional watchers
for detecting and acting on designated PyWebIO "pin" objects.  The class
FoliageTab is a base class used by all the Foliage tab classes.  This common
base class makes it possible to implement tab creation and pin watching in
__main__.py's foliage_page() as a loop over a list of objects, rather than
by hardcoding calls to every tab directly.

Copyright
---------

Copyright (c) 2021-2022 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''


class FoliageTab():
    def contents(self):
        '''Return a dict of elements {'title': '...', 'content': [objects]}.'''
        raise NotImplementedError()

    def pin_watchers(self):
        '''Return a dict of elements {'pin_name': callback_function}.'''
        raise NotImplementedError()
