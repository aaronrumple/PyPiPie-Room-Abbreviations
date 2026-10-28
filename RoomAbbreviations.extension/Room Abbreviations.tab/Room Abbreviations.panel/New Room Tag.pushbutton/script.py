# -*- coding: utf-8 -*-
__title__ = "New Room\nTag Family"
__doc__ = """Start a new, blank room tag family from Revit's Room Tag
template, with the Room Abbreviation shared parameter available in the
Edit Label dialog. Explains the steps first. Uses the GUID of the Room
Abbreviation parameter in the open project (normally the shared PyPiPie
GUID). To start from the office standard tag instead, use Setup."""

import os

from pyrevit import HOST_APP, forms, script

from roomabbrev import tagfamily

app = HOST_APP.app
uiapp = HOST_APP.uiapp
output = script.get_output()


# ------------------------------------------------------------- template
def find_templates():
    found = []
    root = app.FamilyTemplatePath
    if root and os.path.isdir(root):
        for folder, _dirs, files in os.walk(root):
            for f in files:
                low = f.lower()
                if low.endswith(".rft") and "room tag" in low:
                    found.append(os.path.join(folder, f))
    return root, sorted(found)


def choose_template():
    root, found = find_templates()
    browse = "Browse for a template..."
    if len(found) == 1:
        return found[0]
    if found:
        labels = dict((os.path.relpath(p, root), p) for p in found)
        pick = forms.SelectFromList.show(sorted(labels) + [browse],
                                         title="Room tag template", button_name="Use")
        if not pick:
            return None
        if pick != browse:
            return labels[pick]
    path = forms.pick_file(file_ext="rft", init_dir=root or "",
                           title="Pick a Room Tag family template (.rft)")
    return path or None


# ----------------------------------------------------------------- run
result = tagfamily.create_blank(uiapp, choose_template)
if result:
    output.set_title("New Room Tag Family")
    tagfamily.print_report(output, result)
