"""Theme-aware color helpers for GTK/libadwaita."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gi.repository import Gtk


def _new_gdk_rgba() -> object:
    """Create a Gdk RGBA object (PyGObject uses RGBA; older builds used Rgba)."""
    from gi.repository import Gdk

    if hasattr(Gdk, "RGBA"):
        return Gdk.RGBA()
    return Gdk.Rgba()  # type: ignore[attr-defined,no-any-return]


def get_theme_rgba(widget: Gtk.Widget, name: str) -> tuple[float, float, float, float]:
    """Return RGBA for a named GTK/libadwaita color (e.g. error_color)."""
    rgba = _new_gdk_rgba()
    found = False
    try:
        style_context = widget.get_style_context()
        result = style_context.lookup_color(name)
        if isinstance(result, tuple) and len(result) == 2:
            found, rgba = result
        elif result:
            # GTK3-style out-parameter API (local dev fallbacks)
            found = bool(result)
    except TypeError:
        # GTK3: lookup_color(name, rgba_out) -> bool
        try:
            found = style_context.lookup_color(name, rgba)  # type: ignore[call-arg]
        except Exception:
            found = False
    except Exception:
        found = False

    if not found:
        if name in ("window_fg_color", "foreground"):
            fg = widget.get_color()
            return (fg.red, fg.green, fg.blue, fg.alpha)
        return (0.5, 0.5, 0.5, 1.0)

    return (rgba.red, rgba.green, rgba.blue, rgba.alpha)


def rgba_to_hex(rgba: tuple[float, float, float, float]) -> str:
    """Convert normalized RGBA to #rrggbb (clamped to sRGB range)."""
    r, g, b, _a = rgba

    def channel(value: float) -> int:
        return int(max(0.0, min(1.0, value)) * 255)

    return f"#{channel(r):02x}{channel(g):02x}{channel(b):02x}"


def qr_colors_for_widget(widget: Gtk.Widget) -> tuple[str, str]:
    """Return (foreground, background) hex colors for QR generation."""
    fg = rgba_to_hex(get_theme_rgba(widget, "window_fg_color"))
    bg = rgba_to_hex(get_theme_rgba(widget, "window_bg_color"))
    return fg, bg
