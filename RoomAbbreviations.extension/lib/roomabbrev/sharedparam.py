# -*- coding: utf-8 -*-
"""Find, create and bind the Room Abbreviation parameter.

Resolution order in a project (find_room_definition):
  1. The shared parameter with config.PARAM_GUID (shared with PyPiPie /
     Data Pusher's RoomLib) bound to Rooms.
  2. Any other parameter named "Room Abbreviation" bound to Rooms as an
     instance parameter (shared with another GUID, or a project parameter).
Only if neither exists is a new binding created, using config.PARAM_GUID.
"""
import os
from contextlib import contextmanager

from System import Guid
from Autodesk.Revit import DB

from roomabbrev import config

PARAM_GUID = Guid(config.PARAM_GUID)


class SharedParamError(Exception):
    pass


# --------------------------------------------------------------------------
# Shared parameter file
# --------------------------------------------------------------------------
def _ensure_file(path):
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    if not os.path.exists(path):
        # Revit accepts an empty file and writes the header itself.
        open(path, "w").close()


@contextmanager
def active_shared_param_file(app, path, restore=True):
    """Point Revit at `path`, yield the DefinitionFile, then put the user's
    original shared parameter file back (unless restore=False)."""
    original = app.SharedParametersFilename or ""
    _ensure_file(path)
    app.SharedParametersFilename = path
    try:
        dfile = app.OpenSharedParameterFile()
        if dfile is None:
            raise SharedParamError(
                "Revit could not open the shared parameter file:\n" + path)
        yield dfile
    finally:
        if restore and os.path.normcase(original) != os.path.normcase(path):
            try:
                app.SharedParametersFilename = original
            except Exception:
                pass


def _text_spec():
    if hasattr(DB, "SpecTypeId"):                 # Revit 2022+
        return DB.SpecTypeId.String.Text
    return DB.ParameterType.Text                  # Revit 2021 and older


def _creation_options(guid):
    opts = DB.ExternalDefinitionCreationOptions(config.PARAM_NAME, _text_spec())
    opts.GUID = guid
    opts.Description = config.PARAM_DESCRIPTION
    opts.UserModifiable = config.PARAM_USER_MODIFIABLE
    opts.Visible = True
    return opts


def get_or_create_definition(dfile, guid=None):
    """Return the ExternalDefinition with `guid` (default config.PARAM_GUID)
    from the file, creating it if needed."""
    guid = guid or PARAM_GUID
    for grp in dfile.Groups:
        for definition in grp.Definitions:
            if definition.GUID == guid:
                return definition
    grp = dfile.Groups.get_Item(config.PARAM_GROUP_NAME)
    if grp is None:
        grp = dfile.Groups.Create(config.PARAM_GROUP_NAME)
    elif grp.Definitions.get_Item(config.PARAM_NAME) is not None:
        raise SharedParamError(
            "The shared parameter file already has a '{}' in group '{}' with a "
            "different GUID than {}.".format(config.PARAM_NAME,
                                             config.PARAM_GROUP_NAME, guid))
    return grp.Definitions.Create(_creation_options(guid))


def write_definition_to_file(app, path, leave_active=True, guid=None):
    """Make sure `path` contains the definition. With leave_active=True the
    file stays as Revit's active shared parameter file (needed so the Edit
    Label dialog in a tag family can see the parameter)."""
    with active_shared_param_file(app, path, restore=not leave_active) as dfile:
        get_or_create_definition(dfile, guid)


# --------------------------------------------------------------------------
# Project lookup
# --------------------------------------------------------------------------
def _room_category(doc):
    return DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_Rooms)


def _bindings(doc):
    it = doc.ParameterBindings.ForwardIterator()
    it.Reset()
    while it.MoveNext():
        if it.Key is not None:
            yield it.Key, it.Current


def definition_guid(doc, definition):
    """GUID if `definition` is a shared parameter, else None."""
    if isinstance(definition, DB.InternalDefinition):
        elem = doc.GetElement(definition.Id)
        if isinstance(elem, DB.SharedParameterElement):
            return elem.GuidValue
    return None


