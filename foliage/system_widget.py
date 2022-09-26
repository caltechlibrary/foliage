'''
system-widget.py: class for creating a taskbar or menubar widget

A disadvantage of using a PyWebIO-based approach is that there is no obvious
indication to the user whether Foliage is running, aside from looking at the
web page that serves as Foliage's interface.  This is not great: users
typically have a lot of browser windows and tabs open, and could lose track
of the one for Foliage. If the user switches away from the web page or
minimizes the window or does anything that might cause them to lose sight of
it, then they may forget about it altogether or be confused about what's
happening.

A traditional desktop application on Windows or macOS would have an
indication, such as an icon in the Windows taskbar or in the macOS Dock, or
alternatively, an icon in the macOS status bar, showing that the application
is still running.  This widget would be tightly coupled with the application
itself, such that exiting from the widget would exit Foliage too and exiting
Foliage would close the widget.

There is no built-in capability in PyWebIO itself to do this, so I had to
develop a novel approach.  It turned out to be much, much harder than
expected.

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
   non-Python application to create a widget, and then using a subprocess (not
   a thread) to start that widget program.  This avoids the threading problem,
   at the cost of requiring a scheme for communicating with a separate process
   for the widget.

2) On Windows, where a subthread *can* be used for the PyQt widget, it was
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
   will have a Python installed.  After going down a number of rabbit holes,
   I finally hit on a working solution: use a separate, statically-linked
   program that is run by Foliage as a subprocess.  The binary can be bundled
   in the PyInstaller-built application so that Foliage knows where to find
   it.  The Go language provides an especially attractive solution because the
   binaries are very easy to build and statically-linked by default, and as
   luck would have it, a system tray package already existed and I was able to
   use it as a starting point (https://github.com/getlantern/systray).  The
   code for this widget written in Go is in data/macos-systray-widget/.


Copyright
---------

Copyright (c) 2021-2022 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.interrupt import wait
from   os.path import exists, dirname, join, realpath
from   sidetrack import log
import sys


class SystemWidget():
    '''Encapsulate the control of a taskbar/system tray widget

    The approach taken here involves 2 separate systems:

    On Windows: the code for the widget is in this file, in the method
       start_windows_widget(). It  uses PyQt and runs the PyQt event loop
       in a subthread.  It sets the variable self.widget_info to a structured
       object (a dict), and sets a value inside that object when the PyQt
       event loop ends.  The PyQt event loop ends when the user selects "Quit"
       from the widget menu.  The use of a structured object (and not a simple
       Boolean variable) makes it possible to check the value outside the PyQt
       event loop, in the method running().

    On macOS: the widget is implemented as a separate program altogether.  The
       code is in the subdirectory data/macos-systray-widget/.  The method
       start_macos_widget() runs the separate program as a subprocess.  The
       method running() tests whether the process is still running; if it's
       not, it means either the user quit the widget using the "Quit" menu
       or else the widget was killed somehow externally to Foliage.
    '''

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
        '''Return True if the taskbar/system tray widget is still running.

        In the Windows version of the widget (which uses PyQt GUI elements),
        a subthread runs the PyQt event loop.  The user can select the "Quit"
        menu item to indicate they want to exit Foliage.  If the PyQt event
        loop is not running, this method returns False.

        In the macOS version of the widget (which is a completely separate
        program written in Go), a subprocess runs the widget program.  The
        user can select the "Quit" menu item to exit the widget.  If the
        widget process is not running, this method returns False.
        '''
        if sys.platform.startswith('darwin'):
            return self.widget_process and (self.widget_process.poll() is None)
        else:
            return self.widget_info and self.widget_info['running']


    def stop(self):
        '''Stop the widget.

        On Windows, this does not actually need to do anything, because when
        the main Foliage application process exits then Python will kill
        daemon threads automatically.

        On macOS, this performs a process kill() on the subprocess, and if
        that fails, it sends a SIGTERM to the process.
        '''
        if not self.running():
            log('stop called for system widget but it is no longer running')
            return
        if self.widget_process:
            log('killing macos widget process')
            self.widget_process.kill()
            try:
                out, err = self.widget_process.communicate(timeout = 1)
                log('widget process output: ' + str(out))
            except Exception:           # noqa: PIE786
                import signal
                log('sending SIGTERM to widget process')
                self.widget_process.send_signal(signal.SIGTERM)
            self.widget_process = None
        elif self.widget_info and self.widget_info['running']:
            # Nothing to do; it will get killed when Foliage exits.
            log('letting Windows widget get terminated normally on quit')


    def start_macos_widget(self):
        '''Start the Foliage system tray widget on macOS.'''
        import subprocess
        data_dir = realpath(join(dirname(__file__), 'data'))
        widget = join(data_dir, 'macos-systray-widget', 'macos-systray-widget')
        if exists(widget):
            log('starting macos systray widget: ' + widget)
            self.widget_process = subprocess.Popen(widget)
        else:
            log('macos widget binary is not at the expected path')


    def start_windows_widget(self):
        '''Start the taskbar widget on Windows.'''
        # We use a structured type, not a simple Boolean, because the value
        # needs to be set inside a thread but we need a handle on it from
        # outside the thread outside.  This next variable declaration puts it
        # in the lexical scope of the current function, such that the
        # show_widget() function below can access it.  Then, at the very end
        # of the current function, we set self.widget_info to point to this.
        # The indirection is needed because show_widget() can't get access
        # self.widget_info directly, because of scoping issues.
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
            icon.addFile(join(data_dir, 'foliage-icon-256x256.png'), QtCore.QSize(256, 256))
            icon.addFile(join(data_dir, 'foliage-icon-128x128.png'), QtCore.QSize(128, 128))
            icon.addFile(join(data_dir, 'foliage-icon-64x64.png')  , QtCore.QSize(64, 64))
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
            # app.exec_() exits and we continue execution here.  We proceed to
            # set the value inside widget_info to False.
            log('taskbar widget returned from exec_()')
            widget_info['running'] = False

            # The main Foliage loop tests the running state (via the method
            # running() on our parent object) on a 1-second polling interval.
            # Here we have to wait longer than 1 second, to give the main
            # loop enough time to detect that the running state has changed
            # and communicate to the browser window to close itself.  If we
            # don't pause long enough here, then something bad happens: the
            # ending of the PyQt thread results in Foliage being killed
            # before the main loop has a chance to perform an orderly quit
            # (and specifically, before it has time to run JavaScript code in
            # the browser window to close the window). If the Foliage window
            # is left on the screen but the Foliage process has quit, it's
            # very confusing for users, so we want to avoid that.  I haven't
            # been able to figure out how to prevent the PyQt thread exit
            # from killing all of Foliage; I think the problem lies in how
            # PyQt uses signals to communicate events, but despite various
            # attempts to ignore signals in the main thread on Windows, I've
            # been unable to prevent it from happening.  (Python signals on
            # Windows are known to be problematic; see the following very
            # informative posting by Eryk Sun on 2016-03-04 on Stack
            # Overflow: https://stackoverflow.com/a/35792192/743730) The only
            # solution I have found so far is to make *this* code pause
            # longer than the 1-sec polling interval of the main loop, to
            # give the main loop enough time to do an orderly exit.  That is
            # the reason for the next line.
            wait(2)

        from threading import Thread
        log('starting taskbar icon widget in a subthread')
        thread = Thread(target = show_widget, daemon = True, args = ())
        thread.start()
        # Note we never join() the thread, b/c that would block.  We start the
        # widget thread & return so caller can proceed to its own event loop.

        self.widget_info = widget_info
