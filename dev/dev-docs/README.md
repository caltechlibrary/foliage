# Foliage developer documentation

This directory constains my attempt at describing everything about how the Foliage application is built.

To build Foliage for Windows, I use a Windows 10 virtual machine running in [Parallels](https://www.parallels.com) on a Mac. For the command shell where I execute all commands, I use [Cmder](https://cmder.net) instead of the default Windows `cmd.exe`. The Windows environment has a shared file system with the Mac environment, so that any file changes made in one are visible immediately in the other. (All of the build and installation instructions here assume a shared file system between operating environments.)

Explanations about the software architecture:

* [How the Foliage splash screen works](creating-a-splash-screen.md)
* [How the taskbar/system tray widget works](system-widget.md)

Explanations about building the software:

* [Using PyInstaller](using-pyinstaller.md)
* [Making a new release of Foliage](making-a-new-release.md)
