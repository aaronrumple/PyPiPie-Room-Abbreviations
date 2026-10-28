# -*- coding: utf-8 -*-
"""Write abbreviations onto rooms."""
from Autodesk.Revit import DB

from roomabbrev import config, storage, sharedparam


def collect_rooms(doc):
    return (DB.FilteredElementCollector(doc)
            .OfCategory(DB.BuiltInCategory.OST_Rooms)
            .WhereElementIsNotElementType()
            .ToElements())


def room_name(room):
    p = room.get_Parameter(DB.BuiltInParameter.ROOM_NAME)
    return (p.AsString() or u"") if p is not None else u""


def abbreviation_for(name, lookup):
    """Abbreviation string, "" if listed without one, None if not listed."""
    key = storage.normalize(name)
    if not key:
        return None
    return lookup.get(key)


def apply_to_room(room, lookup, definition):
    """Set the room's abbreviation. `definition` comes from
    sharedparam.find_room_definition(). Returns True if the value changed,
    False if unchanged, None if the room doesn't have the parameter."""
    p = room.get_Parameter(definition)
    if p is None:
        return None
    abbr = abbreviation_for(room_name(room), lookup)
    new_value = abbr if abbr is not None else config.NO_MATCH_VALUE
    if (p.AsString() or u"") == new_value:
        return False
    p.Set(new_value)
    return True


def _editable(doc, eid):
    if not doc.IsWorkshared:
        return True
    try:
        if DB.WorksharingUtils.GetCheckoutStatus(doc, eid) == \
                DB.CheckoutStatus.OwnedByOtherUser:
            return False
        if DB.WorksharingUtils.GetModelUpdatesStatus(doc, eid) in (
                DB.ModelUpdatesStatus.DeletedInCentral,
                DB.ModelUpdatesStatus.UpdatedInCentral):
            return False
    except Exception:
        pass
    return True


def update_all_rooms(doc, lookup=None, definition=None):
    """Bulk update. Must run inside a Transaction. Returns a stats dict."""
    if lookup is None:
        lookup = storage.get_lookup(doc)
    if definition is None:
        definition = sharedparam.find_room_definition(doc)
    if definition is None:
        raise sharedparam.SharedParamError(
            "Rooms have no '{}' parameter. Run Setup first.".format(config.PARAM_NAME))
    stats = {"total": 0, "changed": 0, "blank": 0, "unmatched": {},
             "not_editable": [], "failed": []}
    for room in collect_rooms(doc):
        stats["total"] += 1
        name = room_name(room)
        abbr = abbreviation_for(name, lookup)
        if abbr is None:
            label = name or u"<no name>"
            stats["unmatched"][label] = stats["unmatched"].get(label, 0) + 1
        elif abbr == u"":
            stats["blank"] += 1
        if not _editable(doc, room.Id):
            stats["not_editable"].append(room.Id)
            continue
        try:
            if apply_to_room(room, lookup, definition):
                stats["changed"] += 1
        except Exception as ex:
            stats["failed"].append((room.Id, str(ex)))
    return stats


def room_name_counts(doc):
    """({normalized name: room count}, {normalized name: first spelling seen})"""
    counts, display = {}, {}
    for room in collect_rooms(doc):
        name = room_name(room)
        key = storage.normalize(name)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
        display.setdefault(key, u" ".join(name.split()))
    return counts, display


def print_stats(output, stats, header):
    """Pretty report in the pyRevit output window."""
    output.print_md(u"## {}".format(header))
    output.print_md(u"- Rooms in project: **{}**".format(stats["total"]))
    output.print_md(u"- Rooms updated: **{}**".format(stats["changed"]))
    output.print_md(u"- Rooms listed with no abbreviation: **{}**".format(stats["blank"]))
    unmatched = stats["unmatched"]
    output.print_md(u"- Rooms whose name is not in the table: **{}**"
                    .format(sum(unmatched.values())))
    if stats["not_editable"]:
        output.print_md(u"- Skipped (owned by others or out of date with central): **{}**"
                        .format(len(stats["not_editable"])))
        for eid in stats["not_editable"][:50]:
            print(output.linkify(eid))
    if stats["failed"]:
        output.print_md(u"### Failed")
        for eid, msg in stats["failed"]:
            print(u"{}  {}".format(output.linkify(eid), msg))
    if unmatched:
        output.print_md(u"### Room names not in the table")
        rows = [[name, str(cnt)] for name, cnt in sorted(unmatched.items())]
        output.print_table(rows, columns=["Room Name", "Rooms"])
        output.print_md(u"Add these in **Edit Abbreviations** (use *Add room names "
                        u"from project*) or leave them out if they have no abbreviation.")
