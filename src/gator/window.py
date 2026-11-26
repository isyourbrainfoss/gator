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
from .settings import (
    APP_NAME,
    CROC_BINARY,
    get_runtime_croc_version,
    parse_croc_version_output,
    set_runtime_croc_version,
)

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

    def show_croc_missing(self, on_retry: Callable[[], None] | None = None) -> None:
        page = Adw.StatusPage()
        page.set_title(_("croc not found"))
        page.set_description(
            _(
                "Gator needs the croc tool to send and receive files. "
                "Install croc from your package manager, or use the Flatpak "
                "build which already includes it."
            )
        )
        page.set_icon_name("dialog-error-symbolic")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_halign(Gtk.Align.CENTER)
        btn = Gtk.Button(label=_("How to install croc"))
        btn.add_css_class("suggested-action")
        btn.add_css_class("pill")
        btn.connect(
            "clicked",
            lambda *_: Gtk.UriLauncher(uri="https://github.com/schollz/croc").launch(
                self, None, None
            ),
        )
        box.append(btn)
        if on_retry is not None:
            retry = Gtk.Button(label=_("Try again"))
            retry.add_css_class("pill")
            retry.connect("clicked", lambda *_: on_retry())
            box.append(retry)
        page.set_child(box)
        self.toast_overlay.set_child(page)

    def show_checking_croc(self) -> None:
        page = Adw.StatusPage()
        page.set_title(APP_NAME)
        page.set_description(_("Checking for croc…"))
        spinner = Gtk.Spinner()
        spinner.start()
        page.set_child(spinner)
        self.toast_overlay.set_child(page)

    def build_main_ui(self) -> tuple[SendPage, ReceivePage]:
        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)

        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)
        title_label = Adw.WindowTitle(title=APP_NAME)
        header.set_title_widget(title_label)

        menu = Gio.Menu()
        section = Gio.Menu()
        section.append(_("Preferences"), "app.preferences")
        section.append(_("Keyboard Shortcuts"), "app.shortcuts")
        section.append(_("About Gator"), "app.about")
        menu.append_section(None, section)
        quit_section = Gio.Menu()
        quit_section.append(_("Quit"), "app.quit")
        menu.append_section(None, quit_section)
        menu_popover = Gtk.PopoverMenu.new_from_model(menu)
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.add_css_class("flat")
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

        stack.set_visible_child_name("send")
        self._view_stack = stack

        def on_stack_changed(*_args: object) -> None:
            child = stack.get_visible_child_name() or "send"
            title_label.set_subtitle(_("Send") if child == "send" else _("Receive"))

        stack.connect("notify::visible-child", on_stack_changed)
        on_stack_changed()

        self.send_page = send_page
        self.receive_page = receive_page
        return send_page, receive_page

    def visible_tab(self) -> str:
        stack = getattr(self, "_view_stack", None)
        if stack is None:
            return "send"
        return stack.get_visible_child_name() or "send"

    def set_visible_tab(self, name: str) -> None:
        stack = getattr(self, "_view_stack", None)
        if stack is not None:
            stack.set_visible_child_name(name)

    def _configure_menu_popover(self, *, narrow: bool) -> None:
        """Keep the header menu popover inside the window on narrow viewports."""
        popover = self._menu_popover
        if popover is None:
            return
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


# Latest `croc --version` probe. About can subscribe while one is in flight.
_croc_probe_generation = 0
_croc_probe_pending = False
_croc_version_listeners: list[Callable[[str | None], None]] = []


def watch_croc_version(callback: Callable[[str | None], None]) -> None:
    """Call *callback* with the bare runtime version once the current probe ends.

    The callback runs on the main loop. ``None`` means the binary is missing
    or the version line could not be parsed; the caller keeps the bundled pin.
    If no probe is running, the callback is scheduled idle with the cache.
    """
    if not _croc_probe_pending:
        version = get_runtime_croc_version()

        def once(found: str | None) -> bool:
            callback(found)
            return False

        GLib.idle_add(once, version)
        return
    _croc_version_listeners.append(callback)


def _settle_croc_probe(generation: int, *, ok: bool, output: str) -> None:
    """Store the probed version and wake About listeners for this generation."""
    global _croc_probe_pending
    if generation != _croc_probe_generation:
        return
    parsed = parse_croc_version_output(output) if ok else None
    set_runtime_croc_version(parsed)
    _croc_probe_pending = False
    listeners = list(_croc_version_listeners)
    _croc_version_listeners.clear()
    version = get_runtime_croc_version()
    for listener in listeners:
        listener(version)


def check_croc_available(callback: Callable[[bool], None]) -> None:
    """Check for the croc binary without blocking the main loop.

    Also caches the version printed by ``croc --version`` (stdout or stderr)
    so About can show ``croc vX.Y.Z`` for the binary actually in use.
    """
    global _croc_probe_generation, _croc_probe_pending
    _croc_probe_generation += 1
    generation = _croc_probe_generation
    _croc_probe_pending = True

    flags = Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
    launcher = Gio.SubprocessLauncher.new(flags)
    try:
        proc = launcher.spawnv([CROC_BINARY, "--version"])
    except GLib.Error:
        _settle_croc_probe(generation, ok=False, output="")
        GLib.idle_add(callback, False)
        return

    timeout_id = 0

    def clear_timeout() -> None:
        nonlocal timeout_id
        if timeout_id:
            GLib.source_remove(timeout_id)
            timeout_id = 0

    def on_communicate(_proc: Gio.Subprocess, result: Gio.AsyncResult) -> None:
        clear_timeout()
        output = ""
        ok = False
        try:
            success, stdout, stderr = _proc.communicate_utf8_finish(result)
            output = f"{stdout or ''}\n{stderr or ''}"
            if hasattr(_proc, "get_successful"):
                ok = bool(_proc.get_successful())
            else:
                ok = bool(success)
        except GLib.Error:
            ok = False
        if generation != _croc_probe_generation:
            return
        _settle_croc_probe(generation, ok=ok, output=output)
        GLib.idle_add(callback, ok)

    def timeout_kill() -> bool:
        nonlocal timeout_id
        timeout_id = 0
        try:
            proc.force_exit()
        except GLib.Error:
            pass
        return False

    timeout_id = GLib.timeout_add_seconds(5, timeout_kill)
    proc.communicate_utf8_async(None, None, on_communicate)