def find_room_definition(doc):
    """The Definition rooms use for their abbreviation, or None.
    Use with room.get_Parameter(definition)."""
    room_cat = _room_category(doc)
    by_name = None
    for definition, binding in _bindings(doc):
        if not isinstance(binding, DB.InstanceBinding) \
                or not binding.Categories.Contains(room_cat):
            continue
        if definition_guid(doc, definition) == PARAM_GUID:
            return definition
        if by_name is None and definition.Name == config.PARAM_NAME:
            by_name = definition
    return by_name


def is_bound_to_rooms(doc):
    return find_room_definition(doc) is not None


def describe(doc, definition):
    """Short text for reports: which parameter is in use."""
    if definition is None:
        return u"none"
    guid = definition_guid(doc, definition)
    if guid is None:
        return u"'{}' (project parameter - not usable in tags)".format(definition.Name)
    note = u"" if guid == PARAM_GUID else u" - not the standard GUID"
    return u"'{}' (shared, {}{})".format(definition.Name, guid, note)


def _find_unbound_candidate(doc):
    """A definition with our GUID or name that is bound, but not to Rooms."""
    by_name = None
    for definition, binding in _bindings(doc):
        if definition_guid(doc, definition) == PARAM_GUID:
            return definition, binding
        if by_name is None and definition.Name == config.PARAM_NAME:
            by_name = (definition, binding)
    return by_name or (None, None)


# --------------------------------------------------------------------------
# Project binding
# --------------------------------------------------------------------------
def _bind(doc, definition, binding, reinsert):
    pb = doc.ParameterBindings
    method = pb.ReInsert if reinsert else pb.Insert
    if hasattr(DB, "GroupTypeId"):
        try:                                      # Revit 2024+
            return method(definition, binding, DB.GroupTypeId.IdentityData)
        except TypeError:                         # 2022/2023 lack this overload
            pass
    return method(definition, binding, DB.BuiltInParameterGroup.PG_IDENTITY_DATA)


def _allow_vary_between_groups(doc, definition):
    try:
        definition.SetAllowVaryBetweenGroups(doc, True)
    except Exception:
        pass


def ensure_room_binding(doc):
    """Make sure Rooms have a Room Abbreviation parameter, reusing any that
    already exists. Must run inside a Transaction.

    Returns (definition, status) where status is
        "existing" - already bound to Rooms, nothing changed
        "extended" - an existing parameter was also bound to Rooms
        "added"    - new shared parameter (config.PARAM_GUID) bound to Rooms
    """
    definition = find_room_definition(doc)
    if definition is not None:
        return definition, "existing"

    app = doc.Application
    room_cat = _room_category(doc)
    cats = app.Create.NewCategorySet()
    cats.Insert(room_cat)

    # Parameter exists in the project but isn't on Rooms: add Rooms to it.
    candidate, binding = _find_unbound_candidate(doc)
    if candidate is not None:
        if isinstance(binding, DB.TypeBinding):
            raise SharedParamError(
                "'{}' is a TYPE parameter in this project. It must be an "
                "instance parameter to be used on Rooms.".format(candidate.Name))
        for cat in binding.Categories:
            cats.Insert(cat)
        if not _bind(doc, candidate, app.Create.NewInstanceBinding(cats), True):
            raise SharedParamError("Revit refused to add Rooms to '{}'."
                                   .format(candidate.Name))
        status = "extended"
    else:
        # Not in the project at all: create it with the standard GUID.
        with active_shared_param_file(app, config.SHARED_PARAM_FILE) as dfile:
            ext_def = get_or_create_definition(dfile)
            if not _bind(doc, ext_def, app.Create.NewInstanceBinding(cats), False):
                raise SharedParamError("Revit refused to bind '{}' to Rooms."
                                       .format(config.PARAM_NAME))
        status = "added"

    definition = find_room_definition(doc)
    if definition is None:
        raise SharedParamError("'{}' could not be bound to Rooms."
                               .format(config.PARAM_NAME))
    _allow_vary_between_groups(doc, definition)
    return definition, status
