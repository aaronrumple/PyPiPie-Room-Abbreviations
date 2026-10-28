# -*- coding: utf-8 -*-
__title__ = "Update\nAll Rooms"
__doc__ = """Re-apply the project's abbreviation table to every room.
Use after syncing, after the updater was off (project opened without
pyRevit), or to get a report of room names with no abbreviation."""

from pyrevit import revit, forms, script

from roomabbrev import sharedparam, storage, rooms

doc = revit.doc
output = script.get_output()

if doc.IsFamilyDocument:
    forms.alert("Open a project to update rooms.", exitscript=True)
if not sharedparam.is_bound_to_rooms(doc):
    forms.alert("Room Abbreviations is not set up in this project.",
                sub_msg="Run Setup first.", exitscript=True)

lookup = storage.get_lookup(doc)
if not lookup and not forms.alert(
        "The abbreviation table is empty, so every room's abbreviation will be cleared.",
        sub_msg="Continue?", yes=True, no=True):
    script.exit()

with revit.Transaction("Update Room Abbreviations"):
    stats = rooms.update_all_rooms(doc, lookup)

output.set_title("Room Abbreviations")
rooms.print_stats(output, stats, "Rooms")
