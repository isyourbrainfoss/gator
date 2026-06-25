"""Main window shell for Gator."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from .a11y import set_a11y_label
from .i18n import _
from .receive_page import ReceivePage
from .send_page import SendPage
from .settings import APP_NAME, CROC_BINARY

if TYPE_CHECKING:
    from .settings import GatorSettings


class GatorWindow(Adw.ApplicationWindow):
    """Primary application window with adaptive navigation."""

    def __init__(
        self,
        application: Gtk.Application,
        settings: GatorSettings,
        save_dir: str,
    ) -> None:
        super().__init__(application=application)
        self.settings = settings
        self.set_title(APP_NAME)
        self.set_default_size(460, 780)
        self.set_size_request(320, 560)

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        self.send_page: SendPage | None = None
        self.receive_page: ReceivePage | None = None
        self._save_dir = save_dir
        self._menu_btn: Gtk.MenuButton | None = None
        self._menu_popover: Gtk.PopoverMenu | None = None

    def add_toast(self, title: str) -> None:
        toast = Adw.Toast(title=title)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)

    def show_croc_missing(self) -> None:
        page = Adw.StatusPage()
        page.set_title(_("croc not found"))
        page.set_description(
            _(
                "The <b>croc</b> command-line tool is required to use this app.\n"
                "Please install it first."
            )
        )
        page.set_icon_name("dialog-error-symbolic")
        btn = Gtk.Button(label=_("Open croc GitHub page"))
        btn.add_css_class("suggested-action")
        btn.add_css_class("pill")
        btn.connect(
            "clicked",
            lambda *_: Gtk.UriLauncher(uri="https://github.com/schollz/croc").launch(
                self, None, None
            ),
        )
        page.set_child(btn)
        self.toast_overlay.set_child(page)

    def build_main_ui(self) -> tuple[SendPage, ReceivePage]:
        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)

        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)
        title_label = Adw.WindowTitle(title=APP_NAME)
        header.set_title_widget(title_label)

        menu = Gio.Menu()
        menu.append(_("Preferences"), "app.preferences")
        menu.append(_("About Gator"), "app.about")
        menu.append(_("Quit"), "app.quit")
        menu_popover = Gtk.PopoverMenu.new_from_model(menu)
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_tooltip_text(_("Menu"))
        set_a11y_label(menu_btn, _("Menu"))
        menu_btn.set_popover(menu_popover)
        menu_btn.set_direction(Gtk.ArrowType.DOWN)
        header.pack_end(menu_btn)
        self._menu_btn = menu_btn
        self._menu_popover = menu_popover
        self._configure_menu_popover(narrow=False)

        switcher = Adw.ViewSwitcher()
        switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        stack = Adw.ViewStack()
        stack.set_vhomogeneous(False)
        stack.set_hexpand(True)
        toolbar.set_content(stack)

        send_page = SendPage(self.settings)
        send_page.set_hexpand(True)
        send_page.set_vexpand(True)
        stack.add_titled(send_page, "send", _("Send")).set_icon_name(
            "document-send-symbolic"
        )
        receive_page = ReceivePage(self.settings, self._save_dir)
        receive_page.set_hexpand(True)
        receive_page.set_vexpand(True)
        stack.add_titled(receive_page, "receive", _("Receive")).set_icon_name(
            "folder-download-symbolic"
        )

        switcher.set_stack(stack)
        bottom_bar = Adw.ViewSwitcherBar()
        bottom_bar.set_stack(stack)
        toolbar.add_bottom_bar(bottom_bar)

        bp = Adw.Breakpoint()
        bp.set_condition(Adw.BreakpointCondition.parse("max-width: 560sp"))

        def on_narrow(*_):
            header.set_title_widget(title_label)
            bottom_bar.set_reveal(True)
            self._configure_menu_popover(narrow=True)

        def on_wide(*_):
            header.set_title_widget(switcher)
            bottom_bar.set_reveal(False)
            self._configure_menu_popover(narrow=False)

        bp.connect("apply", on_narrow)
        bp.connect("unapply", on_wide)
        self.add_breakpoint(bp)

        def init_layout():
            if self.get_realized():
                if self.get_width() <= 560:
                    on_narrow()
                else:
                    on_wide()
            else:
                GLib.timeout_add(100, init_layout)
            return False

        # Popover parent requires a realized window; re-apply after first map.
        def on_mapped(*_):
            self._configure_menu_popover(narrow=self.get_width() <= 560)

        self.connect("map", on_mapped)

        GLib.idle_add(init_layout)
        stack.set_visible_child_name("send")

        self.send_page = send_page
        self.receive_page = receive_page
        return send_page, receive_page

    def _configure_menu_popover(self, *, narrow: bool) -> None:
        """Keep the header menu popover inside the window on narrow viewports."""
        popover = self._menu_popover
        if popover is None:
            return
        popover.set_parent(self)
        popover.set_halign(Gtk.Align.END)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.set_overflow(Gtk.Overflow.HIDDEN)
        popover.set_has_arrow(not narrow)
        margin = 8 if narrow else 4
        popover.set_margin_start(margin)
        popover.set_margin_end(margin)

    def update_save_dir(self, path: str) -> None:
        self._save_dir = path
        if self.receive_page is not None:
            self.receive_page.set_save_dir_subtitle(path)


def check_croc_available(callback: Callable[[bool], None]) -> None:
    """Check for croc binary without blocking the main loop."""
    flags = Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE
    launcher = Gio.SubprocessLauncher.new(flags)
    try:
        proc = launcher.spawnv([CROC_BINARY, "--version"])
    except GLib.Error:
        GLib.idle_add(callback, False)
        return

    def on_wait(_proc: Gio.Subprocess, result: Gio.AsyncResult) -> None:
        try:
            _proc.wait_finish(result)
            GLib.idle_add(callback, True)
        except GLib.Error:
            GLib.idle_add(callback, False)

    proc.wait_async(None, on_wait)
