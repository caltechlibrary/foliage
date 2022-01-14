# -*- mode: python -*-
# =============================================================================
# @file    pyinstaller-darwin.spec
# @brief   Spec file for PyInstaller for macOS
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

# Get the current software version number from setup.cfg. The value of the
# variable "version" is used near the end, in the call to BUNDLE.

with open('setup.cfg', 'r') as setup_file:
    for line in setup_file.readlines():
        if line.startswith('version'):
            version = line.split('=')[1].strip()
            break
    else:
        raise RuntimeError('Could not read version number from setup.cfg')

# Format of the following list: ('source file', 'destination in bundle').

data_files = [ ('foliage/data/index.tpl', 'data'),
               # I don't know why the next ones need 'foliage/data' for the
               # destination and just 'data' like the one above.
               ('foliage/data/foliage-icon-r.png', 'foliage/data'),
               ('foliage/data/foliage-icon.png', 'foliage/data'),
               ('foliage/data/macos-systray-widget/macos-systray-widget',
                'foliage/data/macos-systray-widget/'),
               # My local hacked copy of PyWebIO.
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

configuration = Analysis(['foliage/__main__.py'],
                         pathex = ['.'],
                         binaries = [],
                         datas = data_files,
                         hiddenimports = ['keyring.backends',
                                          'keyring.backends.OS_X',
                                          ],
                         hookspath = [],
                         runtime_hooks = [],
                         # For reasons I can't figure out, PyInstaller tries
                         # to load matplotlib even though it's never imported
                         # by our code. It causes the build to fail. Need to
                         # exclude it explicitly.
                         excludes = ['matplotlib'],
                         win_no_prefer_redirects = False,
                         win_private_assemblies = False,
                         cipher = None,
                        )

application_pyz    = PYZ(configuration.pure,
                         configuration.zipped_data,
                         cipher = None,
                        )

# Notes about the configuration below:
# - As of PyInstaller 4.7, splash screens are not supported on macOS. That's
#   why the windows configuration has a splash screen but this one doesn't.
#
# - "debug = True" produces output on the cmd line when you start the app.
#
# - "console = True" makes the app show a console window at run time.

executable         = EXE(application_pyz,
                         configuration.scripts,
                         configuration.binaries,
                         configuration.zipfiles,
                         configuration.datas,
                         name = 'foliage',
                         icon = r'dev/icon/foliage-icon.icns',
                         debug = False,
                         strip = False,
                         upx = True,
                         runtime_tmpdir = None,
                         console = False,
                        )

app             = BUNDLE(executable,
                         name = 'Foliage.app',
                         icon = 'dev/icon/foliage-icon.icns',
                         version = version,
                         bundle_identifier = 'edu.caltech.library.foliage',
                         info_plist = {'NSHighResolutionCapable': 'True',
                                       'NSAppleScriptEnabled': False},
                        )
