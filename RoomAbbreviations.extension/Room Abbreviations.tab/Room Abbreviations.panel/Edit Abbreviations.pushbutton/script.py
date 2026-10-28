# -*- coding: utf-8 -*-
__title__ = "Edit\nAbbreviations"
__doc__ = """Edit the Room Abbreviations table stored in this project
(extensible storage). Add names (whether or not the room exists yet),
change abbreviations, check entries and delete them, import/export
tab-delimited files, and pull in room names used in the project."""

import clr
clr.AddReference("System.Data")
clr.AddReference("WindowsBase")            # System.Windows.Threading
clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")  # System.Windows.Controls
from System import String, Int32, Boolean, DBNull, Action
from System.Data import DataTable, DataRowState
from System.Windows.Threading import DispatcherPriority
from System.Windows.Controls import (DataGridEditingUnit, DataGridCellInfo, CheckBox,
                                     TextBox, DataGrid)
from System.Windows.Input import Key, Keyboard
from System.Windows.Media import VisualTreeHelper, Visual

from pyrevit import revit, forms, script

from roomabbrev import config, sharedparam, storage, tsv, rooms, ui, helpdoc

doc = revit.doc
output = script.get_output()

if doc.IsFamilyDocument:
    forms.alert("Open a project (not a family) to edit Room Abbreviations.",
                exitscript=True)


def _text(value):
    if value is None or value is DBNull.Value:
        return u""
    return u" ".join(u"{}".format(value).split())


