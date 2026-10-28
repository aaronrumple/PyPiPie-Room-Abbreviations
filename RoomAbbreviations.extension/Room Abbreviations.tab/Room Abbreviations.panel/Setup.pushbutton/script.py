# -*- coding: utf-8 -*-
__title__ = "Setup"
__doc__ = """Set up Room Abbreviations in this project:
 - adds the Room Abbreviation parameter to Rooms (or uses the existing one),
 - loads abbreviations from the standard list OR a custom tab-delimited file,
 - optionally opens a copy of the standard room tag to create a new tag.
Fills in every room. Run again any time to change the table."""

import os

import clr
clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
from System.Windows import Visibility
from pyrevit import revit, forms, script, HOST_APP

from roomabbrev import (config, sharedparam, storage, tsv, rooms, ui, helpdoc,
                        tagfamily)

doc = revit.doc
output = script.get_output()

if doc.IsFamilyDocument:
    forms.alert("Open a project (not a family) to set up Room Abbreviations.",
                exitscript=True)

FILE_FILTER = "Tab-delimited text (*.txt;*.tsv)|*.txt;*.tsv|All files (*.*)|*.*"


def read_table(path):
    """(table, warnings) or (None, error text)."""
    try:
        table, warnings = tsv.read_tsv(path)
    except Exception as ex:
        return None, u"Could not read the file:\n{}\n\n{}".format(path, ex)
    if not table:
        return None, u"No room names were found in:\n{}".format(path)
    return table, warnings


def warnings_text(warnings, limit=12):
    text = u"\n".join(warnings[:limit])
    if len(warnings) > limit:
        text += u"\n... and {} more".format(len(warnings) - limit)
    return text


# --------------------------------------------------------------- dialog
class SetupDialog(forms.WPFWindow):

    def __init__(self, info):
        forms.WPFWindow.__init__(self, script.get_bundle_file("setup.xaml"))
        ui.apply_theme(self)
        self.result = None
        self.custom_table = None
        self.custom_warnings = []
        self.has_table = bool(info["table"])

        # Parameter status
        definition = sharedparam.find_room_definition(doc)
        if definition is not None:
            self.param_tb.Text = u"Rooms use {}.".format(sharedparam.describe(doc, definition))
        else:
            self.param_tb.Text = (u"Will be added to Rooms: '{}' (shared, {}), Identity Data."
                                  .format(config.PARAM_NAME, config.PARAM_GUID))

        # Abbreviation source: keep / standard / custom (one only)
        if self.has_table:
            self.keep_rb.Content = u"Keep the current table ({} entries)".format(len(info["table"]))
        else:
            self.keep_rb.Content = u"Don't load abbreviations now"
        self.standard_table, self.standard_warnings = None, []
        if os.path.exists(config.STANDARD_ABBREVIATIONS_FILE):
            table, warnings = read_table(config.STANDARD_ABBREVIATIONS_FILE)
            if table:
                self.standard_table, self.standard_warnings = table, warnings
        if self.standard_table:
            self.standard_rb.Content = u"Load the standard abbreviations ({} entries)".format(
                len(self.standard_table))
        else:
            self.standard_rb.Content = u"Load the standard abbreviations (standard file missing)"
            self.standard_rb.IsEnabled = False

        if not self.has_table and self.standard_table:
            self.standard_rb.IsChecked = True
        else:
            self.keep_rb.IsChecked = True

        for rb in (self.keep_rb, self.standard_rb, self.custom_rb):
            rb.Checked += self.on_source_changed
        self.browse_btn.Click += self.on_browse
        self.help_btn.Click += self.on_help
        self.run_btn.Click += self.on_run
        self.cancel_btn.Click += lambda s, e: self.Close()

        if not os.path.exists(config.STANDARD_TAG_FAMILY_FILE):
            self.tag_cb.IsEnabled = False
            self.tag_note_tb.Text = u"Standard tag missing:\n" + config.STANDARD_TAG_FAMILY_FILE
        self.on_source_changed(None, None)

    # ------------------------------------------------------------ state
    def _source(self):
        if self.standard_rb.IsChecked:
            return "standard"
        if self.custom_rb.IsChecked:
            return "custom"
        return "keep"

    def on_source_changed(self, sender, args):
        src = self._source()
        self.path_tb.IsEnabled = src == "custom"
        self.mode_sp.Visibility = (Visibility.Visible if self.has_table and src != "keep"
                                   else Visibility.Collapsed)
        if src == "standard":
            note = u"From the standards folder bundled with the app."
            if self.standard_warnings:
                note += u" {} warning(s) - listed in the report.".format(
                    len(self.standard_warnings))
        elif src == "custom":
            if self.custom_table:
                note = u"{} entries in the file.".format(len(self.custom_table))
            else:
                note = u"Click Browse… to pick the file (Room Name <TAB> Abbreviation)."
        else:
            note = (u"The project's table is left as is; rooms are refreshed from it."
                    if self.has_table else
                    u"Add abbreviations later with Edit Abbreviations.")
        self.src_note_tb.Text = note

    # ----------------------------------------------------------- events
    def on_browse(self, sender, args):
        path = forms.pick_file(files_filter=FILE_FILTER,
                               title="Room abbreviations file (Room Name <TAB> Abbreviation)")
        if not path:
            return
        table, warnings = read_table(path)
        if table is None:
            forms.alert(warnings)
            return
        if warnings and not forms.alert(u"The file has some issues:\n\n" + warnings_text(warnings),
                                        sub_msg="Use it anyway?", yes=True, no=True):
            return
        self.custom_table, self.custom_warnings = table, warnings
        self.path_tb.Text = path
        self.custom_rb.IsChecked = True
        self.on_source_changed(None, None)

    def on_help(self, sender, args):
        try:
            helpdoc.open_help("setup")
        except Exception as ex:
            forms.alert(u"Could not open help:\n{}".format(ex))

    def on_run(self, sender, args):
        src = self._source()
        if src == "custom" and not self.custom_table:
            forms.alert(u"Pick a custom file first, or choose another option.")
            return
        table, path, warnings = None, None, []
        if src == "standard":
            table, path = self.standard_table, config.STANDARD_ABBREVIATIONS_FILE
            warnings = self.standard_warnings
        elif src == "custom":
            table, path, warnings = self.custom_table, self.path_tb.Text, self.custom_warnings
        self.result = {
            "source": src,
            "table": table,
            "path": path,
            "warnings": warnings,
            "merge": self.has_table and bool(self.merge_rb.IsChecked),
            "open_tag": bool(self.tag_cb.IsChecked),
        }
        self.Close()


