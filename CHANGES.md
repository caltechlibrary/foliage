# Change log for foliage

## ★ Version 1.2.0 (2022-02-03) ★

Changes:
* Fixed: it was too easy to cause the initial credentials screen to disappear by accident, and on Windows, simply switching away from Foliage and switching back would cause it to disappear, leaving the user in a lurch.
* Fixed: exporting from the _Look up records_ tab would export all searches done in a session, not just the most recent search. It now exports only the last search done.
* The summary table format in _Look up records_ now shows the location names, not just location identifiers, for records that have locations (items and holdings).
* The exported results from _Delete records_ now includes additional record fields beyond just the record identifiers.
* The description of the checkboxes on the _Look up records_ tab are hopefully more clear.
* The macOS app now starts faster, and the installation `.dmg` file is slightly nicer.
* The _Other_ tab provides a link to the online help pages.


## ★ Version 1.1.0 (2022-01-21) ★

Changes:
* Now automatically handles creation and deletion of holdings records as needed when changing the permanent locations of items.
* Now supports deleting instance and holdings records.
* Now supports uploading `.xslx` files in addition to text files, for uploading lists of identifiers.
* Fix bug in Change tab: if the user supplied instance id's, Foliage didn't correctly detect it, and didn't complain.
* Fix bug in exporting the UUID lists: Foliage would produce an error when attempting to export in CSV format. 
* Fix the title of the Foliage page in web browsers; it should be "Foliage" but instead was an internal description of a function in the code.
* Fix searching for holdings by instance hrid: Foliage would incorrectly report no holdings found.
* Fix other internal bugs.
* Removed splash screen on Windows because it fails to work outside of my development environment. I've [posted a question on the PyInstaller forums](https://github.com/pyinstaller/pyinstaller/discussions/6542) asking for help.
* Add "read me first" file to mac installer.


## ★ Version 1.0.2 (2022-01-20) ★

This verion fixes some minor internal bugs.


## ★ Version 1.0.1 (2022-01-05) ★

This version fixes a bug when retrieving user records.


## ★ Version 1.0.0 (2021-12-22) ★

Highlights of the changes in this release:

* Implemented fully the _Change records_ tab for item and holdings record changes.
* Changed the lookup tab to have a checkbox controlling whether only open loans are searched, or whether all loans are searched.
* Changed the lookup tab to have a checkbox controlling whether the FOLIO inventory API or the storage API is used to get records.
* Revised the order of the tabs to put "lookup records" first, as this seems like a more useful default.
* Slightly revised the user interface layout of some of the tabs.
* Fixed system tray widget for macOS.
* Fixed various bugs throughtout.
* Rewrote various internal functions for (hopefully) better clarity and logic.

Finally, documentation is now available at https://caltechlibrary.github.io/foliage/


## ★ Version 0.0.5 (2021-12-06) ★

Changes relative to the previous release:

* Fix bug in List UUIDs tab that caused the detailed records panel to always show the same record.
* Fix problem that on Windows, errors occurring before the window was created would not be shown at all.
* Make it so that exiting the taskbar widget will exit Foliage.


## ★ Version 0.0.4 (2021-12-02) ★

Changes relative to the previous release:

* Add ability to export a log of what was done in the change and delete tabs.
* Added a better and more informative splash screen on Windows.
* Reimplemented many dialogs using the PyWebIO popup widget instead of the JavaScript dialog used before.
* Fixed various internal coding bugs.


## ★ Version 0.0.3 (2021-10-16) ★

First internal release at the Caltech Library.


## ★ Version 0.0.0 (2021-10-16) ★

Project repository created at https://github.com/caltechlibrary/foliage
by Mike Hucka.
