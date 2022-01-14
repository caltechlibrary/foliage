# Splash screen creator for Foliage

A limitation of PyInstaller's splash screen feature is that it can only show an image. For Foliage, I wanted to show a version number in the splash screen so that the user knows which version they're getting, but doing so meant finding a way to generate a new splash screen image every time a new version of Foliage was produced.

<p align="center">
<img alt="Example of the Foliage splash screen" src="../../.graphics/example-splash-screen.png">
</p>

I automated this process using code in this subdirectory. The artwork is in SVG format. Since an SVG file is written in plain text, it's possible to put placeholders in the SVG file itself and then substitute the values when needed. The scheme for Foliage works like this:

1. The file `foliage-splash-screen.svg.tmpl` contains placeholders.
2. The small program [`create-splash-screen.py`](create-splash-screen.py) is run by the top level `make.bat` file before PyInstaller is run, and performs two steps:
   1. substitute values for the placeholders and produce a new file, `foliage-splash-screen.svg`
   2. convert `foliage-splash-screen.svg` to a PNG file (`foliage-splash-screen.png`) written in the same directory
3. The PyInstaller [specification file](../../pyinstaller-win32.spec) points to the `.png` file in the splash screen configuration, so that PyInstaller reads an image with an up-to-date version number.

The splash screen image for a given Foliage release is static. The small program is run at application build time, not at run-time. The image is embedded in the self-contained Foliage application created by PyInstaller.
