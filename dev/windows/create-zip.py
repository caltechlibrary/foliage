# =============================================================================
# @file    create-zip.py
# @brief   Create zip file
# @author  Michael Hucka <mhucka@caltech.edu>
# @license Please see the file named LICENSE in the project directory
# @website https://github.com/caltechlibrary/foliage
#
# Needed on Windows because Windows doesn't have a command-line zip utility.
# =============================================================================

import os
from   os.path import exists, dirname, join, basename, abspath, realpath, isdir
import plac
import sys
from   zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED


# Internal constants.
# .............................................................................

_ZIP_COMMENT = '''\
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ This Zip archive file includes a self-contained, runnable ┃
┃ version of the program Foliage for macOS. To learn        ┃
┃ more about Foliage, please visit the following site:      ┃
┃                                                           ┃
┃         https://github.com/caltechlibrary/foliage         ┃
┃                                                           ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
'''


# Main function.
# .............................................................................

@plac.annotations(
    dest_dir  = ('the destination directory for the output', 'option', 'd'),
    overwrite = ('overwrite the destination if it exists',   'flag',   'o'),
    files     = 'one or more files to be put into the ZIP archive',
)

def main(dest_dir = 'D', overwrite = False, *files):
    '''Put one or more files into a ZIP archive.'''

    here = abspath(dirname(__file__))
    with open(join(here, '../../setup.cfg')) as setup_file:
        for line in setup_file.readlines():
            if line.startswith('version'):
                version = line.split('=')[1].strip()
                break

    dest_dir = '.' if dest_dir == 'D' else dest_dir
    zip_file = join(dest_dir, f'foliage-{version}-win.zip')
    if exists(zip_file) and not overwrite:
        raise RuntimeError(f'Output destination already exists: {zip_file}')

    inner_folder = f'foliage-{version}-win'
    with ZipFile(zip_file, 'w', ZIP_STORED) as zf:
        for file in files:
            zf.write(file, arcname = join(inner_folder, basename(file)))
        zf.comment = _ZIP_COMMENT.encode()


# Main entry point.
# .............................................................................

# The following allows users to invoke this using "python3 -m create-zip".
if __name__ == '__main__':
    if len(sys.argv) == 1 or (len(sys.argv) > 1 and sys.argv[1] == 'help'):
        plac.call(main, ['-h'])
    else:
        plac.call(main)
