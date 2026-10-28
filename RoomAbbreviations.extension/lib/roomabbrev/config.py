# -*- coding: utf-8 -*-
"""Static identifiers for the Room Abbreviations tools.

NEVER change the GUIDs once this has been used in a real project:
  - PARAM_GUID ties every project's "Room Abbreviation" parameter (and every
    room tag label) to this tool.
  - SCHEMA_GUID identifies the extensible storage schema. A schema's fields
    are fixed forever for a given GUID; if you ever need new fields, make a
    new schema GUID and migrate.
  - UPDATER_GUID identifies the IUpdater. Projects remember it, so changing
    it produces "missing updater" warnings in older projects.
"""
import os
import tempfile

# --- Shared parameter -------------------------------------------------------
PARAM_NAME = "Room Abbreviation"
# Same definition as PyPiPie_RoomLib (Data Pusher) so both tools share ONE
# parameter. Keep GUID, name, group, description and flags identical to it.
PARAM_GUID = "7dcd381d-1775-4033-926e-13705844273d"
PARAM_GROUP_NAME = "Rooms"                  # group inside the shared param file
PARAM_DESCRIPTION = "Abbreviation for room name."
PARAM_USER_MODIFIABLE = True

# --- Extensible storage -----------------------------------------------------
SCHEMA_GUID = "a553f366-a932-4239-971b-3d8ee302fab2"
SCHEMA_NAME = "PyRevitRoomAbbreviations"    # letters/digits/underscore only
VENDOR_ID = "PYREVIT"

# --- Updater ----------------------------------------------------------------
UPDATER_GUID = "d7ddfa3e-0ff4-4d38-a5a8-8ac0b768119e"
UPDATER_NAME = "Room Abbreviation Updater"

# --- Behaviour --------------------------------------------------------------
# Value written to rooms whose name is not in the table. "" clears stale
# abbreviations when a room is renamed to something without one.
NO_MATCH_VALUE = ""

# --- Files ------------------------------------------------------------------
_APPDATA = os.environ.get("APPDATA") or tempfile.gettempdir()
DATA_DIR = os.path.join(_APPDATA, "pyRevit", "RoomAbbreviations")
# Shared parameter file this tool writes its definition into when the user
# has none of their own (or chooses not to touch theirs).
SHARED_PARAM_FILE = os.path.join(DATA_DIR, "RoomAbbreviations_SharedParameters.txt")

# --- Bundled standards (RoomAbbreviations.extension/standards) ---------------
# Replace these files to change the office standard; keep the names.
EXT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STANDARDS_DIR = os.path.join(EXT_DIR, "standards")
STANDARD_ABBREVIATIONS_FILE = os.path.join(STANDARDS_DIR, "Standard Room Abbreviations.txt")
STANDARD_TAG_FAMILY_FILE = os.path.join(STANDARDS_DIR, "Room Tag - Abbreviation.rfa")
