# =============================================================================
# @file    create_version.py
# @brief   Replace version numbers and create version.py file for Foliage
# @author  Michael Hucka <mhucka@caltech.edu>
# @license Please see the file named LICENSE in the project directory
# @website https://github.com/caltechlibrary/foliage
#
# This expects to be in the same directory as version.py.tmpl.
# =============================================================================

import re
from   os.path import abspath, dirname, join
from   string import Template


def parse_release_parts(version):
    '''Return numeric (major, minor, patch) parts from a version string.'''
    parts = re.findall(r'\d+', version)
    if len(parts) < 3:
        raise RuntimeError(f'Could not parse release version from: {version}')
    return parts[0], parts[1], parts[2]

here = abspath(dirname(__file__))
version = None
with open(join(here, '../../../setup.cfg')) as setup_file:
    for line in setup_file.readlines():
        if line.startswith('version'):
            version = line.split('=')[1].strip()
            break

if not version:
    raise RuntimeError('Could not find version in setup.cfg')

major, minor, patch = parse_release_parts(version)

with open(join(here, 'version.py.tmpl'), 'r') as template_file:
    with open(join(here, 'version.py'), 'w') as output_file:
        tmpl = Template(template_file.read())
        text = tmpl.substitute(major = major,
                               minor = minor,
                               patch = patch,
                               version = version)
        output_file.write(text)
