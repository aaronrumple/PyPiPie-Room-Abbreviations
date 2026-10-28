# -*- coding: utf-8 -*-
"""Small UI helpers: follow Revit's light/dark theme in WPF windows."""
import clr
clr.AddReference("WindowsBase")
clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
from System.Windows.Media import SolidColorBrush, ColorConverter

LIGHT = {"Bg": "#FFFFFF", "Fg": "#1E1E1E", "Panel": "#F2F2F2", "Line": "#C8C8C8",
         "Alt": "#F6F8FB", "Accent": "#2D7DD2", "AccentFg": "#FFFFFF", "Muted": "#666666",
         "Warn": "#B25E00"}
DARK = {"Bg": "#2B2B2B", "Fg": "#E6E6E6", "Panel": "#383838", "Line": "#4C4C4C",
        "Alt": "#313131", "Accent": "#3D8EE0", "AccentFg": "#FFFFFF", "Muted": "#A3A3A3",
        "Warn": "#F0A040"}


def is_dark():
    try:
        from Autodesk.Revit.UI import UIThemeManager, UITheme   # Revit 2024+
        return UIThemeManager.CurrentTheme == UITheme.Dark
    except Exception:
        return False


def apply_theme(window):
    palette = DARK if is_dark() else LIGHT
    for key, hexval in palette.items():
        window.Resources[key] = SolidColorBrush(ColorConverter.ConvertFromString(hexval))
