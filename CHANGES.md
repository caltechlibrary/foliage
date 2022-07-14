# Change log for foliage

## ★ Version 1.3.0 (2022-07-13) ★

This version adds new new features:
* The _Change Records_ tab now supports changing the loan type on records.
* A new tab, _Clean Records_, is available. It currently has one capability: to delete "phantom" loans based on user id's, meaning loan records associated with users but for items that no longer exist in Folio.


## ★ Version 1.2.8 (2022-06-10) ★

Changes in this version:
* Fix a bug reported by Donna W. on 2022-06-09, in which it would incorrectly report all loans on the instance associated with a given holdings record, instead of only considering the items attached to the given holdings record.


## ★ Version 1.2.7 (2022-06-03) ★

Changes in this version:
* Fixes an error deleting instance records that didn't have a corresponding SRS record. The new approach just ignores a missing SRS record and proceeds with deletions in the FOLIO storage and inventory systems.
* Now accepts Caltech user id's with or without the leading `000`. Previously, unless a UID had the the form `0001234567`, Foliage would fail to find records. Now it tries a second time after adding leading 0's.
* Updates some dependency versions in `requirements.txt`.


## ★ Version 1.2.6 (2022-05-11) ★

A late-breaking discovery forced another release. It turns out that PyPI will not accept a package that uses a `git+https://` package dependency, which means Foliage can't be uploaded as it was. So, this release changes the `requirements.txt` file again, changes the installation process, and reduces the installation options.


## ★ Version 1.2.5 (2022-05-11) ★

Changes in this version:
* Use a fork of PyWebIO 1.4.0 with just the changes I need to fix a couple of limitations in the framework. Foliage's `requirements.txt` file references the fork in GitHub, so that installation of Foliage will get that version instead of the official PyWebIO version from PyPI.
* Update the (internal) constant used to recognize accession numbers.
* Fix a UI bug in the _Look up records_ tab, wherein clicking the _Look up records_ button while it was already running could result in multiple output streams and confusing output.


## ★ Version 1.2.4 (2022-04-01) ★

Changes in this version:
* If the FOLIO token is invalidated by EBSCO, then when Foliage starts up, the only option given to the user is to quit. If the user couldn't run the command-line version with `-K`, then they were unable to ever cause Foliage to regenerate the token. Fixed. The new code gives the user the option of editing the credentials and trying again.
* On Windows, Excel files might not have been recognized because Foliage didn't consider enough candidate MIME types. Fixed.
* Changed the Lookup tab to print the total number of records found (in addition to the number looked up).


## ★ Version 1.2.3 (2022-02-10) ★

This version fixes a bug in exporting storage (rather than inventory) records.


## ★ Version 1.2.2 (2022-02-10) ★

This version fixes a bug in printing inventory records in summary form in the _Look up records_ tab.


## ★ Version 1.2.1 (2022-02-08) ★

Changes:
* Fix bug in printing item summary with notes, in the _Look up records_ tab.
* Print notes for instance records in the summary view in the _Look up records_ tab.


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
