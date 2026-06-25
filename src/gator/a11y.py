"""Accessibility helpers."""

from __future__ import annotations

from gi.repository import Gtk


def set_a11y_label(widget: Gtk.Widget, label: str) -> None:
    """Set accessible label when the GTK build exposes the API."""
    setter = getattr(widget, "set_accessible_name", None)
    if callable(setter):
        setter(label)
        return
    updater = getattr(widget, "update_accessible_property", None)
    if callable(updater):
        updater(Gtk.AccessibleProperty.LABEL, label)
