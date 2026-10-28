# -*- coding: utf-8 -*-
"""pyRevit runs this when the extension loads (Revit start and every
pyRevit Reload). It registers the Room Abbreviation IUpdater."""
from pyrevit import HOST_APP, script

logger = script.get_logger()


def _addin_id():
    for getter in (lambda: HOST_APP.addin_id,
                   lambda: __revit__.ActiveAddInId,               # noqa: F821
                   lambda: __revit__.Application.ActiveAddInId):  # noqa: F821
        try:
            value = getter()
            if value is not None:
                return value
        except Exception:
            continue
    return None


try:
    from roomabbrev import updater
    addin_id = _addin_id()
    if addin_id is None:
        logger.error("Room Abbreviations: no AddInId available; updater not registered.")
    else:
        updater.register(addin_id)
except Exception as ex:
    logger.error("Room Abbreviations: could not register updater: {}".format(ex))
