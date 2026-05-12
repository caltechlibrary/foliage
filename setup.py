#!/usr/bin/env python3
# =============================================================================
# @file    setup.py
# @brief   Installation setup file
# @created 2021-10-16
# @license Please see the file named LICENSE in the project directory
# @website https://github.com/caltechlibrary/foliage
#
# Note: configuration metadata is maintained in setup.cfg.  This file exists
# primarily to hook in setup.cfg and requirements.txt.
# =============================================================================

from setuptools import setup


def requirements(file):
    from os import path
    required = []
    requirements_file = path.join(path.abspath(path.dirname(__file__)), file)
    if path.exists(requirements_file):
        with open(requirements_file, encoding='utf-8') as f:
            for ln in filter(str.strip, f.read().splitlines()):
                if ln.startswith('#'):
                    continue
                if ln.startswith('-r '):
                    # Recurse into included requirements file.
                    included = ln[3:].strip()
                    required.extend(requirements(included))
                elif not ln.startswith(('-', '.', '/')):
                    required.append(ln)
    return required


setup(
    setup_requires = ['wheel'],
    install_requires = requirements('requirements.txt'),
    extras_require={'dev': requirements('requirements-dev.txt')},
)
