# =============================================================================
# @file    create-innosetup-script.py
# @brief   Replace version string in foliage_innosetup_script.iss.in
# @author  Michael Hucka <mhucka@caltech.edu>
# @license Please see the file named LICENSE in the project directory
# @website https://github.com/caltechlibrary/foliage
# =============================================================================

import os
from   os.path import abspath, dirname, join
from   string import Template

here = abspath(dirname(__file__))
with open(join(here, '../../../setup.cfg')) as setup_file:
    for line in setup_file.readlines():
        if line.startswith('version'):
            version = line.split('=')[1].strip()
            break

with open(join(here, 'foliage_innosetup_script.iss.tmpl')) as template_file:
    with open(join(here, 'foliage_innosetup_script.iss'), 'w') as output_file:
        output_file.write(template_file.read().replace('@@VERSION@@', version))
