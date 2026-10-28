# -*- coding: utf-8 -*-
"""Create room tag families that show the Room Abbreviation, either from a
copy of the bundled standard tag or from Revit's blank Room Tag template.

Every flow shows an explanation dialog first, then opens the family in the
Family Editor. Functions return None when the user cancels.
"""
import os
import shutil

import clr
clr.AddReference("WindowsBase")
clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
from System import Guid
from System.Windows import Thickness, TextWrapping, FontWeights
from System.Windows.Controls import TextBlock

from pyrevit import DB, forms

from roomabbrev import config, sharedparam, ui, helpdoc

INTRO_XAML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xaml", "tag_intro.xaml")

STANDARD = "standard"
BLANK = "blank"

_ADD_PARAM_STEP = (u"In Edit Label, click Add Parameter (bottom left) > Select... > group "
                   u"'{}' > '{}' > OK, then move it into Label Parameters."
                   .format(config.PARAM_GROUP_NAME, config.PARAM_NAME))

_TEXT = {
    STANDARD: {
        "title": u"Create a new room tag from the standard",
        "intro": u"You'll get your own copy of the standard 'Room Tag - Abbreviation' family "
                 u"to change. The standard that ships with the app is never modified.",
        "sections": [
            (u"What happens next", [
                u"Choose a name and folder for your copy.",
                u"The copy opens in the Family Editor.",
            ]),
            (u"In the Family Editor", [
                u"The Room Abbreviation label is already set up. Select a label and click "
                u"Edit Label to change what it shows.",
                u"Change text types, sizes and linework as needed.",
                u"To show the abbreviation on another label: " + _ADD_PARAM_STEP,
            ]),
            (u"When you're done", [
                u"Save. The family takes its name from the file, so a new file name keeps "
                u"the standard tag in your projects unchanged.",
                u"Click Load into Project, pick the project, and tag rooms with it.",
            ]),
        ],
    },
    BLANK: {
        "title": u"Create a new blank room tag",
        "intro": u"A blank family is made from Revit's Room Tag template. You add the labels.",
        "sections": [
            (u"What happens next", [
                u"Pick a Room Tag template (if Revit has more than one).",
                u"If you use your own shared parameter file, choose whether to add Room "
                u"Abbreviation to it so Edit Label can find it.",
                u"Choose a name and folder for the family. It opens in the Family Editor.",
            ]),
            (u"In the Family Editor", [
                u"Create > Label, then click in the view.",
                _ADD_PARAM_STEP,
                u"Add Name, Number or anything else the tag should show.",
            ]),
            (u"When you're done", [
                u"Save, then click Load into Project and tag rooms with it.",
            ]),
        ],
    },
}
_TIP = (u"Rooms without an abbreviation show an empty value. Keep the abbreviation on its "
        u"own label, rather than combined with the name, to avoid a blank line or stray "
        u"separator.")


# --------------------------------------------------------- intro dialog
class TagIntroDialog(forms.WPFWindow):

    def __init__(self, mode):
        forms.WPFWindow.__init__(self, INTRO_XAML)
        ui.apply_theme(self)
        self.accepted = False
        text = _TEXT[mode]
        self.title_tb.Text = text["title"]
        self.intro_tb.Text = text["intro"]
        self.tip_tb.Text = _TIP
        for heading, steps in text["sections"]:
            h = TextBlock()
            h.Text = heading
            h.FontWeight = FontWeights.SemiBold
            h.Margin = Thickness(0, 10, 0, 4)
            self.sections_sp.Children.Add(h)
            for i, step in enumerate(steps, 1):
                t = TextBlock()
                t.Text = u"{}.  {}".format(i, step)
                t.TextWrapping = TextWrapping.Wrap
                t.Margin = Thickness(10, 0, 0, 3)
                self.sections_sp.Children.Add(t)
        self.continue_btn.Click += self.on_continue
        self.cancel_btn.Click += lambda s, e: self.Close()
        self.help_btn.Click += self.on_help

    def on_continue(self, sender, args):
        self.accepted = True
        self.Close()

    def on_help(self, sender, args):
        try:
            helpdoc.open_help("room-tag")
        except Exception as ex:
            forms.alert(u"Could not open help:\n{}".format(ex))


def show_intro(mode):
    dlg = TagIntroDialog(mode)
    dlg.ShowDialog()
    return dlg.accepted


# --------------------------------------------- parameter / shared file
def param_guid(uiapp):
    """GUID of the active project's Room Abbreviation, else the standard one.
    None if the user cancels."""
    standard = Guid(config.PARAM_GUID)
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document if uidoc else None
    if doc is None or doc.IsFamilyDocument:
        return standard
    definition = sharedparam.find_room_definition(doc)
    if definition is None:
        return standard
    guid = sharedparam.definition_guid(doc, definition)
    if guid is None:
        if not forms.alert(
                u"Rooms in '{}' use a PROJECT parameter named '{}'. Tags can only show "
                u"shared parameters, so this tag won't display it in that project."
                .format(doc.Title, definition.Name),
                sub_msg=u"Continue with the standard shared parameter?",
                yes=True, no=True):
            return None
        return standard
    return guid


