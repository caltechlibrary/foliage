# Foliage<img width="12%" align="right" src="https://github.com/caltechlibrary/foliage/raw/main/.graphics/foliage-icon.png">

Foliage is the FOLIo chAnGe Editor, a tool to do bulk changes and other operations in FOLIO using the network API.

[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg?style=flat-square)](https://choosealicense.com/licenses/bsd-3-clause)
[![Python](https://img.shields.io/badge/Python-3.8+-brightgreen.svg?style=flat-square)](https://www.python.org/downloads/release/python-380/)
[![Latest release](https://img.shields.io/github/v/release/caltechlibrary/foliage.svg?style=flat-square&color=b44e88)](https://github.com/caltechlibrary/foliage/releases)
[![DOI](https://img.shields.io/badge/dynamic/json.svg?label=DOI&style=flat-square&color=lightgray&query=$.metadata.doi&uri=https://data.caltech.edu/api/record/20025)](https://data.caltech.edu/records/20025)


## Table of contents

* [Introduction](#introduction)
* [Installation](#installation)
* [Usage](#usage)
* [Getting help](#getting-help)
* [Contributing](#contributing)
* [License](#license)
* [Acknowledgments](#authors-and-acknowledgments)


## Introduction

Foliage (_**Foli**o ch**a**n**g**e **E**ditor_) is a desktop computer application that can perform operations in [FOLIO](https://www.folio.org), a library services platform ([LSP](https://journals.ala.org/index.php/ltr/article/view/5686/7063)) used by Caltech and other institutions. Foliage allows a user to look up records of various kinds, perform bulk changes in the values of record fields, delete records, and more. It communicates with a FOLIO server using the [OKAPI network API](https://github.com/folio-org/okapi/blob/master/doc/guide.md). The program is cross-platform compatible and currently in use on Windows and macOS computers at the Caltech Library.

<p align="center">
<img width="700"  src="https://github.com/caltechlibrary/foliage/raw/main/.graphics/foliage-screenshot.png">
</p>

Although Foliage is a desktop application and not a web service, it uses a web page as its user interface &ndash; it opens a page in a browser on the user's computer, letting the user interact with the program through the familiar elements of a web page. This lets Foliage present an identical user interface no matter whether it is running on Window, macOS, or Linux.


## Installation

There are multiple ways of installing Foliage, ranging from downloading a self-contained, single-file, ready-to-run program, to installing it as a typical Python program using `pip`.  Please choose the alternative that suits you.


### _Alternative 1: installing the ready-to-run executable programs_

For the Caltech Library, we provide Foliage in a ready-to-run form for Windows computers. This is the easiest and preferred way of getting a copy of Foliage. Please contact the author for more information.


### _Alternative 2: installing Foliage using `pipx`_

You can use [pipx](https://pypa.github.io/pipx/) to install Foliage. Pipx will install it into a separate Python environment that isolates the dependencies needed by Foliage from other Python programs on your system, and yet the resulting `foliage` command wil be executable from any shell &ndash; like any normal program on your computer. If you do not already have `pipx` on your system, it can be installed in a variety of easy ways and it is best to consult [Pipx's installation guide](https://pypa.github.io/pipx/installation/) for instructions. Once you have pipx on your system, you can install Foliage with the following command:
```sh
pipx install foliage
```

Pipx can also let you run Foliage directly using `pipx run foliage`, although in that case, you must always prefix every `foliage` command with `pipx run`.  Consult the [documentation for `pipx run`](https://github.com/pypa/pipx#walkthrough-running-an-application-in-a-temporary-virtual-environment) for more information.


### _Alternative 3: installing Foliage using `pip`_

The instructions below assume you have a Python 3 interpreter installed on your computer.  Note that the default on macOS at least through 10.14 (Mojave) is Python **2** &ndash; please first install Python version 3 and familiarize yourself with running Python programs on your system before proceeding further.

You should be able to install `foliage` with [`pip`](https://pip.pypa.io/en/stable/installing/) for Python&nbsp;3.  To install `foliage` from the [Python package repository (PyPI)](https://pypi.org), run the following command:
```sh
python3 -m pip install foliage
```

As an alternative to getting it from [PyPI](https://pypi.org), you can use `pip` to install `foliage` directly from GitHub:
```sh
python3 -m pip install git+https://github.com/calitechlibrary/foliage.git
```

_If you already installed Foliage once before_, and want to update to the latest version, add `--upgrade` to the end of either command line above.


### _Alternative 4: installing Foliage from sources_

If  you prefer to install Foliage directly from the source code, you can do that too. To get a copy of the files, you can clone the GitHub repository:
```sh
git clone https://github.com/caltechlibrary/foliage
```

Alternatively, you can download the files as a ZIP archive using this link directly from your browser using this link: <https://github.com/caltechlibrary/foliage/archive/refs/heads/main.zip>

Next, after getting a copy of the files,  run `setup.py` inside the code directory:
```sh
cd foliage
python3 setup.py install
```


## Usage

Documentation for Foliage is available online at [https://caltechlibrary.github.io/foliage/](https://caltechlibrary.github.io/foliage/).


## Getting help

If you find an issue, please submit it in [the GitHub issue tracker](https://github.com/caltechlibrary/foliage/issues) for this repository.


## Contributing

Your help and participation in enhancing Foliage is welcome!  Please visit the [guidelines for contributing](CONTRIBUTING.md) for some tips on getting started. Developer documentation is available in the repository at [`dev/dev-docs`](dev/dev-docs).


## License

Software produced by the Caltech Library is Copyright © 2021&ndash;2022 California Institute of Technology.  This software is freely distributed under a BSD type license.  Please see the [LICENSE](LICENSE) file for more information.


## Acknowledgments

This work was funded by the California Institute of Technology Library.

The [vector artwork](https://thenounproject.com/term/branch/1047074/) used as a starting point for the logo for this repository was created by [Alice Noir](https://thenounproject.com/AliceNoir/) for the [Noun Project](https://thenounproject.com).  It is licensed under the Creative Commons [Attribution 3.0 Unported](https://creativecommons.org/licenses/by/3.0/deed.en) license.  The vector graphics was modified by Mike Hucka to change the color.

<div align="center">
  <br>
  <a href="https://www.caltech.edu">
    <img width="100" height="100" src="https://raw.githubusercontent.com/caltechlibrary/foliage/main/.graphics/caltech-round.png">
  </a>
</div>
