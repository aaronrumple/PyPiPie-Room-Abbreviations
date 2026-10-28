# -*- coding: utf-8 -*-
"""Read/write the tab-delimited abbreviation file.

Format (one room per line, header row optional, # starts a comment):
    Room Name<TAB>Abbreviation
    OFFICE<TAB>OFF
    MECHANICAL<TAB>MECH
    CORRIDOR                <- no abbreviation (blank second column is fine)

Saved from Excel as "Text (Tab delimited)" or "Unicode Text" both work.
"""
import io
import codecs

from roomabbrev import storage

_NAME_HEADERS = set([u"name", u"room", u"room name", u"roomname"])
_ABBR_HEADERS = set([u"abbreviation", u"abbr", u"abbrev", u"room abbreviation",
                     u"code", u"short name"])


def _read_text(path):
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeError:
            continue
    return raw.decode("latin-1")


def read_tsv(path):
    """Returns (table {name: abbr}, warnings [str])."""
    text = _read_text(path)
    table, keys, warnings = {}, {}, []
    saw_tab = False
    first = True
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith(u"#"):
            continue
        parts = line.split(u"\t")
        if len(parts) > 1:
            saw_tab = True
        name = u" ".join(parts[0].strip().strip(u'"').split())
        abbr = parts[1].strip().strip(u'"') if len(parts) > 1 else u""
        if first:
            first = False
            if name.lower() in _NAME_HEADERS and \
                    (abbr.lower() in _ABBR_HEADERS or not abbr):
                continue                          # header row
        if not name:
            if abbr:
                warnings.append(u"Line {}: abbreviation '{}' has no room name - skipped."
                                .format(lineno, abbr))
            continue
        key = storage.normalize(name)
        if key in keys:
            old_name = keys[key]
            if table[old_name] != abbr:
                warnings.append(u"Line {}: '{}' is listed again ('{}' replaces '{}')."
                                .format(lineno, name, abbr, table[old_name]))
            del table[old_name]
        keys[key] = name
        table[name] = abbr
    if table and not saw_tab:
        warnings.append(u"No tab characters were found. Is the file tab-delimited? "
                        u"Every line was read as a room name with no abbreviation.")
    return table, warnings


def write_tsv(path, table):
    with io.open(path, "w", encoding="utf-8-sig", newline=u"\r\n") as f:
        f.write(u"Room Name\tAbbreviation\n")
        for name in sorted(table, key=lambda n: storage.normalize(n)):
            f.write(u"{}\t{}\n".format(name, table[name] or u""))
