# =============================================================================
# @file    create-wix-script.py
# @brief   Replace version string in Product.wxs.tmpl
# @author  GitHub Copilot (reviewed by Tommy Keswick;
#          adapted from create-innosetup-script.py by Mike Hucka)
# @license Please see the file named LICENSE in the project directory
# @website https://github.com/caltechlibrary/foliage
# =============================================================================

import re
from os.path import abspath, dirname, join


def msi_version(version):
    '''Convert a version string to a 3-part MSI-compatible version.'''
    parts = re.findall(r'\d+', version)
    if not parts:
        raise RuntimeError(f'Could not parse version string: {version}')
    while len(parts) < 3:
        parts.append('0')
    return '.'.join(parts[:3])


here = abspath(dirname(__file__))
version = None
with open(join(here, '../../../setup.cfg')) as setup_file:
    for line in setup_file.readlines():
        if line.startswith('version'):
            version = line.split('=')[1].strip()
            break

if not version:
    raise RuntimeError('Could not find version in setup.cfg')

with open(join(here, 'Product.wxs.tmpl')) as template_file:
    with open(join(here, 'Product.wxs'), 'w') as output_file:
        output_file.write(
            template_file.read().replace('@@MSI_VERSION@@', msi_version(version))
        )
