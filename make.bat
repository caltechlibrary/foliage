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
REM   3. run "make"
REM ===========================================================================

ECHO Removing "dist/win" and "build/win" subdirectories.

IF EXIST dist\win RD /S /Q dist\win
IF EXIST build\win RD /S /Q build\win

ECHO Making sure all Python packages are the right version

python -m pip install -r requirements.txt

ECHO Generating version.py ...

python dev/installers/windows/create-version.py

ECHO Generating InnoSetup script.

python dev/installers/windows/create-innosetup-script.py

ECHO Generating splash screen file ...

python dev/splash-screen/create-splash-screen.py

ECHO Running PyInstaller ...

python -m PyInstaller --distpath dist/win --clean --noconfirm pyinstaller-win32.spec

ECHO "make.bat" finished.
ECHO The .exe will be in the "dist" subdirectory.
ECHO Now run Innosetup to create an installer.
