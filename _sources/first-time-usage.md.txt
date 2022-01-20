# Starting Foliage

Foliage is a desktop application that runs on your computer, but &ndash; somewhat uncommonly &ndash; it uses a web page as its user interface. When you run Foliage, **you interact with it through your usual web browser**, but all the while, you are interacting with a program running on your computer. This style of user interface means the elements of the interface (the buttons, tabs, scroll bars) will be very familiar to anyone who has interacted with a modern web page. It also means that Foliage looks and behaves identically no matter whether it is running on Window, macOS, or Linux.

The sections below describe how Foliage works and the functionality presented in the user interface.

## Starting and quitting

There are multiple ways to start Foliage. One way is to double-click the program icon in the Windows Explorer or macOS Finder. You can also run Foliage as a command line application. (When doing the latter, you can find out available command-line options by running `foliage help`.)

In either case, Foliage will both (a) open a web browser page that acts as the main Foliage interface and (b) provide an icon in the Windows taskbar or the macOS system tray. The icon serves as a reminder that Foliage is running, and offers a single menu option to quit Foliage. You can access the menu by right-clicking on Windows and control-clicking on macOS. Below are images of what this icon looks like on different computers:

<figure>
    <img width="250px" src="_static/media/foliage-macos-systray.png">
    <figcaption>Portion of a macOS menubar, showing the Foliage "leaf" icon on the left.</figcaption>
</figure>

<figure>
    <img width="450px" src="_static/media/foliage-windows-taskbar.png">
    <figcaption>Portion of a Windows taskbar, showing the Foliage "leaf" icon on the right.</figcaption>
</figure>


## First-time permissions

When you start a given version of Foliage for the first time on Windows or macOS, the operating system will ask you to give permission for the application to accept network connections.  The following images show examples from macOS and Windows, respectively:

<figure>
    <img width="500px" src="_static/media/macos-accept-connections.png">
</figure>

<figure style="margin-top: 0;">
    <img class="shadowed" width="500px" style="margin-bottom: 3em" src="_static/media/windows-accept-connections.png">
</figure>

Make sure to click **Allow**. The request for accepting network connections is normal and not a sign of a problem. The reason it happens is that, although Foliage is a desktop application, it needs to let your web browser to connect to it so that the browser can interact with Foliage, and this triggers normal operating system security warnings. The operating system will not ask again after the first time you run a particular version of Foliage.


## FOLIO authentication

Before you can do anything in Foliage, the program will need to ask the FOLIO server for a _token_ (a secret key) that Foliage will use to authenticate itself every time it communicates with the server. To get the token, Foliage needs to ask you for some basic information. It does this with a short form that it presents the first time it is run on a new computer:

<figure>
    <img src="_static/media/authentication.png">
</figure>

Foliage needs four pieces of information to connect and authenticate itself to a FOLIO server: a user account name and password, the URL for the FOLIO server, and the tenant id for the FOLIO server. The user name and password must belong to a valid account in FOLIO and are unique to each user; the URL and tenant id are the same for all users at an institution, and need to be obtained from the institute's contacts at FOLIO.

Foliage **does not store** your user name and password. It uses them temporarily in the process of asking FOLIO for a token, but once it has the token, it stores _that_ (along with the URL and tenant id) in the secure password management system on the computer.

Once Foliage has stored the token, subsequent start-ups of Foliage will retrieve it from the secure password management system and will not ask you for the credentials again. If something happens and you need to change the credentials or regenerate the token, you can do so by going to the "Other" tab in Foliage and clicking the <span class="button color-primary">Edit credentials</span> button.

<figure>
    <img src="_static/media/other-tab.png">
</figure>


## Second-time permissions

On macOS, after you have run a given version of Foliage for the first time and it has stored the FOLIO token, the next time you start Foliage, macOS will ask you for another set of permissions:

<figure>
    <img width="500px" src="_static/media/macos-keychain.png">
</figure>

Click **Always Allow** in this dialog. Foliage needs to read the token it stored in your password keychain. It is safe to give Foliage this access because it only reads a specific key in the keychain (namely, `org.caltechlibrary.foliage`) and cannot read any other keys in your keychain.

If you only click **Allow** in this dialog, macOS will nag you repeatedly about the permissions and it will be very annoying.