class AbbreviationEditor(forms.WPFWindow):

    def __init__(self, table):
        forms.WPFWindow.__init__(self, script.get_bundle_file("editor.xaml"))
        ui.apply_theme(self)
        self.result = None
        self.room_counts, self.room_display = rooms.room_name_counts(doc)

        self.original = dict((storage.normalize(k), (v or u"")) for k, v in table.items())
        self.dt = DataTable("Abbreviations")
        sel_col = self.dt.Columns.Add("Selected", clr.GetClrType(Boolean))
        sel_col.DefaultValue = False
        self.dt.Columns.Add("Name", clr.GetClrType(String))
        self.dt.Columns.Add("Abbreviation", clr.GetClrType(String))
        rooms_col = self.dt.Columns.Add("Rooms", clr.GetClrType(Int32))
        rooms_col.DefaultValue = 0
        for name in sorted(table, key=storage.normalize):
            self._add_row(name, table[name])
        self.dt.DefaultView.Sort = "Name ASC"
        self.grid.ItemsSource = self.dt.DefaultView

        # Header checkbox: check / uncheck every row currently shown.
        self.check_all = CheckBox()
        self.check_all.ToolTip = "Check or uncheck all rows shown"
        self.check_all.Focusable = False
        self.check_all.Click += self.on_check_all
        self.grid.Columns[0].Header = self.check_all

        self.search_tb.TextChanged += self.on_search
        self.add_btn.Click += self.on_add
        self.help_btn.Click += self.on_help
        self.PreviewKeyDown += self.on_window_key_down
        self.import_btn.Click += self.on_import
        self.export_btn.Click += self.on_export
        self.addnames_btn.Click += self.on_add_names
        self.delete_btn.Click += self.on_delete
        self.save_btn.Click += self.on_save
        self.cancel_btn.Click += self.on_cancel
        self.grid.RowEditEnding += self.on_row_edit_ending
        self.grid.PreviewKeyDown += self.on_grid_key_down
        self.grid.PreviewMouseLeftButtonDown += self.on_grid_mouse_down
        self.dt.RowDeleted += lambda s, e: self.refresh_later()
        self.dt.ColumnChanged += self.on_column_changed
        self.refresh()

    # ------------------------------------------------------------ helpers
    def _add_row(self, name, abbr):
        row = self.dt.NewRow()
        row["Selected"] = False
        row["Name"] = name
        row["Abbreviation"] = abbr or u""
        row["Rooms"] = self.room_counts.get(storage.normalize(name), 0)
        self.dt.Rows.Add(row)
        return row

    def _live_rows(self):
        return [r for r in self.dt.Rows
                if r.RowState not in (DataRowState.Deleted, DataRowState.Detached)]

    def _commit_grid(self):
        try:
            self.grid.CommitEdit(DataGridEditingUnit.Cell, True)
            self.grid.CommitEdit(DataGridEditingUnit.Row, True)
        except Exception:
            pass

    def _key_index(self):
        return dict((storage.normalize(_text(r["Name"])), r) for r in self._live_rows()
                    if _text(r["Name"]))

    def _checked_rows(self):
        return [r for r in self._live_rows() if self._is_checked(r)]

    def _is_dirty(self):
        current = dict((storage.normalize(k), v) for k, v in self.collect().items())
        return current != self.original

    def refresh_later(self):
        # Let the grid finish committing before we touch rows again.
        self.Dispatcher.BeginInvoke(DispatcherPriority.Background, Action(self.refresh))

    def refresh(self):
        seen, dupes = {}, set()
        blanks = 0
        for r in self._live_rows():
            name = _text(r["Name"])
            key = storage.normalize(name)
            count = self.room_counts.get(key, 0)
            if r["Rooms"] is DBNull.Value or r["Rooms"] != count:
                r["Rooms"] = count
            if not key:
                continue
            if key in seen:
                dupes.add(name)
            seen[key] = True
            if not _text(r["Abbreviation"]):
                blanks += 1
        unmatched_names = [k for k in self.room_counts if k not in seen]
        unmatched_rooms = sum(self.room_counts[k] for k in unmatched_names)
        parts = [u"{} entries".format(len(seen)),
                 u"{} without abbreviation".format(blanks),
                 u"{} project room(s) under {} name(s) not listed".format(
                     unmatched_rooms, len(unmatched_names))]
        n_checked = len(self._checked_rows())
        if n_checked:
            parts.append(u"{} checked".format(n_checked))
        text = u"  ·  ".join(parts)
        if dupes:
            text += u"\nDuplicate names (fix before saving): " + u", ".join(sorted(dupes))
            self.status_tb.Foreground = self.Resources["Warn"]
        else:
            self.status_tb.Foreground = self.Resources["Muted"]
        self.status_tb.Text = text
        return dupes

    def collect(self):
        table = {}
        for r in self._live_rows():
            name = _text(r["Name"])
            if name:
                table[name] = _text(r["Abbreviation"])
        return table

    # ------------------------------------------------------------ events
    def on_row_edit_ending(self, sender, args):
        self.refresh_later()

    def on_search(self, sender, args):
        text = self.search_tb.Text.strip()
        if not text:
            self.dt.DefaultView.RowFilter = ""
            return
        safe = text
        for ch in u"[]*%":
            safe = safe.replace(ch, u"[{}]".format(ch))
        safe = safe.replace(u"'", u"''")
        self.dt.DefaultView.RowFilter = (u"Name LIKE '%{0}%' OR Abbreviation LIKE '%{0}%'"
                                         .format(safe))

    def on_help(self, sender, args):
        try:
            helpdoc.open_help("editor")
        except Exception as ex:
            forms.alert(u"Could not open help:\n{}".format(ex))

    def on_window_key_down(self, sender, args):
        if args.Key == Key.F1:
            self.on_help(sender, args)
            args.Handled = True

    def on_add(self, sender, args):
        """New blank row, ready to type a room name (it doesn't have to be
        in the project yet)."""
        self._commit_grid()
        if self.search_tb.Text:
            self.search_tb.Text = u""                 # make sure the row is visible
        row = self._add_row(u"", u"")
        view_row = None
        for drv in self.dt.DefaultView:
            if drv.Row is row:
                view_row = drv
                break
        if view_row is None:
            return

        def start_edit():
            self.grid.SelectedItem = view_row
            self.grid.ScrollIntoView(view_row)
            self.grid.Focus()
            self.grid.CurrentCell = DataGridCellInfo(view_row, self.grid.Columns[1])
            self.grid.BeginEdit()
        self.Dispatcher.BeginInvoke(DispatcherPriority.Background, Action(start_edit))
        self.refresh()

    # ---------------------------------------------- bulk check / uncheck
    def _selected_view_rows(self):
        return [item for item in list(self.grid.SelectedItems) if hasattr(item, "Row")]

    def _set_checked(self, view_rows, value):
        for drv in view_rows:
            drv.Row["Selected"] = value
        self.refresh()

    def on_grid_key_down(self, sender, args):
        """Spacebar toggles the checkbox of every highlighted row. If any of
        them is unchecked they all get checked, otherwise all unchecked."""
        if args.Key != Key.Space or int(Keyboard.Modifiers) != 0:   # plain Space only
            return
        if isinstance(args.OriginalSource, TextBox):      # typing in a cell
            return
        view_rows = self._selected_view_rows()
        if not view_rows:
            return
        self._commit_grid()
        any_unchecked = any(not self._is_checked(drv.Row) for drv in view_rows)
        self._set_checked(view_rows, any_unchecked)
        args.Handled = True

    def on_grid_mouse_down(self, sender, args):
        """Clicking the checkbox of one highlighted row applies the new state
        to all highlighted rows (and keeps the multi-row selection)."""
        checkbox = self._ancestor_checkbox(args.OriginalSource)
        if checkbox is None:
            return
        drv = checkbox.DataContext
        if not hasattr(drv, "Row"):
            return
        view_rows = self._selected_view_rows()
        if len(view_rows) < 2 or not any(v.Row is drv.Row for v in view_rows):
            return                                        # normal single click
        self._commit_grid()
        self._set_checked(view_rows, not self._is_checked(drv.Row))
        args.Handled = True                               # keep the selection

    @staticmethod
    def _ancestor_checkbox(element):
        while element is not None and not isinstance(element, DataGrid):
            if isinstance(element, CheckBox):
                return element
            if not isinstance(element, Visual):
                return None
            element = VisualTreeHelper.GetParent(element)
        return None

    @staticmethod
    def _is_checked(row):
        value = row["Selected"]
        return value is not DBNull.Value and bool(value)

    def on_column_changed(self, sender, args):
        if args.Column.ColumnName == "Selected":      # keep the "N checked" count live
            self.refresh_later()

    def on_check_all(self, sender, args):
        self._commit_grid()
        value = bool(self.check_all.IsChecked)
        for drv in list(self.dt.DefaultView):           # only rows passing the search
            drv.Row["Selected"] = value
        self.refresh()

    def on_import(self, sender, args):
        self._commit_grid()
        path = forms.pick_file(
            files_filter="Tab-delimited text (*.txt;*.tsv)|*.txt;*.tsv|All files (*.*)|*.*",
            title="Import room abbreviations")
        if not path:
            return
        try:
            table, warnings = tsv.read_tsv(path)
        except Exception as ex:
            forms.alert(u"Could not read the file:\n{}".format(ex))
            return
        if not table:
            forms.alert(u"No room names found in the file.")
            return
        msg = u"{} entries in the file.".format(len(table))
        if warnings:
            msg += u"\n\n" + u"\n".join(warnings[:10])
        choice = forms.alert(msg, sub_msg="Merge: the file wins where names match.\n"
                                          "Replace: discard the current table.",
                             options=["Merge", "Replace", "Cancel"])
        if choice not in ("Merge", "Replace"):
            return
        if choice == "Replace":
            for r in self._live_rows():
                r.Delete()
        index = self._key_index()
        for name, abbr in table.items():
            row = index.get(storage.normalize(name))
            if row is not None:
                row["Abbreviation"] = abbr
            else:
                self._add_row(name, abbr)
        self.refresh()

    def on_export(self, sender, args):
        self._commit_grid()
        path = forms.save_file(file_ext="txt", default_name="Room Abbreviations",
                               title="Export room abbreviations")
        if not path:
            return
        try:
            tsv.write_tsv(path, self.collect())
        except Exception as ex:
            forms.alert(u"Export failed:\n{}".format(ex))

    def on_add_names(self, sender, args):
        self._commit_grid()
        index = self._key_index()
        added = 0
        for key, display in sorted(self.room_display.items()):
            if key not in index:
                self._add_row(display, u"")
                added += 1
        self.refresh()
        if not added:
            forms.alert(u"Every room name in the project is already listed.")

    def on_delete(self, sender, args):
        self._commit_grid()
        rows = self._checked_rows()
        if not rows:                                      # fall back to highlighted rows
            rows = [item.Row for item in list(self.grid.SelectedItems)
                    if hasattr(item, "Row")]              # skips the new-row placeholder
        if not rows:
            forms.alert(u"Check the entries to delete first.")
            return
        names = [_text(r["Name"]) or u"<blank>" for r in rows]
        shown = u"\n".join(names[:20])
        if len(names) > 20:
            shown += u"\n... and {} more".format(len(names) - 20)
        if not forms.alert(u"Delete {} entr{} from this project's table?\n\n{}".format(
                len(rows), u"y" if len(rows) == 1 else u"ies", shown),
                sub_msg=u"Nothing changes in the project until you Save.",
                yes=True, no=True):
            return
        for row in rows:
            row.Delete()
        self.check_all.IsChecked = False
        self.refresh()

    def on_save(self, sender, args):
        self._commit_grid()
        dupes = self.refresh()
        if dupes:
            forms.alert(u"These names are listed more than once:\n\n" +
                        u"\n".join(sorted(dupes)) +
                        u"\n\nRemove the duplicates before saving.")
            return
        self.result = {"table": self.collect(),
                       "update_rooms": bool(self.update_cb.IsChecked)}
        self.Close()

    def on_cancel(self, sender, args):
        self._commit_grid()
        if self._is_dirty():
            if not forms.alert(u"Discard your changes?", yes=True, no=True):
                return
        self.Close()


