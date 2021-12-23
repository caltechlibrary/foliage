# Change log for foliage

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
