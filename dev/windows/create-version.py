# =============================================================================
# @file    create_version.py
# @brief   Replace version numbers and create version.py file for Foliage
# @author  Michael Hucka <mhucka@caltech.edu>
# @license Please see the file named LICENSE in the project directory
# @website https://github.com/caltechlibrary/foliage
#
# This expects to be in the same directory as version.py.tmpl.
# =============================================================================

import os
from   os.path import abspath, dirname, join
from   string import Template

here = abspath(dirname(__file__))
with open(join(here, '../../setup.cfg')) as setup_file:
    for line in setup_file.readlines():
        if line.startswith('version'):
            version = line.split('=')[1].strip()
            break

major, minor, patch = version.split('.')

with open(join(here, 'version.py.tmpl'), 'r') as template_file:
    with open(join(here, 'version.py'), 'w') as output_file:
        tmpl = Template(template_file.read())
        text = tmpl.substitute(major = major, minor = minor, patch = patch)
        output_file.write(text)
