# The Foliage user interface

When you start Foliage normally (or after it shows the one-time credentials screen, described below), your browser should present a page that looks like the one below:

<figure>
    <img src="_static/media/main-page.png">
</figure>

The interface is organized into five areas of functionality accessed by clicking on the row of tabs near the top: (1) _Look up records_ (the first one shown when Foliage starts up), (2) _Change records_, (3) _Delete records_, (4) _Clean Records_, (5) _List UUIDs_, and (6) _Other_. They are described in detail below.

## Tab: look up records

The first tab &ndash; the one visible when you start up Foliage &ndash; provides a facility for looking up any item, instance, holdings, loan, or user record using any of the common identifiers by which the records can be addressed.  Depending on the type of record, this may be a barcode, a unique id (i.e., a string that looks like `f6fac97a-ee31-4300-aef6-b63be4ea23a2`), an "hrid" (human readable identifier), or an accession number. You can either type or paste the numbers into the text box on the page, or use the <span class="button color-outline-primary">Upload</span> button to upload a text file containing such identifiers. Identifiers can be separated by newlines, spaces, commas, colons, or semicolons; Foliage will also strip any quote characters from the input. Lastly, identifiers can be mixed: you can enter barcodes for some items and hrid's for others all at once, and Foliage won't care.

The screenshot below shows an example of looking up an item by its barcode:

<figure>
    <img src="_static/media/lookup-barcode.png">
</figure>

### Options for controlling lookups

Under the input text box, there are four control elements that influence what Foliage does.

