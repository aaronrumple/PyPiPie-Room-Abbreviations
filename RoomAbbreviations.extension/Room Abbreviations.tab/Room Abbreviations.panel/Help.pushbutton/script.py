# -*- coding: utf-8 -*-
__title__ = "Help"
__doc__ = """Open the Room Abbreviations help page."""

from pyrevit import forms

from roomabbrev import helpdoc

try:
    helpdoc.open_help()
except Exception as ex:
    forms.alert(u"Could not open help:\n{}".format(ex))
