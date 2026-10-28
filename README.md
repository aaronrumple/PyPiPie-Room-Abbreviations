# Room Abbreviations (pyRevit)

Keeps a **Room Abbreviation** parameter on Rooms filled from a room-name → abbreviation table
stored in the project's extensible storage.

The parameter is shared with PyPiPie / Data Pusher's RoomLib (GUID
`7dcd381d-1775-4033-926e-13705844273d`, group "Rooms"). If a project already has a
"Room Abbreviation" on Rooms (that GUID, another GUID, or a project parameter) it is used as is;
a parameter with that name bound to other categories gets Rooms added. A new one is created only
when none exists.

## Install
Copy `RoomAbbreviations.extension` into a pyRevit extensions folder (or add its parent folder in
pyRevit Settings > Custom Extension Directories) and Reload. Tab: **Rooms**, panel **Room Abbreviations**.

To merge into another extension: copy `lib/roomabbrev` into that extension's `lib`, copy the
panel folder into its tab, and paste the body of `startup.py` into its `startup.py`.

## Buttons
| Button | What it does |
|---|---|
| **Setup** | WPF dialog. Finds or binds the parameter on Rooms (Identity Data). Abbreviations: keep the current table, load the bundled standard, **or** load a custom tab-delimited file (replace or merge). Optionally opens a copy of the standard room tag to create a new tag (explanation dialog first). Fills every room and reports unmatched names. |
| **Edit Abbreviations** | Grid editor for the stored table: search, add/delete, import/export, *Add room names from project*, duplicate check, optional update of all rooms on save. Follows Revit's light/dark theme. |
| **Update All Rooms** | Re-applies the table to every room (e.g. after the project was edited without pyRevit). |
| **New Room Tag Family** | Explanation dialog, then a new blank family from the Room Tag template with the parameter in the active shared parameter file so *Edit Label > Add Parameter* can pick it. |
| **Help** | Opens `help/RoomAbbreviations.html`. The editor also has a Help button and F1, which open the editor section. |

## Automatic updates
`startup.py` registers an optional IUpdater for all documents. When a room is placed or its
**Name** changes, the abbreviation is written. Matching ignores case and extra spaces.
Rooms whose name isn't listed, or is listed with a blank abbreviation, get an empty value
(`NO_MATCH_VALUE` in `lib/roomabbrev/config.py`). Projects where Setup hasn't run are ignored.

## File format
```
Room Name<TAB>Abbreviation
OFFICE<TAB>OFF
VESTIBULE<TAB>
```
Header row optional, `#` lines ignored. Excel "Text (Tab delimited)" and "Unicode Text" both work.
## Office standards
`standards/` ships with the app and is what Setup's standard options use:
- `Standard Room Abbreviations.txt` - the standard abbreviation table (tab-delimited, format above).
- `Room Tag - Abbreviation.rfa` - the standard room tag; Setup opens a *copy* of it to create a new tag (its label uses the shared parameter GUID above).

Replace either file to change the standard; keep the file names.

## Notes
- Don't change the GUIDs in `config.py` after first use.
- Workshared models: the table lives in one DataStorage element; saving it needs that element
  to be editable. Rooms owned by others are skipped and listed in the report.
- Written for pyRevit's IronPython engine (Revit 2021–2026).
