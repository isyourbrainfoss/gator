"""Theme-aware color helpers for GTK/libadwaita."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gi.repository import Gtk


def get_theme_rgba(widget: Gtk.Widget, name: str) -> tuple[float, float, float, float]:
    """Return RGBA for a named GTK color (e.g. error_color, window_bg_color)."""
    from gi.repository import Gdk, Gtk

    style_context = widget.get_style_context()
    provider = Gtk.CssProvider()
    provider.load_from_string(f"dummy {{ color: @{name}; }}")
    style_context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    rgba = Gdk.Rgba()
    if not style_context.lookup_color("color", rgba):
        rgba.red = rgba.green = rgba.blue = 0.5
        rgba.alpha = 1.0
    style_context.remove_provider(provider)
    return (rgba.red, rgba.green, rgba.blue, rgba.alpha)


def rgba_to_hex(rgba: tuple[float, float, float, float]) -> str:
    """Convert normalized RGBA to #rrggbb."""
    r, g, b, _a = rgba
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def qr_colors_for_widget(widget: Gtk.Widget) -> tuple[str, str]:
    """Return (foreground, background) hex colors for QR generation."""
    fg = rgba_to_hex(get_theme_rgba(widget, "window_fg_color"))
    bg = rgba_to_hex(get_theme_rgba(widget, "window_bg_color"))
    return fg, bg
