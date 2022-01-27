# Glossary

A glossary of common terms used in Foliage and FOLIO.

```{glossary}
API
    "Application programm interface." An API is a well-defined interface
    through which interactions between software can take place. It is an
    approach for software systems to communicate with each other. In the
    context of FOLIO and Foliage, the APIs used are network-based:
    Foliage makes calls to network APIs provided by FOLIO.

CQL
    "[Contextual Query Language](http://zing.z3950.org/cql/intro.html)."
    A syntax for writing information queries. Here is an example of what
    a CQL expression looks like:
    `(username=="ab*" or personal.firstName=="ab*" or personal.lastName=="ab*")`

CSV
    "Comma-separated values." A spreadsheet format stored as text, in which
    values of different columns are separated by commas.

Foliage
    **FOLI**O ch**a**n**g**e **e**ditor.

FOLIO
    "The Future Of Libraries Is Open." FOLIO is an open-source library services
    platform that integrates print and electronic resource management.

HRID
    "Human readable identifier" (_not_ a holdings identifier!). Many
    of the record types in FOLIO have an `hrid` field.


JSON
    "JavaScript Object Notation." An open-standard format for storing
    data. The format uses a textual notation that is more or less
    human readable. It can be used to store lists, texts, numbers,
    attribute-value pairs, and more.

LSP
    "Library services platform." The kind of system that FOLIO is.
    
Microservices
    A type of software system architecture in which a single server provides
    a service to multiple tenants.

OKAPI
	"Okay API." The FOLIO API system. (Technically, the FOLIO middleware and
	API gateway.)

SRS
    FOLIO's "Source Record Storage." The server-side storage system
    underlying FOLIO's database facilities.
    
UUID
    "Universally unique identifier." A label used for information in computer
    systems. In FOLIO, UUIDs are the values of the `id` fields in records. An
    example UUID is `e9559bdb-868e-4f8b-bebc-6b482b0d91ea`.

```
