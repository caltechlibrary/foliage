# -*- mode: python -*-
# =============================================================================
# @file    pyinstaller-win32.spec
# @brief   Spec file for PyInstaller for Windows
# @author  Michael Hucka
# @license Please see the file named LICENSE in the project directory
# @website https://github.com/caltechlibrary/foliage
#
# Note: despite the .spec file name extension, this file is Python code run by
# PyInstaller, which means you can do more than just set variables.
# =============================================================================

from   os import getcwd
from   os.path import join, exists
from   PyInstaller.building.datastruct import Tree
import PyInstaller.config
from   PyInstaller.utils.hooks import copy_metadata


# Sanity-check the run-time environment before attempting anything else.
# .............................................................................

here = getcwd()
setup_file = join(here, 'setup.cfg')
if not exists(setup_file):
    raise RuntimeError(f'Must run PyInstaller from the same directory as the '
                       + f'setup.cfg file. Could not find it here ({here}).')


# Gather information.
# .............................................................................

# Format of the following list: ('source file', 'destination in bundle').

data_files = [ ('foliage/data/index.tpl', 'data'),
               # I don't know why the next ones need 'foliage/data' for the
               # destination and just 'data' like the one above.
               ('foliage/data/foliage-icon-r.png', 'foliage/data'),
               ('foliage/data/foliage-icon.png', 'foliage/data'),
               ('foliage/data/foliage-icon-32x32.png', 'foliage/data'),
               ('foliage/data/foliage-icon-64x64.png', 'foliage/data'),
               ('foliage/data/foliage-icon-128x128.png', 'foliage/data'),
               ('foliage/data/foliage-icon-256x256.png', 'foliage/data'),
               ('foliage/data/foliage-icon.ico', 'foliage/data'),
               # Local hacked copy of PyWebIO.
               ('../PyWebIO/pywebio/platform/tpl', 'pywebio/platform/tpl'),
               ('../PyWebIO/pywebio/html', 'pywebio/html'),
              ]

# The data_files setting below, for humanize, fixes this run-time error:
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
# and does have it in its requirements.txt, and PyInstaller looks like it's
# picking it up. Even weirder, this was an issue in PyInstaller
# (https://github.com/jmoiron/humanize/issues/105) and has been closed as
# solved. I'm stumped about why humanize seems to get missed in the
# binary produced by PyInstaller but don't have time to debug more.

data_files += copy_metadata('humanize')


# Create the PyInstaller configuration.
# .............................................................................

# The following controls how PyInstaller finds what comprises the application.

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
                         # to load matplotlib even though it's never imported
                         # by our code. It causes the build to fail. Need to
                         # exclude it explicitly.
                         excludes = ['matplotlib'],
                         cipher = None,
                        )

application_pyz    = PYZ(configuration.pure,
                         configuration.zipped_data,
                         cipher = None,
                        )

# splash          = Splash(r'dev\splash-screen\foliage-splash-screen.png',
#                          binaries = configuration.binaries,
#                          datas = configuration.datas
#                          )

# Notes about the configuration below:
# - "debug = True" produces output on the cmd line when you start the app.
# - "console = True" makes the app show a console window at run time.

executable         = EXE(application_pyz,
                         configuration.scripts,
                         configuration.binaries,
                         configuration.zipfiles,
                         configuration.datas,
                         # splash,
                         # splash.binaries,
                         name = 'Foliage',
                         icon = r'dev/icon/foliage-icon.ico',
                         version = r'dev/installers/windows/version.py',
                         strip = False,
                         upx = False,
                         runtime_tmpdir = None,
                         # To debug run problems on Windows, first try setting
                         # console to True. If that doesn't reveal enough, then
                         # try setting debug to True. (Debug produces a lot of
                         # dialogs, so better to start with console.)
                         console = False,
                         debug = False,
                        )

# collected_files = COLLECT(executable,
#                           configuration.binaries,
#                           configuration.zipfiles,
#                           configuration.datas,
#                           strip = False,
#                           upx = False,
#                           upx_exclude = [],
#                           name = 'foliage')

app             = BUNDLE(executable,
                         name = 'Foliage.exe',
                         icon = r'foliage/data/foliage-icon.ico',
                         bundle_identifier = None,
                         info_plist = {'NSHighResolutionCapable': 'True'},
                        )
