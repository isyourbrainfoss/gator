"""Modal dialogs for Gator."""

from __future__ import annotations

import logging
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from .a11y import set_a11y_label
from .i18n import _

logger = logging.getLogger(__name__)


def show_add_text_dialog(
    parent: Gtk.Window,
    on_accept: Callable[[str], None],
    initial: str = "",
) -> None:
    """Modal editor for text to send via croc --text."""
    text_win = Adw.Window(transient_for=parent, modal=True)
    text_win.set_title(_("Add Text to Send"))
    text_win.set_default_size(500, 400)

    toolbar = Adw.ToolbarView()
    header = Adw.HeaderBar()
    toolbar.add_top_bar(header)

    cancel_btn = Gtk.Button(label=_("Cancel"))
    cancel_btn.connect("clicked", lambda *_: text_win.close())
    header.pack_start(cancel_btn)

    paste_btn = Gtk.Button(icon_name="edit-paste-symbolic")
    paste_btn.set_tooltip_text(_("Paste from clipboard"))
    set_a11y_label(paste_btn, _("Paste from clipboard"))
    header.pack_end(paste_btn)

    ok_btn = Gtk.Button(label=_("Add"))
    ok_btn.add_css_class("suggested-action")
    ok_btn.set_sensitive(bool(initial.strip()))
    header.pack_end(ok_btn)

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    box.set_margin_start(12)
    box.set_margin_end(12)
    box.set_margin_top(6)
    box.set_margin_bottom(12)
    toolbar.set_content(box)

    scroll = Gtk.ScrolledWindow(vexpand=True)
    text_view = Gtk.TextView(monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
    set_a11y_label(text_view, _("Text to send"))
    if initial:
        text_view.get_buffer().set_text(initial)
    scroll.set_child(text_view)
    box.append(scroll)

    def _buffer_nonempty() -> bool:
        buf = text_view.get_buffer()
        start, end = buf.get_bounds()
        return bool(buf.get_text(start, end, False).strip())

    def on_buffer_changed(_buf: Gtk.TextBuffer) -> None:
        ok_btn.set_sensitive(_buffer_nonempty())

    text_view.get_buffer().connect("changed", on_buffer_changed)

    def paste_from_clipboard(_btn: Gtk.Button) -> None:
        clipboard = parent.get_clipboard()

        def cb(_c, res):
            try:
                text = clipboard.read_text_finish(res)
                if text:
                    text_view.get_buffer().set_text(text)
            except Exception:
                logger.warning("Clipboard paste failed", exc_info=True)

        clipboard.read_text_async(None, cb)

    paste_btn.connect("clicked", paste_from_clipboard)

    def accept(_btn: Gtk.Button) -> None:
        if not _buffer_nonempty():
            return
        buf = text_view.get_buffer()
        start, end = buf.get_bounds()
        on_accept(buf.get_text(start, end, False))
        text_win.close()

    ok_btn.connect("clicked", accept)
    text_win.set_content(toolbar)
    text_win.present()


def show_received_text_dialog(
    parent: Gtk.Window,
    text: str,
    on_copied: Callable[[], None] | None = None,
) -> None:
    """Display received text in a modal window."""
    text_win = Adw.Window(transient_for=parent, modal=True)
    text_win.set_title(_("Received Text"))
    text_win.set_default_size(500, 400)

    toolbar = Adw.ToolbarView()
    header = Adw.HeaderBar()
    copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
    copy_btn.set_tooltip_text(_("Copy to clipboard"))
    set_a11y_label(copy_btn, _("Copy to clipboard"))
    copy_btn.add_css_class("suggested-action")

    def do_copy(_btn: Gtk.Button) -> None:
        parent.get_clipboard().set(text)
        if on_copied:
            on_copied()

    copy_btn.connect("clicked", do_copy)
    header.pack_end(copy_btn)
    toolbar.add_top_bar(header)

    scroll = Gtk.ScrolledWindow(
        vexpand=True,
        margin_start=12,
        margin_end=12,
        margin_top=6,
        margin_bottom=12,
    )
    text_view = Gtk.TextView(
        editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR
    )
    text_view.get_buffer().set_text(text)
    scroll.set_child(text_view)
    toolbar.set_content(scroll)
    text_win.set_content(toolbar)
    text_win.present()
