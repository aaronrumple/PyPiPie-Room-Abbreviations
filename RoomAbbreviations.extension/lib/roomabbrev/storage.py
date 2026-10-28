# -*- coding: utf-8 -*-
"""Room name -> abbreviation table kept in the project's extensible storage.

One DataStorage element holds one Entity of our schema:
    Abbreviations : map<string, string>   room name -> abbreviation ("" = none)
    SourceFile    : string                last file imported
    Modified      : string                ISO timestamp of last save
"""
import datetime

import clr
from System import Guid, String
from System.Collections.Generic import IDictionary, Dictionary
from Autodesk.Revit import DB
from Autodesk.Revit.DB.ExtensibleStorage import (
    Schema, SchemaBuilder, Entity, AccessLevel)

from roomabbrev import config

SCHEMA_GUID = Guid(config.SCHEMA_GUID)
FIELD_MAP = "Abbreviations"
FIELD_SOURCE = "SourceFile"
FIELD_MODIFIED = "Modified"
_STR = clr.GetClrType(String)
_MAP_T = IDictionary[String, String]


# --------------------------------------------------------------------------
# Name matching
# --------------------------------------------------------------------------
def normalize(name):
    """Case-insensitive, whitespace-collapsed key: ' Mech  room' -> 'MECH ROOM'."""
    if not name:
        return ""
    return u" ".join(name.split()).upper()


def build_lookup(table):
    """{normalized name: abbreviation} from a {name: abbreviation} table."""
    lookup = {}
    for name, abbr in table.items():
        key = normalize(name)
        if key:
            lookup[key] = abbr or ""
    return lookup


# --------------------------------------------------------------------------
# Schema / DataStorage
# --------------------------------------------------------------------------
def get_schema(create=False):
    schema = Schema.Lookup(SCHEMA_GUID)
    if schema is not None or not create:
        return schema
    sb = SchemaBuilder(SCHEMA_GUID)
    sb.SetSchemaName(config.SCHEMA_NAME)
    sb.SetVendorId(config.VENDOR_ID)
    sb.SetReadAccessLevel(AccessLevel.Public)
    sb.SetWriteAccessLevel(AccessLevel.Public)
    sb.SetDocumentation("Room name to abbreviation lookup (pyRevit Room Abbreviations).")
    sb.AddMapField(FIELD_MAP, _STR, _STR)
    sb.AddSimpleField(FIELD_SOURCE, _STR)
    sb.AddSimpleField(FIELD_MODIFIED, _STR)
    return sb.Finish()


def find_storage(doc, schema):
    """(DataStorage, Entity) holding our data, or (None, None)."""
    if schema is None:
        return None, None
    for ds in DB.FilteredElementCollector(doc).OfClass(DB.ExtensibleStorage.DataStorage):
        ent = ds.GetEntity(schema)
        if ent is not None and ent.IsValid():
            return ds, ent
    return None, None


def read_table(doc):
    """{room name: abbreviation} exactly as stored (empty dict if none)."""
    info = read_info(doc)
    return info["table"]


def read_info(doc):
    schema = get_schema(create=False)
    ds, ent = find_storage(doc, schema)
    info = {"table": {}, "source": "", "modified": "", "exists": ent is not None}
    if ent is None:
        return info
    mapping = ent.Get[_MAP_T](schema.GetField(FIELD_MAP))
    if mapping is not None:
        for key in mapping.Keys:
            info["table"][key] = mapping[key] or ""
    info["source"] = ent.Get[String](schema.GetField(FIELD_SOURCE)) or ""
    info["modified"] = ent.Get[String](schema.GetField(FIELD_MODIFIED)) or ""
    return info


def get_lookup(doc):
    return build_lookup(read_table(doc))


def write_table(doc, table, source=None):
    """Replace the stored table. Must run inside a Transaction."""
    schema = get_schema(create=True)
    ds, old = find_storage(doc, schema)
    if ds is None:
        ds = DB.ExtensibleStorage.DataStorage.Create(doc)
    if source is None and old is not None:
        source = old.Get[String](schema.GetField(FIELD_SOURCE)) or ""

    mapping = Dictionary[String, String]()
    for name, abbr in table.items():
        name = (name or u"").strip()
        if name:
            mapping[name] = (abbr or u"").strip()

    ent = Entity(schema)
    ent.Set[_MAP_T](schema.GetField(FIELD_MAP), mapping)
    ent.Set[String](schema.GetField(FIELD_SOURCE), source or "")
    ent.Set[String](schema.GetField(FIELD_MODIFIED),
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    ds.SetEntity(ent)
    return ds
