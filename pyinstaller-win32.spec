# -*- mode: python -*-
# =============================================================================
# @file    pyinstaller-win32.spec
# @brief   Spec file for PyInstaller for Windows
# @author  Michael Hucka
# @license Please see the file named LICENSE in the project directory
# @website https://github.com/caltechlibrary/foliage
# =============================================================================

import imp
import os
from   PyInstaller.building.datastruct import Tree
from   PyInstaller.utils.hooks import copy_metadata

# The list must contain tuples: ('file', 'destination directory').
data_files = [ ('foliage/data/index.tpl', 'data'),
               # I don't know why the next ones need 'foliage/data', but they
               # won't be found if you just use 'data' like the one above.
               ('foliage/data/foliage-icon-r.png', 'foliage/data'),
               ('foliage/data/foliage-icon.png', 'foliage/data'),
               # Local hacked copy of PyWebIO.
               ('../PyWebIO/pywebio/platform/tpl', 'pywebio/platform/tpl'),
               ('../PyWebIO/pywebio/html', 'pywebio/html'),
              ]

# The data_files setting below following fixes this run-time error:
#
#   File "humanize/__init__.py", line 14, in <module>
#   File "pkg_resources/__init__.py", line 465, in get_distribution
#   File "pkg_resources/__init__.py", line 341, in get_provider
#   File "pkg_resources/__init__.py", line 884, in require
#   File "pkg_resources/__init__.py", line 770, in resolve
#   pkg_resources.DistributionNotFound: The 'humanize' distribution was
#   not found and is required by the application
#
# I don't actually know why that error occurs.  CommonPy imports humanize,
# and it has it in its requirements.txt, and PyInstaller looks like it's
# picking it up.  So I'm stumped about why humanize seems to get missed in
# the binary produced by PyInstaller.  Even weirder, this was an issue in
# PyInstaller (https://github.com/jmoiron/humanize/issues/105) and has been
# closed as solved.  Don't have time to debug more.
data_files += copy_metadata('humanize')

configuration = Analysis([r'foliage\__main__.py'],
                         pathex = ['.'],
                         binaries = [],
                         datas = data_files,
                         hiddenimports = ['keyring.backends',
                                          'win32timezone',
                                          'winreg',
                                          ],
                         hookspath = [],
                         runtime_hooks = [],
                         # For reasons I can't figure out, PyInstaller tries
                         # to load these even though they're never imported
                         # by the Martian code.  Have to exclude them manually.
                         excludes = ['PyQt4', 'PyQt5', 'gtk', 'matplotlib',
                                     'numpy'],
                         win_no_prefer_redirects = False,
                         win_private_assemblies = False,
                         cipher = None,
                        )

application_pyz    = PYZ(configuration.pure,
                         configuration.zipped_data,
                         cipher = None,
                        )

executable         = EXE(application_pyz,
                         configuration.scripts,
                         configuration.binaries,
                         configuration.zipfiles,
                         configuration.datas,
                         name = 'Foliage',
                         icon = r'dev\icon\foliage-icon.ico',
                         debug = True,
                         strip = False,
                         upx = True,
                         runtime_tmpdir = None,
                         console = True,
                        )

app             = BUNDLE(executable,
                         name = 'Foliage.exe',
                         icon = r'dev\icon\foliage-icon.ico',
                         bundle_identifier = None,
                         info_plist = {'NSHighResolutionCapable': 'True'},
                        )
