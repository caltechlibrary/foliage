'''
enum_utils.py: extensions and utilities for working with enums

Copyright
---------

Copyright (c) 2021-2022 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from enum import Enum, EnumMeta


# The following class was based in part on the posting by user "Pierre D" at
# https://stackoverflow.com/a/65225753/743730 made on 2020-12-09.

class MetaEnum(EnumMeta):
    '''Meta class for enums that implements "contain" test ability.'''
    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        return True


# Inheriting from str solves the problem that PyWebIO otherwise complains about
# the type values not being json serializable.  This brilliant approach is due
# to a posting by "Justin Carter" @ https://stackoverflow.com/a/51976841/743730

class ExtendedEnum(str, Enum, metaclass = MetaEnum):
    '''Extend Enum class with a function allowing a test for containment.'''
