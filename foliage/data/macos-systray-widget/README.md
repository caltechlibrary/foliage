# Systray widget for macOS

This directory contains a widget for putting an icon in the macOS system tray (the row of icons in the upper right of the screen on macOS, in the system menubar). The widget has only one function: offer a _Quit_ menu option. It is started when Foliage first starts up, and while Foliage runs, the widget will stay in the system tray. Its purpose is to make it possible for the user to quit Foliage if they have lost track of Foliage's web page.

The widget is written in [go](https://go.dev) rather than Python so that it is possible to create a self-contained executable that can be bundled inside the Foliage application created using PyInstaller. It is not possible to use a Python script for this purpose because PyInstaller [does not bundle a Python interpreter](https://github.com/pyinstaller/pyinstaller/wiki/FAQ) in the application it creates, and we can't assume that the user's environment has a Python interpreter (or where it might be installed). Give this constraint, I searched for a solution that would allow a self-contained binary to be bundled inside the application we create using PyInstaller, so that Foliage could run this application as a subprocess. Go is well suited to this purpose because the binaries it creates are statically-linked.

This widget code is based on the example widget with [systray](https://github.com/getlantern/systray), a cross-platform Go library to create system tray widgets. I simply copied the example's [main.go](https://github.com/getlantern/systray/blob/master/example/main.go) file and the icon code, and adapted them to create what's in this directory.

The [systray](https://github.com/getlantern/systray) code by [Lantern](https://github.com/getlantern) is licensed under the Apache 2.0 open-source license.
