# Using PyInstaller

PyInstaller is a tool that bundles a Python application and all its dependencies into a single package. It can be used to produce self-contained, single-file executable applications on Windows, macOS, and Linux. I’ve used it to create binaries for many applications used by library staff (e.g., _Hold It_, _Lost It_, _Handprint_, _Foliage_, many others). There are other methods of creating single-file executables, such as using `shiv` (which I also do); compared to `shiv`, PyInstaller has the advantage that the result is truly a standalone application and does not require the user to have a Python runtime environment installed on their computer (unlike the case with `shiv`) but a disadvantage that the resulting application takes a noticeable amount of time to start up every time the user runs it.

What follows is an attempt at describing everything I know about using PyInstaller. I will use Foliage as the example because that application makes use of some newer and advanced PyInstaller features.


## Preliminary notes

I was unable to get this to work in Python 3.9.8 on Windows; I had to downgrade to Python 3.9.7.


## PyInstaller resources

Here is where I look for information when I need it:

* PyInstaller documentation at <pyinstaller.readthedocs.io>
* FAQ at <https://github.com/pyinstaller/pyinstaller/wiki/FAQ>
* [“If things go wrong”](https://github.com/pyinstaller/pyinstaller/wiki/If-Things-Go-Wrong) page
* Stack Overflow (PyInstaller has its [own tag](https://stackoverflow.com/questions/tagged/pyinstaller))

## Building an application using PyInstaller

A typical Python application will have a directory structure somewhat like this:

```
├── Makefile
├── make.bat
├── foliage
│   ├── __init__.py
│   ├── __main__.py
│   ├── data
│   │   ├── foliage-icon.ico
│   │   ├── foliage-icon.png
│   │   └── ...
│   └── ... other application Python files ...
├── pyinstaller-macos.spec
├── pyinstaller-win32.spec
├── requirements.txt
├── setup.cfg
└── setup.py
```

The procedure for using PyInstaller involves creating a configuration file (described below) and then running pyinstaller in the project directory. The configuration file references other files such as the source files in the application subdirectory. I write `Makefile` (for macOS) and `make.bat` (for Windows) rules to run `pyinstaller` with suitable arguments to run PyInstaller with the appropriate configuration file (for macOS or Windows, depending). An example of the basic command line for is:

```sh
pyinstaller --distpath dist/win --clean --noconfirm pyinstaller-win32.spec
```

The `--distpath` argument tells PyInstaller to put the output in the subdirectory `dist/win`; the `--clean` argument tells PyInstaller to remove temporary build files from previous runs.


## The two types of applications that can be built by PyInstaller

PyInstaller can build applications in two "modes": a so-called "one-dir" mode and a "one-file" mode. Foliage uses one mode for macOS and the other for Windows. The reasons for this are as follows.

In "one-file" mode, PyInstaller creates a compressed single-file archive of the application plus all the Python libraries and necessary system libraries (`.dll`'s on Windows) to create a self-contained, single-file application. This single-file app contains a bootloader program that is the thing actually executed when the user runs the app. This bootloader unpacks everything at run time into a temporary directory, and after that, starts the real Foliage application (all behind the scenes -- the user doesn't see any of this happening). However, this unpacking step takes time, during which nothing seems to be happening. Not only is this long startup time annoying for the user, but the lack of feedback can be very confusing ("did Foliage actually start? how long should I wait?"). The one-file app is great for packaging and distribution (because the result looks like any other application), but not for the user experience.

In "one-dir" mode, PyInstaller does not create a single-file archive; it leaves the files (the dependencies, dynamic libraries, data files, etc.) in a single folder, unpacked. Within this folder, there's a binary that is the program you actually run. The result is faster startup at run time because the unpacking step is unnecessary, _but_ the user has to know to find the right binary file inside that folder &ndash; a folder that contains dozens upon dozens of other files and folders. This is an even more confusing user experience. However, on macOS, unlike Windows, there's a feature we can use to advantage here. MacOS apps are _already_ folders: in the Finder, a program that looks like it's named `Foliage` is actually a folder named `Foliage.app`, and inside this folder are various files and subfolders. So it doesn't matter if we use PyInstaller's one-dir mode, because we can hide the results in the Foliage.app folder and the user doesn't need to know about these details. As a result, we take advantage of one-dir mode for its faster start times without compromising the user experience.


## The PyInstaller configuration file

At the top level of an application such as Foliage, you will find configuration files for using PyInstaller for different operating systems. For the Library we’ve only needed to build for Windows and macOS. The file name does not matter. Most people seem to name the file with a `.spec` suffix (e.g., `pyinstaller-win32.spec`) but the content of the file is actually Python code. This is handy because for some complex cases, you can add Python code to the specification file to accomplish some things beyond merely setting variables.

PyInstaller has two ways of building applications: a so-called one folder approach, and a one file approach. The latter is what you might expect and is the method that produces the most “normal” kind of application ("normal" to people used to using other desktop applications). The configuration file for a one-file application can have up to 5 main components, which take the form of objects named `Analysis`, `PYZ`, `EXE`, `BUNDLE`, and `Splash`. (The last is for a startup splash screen and is optional, but is used by Foliage on Windows.) Each of these objects take various keyword values. Most of the settings stay the same from application to application, and I end up copying an existing spec file to create new ones, then modifying the values in the file as needed. Many of the values are paths, and it’s easy to figure out what needs to be changed.

When trying to get a PyInstaller application build properly for the first time, the most common problems I’ve experienced have been the following:

* _Incorrect paths at build time_. This can be, for example, a path to an icon file that does not exist. The spec file needs to be adjusted, or maybe the missing file needs to be created.
* _Incorrect paths at application run time_. All of the files that comprise the application, including data files (icons, other data), all get embedded by PyInstaller into the one-file executable, and at run time, your Python program needs to find them inside that executable. This means your code has to get the right path, and the PyInstaller configuration must put them where you think they are getting put. This is especially true for the list of files passed to the `datas` argument to the Analysis object. This sometimes takes some trial and error. The debugging tips below can help with that.
* _Missing imports_. PyInstaller tries to figure out all the Python modules that need to be embedded inside the executable, but sometimes it misses some. Make sure that (1) the `requirements.txt` file is up to date, and (2) you run `pip3 install -r requirements.txt` before running PyInstaller so that the Python environment you’re using actually contains the version of the packages that are specified in the `requirements.txt` file. Despite all that, some imports can get missed by PyInstaller for obscure reasons. That’s when you may have to adjust the value of the `hiddenimports` parameter to the Analysis object in the spec file.
* _No Python interpreter in the executable_. For a while I was under the mistaken impression that PyInstaller bundled a Python interpreter in the one-file executable. PyInstaller **does not embed a Python interpreter in the executable**, as counterintuitive as that may be. Instead, it converts your code to an executable form, and includes necessary run-time libraries, and that’s what gets run when you use your final application. The implication is that you can’t run Python scripts from your application.

## Debugging a PyInstaller configuration

The debugging loop goes roughly like this:

1. In the spec file, set the parameter values `debug = True` and `console = True` for the `EXE` part.
2. Run PyInstaller to create the executable.
3. Try to run the executable on the command line. If it fails, look at the debugging output to try to figure out what went wrong. (Often it’s a missing Python module.) Iterate this step.
4. If the application provides a GUI, then once you get it to start from the command line (step 3 above), next try to double-click the executable to start it like a regular application. With the `console = True` flag, the PyInstaller app will open a console window when it runs, and if the application generates errors, you may be able to see them printed there. Work on fixing the errors, and iterate this step until your application works.
5. Edit the spec file to set `debug = False` and `console = False`, and try to run the application again.
