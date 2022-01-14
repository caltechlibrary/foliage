# Making a new release of Foliage

Here is the overall sequence of steps I use to create a new release of Foliage.

In the current workflow, certain steps must be performed on a non-Windows system. (I only use Windows to generate the Windows binaries, not to develop software or do other work.) The steps here assume that you have a shared file system between your Mac or Linux system, and the Windows system.

## 1. First generate a working macOS binary

This step will update some in the Foliage source directory, and those changes are assumed to be visible in your Windows computing environment via a shared file system. (If you don't have a shared file system established between the computers, you will need to copy files to a Windows system, and that's much more error prone and time-consuming that using a shared file system.)

1. Cd to the top level of the Foliage source directory
2. Open `setup.py` in a text editor, update the version number inside, and commit the change to git
3. Run `make update-init`
4. Run `make really-clean`
5. Run `make binary`
6. Test the binary that gets built:
   1. Run it from the command line by starting `dist/macos/foliage`
   2. Run it by double-clicking `dist/macos/Foliage.app` in the macOS Finder


## 2. Next, generate a working Windows binary

Start up a Window environment, then in a terminal emulator:

1. Cd to the top level of the Foliage source directory
2. Run `make`
3. Test the binary that gets built:
   1. Run it from the command line by starting `dist/win/Foliage.exe`
   2. Run it by double-clicking `dist/win/Foliage.exe` in the Windows File Explorer.


## 3. If all seems to work, only then make a release

1. Run `make release`
2. Run `make print-instructions`
3. Run `make update-doi`
4. Run `make packages`
5. Run `make test-pypi`
6. Check the test release at <https://test.pypi.org/project/foliage>

