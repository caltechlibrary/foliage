'''
system-widget.py: class for creating a taskbar or menubar widget

A disadvantage of using a PyWebIO-based approach is that there is no obvious
indication to the user whether Foliage is running, aside from looking at the
web page that serves as Foliage's interface.  If the user switches away from
the web page or minimizes the window or does anything that might cause them
to lose sight of it, then they may forget about it altogther or be confused
about what's happening.

A traditional application would have an indication, such as an icon in the
Windows taskbar or in the macOS Dock, or alternatively, an icon in the macOS
status bar, to show that the application is still running.  This widget would
be tightly coupled with the application, such that exiting from the widget
would exit Foliage too and exiting Foliage would close the widget.

The purpose of the code in this file is to implement such a thing.  It turned
out to be much, much harder than expected.

The biggest obstacle to doing it is how GUI libraries expect event loops to
be implemented, and on macOS, a related problem involving GUI threads.
Libraries like PyQt require you to execute a blocking call (in the case of
PyQt, it's app.exec_()) that starts the user interaction, but here in
Foliage, we have to start a different event loop controlled by PyWebIO.  So,
we can't use app.exec_() in the main thread.  This leads to the need to use
separate threads, which then leads to more problems:

1) On macOS, you can't run GUI event loops anywhere except in the main
   application thread, but as mentioned above, we can't do that because our
   main application thread is started by PyWebIO.  Doing so will result in an
   error from macOS about operations not being allowed outside the main
   thread.  In the end, on macOS, I couldn't find a way to make things work
   with PyQt at all: even trying to run a subprocess for the PyQt widget
   resulted in errors about not being in the main application thread.
   Non-PyQt solutions failed for similar reasons.  Basically, no GUI toolkit
   worked in a subthread.  (Thankfully, on Windows, this problem doesn't seem
   to exist, and a PyQt solution is possible.)  I briefly looked at PyWebIO's
   coroutines scheme as an alternative to its default subthread approach, but
   it wasn't immediately obvious how it would help solve the problem that we
   can't call app.exec_() from the Foliage main thread.

   The solution that I finally hit upon for macOS is to bundle a separate
   Python script just to create a widget, and then using a subprocess (not a
   thread) to start that widget program.  This avoids the threading problem,
   at the cost of requiring a scheme for being able to learn the state of the
   widget.

2) On Windows, where a subthread can be used for the PyQt widget, it was
   another challenge to figure out how to communicate to the main Foliage app
   when the user chooses to quit the widget.  It would have been simplest to
   have the widget code call our quit_app() directly.  It turns out that a
   subthread cannot issue PyWebIO calls because PyWebIO calls must be
   executed from the thread that started PyWebIO.  If you try, you don't get
   the kind of system errors you get when trying to use GUI event loops in a
   subthread, but the actions have no effect.  The widget function also can't
   throw an exception (e.g., SystemExit would have been an appropriate
   exception to throw for this purpose) because the exception won't end up in
   the main thread.  Thus, if you manage to get a GUI widget working in a
   subthread, you now face the problem of communicating to the parent thread
   that the user has selected "Quit" from the widget.

   After considerable time and many rabbit holes, I hit on the approach of
   (1) making the quit button in the PyWebIO UI use a PyWebIO pin object, so
   that testing for the quit button event can be done in the main event loop;
   (2) using a structured object (specifically a dict) containing a field
   value that is set inside the widget; (3) holding on to this structured
   object outside the widget, in the main thread, so that the main thread can
   test the value; and (4) using a timeout on the PyWebIO wait in the main
   foliage() "while True" loop, so the main thread can periodically test the
   value of that structured object to learn the current value set by the
   widget.  (See the end of the function foliage_page() in __main__.py.)

3) On Windows, the scheme worked.  On macOS, it worked on the command line
   when running "python3 -m foliage" or the equivalent, but ... failed in a
   PyInstaller-built application.  The problem is that PyInstaller does not
   bundle a Python interpreter, so running a separate Python script becomes
   impossible.  You don't want to make the assumption that the user's machine
   will have a Python installed.


Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.interrupt import wait
import os
from   os.path import exists, dirname, join, basename, abspath, realpath, isdir
from   sidetrack import log
import sys


class SystemWidget():

    def __init__(self):
        log('creating system widget')
        self.widget_info = None
        self.widget_process = None
        self.widget_thread = None
        if sys.platform.startswith('darwin'):
            self.start_macos_widget()
        else:
            self.start_windows_widget()


    def running(self):
        if sys.platform.startswith('darwin'):
            return self.widget_process and (self.widget_process.poll() is None)
        else:
            return self.widget_info and self.widget_info['running']


    def stop(self):
        if not self.running():
            log('stop called for system widget but it is no longer running')
            return
        if self.widget_process:
            log('killing macos widget process')
            self.widget_process.kill()
            try:
                out, err = self.widget_process.communicate(timeout = 1)
                log('widget process output: ' + str(out))
            except:
                import signal
                log('sending SIGTERM to widget process')
                self.widget_process.send_signal(signal.SIGTERM)
            self.widget_process = None
        elif self.widget_info and self.widget_info['running']:
            # Nothing to do; it will get killed when Foliage exits.
            log('letting Windows widget get terminated normally on quit')


    def start_macos_widget(self):
        import subprocess
        data_dir = realpath(join(dirname(__file__), 'data'))
        widget = join(data_dir, 'macos-systray-widget', 'macos-systray-widget')
        if exists(widget):
            log('starting macos systray widget: ' + widget)
            self.widget_process = subprocess.Popen(widget)
        else:
            log('macos widget binary is not at the expected path')


    def start_windows_widget(self):
        # We return a structured type, because the value needs to be set
        # inside a thread but we need to have a handle on it from the outside.
        widget_info = {'running': True}

        # The taskbar widget is implemented using PyQt and runs in a subthread.
        def show_widget():
            from PyQt5 import QtGui, QtWidgets, QtCore
            from PyQt5.QtCore import Qt

            log('creating Qt app for producing taskbar icon')
            app = QtWidgets.QApplication([])
            icon = QtGui.QIcon()
            data_dir = join(dirname(__file__), 'data')
            log('reading widget icons from ' + data_dir)
            icon.addFile(join(data_dir, 'foliage-icon-256x256.png'), QtCore.QSize(256,256))
            icon.addFile(join(data_dir, 'foliage-icon-128x128.png'), QtCore.QSize(128,128))
            icon.addFile(join(data_dir, 'foliage-icon-64x64.png'),   QtCore.QSize(64,64))
            app.setWindowIcon(icon)
            mw = QtWidgets.QMainWindow()
            mw.setWindowIcon(icon)
            mw.setWindowTitle('Foliage')
            mw.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowMinimizeButtonHint)
            mw.showMinimized()

            nonlocal widget_info
            log('starting windows taskbar widget')
            # The following call will block until the widget is exited (by
            # the user right-clicking on the widget and selecting "exit").
            app.exec_()

            # If the user right-clicks on the taskbar widget & chooses exit,
            # we end up here. Set a flag to tell the main loop what happened.
            log('taskbar widget returned from exec_()')
            widget_info['running'] = False

            # Wait a time to give the main loop time to run the quit actions.
            wait(2)

        from threading import Thread
        log(f'starting taskbar icon widget in a subthread')
        thread = Thread(target = show_widget, daemon = True, args = ())
        thread.start()
        # Note we never join() the thread, b/c that would block.  We start the
        # widget thread & return so caller can proceed to its own event loop.

        self.widget_info = widget_info
