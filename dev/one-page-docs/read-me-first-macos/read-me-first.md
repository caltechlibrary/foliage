# Important macOS info about Foliage

There are two issues on macOS that may cause confusion the first time you try to use Foliage: a macOS security error, and slow startup times.

## macOS security error

After you download the Foliage disk image and open it, if you first try to run the application by double-clicking the icon in the Finder, you will get a macOS error dialog:

<p align="center">
<img src="dev/one-page-docs/read-me-first-macos/macos-malicious-warning.png">
</p>

To get around the warning, instead of double-clicking the Foliage app, **control-click on the Foliage icon in the Finder to get the following pop-up menu**:

<p align="center">
<img src="dev/one-page-docs/read-me-first-macos/control-click.png">
</p>

Next, select "Open" from the menu. MacOS will show a similar warning as before, but this time, the warning dialog will have an additional button named "Open":

<p align="center">
<img src="dev/one-page-docs/read-me-first-macos/file-dialog.png">
</p>

**Click the "Open" button**, and now it will start Foliage.

After you do these steps, macOS will **not** ask you again, and you will be able to double-click the icon to start it as usual. 


## Slow startup time

You may experience very long startup times on macOS. This is currently a known issue. During the startup, there will unfortunately be no feedback – it will look like nothing is happening. Please be patient and give it a significant time, as much as half a minute depending on your hardware. It should eventually start up.

