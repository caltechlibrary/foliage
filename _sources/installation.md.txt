# Installation

There are multiple ways of installing Foliage, ranging from downloading a self-contained, single-file, ready-to-run program, to installing it as a typical Python program using `pip`.  Please choose the alternative that suits you.


## Preliminary requirements

Foliage is written in [Python 3](https://www.python.org) and makes use of some additional Python software libraries that are installed automatically during the [installation steps](#installation). It also assumes a macOS, Windows or Linux environment, and a working Internet connection.


## Installation instructions

### _Alternative 1: installing the ready-to-run version_

For the Caltech Library, we provide Foliage in a ready-to-run form for Windows and macOS computers. This is the easiest and preferred way of getting a copy of Foliage. Please contact the author for more information.


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

