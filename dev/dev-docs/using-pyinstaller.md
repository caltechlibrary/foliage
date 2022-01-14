# Using PyInstaller

PyInstaller is a tool that bundles a Python application and all its dependencies into a single package. It can be used to produce self-contained, single-file executable applications on Windows, macOS, and Linux. I’ve used it to create binaries for many applications used by library staff (e.g., _Hold It_, _Lost It_, _Handprint_, _Foliage_, many others). There are other methods of creating single-file executables, such as using `shiv` (which I also do); compared to `shiv`, PyInstaller has the advantage that the result is truly a standalone application and does not require the user to have a Python runtime environment installed on their computer (unlike the case with `shiv`) but a disadvantage that the resulting application takes a noticeable amount of time to start up every time the user runs it.

What follows is an attempt at describing everything I know about using PyInstaller. I will use Foliage as the example because that application makes use of some newer and advanced PyInstaller features.

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
├── foliage
│   ├── __init__.py
│   ├── __main__.py
│   ├── data
│   │   ├── foliage-icon.ico
│   │   ├── foliage-icon.png
│   │   └── ...
│   └── ... other application Python files ...
├── make.bat
├── pyinstaller-macos.spec
├── pyinstaller-win32.spec
├── requirements.txt
├── setup.cfg
└── setup.py
```

The procedure for using PyInstaller involves creating a configuration file (described below) and then running pyinstaller in the project directory. The configuration file references other files such as the source files in the application subdirectory. In the case of Foliage and other application I write, I write `Makefile` (for macOS) and `make.bat` (for Windows) rules to run `pyinstaller` with suitable arguments, but the basic command line is (showing the case for Windows):

```sh
pyinstaller --distpath dist/win --clean --noconfirm pyinstaller-win32.spec
```

This will put the output in the subdirectory `dist`/win.

## The PyInstaller configuration file

At the top level of an application such as Foliage, you will find configuration files for using PyInstaller for different operating systems. For the Library we’ve only needed to build for Windows and macOS. The file name does not matter. Most people seem to name the file with a `.spec` suffix (e.g., `pyinstaller-win32.spec`) but – and this was not clear to me at first – the content of the file is actually Python code. This is handy because for some complex cases, you can add Python code to the specification file to accomplish some things beyond merely setting variables.

PyInstaller has two ways of building applications, a so-called one folder approach and a one file approach. The latter is what you might expect and is the method that produces the most “normal” kind of application (normal to people used to using other desktop applications). The configuration file for a one-file application can have up to 5 main components, which take the form of objects named `Analysis`, `PYZ`, `EXE`, `BUNDLE`, and `Splash`. (The last is for a startup splash screen and is optional, but is used by Foliage.) Each of these objects take various keyword values. Most of the settings stay the same from application to application, and I end up copying an existing spec file to create new ones, then modifying the values in the file as needed. Many of the values are paths, and it’s easy to figure out what needs to be changed.

When trying to get a PyInstaller application build properly for the first time, the most common problems I’ve experienced have been the following:

* _Incorrect paths at build time_. This can be, for example, a path to an icon file that does not exist. The spec file needs to be adjusted, or maybe the missing file needs to be created.
* _Incorrect paths at application run time_. All of the files that comprise the application, including data files (icons, other data), all get embedded in the one-file executable, and at run time, your Python program needs to find them inside that executable. This means your code has to get the right path, and the PyInstaller configuration must actually put them where you think they getting put. This is especially true for the list of files passed to the `datas` argument to the Analysis object. This sometimes takes some trial and error. The debugging tips below can help with that.
* _Missing imports_. PyInstaller tries to figure out all the Python modules that need to be embedded inside the executable, but sometimes it misses some. Make sure that (1) the `requirements.txt` file is up to date, and (2) you run `pip3 install -r requirements.txt` before running PyInstaller so that the Python environment you’re using actually contains the version of the packages that are specified in the `requirements.txt` file. Still, some can get missed, for obscure reasons. That’s when you may have to adjust the value of the `hiddenimports` parameter to the Analysis object in the spec file.
* _No Python interpreter in the executable_. For a while I was under the mistaken impression that PyInstaller bundled a Python interpreter in the one-file executable. PyInstaller **does not embed a Python interpreter in the executable**, as counterintuitive as that may be. Instead, it converts your code to an executable form, and includes necessary run-time libraries, and that’s what gets run when you use your final application. The implication is that you can’t run Python scripts from your application.

## Debugging a PyInstaller configuration

The debugging loop goes roughly like this:

1. In the spec file, set the parameter values `debug = True` and `console = True` for the `EXE` part.
2. Run PyInstaller to create the executable.
3. Try to run the executable on the command line. If it fails, look at the debugging output to try to figure out what went wrong. (Often it’s a missing Python module.) Iterate this step.
4. If the application provides a GUI, then once you get it to start from the command line (step 3 above), next try to double-click the executable to start it like a regular application. With the `console = True` flag, the PyInstaller app will open a console window when it runs, and if the application generates errors, you may be able to see them printed there. Work on fixing the errors, and iterate this step until your application works.
5. Edit the spec file to set `debug = False` and `console = False`, and try to run the application again.