# ------------------------------------------------------------------ run
info = storage.read_info(doc)
dlg = SetupDialog(info)
dlg.ShowDialog()
choice = dlg.result
if not choice:
    script.exit()

table = dict(info["table"])
new_table = choice["table"]
if new_table is not None:
    if not choice["merge"]:
        table = {}
    existing_keys = dict((storage.normalize(n), n) for n in table)
    for name, abbr in new_table.items():
        old = existing_keys.get(storage.normalize(name))
        if old is not None:
            del table[old]
        table[name] = abbr

try:
    with revit.Transaction("Room Abbreviations Setup"):
        definition, param_status = sharedparam.ensure_room_binding(doc)
        if new_table is not None:
            storage.write_table(doc, table, source=choice["path"])
        stats = rooms.update_all_rooms(doc, storage.build_lookup(table), definition)
except sharedparam.SharedParamError as ex:
    forms.alert(str(ex), exitscript=True)
except Exception as ex:
    forms.alert(u"Setup failed:\n{}".format(ex), exitscript=True)

output.set_title("Room Abbreviations Setup")
_verb = {"existing": u"Using existing parameter",
         "extended": u"Added Rooms to existing parameter",
         "added": u"Added shared parameter"}[param_status]
output.print_md(u"{} {}.".format(_verb, sharedparam.describe(doc, definition)))
if new_table is not None:
    output.print_md(u"{} **{}** {} abbreviations from `{}`. The table now has **{}** entries."
                    .format(u"Merged" if choice["merge"] else u"Loaded", len(new_table),
                            choice["source"], choice["path"], len(table)))
    if choice["warnings"]:
        output.print_md(u"### File warnings")
        for w in choice["warnings"]:
            print(w)
else:
    output.print_md(u"Abbreviation table unchanged ({} entries).".format(len(table)))
rooms.print_stats(output, stats, "Rooms")

# Opening a family switches the active document, so do it last.
if choice["open_tag"]:
    result = tagfamily.create_from_standard(HOST_APP.uiapp)
    if result:
        tagfamily.print_report(output, result)
