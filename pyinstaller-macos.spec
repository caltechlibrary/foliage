# -*- mode: python -*-
# =============================================================================
# @file    pyinstaller-darwin.spec
# @brief   Spec file for PyInstaller for macOS
# @author  Michael Hucka
# @license Please see the file named LICENSE in the project directory
# @website https://github.com/caltechlibrary/foliage
#
# This PyInstaller config makes the macOS app in what's called "one-dir" mode,
# unlike our Windows Foliage app, which we make in "one-file" mode. Here's an
# explanation of why it's done differently in macOS versus Windows.
#
# In "one-file" mode, PyInstaller creates a compressed single-file archive of
# the application plus all the Python libraries and necessary system
# libraries (dll's on Windows) to create a self-contained, single-file
# application. This single-file app contains a bootloader program that is the
# thing actually executed when the user runs the app. This bootloader unpacks
# everything at run time into a temporary directory, and after that, starts
# the real Foliage application (all behind the scenes -- the user doesn't see
# any of this happening). However, this unpacking step takes time, during
# which nothing seems to be happening. Not only is this long startup time
# annoying for the user, but the lack of feedback can be very confusing ("did
# Foliage actually start? how long should I wait?"). The one-file app is
# great for packaging and distribution (because the result looks like any
# other application), but not for the user experience.
#
# In "one-dir" mode, PyInstaller doesn't create a single-file archive; it
# leaves the files (the dependencies, dynamic libraries, data files, etc.)
# in a single folder, unpacked. Within this folder, there's a binary that is
# the program you actually run. The result is faster startup at run time
# because the unpacking step is unnecessary, *but* the user has to know to
# find the right binary file inside that folder -- a folder that contains
# dozens upon dozens of other files and folders. This is an even more
# confusing user experience. However, on macOS, unlike Windows, there's a
# feature we can use to advantage here. MacOS apps are *already* folders: in
# the Finder, a program that looks like it's named "Foliage" is actually a
# folder named "Foliage.app", and inside this folder are various files and
# subfolders. So it doesn't matter if we use PyInstaller's one-dir mode,
# because we can hide the results in the Foliage.app folder and the user
# doesn't need to know about these details. As a result, we take advantage
# of one-dir mode for its faster start times without compromising the user
# experience.
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
    raise RuntimeError('Must run PyInstaller from the same directory as the '
                       f'setup.cfg file. Could not find it here ({here}).')


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

data_files = [('foliage/data/index.tpl', 'data'),
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
# - "debug = True" produces output on the cmd line when you start the app.
# - "console = True" makes the app show a console window at run time.

executable         = EXE(application_pyz,
                         configuration.scripts,
                         exclude_binaries = True,
                         # Make sure the following 'name' field value is
                         # different from the one defined in COLLECT below.
                         name = 'Foliageapp',
                         icon = r'dev/icon/foliage-icon.icns',
                         strip = False,
                         upx = True,
                         runtime_tmpdir = None,
                         bootloader_ignore_signals = False,
                         codesign_identity = 'Developer ID Application: Michael Hucka (FBQTM3C6ZA)',
                         entitlements_file = 'entitlements.plist',
                         # To debug run problems, first try setting console
                         # to True. If that doesn't reveal enough, then try
                         # setting debug to True. (Debug produces a lot of
                         # dialogs, so better to start with console.)
                         # IMPORTANT: console = True *also* prevents the app
                         # from showing an icon in the macOS Dock.  Use
                         # console = False to get the Dock icon to show up.
                         debug = False,
                         console = True,
                        )

collected_files = COLLECT(executable,
                          configuration.binaries,
                          configuration.zipfiles,
                          configuration.datas,
                          strip = False,
                          upx = False,
                          upx_exclude = [],
                          # Make sure this name is different from the 'name'
                          # used for EXE above, or there'll be a name collison
                          # & PyInstaller will create a working app.
                          name = 'foliage')

app             = BUNDLE(collected_files,
                         name = 'Foliage.app',
                         icon = 'dev/icon/foliage-icon.icns',
                         version = version,
                         bundle_identifier = 'edu.caltech.library.foliage',
                         info_plist = {'NSHighResolutionCapable': 'True',
                                       'NSPrincipalClass': 'NSApplication',
                                       'NSAppleScriptEnabled': False},
                        )
