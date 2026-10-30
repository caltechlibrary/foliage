# Foliage<img alt="Foliage icon" width="12%" align="right" src="https://github.com/caltechlibrary/foliage/raw/main/.graphics/foliage-icon.png">

Foliage is the FOLIo chAnGe Editor, a tool to do bulk changes and other operations in FOLIO using the network API.

[![License](https://img.shields.io/badge/License-BSD--like-blue.svg?style=flat-square)](https://choosealicense.com/licenses/bsd-3-clause)
[![Python](https://img.shields.io/badge/Python-3.8+-brightgreen.svg?style=flat-square)](https://www.python.org/downloads/release/python-380/)
[![Latest release](https://img.shields.io/github/v/release/caltechlibrary/foliage.svg?style=flat-square&color=b44e88)](https://github.com/caltechlibrary/foliage/releases)


## Table of contents

* [Introduction](#introduction)
* [Installation](#installation)
* [Usage](#usage)
* [Getting help](#getting-help)
* [Contributing](#contributing)
* [License](#license)
* [Acknowledgments](#acknowledgments)


## Introduction

Foliage (_**Foli**o ch**a**n**g**e **E**ditor_) is a desktop computer application that can perform operations in [FOLIO](https://www.folio.org), a library services platform ([LSP](https://journals.ala.org/index.php/ltr/article/view/5686/7063)) used by Caltech and other institutions. Foliage allows a user to look up records of various kinds, perform bulk changes in the values of record fields, delete records, and more. It communicates with a FOLIO server using the [OKAPI network API](https://github.com/folio-org/okapi/blob/master/doc/guide.md). The program is cross-platform compatible and currently in use on Windows and macOS computers at the Caltech Library.

<p align="center">
<img width="700"  alt="Foliage screenshot" src="https://github.com/caltechlibrary/foliage/raw/main/.graphics/foliage-screenshot.png">
</p>

Although Foliage is a desktop application and not a web service, it uses a web page as its user interface &ndash; it opens a page in a browser on the user's computer, letting the user interact with the program through the familiar elements of a web page. This lets Foliage present an identical user interface no matter whether it is running on Window, macOS, or Linux.

<p align="center"><img width="80%" alt="Foliage warning" src="https://github.com/caltechlibrary/foliage/raw/main/.graphics/status-warning.svg"></p>


## Installation

Most people should install the ready-to-run application for macOS or Windows. Developers can run Foliage from a copy of the source code.


### _Alternative 1: installing the macOS or Windows application_

Download the installer for your computer from the [latest release](https://github.com/caltechlibrary/foliage/releases/latest):

* **macOS:** `foliage_X.Y.Z_macos_arm64.dmg`, for Macs with Apple silicon. Open the DMG and drag Foliage to your Applications folder. The first time you open it, macOS may say it can’t verify the app. If so, go to _System Settings_ → _Privacy & Security_, and click _Open Anyway_.
* **Windows:** `foliage_X.Y.Z_windows_x64.msi`. Double-click it to install Foliage. If Windows says it protected your PC, click _More info_, then _Run anyway_.


### _Alternative 2: running Foliage from the source code_

This requires Python 3.11 or later. Foliage needs a [modified copy of PyWebIO](https://github.com/mhucka/PyWebIO), which has to be installed separately before Foliage:

```sh
git clone https://github.com/caltechlibrary/foliage
cd foliage
python3 -m pip install git+https://github.com/mhucka/PyWebIO.git@2af53fc
python3 -m pip install .
```

Foliage isn’t published on PyPI.


## Usage

Documentation for Foliage is available online at [https://caltechlibrary.github.io/foliage/](https://caltechlibrary.github.io/foliage/).


## Getting help

If you find an issue, please submit it in [the GitHub issue tracker](https://github.com/caltechlibrary/foliage/issues) for this repository.


## Contributing

Your help and participation in enhancing Foliage is welcome!  Please visit the [guidelines for contributing](CONTRIBUTING.md) for some tips on getting started. Developer documentation is available in the repository at [`dev/dev-docs`](dev/dev-docs).


## License

Software produced by the Caltech Library is Copyright © 2021&ndash;2023 California Institute of Technology.  This software is freely distributed under a BSD type license.  Please see the [LICENSE](LICENSE) file for more information.


## Acknowledgments

This work was funded by the California Institute of Technology Library.

The [vector artwork](https://thenounproject.com/term/branch/1047074/) used as a starting point for the logo for this repository was created by [Alice Noir](https://thenounproject.com/AliceNoir/) for the [Noun Project](https://thenounproject.com).  It is licensed under the Creative Commons [Attribution 3.0 Unported](https://creativecommons.org/licenses/by/3.0/deed.en) license.  The vector graphics was modified by Mike Hucka to change the color.

<div align="center">
  <br>
  <a href="https://www.caltech.edu">
    <img width="100" height="100" alt="Caltech logo" src="https://raw.githubusercontent.com/caltechlibrary/foliage/main/.graphics/caltech-round.png">
  </a>
</div>
