# -*- coding: utf-8 -*-
"""Open the bundled HTML help, optionally at a section.

Windows drops the #section when a local file is opened directly, so a tiny
redirect page in %TEMP% is opened instead and jumps to the section."""
import io
import os
import tempfile

try:
    from urllib import quote            # IronPython 2.7
except ImportError:
    from urllib.parse import quote      # CPython 3

from roomabbrev import config

HELP_FILE = os.path.join(config.EXT_DIR, "help", "RoomAbbreviations.html")


def _file_url(path, section=None):
    url = u"file:///" + quote(path.replace(u"\\", u"/").encode("utf-8"), safe=":/")
    return url + (u"#" + section if section else u"")


def open_help(section=None):
    if not os.path.exists(HELP_FILE):
        raise IOError("Help file not found:\n" + HELP_FILE)
    target = HELP_FILE
    if section:
        target = os.path.join(tempfile.gettempdir(), "RoomAbbreviations_help.html")
        with io.open(target, "w", encoding="utf-8") as f:
            f.write(u'<!doctype html><meta charset="utf-8">'
                    u'<meta http-equiv="refresh" content="0;url={0}">'
                    u'<a href="{0}">Room Abbreviations Help</a>'
                    .format(_file_url(HELP_FILE, section)))
    os.startfile(target)
