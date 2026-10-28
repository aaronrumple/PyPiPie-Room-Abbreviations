# -*- coding: utf-8 -*-
"""IUpdater: when a room is placed or its Name changes, write the matching
abbreviation into the Room Abbreviation parameter.

Registered for all documents from the extension's startup.py. It is
optional, so projects opened without pyRevit don't get a warning.
Projects without a Room Abbreviation parameter on Rooms are skipped.
The parameter is resolved per project (see sharedparam.find_room_definition)
so the PyPiPie/Data Pusher parameter, or any existing "Room Abbreviation",
is used.
"""
from System import Guid
from Autodesk.Revit import DB

from roomabbrev import config, storage, rooms, sharedparam

_UPDATER = None   # keep a live reference so it isn't garbage collected


def _log(msg):
    try:
        from pyrevit import script
        script.get_logger().warning(u"[Room Abbreviations] " + msg)
    except Exception:
        pass


class RoomAbbreviationUpdater(DB.IUpdater):

    def __init__(self, addin_id):
        self._id = DB.UpdaterId(addin_id, Guid(config.UPDATER_GUID))

    # -- IUpdater ------------------------------------------------------------
    def GetUpdaterId(self):
        return self._id

    def GetUpdaterName(self):
        return config.UPDATER_NAME

    def GetAdditionalInformation(self):
        return ("Writes the Room Abbreviation parameter from the project's "
                "Room Abbreviations table when rooms are placed or renamed.")

    def GetChangePriority(self):
        return DB.ChangePriority.RoomsSpacesZones

    def Execute(self, data):
        # Never let an exception escape: Revit would disable the updater
        # and nag the user.
        try:
            doc = data.GetDocument()
            if doc.IsFamilyDocument:
                return
            ids = list(data.GetModifiedElementIds()) + list(data.GetAddedElementIds())
            if not ids:
                return
            definition = sharedparam.find_room_definition(doc)
            if definition is None:
                return                    # no Room Abbreviation on Rooms here
            lookup = storage.get_lookup(doc)
            for eid in ids:
                room = doc.GetElement(eid)
                if room is None:
                    continue
                try:
                    rooms.apply_to_room(room, lookup, definition)
                except Exception as ex:
                    _log(u"Room {}: {}".format(eid, ex))
        except Exception as ex:
            _log(u"Updater error: {}".format(ex))


def updater_id(addin_id):
    return DB.UpdaterId(addin_id, Guid(config.UPDATER_GUID))


def register(addin_id):
    """(Re)register the updater and its triggers. Safe to call on every
    pyRevit reload: the old instance is replaced by one built from the
    freshly loaded code."""
    global _UPDATER
    uid = updater_id(addin_id)
    if DB.UpdaterRegistry.IsUpdaterRegistered(uid):
        try:
            DB.UpdaterRegistry.UnregisterUpdater(uid)
        except Exception:
            pass

    _UPDATER = RoomAbbreviationUpdater(addin_id)
    DB.UpdaterRegistry.RegisterUpdater(_UPDATER, True)     # True = optional

    rooms_filter = DB.ElementCategoryFilter(DB.BuiltInCategory.OST_Rooms)
    name_param = DB.ElementId(DB.BuiltInParameter.ROOM_NAME)
    DB.UpdaterRegistry.AddTrigger(
        uid, rooms_filter, DB.Element.GetChangeTypeParameter(name_param))
    DB.UpdaterRegistry.AddTrigger(
        uid, rooms_filter, DB.Element.GetChangeTypeElementAddition())
    return _UPDATER
