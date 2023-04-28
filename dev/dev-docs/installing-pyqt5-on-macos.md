# Notes about install PyQt5 on macOS systems

As of 2023-04-27, getting PyQt5 installed in Python seems much harder for Python versions 3.10 and later. I ended up using Python 3.9 for this reason for Foliage development.

On macOS Ventura, When I tried `pip install pyqt5`, it produced errors that implied it couldn't find `qmake`.

I got a copy of `qmake` by doing
```
brew install qt5
```

This put `qmake` in `/opt/homebrew/opt/qt5/bin`. I put that path on my shell `$PATH`, and verified `qmake` existed, then ran
```
pip3 install pyqt5 --config-settings --confirm-license= --verbose
```
again, and it worked that time.