* _Kind of record to retrieve_: The five radio boxes allow you to select the kind of record to retrieve based on the identifiers given. One of Foliage's powerful features is that it lets you use one kind of record identifier to search for _other_ kinds of records. For example, you can supply item barcodes and select _Instance_ as the type of record to retrieve, and Foliage will retrieve the instance records for the given identifiers. Or you can select _Loan_ as the type to retrieve and find out if there are any loans out for the given items. To take another example, you could provide a user identifier, select _Item_ as the kind of record to retrieve, and get back a list of the items on loan to the user.
* _Search open loans only_: When searching for loans, Foliage can be told to consider only open loans, or all loans. You can use this checkbox to choose what Foliage should do. Use this option with caution: unchecking this will cause Foliage to retrieve any loans, including closed loans from the history of loans for every item in the input, which could potentially be a long list and take a very long time to retrieve.
* _Output format_: Foliage can present the output either in a summary format or in the raw data format retrieved from the FOLIO server. The summary format is a custom tabular format that shows a subset of the fields from each record. Different record kinds are presented with different fields in the output.
* _Use inventory [API](glossary.html#API) for items and instances_: Items and instances in FOLIO come in two slightly different record formats, depending on which one of two FOLIO APIs are used to retrieve them. The so-called "inventory" API returns results that have slightly more data compared to the so-called "storage" API. The additional fields are computed by FOLIO and are not actually stored with the records. The additional information can be useful when exploring items and instances, but because the inventory API does not represent what is actually stored by FOLIO, it is better to deselect this option and make Foliage use the storage API if you are working with records for the purpose of changing field values or performing other actions.

### Saving the results

After performing the search and displaying the results, Foliage includes a button named <span class="button color-outline-primary">Export</span> at the bottom of the page. This allows you to export a list of all the records you looked up as a file in [CSV](glossary.html#CSV) or [JSON](glossary.html#JSON) format.


## Tab: change records

The _Change records_ tab provides functionality for changing the values of fields in records. You can use it to add, change, or delete values. It currently works only for item and holdings records, and only for the _Temporary location_, _Permanent location_, and _Loan type_ fields, though this may be expanded in the future.

<figure>
    <img src="_static/media/change-tab.png">
</figure>

The bottom left-hand half of the _Change records_ tab includes an input box where you can type or copy-paste identifiers of item records and/or holdings records. "Identifiers" here can be barcodes, unique id's (i.e., strings that looks like `f6fac97a-ee31-4300-aef6-b63be4ea23a2`), or hrid's (human readable identifiers). Alternatively, instead of typing or copy-pasting identifiers, you can upload a file of identifiers by clicking on the <span class="button color-outline-primary">Upload</span> button.

The bottom right-hand half of the _Change records_ tab features a set of <span class="button color-primary">Select</span> buttons and radio buttons. The first button allows you to select the field to be changed. Clicking on the button will pop up a dialog where you can select from a list of fields that Foliage knows how to change:

<figure>
    <img src="_static/media/change-tab-select-field.png">
</figure>

Once you select a field and click <span class="button color-primary">Submit</span> in the dialog, the _Change records_ tab will show the selected field to the right of the button you just clicked:

<figure>
    <img src="_static/media/change-tab-selected-field.png">
</figure>

Next, choose the action to be performed on the records. The following are the possible actions and their meanings:

* _Add value_: this only acts when an item record does not have a value for the selected field. If you select _Add value_, only the new field value selector is enabled; the selector for the current field value is grayed out and disabled. When the operation is actually performed, Foliage will check each record to see if the field is present at all (with any value); if the field is missing, then Foliage will add it with the given value, but if a record has a value for the given, then Foliage will skip that record.
* _Change value_: this operation needs both a current field value and a new field value, so both selectors are enabled when you select _Change value_ as the action. When the operation is performed, Foliage will check each record to see if it has the specified current field value. If it does, the record will be changed to have the new field value, but if the record doesn't (either because the value it has is different or the record doesn't have the field at all) then Foliage will skip that record.
* _Delete value_: this operation needs a current field value but not a new field value, so when the action is _Delete value_, the new field value selector is disabled. When the operation is performed, Foliage will check if each record has the given value for the field. If it does, Foliage will delete the field value; if a record doesn't, Foliage wil skip that record.

Depending on the action chosen, <span class="button color-primary">Select</span> buttons may be enabled for either or both the current field value and/or the new field value. When clicked, Foliage will pop up a dialog with a long list of possible field values. Here is an example:

<figure>
    <img src="_static/media/change-tab-value-selector.png">
</figure>

Once the required values have been selected for the relevant fields, click the <span class="button color-primary">Change records</span> button to proceed with the changes.

### Field matching and change operations

The selectors in the _Change records_ interface are designed to ask only for the values actually needed for a given operation. The values requested are required. For example, if you select _Delete value_ as the action, the Foliage interface will require you to select a current field value and will not allow you to leave it blank , and it will not let you specify a new field value. Foliage is also strict about matching field values when it performs the changes. For example, it will not change a record's field value to a new value unless it matches the value expected to be the current value.

These strict requirements are mainly motivated by the goal of reducing the chance of accidental unintended changes when long lists of records are involved, but they also have some benefits for how users can perform changes. For example, it's safe to give Foliage a list of data that may or may not have specific field values, because it will skip those that don't match. For example, suppose books from two different locations A and B are being moved to location C. You can load a list of the book barcodes, select A as the current location field value and C as the new field value, click the <span class="button color-primary">Change records</span> button to make the changes, then (without doing anything else) change the selection of the current field value to B in the user interface, and click <span class="button color-primary">Change records</span> button a second time. Since Foliage will only change matching records, the first run will change only those records that have current location A and the second run will change only those records that have current location B. Together, the two runs will have performed movers A → C and B → C.

### Saving a log of the results

After performing the changes and printing a summary of the results, Foliage will include a button named <span class="button color-outline-primary">Export</span> at the bottom. This allows you to export a list of all the changes as a CSV file.


## Tab: delete records

You may already have guessed what the _Delete records_ tab in Foliage allows you to do. The current version of Foliage allows the deletion of item, holdings, and instance records. Foliage is smart enough to perform deletions recursively if necessary: deleting a holdings record deletes all the associated items, and deleting an instance record deletes all the associated holdings and items.

<figure>
    <img src="_static/media/delete-tab.png">
</figure>

The tab layout is simple. It includes an input box where you can type or copy-paste identifiers of item records (barcodes, unique id's, or hrid's), an <span class="button color-outline-primary">Upload</span> button that lets you upload a file of identifiers, a <span class="button color-primary">Delete records</span> button to perform the deletions, and finally, the usual <span class="button color-outline-primary">Clear</span> button to clear past output.

```{warning}
As noted above, deleting a holdings record **will delete all the item records too**, for items associated with the holdings record; likewise, deleting an instance record **will delete all its holdings and items**. Use the Delete facility carefully!
```


## Tab: clean records

At Caltech Library, the following situation sometimes occurs. A patron may have had loans on items, and at some point one of those items may be deemed lost. Normally, Library staff need to delete the loans and delete the item records from FOLIO. However, if the regular order of events is not followed and _only_ the item record is deleted, then patron's record in FOLIO will have an associated loan record that refers to a nonexistent item. At Caltech Library, we call these _phantom loans_ because they are ghosts that haunt FOLIO and cause problems.

The _Clean Records_ tab in Foliage is designed to search for loans based on user identifiers, and delete any loan records for items that cannot be found in FOLIO. Loans for items that do exist are left untouched; only loans on nonexistent items are affected.

<figure>
    <img src="_static/media/clean-records-tab.png">
</figure>

To use _Clean Records_, input or upload a list of user identifiers (either user barcodes or user id's), and click on the <span class="button color-primary">Delete phantom loans</span> button.


## Tab: list UUIDs

Many data fields in FOLIO records take values drawn from controlled vocabularies. These vocabularies consist of unique identifiers ([UUIDs](glossary.html#UUID) &ndash; strings that look like `f6fac97a-ee31-4300-aef6-b63be4ea23a2`). Each different type of field in a record can take on values from a specific list of values.

Finding out the possible values is not easy to do directly in FOLIO. To help compensate, Foliage offers a simple way to list the possible values of various identifier types. This can be done in the _List UUIDs_ tab.

<figure>
    <img src="_static/media/list-uuids-tab.png">
</figure>

The operation of the _List UUIDs_ tab is simple: select a type of [UUIDs](glossary.html#UUID) from the pop-up menu, and click the <span class="button color-primary">Get list</span> button to make Foliage retrieve the list of identifiers from FOLIO. Shown below is an example of doing this for the "Holdings type" list.

<figure>
    <img src="_static/media/list-uuids-example.png">
</figure>

The identifiers can be clicked to get the full data for a given value. The complete list can also be exported by clicking the  <span class="button color-outline-primary">Export</span> button.



## Tab: other

The _Other_ tab has already been mentioned above in the section on [Authentication](#authentication). On this tab, Foliage provides three buttons, shown in the screenshot below:

<figure>
    <img src="_static/media/other-tab.png">
</figure>

* The <span class="button color-primary">Edit credentials</span> button allows you to edit the credentials used by Foliage for interacting with the FOLIO server. This includes the user name and password for FOLIO, the URL for the FOLIO server, and the tenant id. As mentioned in the [section on authentication](#authentication), Foliage does not store your user name and password, so when you click this button to edit the credentials, those fields will be blank and you will have to enter them again.
* The <span class="button color-primary">Show backups</span> button opens a Windows Explorer or macOS Finder window (depending on your operating system) on the folder where Foliage writes backups of every record it changes or deletes before it makes any change to the record. The backups are organized by the unique identifier of the record in question; within each subfolder, you will find a file named after the time the backup was made and containing the raw record data in a format known as [JSON](https://en.wikipedia.org/wiki/JSON). This is a simple backup scheme meant only as a last-ditch safety measure to guard against catastrophic errors. Note: Foliage does not offer a way of restoring records from these backup files. If you need to restore a record using these backups, consult with the FOLIO experts at your institution.
* The <span class="button color-primary">Show log file</span> button displays a log of all the actions taken by Foliage since it was started in the current session. The information is quite detailed and probably not much use to anyone but the developers of Foliage, but they can be useful when trying to investigate program bugs and other problems.

