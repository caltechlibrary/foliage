# Creating a splash screen

When Foliage runs on Windows, it shows a splash screen when it first starts up. Here is how the splash screen is created.


## Splash screens in PyInstaller

On Windows, it is possible to make a PyInstaller-produced application [show a splash screen](https://pyinstaller.readthedocs.io/en/stable/usage.html#splash-screen-experimental) while an application is starting. This splash screen is shown by the loader that PyInstaller creates, and it's shown before your application's code is unpacked and loaded at run-time, so the screen shows up almost immediately after a user starts the application. This is a good thing, because PyInstaller-built binaries tend to take a long time to start.

The application does not need to do anything to start the splash screen (this is done by putting appropriate configuration values into the [PyInstaller specification file](../../pyinstaller-win32.spec)), but the application _does_ need to do something to make the splash screen disappear. This is accomplished by running the following bit of PyInstaller code at an appropriate time:

```python
import pyi_splash

# The splash screen remains open until this function is called
# or the Python program is terminated.
pyi_splash.close()
```

In Foliage, this code is wrapped up in another function defined in `ui.py`, and _that_ function is invoked by the main Foliage loop after the application creates the main Foliage window.


## Generating a splash screen a build time

A limitation of PyInstaller's splash screen feature is that it can only show an image. For Foliage, I wanted to show a version number in the splash screen so that the user knows which version they're getting, but doing so meant finding a way to generate a new splash screen image every time a new version of Foliage was produced.

<p align="center">
<img alt="Example of the Foliage splash screen" src="../../.graphics/example-splash-screen.png">
</p>

I automated this process using code in the subdirectory [`dev/splash-screen`](../splash-screen). The artwork is in SVG format. Since an SVG file is written in plain text, it's possible to put placeholders in the SVG file itself and then substitute the values when needed. The scheme for Foliage works like this:

1. The file `foliage-splash-screen.svg.tmpl` contains placeholders.
2. The small program [`create-splash-screen.py`](../splash-screen/create-splash-screen.py) is run by the `make.bat` file before PyInstaller is run, and performs two steps:
   1. substitute values for the placeholders and produce a new file, `foliage-splash-screen.svg`
   2. convert `foliage-splash-screen.svg` to a PNG file (`foliage-splash-screen.png`) written in the same directory
3. The PyInstaller [specification file](../../pyinstaller-win32.spec) points to the `.png` file in the splash screen configuration, so that PyInstaller reads an image with an up-to-date version number.

The splash screen image for a given Foliage release is static. The small program is run at application build time, not at run-time. The image is embedded in the self-contained Foliage application created by PyInstaller.
