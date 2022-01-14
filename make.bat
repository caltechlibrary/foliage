@ECHO off
REM ===========================================================================
REM @file    make.bat
REM @brief   Build a .exe using PyInstaller
REM @author  Michael Hucka <mhucka@caltech.edu>
REM @license Please see the file named LICENSE in the project directory
REM @website https://github.com/caltechlibrary/holdit
REM
REM Usage:
REM   1. start a terminal shell (e.g., cmd.exe)
REM   2. cd into this directory
REM   3. run "make.bat"
REM ===========================================================================

ECHO Removing "dist/win" and "build/win" subdirectories.

RD /S /Q dist/win build/win

ECHO Making sure all Python packages are the right version

python -m pip install -r requirements.txt

ECHO Generating version.py ...

python dev/installers/windows/create-version.py

ECHO Generating splash screen file ...

python dev/splash-screen/create-splash-screen.py

ECHO Running PyInstaller ...

python -m PyInstaller --distpath dist/win --clean --noconfirm pyinstaller-win32.spec

ECHO Creating ZIP file

python dev/installer/windows/create-zip.py -o -d dist/win dist/win/Foliage.exe

ECHO "make.bat" finished.
ECHO The .exe will be in the "dist" subdirectory.
