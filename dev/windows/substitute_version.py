# =============================================================================
# @file    substitute_version.py
# @brief   Replace version string in foliage_innosetup_script.iss.in
# @author  Michael Hucka <mhucka@caltech.edu>
# @license Please see the file named LICENSE in the project directory
# @website https://github.com/caltechlibrary/foliage
# =============================================================================

import os
from   os import path

this_version = 0

here = path.abspath(path.dirname(__file__))
with open(path.join(here, '../../foliage/__init__.py')) as f:
    lines = f.read().rstrip().splitlines()
    for line in [x for x in lines if x.startswith('__') and '=' in x]:
        setting = line.split('=')
        name = setting[0].strip()
        if name == '__version__':
            this_version = setting[1].strip().replace("'", '')

with open(path.join(here, 'foliage_innosetup_script.iss.in')) as infile:
    with open(path.join(here, 'foliage_innosetup_script.iss'), 'w') as outfile:
        outfile.write(infile.read().replace('@@VERSION@@', this_version))
