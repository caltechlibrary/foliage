# Installation

Most people should install the ready-to-run application for macOS or Windows. Developers can run Foliage from a copy of the source code.


## Preliminary requirements

Foliage runs on macOS, Windows, and Linux, and needs a working Internet connection. The macOS and Windows applications include everything they need. Running Foliage from the source code requires [Python](https://www.python.org) 3.11 or later.


## Installation instructions

### _Alternative 1: installing the macOS or Windows application_

Download the installer for your computer from the [latest release](https://github.com/caltechlibrary/foliage/releases/latest):

* **macOS:** `foliage_X.Y.Z_macos_arm64.dmg`, for Macs with Apple silicon. Open the DMG and drag Foliage to your Applications folder. The first time you open it, macOS may say it can’t verify the app. If so, go to _System Settings_ → _Privacy & Security_, and click _Open Anyway_.
* **Windows:** `foliage_X.Y.Z_windows_x64.msi`. Double-click it to install Foliage. If Windows says it protected your PC, click _More info_, then _Run anyway_.


### _Alternative 2: running Foliage from the source code_

Foliage needs a [modified copy of PyWebIO](https://github.com/mhucka/PyWebIO), which has to be installed separately before Foliage:

```sh
git clone https://github.com/caltechlibrary/foliage
cd foliage
python3 -m pip install git+https://github.com/mhucka/PyWebIO.git@2af53fc
python3 -m pip install .
```

To update later, run `git pull` in the `foliage` folder, then run the last command again.

Foliage isn’t published on PyPI.
