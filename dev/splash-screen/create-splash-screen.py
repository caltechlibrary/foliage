# =============================================================================
# @file    create-splash-screen.py
# @brief   Replace version number in splash screen SVG and generate a PNG file
# @author  Michael Hucka <mhucka@caltech.edu>
# @license Please see the file named LICENSE in the project directory
# @website https://github.com/caltechlibrary/foliage
#
# This expects to be in the same directory as foliage-splash-screen.svg.tmpl.
# =============================================================================

import os
from   os.path import abspath, dirname, join
from   string import Template
from   wand.image import Image

here = abspath(dirname(__file__))
with open(join(here, '../../setup.cfg')) as setup_file:
    for line in setup_file.readlines():
        if line.startswith('version'):
            version = line.split('=')[1].strip()
            break

major, minor, patch = version.split('.')

with open(join(here, 'foliage-splash-screen.svg.tmpl'), 'r') as template_file:
    tmpl = Template(template_file.read())
    svg  = tmpl.substitute(major = major, minor = minor, patch = patch)
    with Image(blob = svg.encode(), format = "svg") as image:
        image.format = 'png'
        image.save(filename = join(here, 'foliage-splash-screen.png'))
