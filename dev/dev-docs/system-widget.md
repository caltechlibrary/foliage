# Taskbar/menubar widget for Foliage

A disadvantage of using a PyWebIO-based approach is that there is no obvious indication to the user whether Foliage is running, aside from looking at the web page that serves as Foliage's interface.  This is not great: users typically have a lot of browser windows and tabs open, and could lose track of the one for Foliage. If the user switches away from the web page or minimizes the window or does anything that might cause them to lose sight of it, then they may forget about it altogether or be confused about what's happening.

A traditional desktop application on Windows or macOS would have an indication, such as an icon in the Windows taskbar or in the macOS Dock, or alternatively, an icon in the macOS status bar, showing that the application is still running.  This widget would be tightly coupled with the application itself, such that exiting from the widget would exit Foliage too, and conversely, exiting Foliage would close the widget. 

There is no built-in capability in PyWebIO itself to do this. That's actually not so surprising; PyWebIO's purpose is to let applications use a web page in a browser as a user interface, so it makes sense that it does not have facilities for creating or managing taskbar/menubar/dock widgets. A separate and independent (from PyWebIO) approach must be used. I could find no existing solution, so I developed a novel approach. It works, but creating it turned out to be much harder than expected.

## The obstacles

I explored a variety of options including off-the-shelf widget packages for Python ([pystray](https://github.com/moses-palmer/pystray) and [rumps](https://github.com/jaredks/rumps)), writing code in PyQt, and writing code in [pywin32](https://pypi.org/project/pywin32/) and Apple's AppKit.

At first, the Python packages seemed to work and offered the simplest solution ... until I tried them in the PyInstaller-built Foliage application. It turns out that [PyInstaller does not bundle a Python interpreter](https://github.com/pyinstaller/pyinstaller/wiki/FAQ), which means they won't work in the final application without a lot of effort. (You could do it by building _two_ PyInstaller applications, one for Foliage and one for the widget, and install them both on the user's system, and then find a way to make sure Foliage can locate the widget application on the user's computer and start it, and so on. It all seemed too complex and fragile.)

This led me to coding something in PyQt. The code is simple enough, and worked on Windows. I thought I was done, then I tried it on macOS ... and it was impossible to make work on macOS. The problem there lies is how GUI libraries expect event loops to be implemented and how that interacts with GUI threads on macOS. Libraries like PyQt require you to execute a blocking call (in the case of PyQt, it's `app.exec_()`) to start the user interaction, but in Foliage, we have to start a _different_ event loop controlled by PyWebIO. You can't call `app.exec_()` in that thread (because it would block the PyWebIO event loop), and you also can't start a separate Python thread and call `app.exec_()` there &ndash; doing so leads to a macOS error about the GUI event loop being outside the main thread. (For reasons that are not entirely clear, this problem does not seem to exist on Windows.)

The only solution I found on macOS is to run the widget as a separate _process_ spawned by Foliage. This lead to a new problem: how to provide a self-contained executable for the widget, one that could be bundled inside the PyInstaller-built Foliage application. The complexity of managing two PyInstaller-based applications seemed too high, so I searched for a way to write a simple program that could be compiled with static linking so that it would have no other dependencies. I remembered that Go language programs are statically linked by default, and as luck would have it, someone else wrote [systray](https://github.com/getlantern/systray), a simple system tray widget in Go, which gave me a starting point.

That solved the problem, and led to solutions for both operating systems. On Windows, Foliage uses PyQt code to create a simple taskbar widget and runs it in a separate thread; on macOS, Foliage uses a self-contained, statically-linked binary that it runs in a subprocess.


## Architecture

The main widget-handling code is in [`../../foliage/system-widget.md`](../../foliage/system-widget.py). This defines a class, `SystemWidget`, that encapsulates the control of the widget for both Windows and macOS. The Foliage `main()` function in [`../../foliage/__main__.py`](../../foliage/__main__.py) creates an instance of `SystemWidget` right before starting the PyWebIO server loop.

In the Windows version of the widget (which uses PyQt GUI elements), a subthread runs the PyQt event loop. In the macOS version of the widget, a subprocess runs a completely independent program written in Go (for reasons discussed above). The `SystemWidget` object provides a method, `running()`, that can be tested periodically by the Foliage main loop to see if the widget is still running. If the user chooses Quit from the widget, whether it's the PyQt-based widget in a subthread or the separate program running in a subprocess, it causes the widget to stop. The method `running()` will return `False`, and this is used by the Foliage main loop as an indication that it's time to exit.

The approach for testing `running()` in the Foliage main loop is slightly unobvious, so here is some additional elaboration about what's going on. The relevant code is at the end of the function `foliage_page()` in [`../../foliage/__main__.py`](../../foliage/__main__.py):

```python
    while True:
        # Block, waiting for a change event on any of the pins being watched.
        # The timeout is so we can check if the user quit the taskbar widget.
        changed = pin_wait_change(pin_names, timeout = 1)
        if (not widget or widget.running()) and not changed:
             continue
        if (widget and not widget.running()):
            log('widget has exited')
            quit_app(ask_confirm = False)
        if changed and changed['name'] == 'quit':
            log('user clicked the Quit button')
            quit_app(ask_confirm = True)
            continue                    # In case the user cancels the exit.
        # Find handler associated w/ pin name & call it with value from event.
        name = changed["name"]
        log(f'invoking pin callback for {name}')
        watchers[name](changed['value'])
```

The infinite loop checks the state of PyWebIO GUI elements on a 1 second interval. When 1 second has passed, the call to `pin_wait_changes(...)` returns. The next line tests if the widget is still running; if it is, and none of the GUI elements have changed state, then the loop immediately returns for another round. If instead the widget is no longer running, then Foliage calls `quit_app(...)`.

It is possible to start Foliage without running the widget; this is an option when running Foliage from the command line with the option `--no-widget`. This is why the code above first tests that the variable `widget` has a value.