# ---------------------------------------------------------------- run
editor = AbbreviationEditor(storage.read_table(doc))
editor.ShowDialog()
result = editor.result
if not result:
    script.exit()

try:
    with revit.Transaction("Edit Room Abbreviations"):
        definition, param_status = sharedparam.ensure_room_binding(doc)
        added_param = param_status != "existing"
        storage.write_table(doc, result["table"])
        stats = None
        if result["update_rooms"] or added_param:
            stats = rooms.update_all_rooms(doc, storage.build_lookup(result["table"]),
                                           definition)
except sharedparam.SharedParamError as ex:
    forms.alert(str(ex), exitscript=True)
except Exception as ex:
    forms.alert(u"Saving failed (in a workshared model, someone else may own the "
                u"abbreviation table - sync and try again):\n{}".format(ex),
                exitscript=True)

if added_param or (stats and (stats["unmatched"] or stats["not_editable"] or stats["failed"])):
    output.set_title("Room Abbreviations")
    if added_param:
        output.print_md(u"Rooms now use {}.".format(sharedparam.describe(doc, definition)))
    if stats:
        rooms.print_stats(output, stats, "Rooms")
elif stats:
    msg = u"Saved {} abbreviations - {} room(s) updated.".format(
        len(result["table"]), stats["changed"])
    try:
        forms.show_balloon("Room Abbreviations", msg)
    except Exception:
        print(msg)