def prepare_shared_param_file(app, guid):
    """Put the definition in the active shared parameter file so Edit Label
    can add it. Returns (active path, original path), or None if cancelled."""
    current = app.SharedParametersFilename or ""
    ours = config.SHARED_PARAM_FILE
    target = ours
    if current and os.path.exists(current) and \
            os.path.normcase(current) != os.path.normcase(ours):
        choice = forms.alert(
            u"Edit Label only lists parameters from the active shared parameter "
            u"file:\n{}".format(current),
            sub_msg=u"Add '{}' to that file (recommended - nothing else changes), or "
                    u"switch Revit to the Room Abbreviations file?".format(config.PARAM_NAME),
            options=["Add to my current file", "Switch to Room Abbreviations file", "Cancel"])
        if choice == "Add to my current file":
            target = current
        elif choice != "Switch to Room Abbreviations file":
            return None
    try:
        sharedparam.write_definition_to_file(app, target, leave_active=True, guid=guid)
    except sharedparam.SharedParamError as ex:
        forms.alert(str(ex), sub_msg="Try the Room Abbreviations file instead.")
        return None
    return target, current


# ------------------------------------------------------------ flows
def _ask_save_path(default_name):
    while True:
        path = forms.save_file(file_ext="rfa", default_name=default_name,
                               title="Save the new room tag family as")
        if not path:
            return None
        if os.path.normcase(os.path.abspath(path)) == \
                os.path.normcase(os.path.abspath(config.STANDARD_TAG_FAMILY_FILE)):
            forms.alert(u"That's the bundled standard. Choose another name or folder.")
            continue
        return path


def _open(uiapp, path):
    try:
        uiapp.OpenAndActivateDocument(path)
        return True
    except Exception as ex:
        forms.alert(u"Revit couldn't open the family:\n{}\n\n{}".format(path, ex))
        return False


def create_from_standard(uiapp):
    """Copy the bundled standard tag and open it. Returns a report dict or None."""
    src = config.STANDARD_TAG_FAMILY_FILE
    if not os.path.exists(src):
        forms.alert(u"The standard room tag is missing:\n" + src)
        return None
    if not show_intro(STANDARD):
        return None
    guid = param_guid(uiapp)
    if guid is None:
        return None
    spf = prepare_shared_param_file(uiapp.Application, guid)
    if spf is None:
        return None
    dst = _ask_save_path(u"Room Tag - Abbreviation - Custom")
    if dst is None:
        return None
    shutil.copyfile(src, dst)
    if not _open(uiapp, dst):
        return None
    return {"path": dst, "source": src, "guid": guid,
            "active_spf": spf[0], "original_spf": spf[1]}


def create_blank(uiapp, template):
    """New family from a Room Tag template and open it. `template` is a
    callable returning the .rft path (or None) so it runs after the intro."""
    if not show_intro(BLANK):
        return None
    rft = template()
    if not rft:
        return None
    guid = param_guid(uiapp)
    if guid is None:
        return None
    spf = prepare_shared_param_file(uiapp.Application, guid)
    if spf is None:
        return None
    dst = _ask_save_path(u"Room Tag - Abbreviation")
    if dst is None:
        return None
    famdoc = uiapp.Application.NewFamilyDocument(rft)
    if famdoc is None:
        forms.alert(u"Revit could not create a family from:\n" + rft)
        return None
    try:
        opts = DB.SaveAsOptions()
        opts.OverwriteExistingFile = True
        famdoc.SaveAs(dst, opts)
    finally:
        famdoc.Close(False)
    if not _open(uiapp, dst):
        return None
    return {"path": dst, "source": rft, "guid": guid,
            "active_spf": spf[0], "original_spf": spf[1]}


def print_report(output, result):
    output.print_md(u"## New room tag family")
    output.print_md(u"- Family: `{}`".format(result["path"]))
    output.print_md(u"- Started from: `{}`".format(result["source"]))
    output.print_md(u"- Parameter: **{}** `{}`".format(config.PARAM_NAME, result["guid"]))
    output.print_md(u"- Active shared parameter file: `{}`".format(result["active_spf"]))
    orig = result["original_spf"]
    if orig and os.path.normcase(orig) != os.path.normcase(result["active_spf"]):
        output.print_md(u"- Your previous shared parameter file was `{}`. Switch back in "
                        u"**Manage > Shared Parameters** when you're done.".format(orig))
