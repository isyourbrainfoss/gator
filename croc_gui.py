#!/usr/bin/env python3
# Croc GUI – Modern adaptive GTK4/Libadwaita frontend for croc
# © 2025 Your Name – GPL-3.0-or-later
# https://github.com/yourname/croc-gui
"""croc_gui – GTK4/Libadwaita graphical front-end for the croc file-transfer tool.

Single-file application; intended to be split into modules before Flathub
submission (see TASKS.md).  All subprocess I/O runs on daemon threads; UI
updates are always dispatched back to the main loop via GLib.idle_add.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
import logging

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from receive_page import ReceivePage
from send_page import SendPage
from settings import (
    APP_ID,
    APP_NAME,
    APP_VERSION,
    CROC_BINARY,
    DEFAULT_PORT,
    DEFAULT_TRANSFERS,
    get_default_save_dir,
    validate_settings,
)
from settings import (
    load_settings as _load_settings,
)
from settings import (
    save_settings as _save_settings,
)
from transfer import CrocReceiveTransfer, CrocSendTransfer

logger = logging.getLogger(__name__)

# ── Optional QR support ───────────────────────────────────────────────────────
from qr import HAS_QR_GEN, HAS_QR_SCAN, generate_qr_texture, scan_qr_from_image_path


class CrocGUI(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        GLib.set_application_name(APP_NAME)
        GLib.set_prgname("croc-gui")

        # Runtime state
        self.selected_files: list[str] = []
        self.excluded_items: list[str] = []
        self.send_text: str = ""
        self.received_text_content: str = ""
        self._send_transfer: CrocSendTransfer | None = None
        self._receive_transfer: CrocReceiveTransfer | None = None

        # Config (delegates to settings module for load/JSON)
        raw = _load_settings()
        self.settings = validate_settings(raw)

        # Apply saved theme
        self.apply_color_scheme()

        self.save_dir = self.settings.get("save_dir") or get_default_save_dir()

        # Toast overlay for notifications
        self.toast_overlay = Adw.ToastOverlay()

        # Actions
        self.create_action("quit", lambda *_: self.quit(), ["<Ctrl>q"])
        self.create_action("about", self.show_about)
        self.create_action("preferences", self.show_preferences)

    def create_action(
        self, name: str, callback: Any, accels: list[str] | None = None
    ) -> None:
        """Register a ``Gio.SimpleAction`` on the application with optional keyboard shortcuts."""
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if accels:
            self.set_accels_for_action(f"app.{name}", accels)

    def load_settings(self) -> dict[str, Any]:
        """Thin wrapper for backwards compatibility inside the class."""
        raw = _load_settings()
        return validate_settings(raw)

    def save_settings(self) -> None:
        """Persist via the settings module; surface errors as toasts."""
        try:
            _save_settings(self.settings)
        except Exception as e:  # defensive
            logger.error("Could not save settings: %s", e)
            GLib.idle_add(self.add_toast, "Warning: settings could not be saved")

    def apply_color_scheme(self) -> None:
        """Apply the saved color-scheme preference to the Adw.StyleManager.

        We also explicitly turn off the legacy GtkSettings flag that libadwaita
        complains about when it sees gtk-application-prefer-dark-theme.
        """
        # Suppress the "Using GtkSettings:gtk-application-prefer-dark-theme with
        # libadwaita is unsupported" warning by disabling the legacy setting.
        try:
            gtk_settings = Gtk.Settings.get_default()
            if gtk_settings:
                gtk_settings.set_property("gtk-application-prefer-dark-theme", False)
        except Exception:
            pass

        scheme = self.settings.get("color_scheme", "default")
        manager = Adw.StyleManager.get_default()
        if scheme == "light":
            cs = Adw.ColorScheme.FORCE_LIGHT
        elif scheme == "dark":
            cs = Adw.ColorScheme.FORCE_DARK
        else:
            cs = Adw.ColorScheme.DEFAULT
        try:
            manager.set_color_scheme(cs)
        except AttributeError:
            manager.color_scheme = cs

    def on_color_scheme_radio_toggled(
        self, button: Gtk.CheckButton, scheme: str
    ) -> None:
        """Handle a color-scheme radio button toggle in the preferences dialog."""
        if not button.get_active():
            return
        if self.settings.get("color_scheme") == scheme:
            return
        self.settings["color_scheme"] = scheme
        self.save_settings()
        GLib.idle_add(self.apply_color_scheme)

    def do_activate(self) -> None:
        """GApplication vfunc – create the main window and check for croc binary."""
        self.win = Adw.ApplicationWindow(application=self)
        self.win.set_title(APP_NAME)
        self.win.set_default_size(460, 780)
        self.win.set_size_request(380, 560)

        self.win.set_content(self.toast_overlay)

        try:
            subprocess.run(
                [CROC_BINARY, "--version"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            self.show_croc_missing()
        else:
            self.build_ui()
            self.win.present()

    def add_toast(self, title: str) -> None:
        """Show a brief toast notification in the main window."""
        toast = Adw.Toast(title=title)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)

    def show_croc_missing(self) -> None:
        """Replace the window content with an error status page when croc is absent."""
        page = Adw.StatusPage()
        page.set_title("croc not found")
        page.set_description(
            "The <b>croc</b> command-line tool is required to use this app.\nPlease install it first."
        )
        page.set_icon_name("dialog-error-symbolic")
        btn = Gtk.Button(label="Open croc GitHub page")
        btn.add_css_class("suggested-action")
        btn.add_css_class("pill")
        btn.connect(
            "clicked",
            lambda *_: Gtk.UriLauncher(uri="https://github.com/schollz/croc").launch(
                self.win, None, None
            ),
        )
        page.set_child(btn)
        self.toast_overlay.set_child(page)

    def build_ui(self) -> None:
        """Build and attach the main adaptive UI (header, ViewStack, breakpoint)."""
        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)

        # HeaderBar
        self.header = Adw.HeaderBar()
        toolbar.add_top_bar(self.header)
        self.title_label = Adw.WindowTitle(title=APP_NAME)
        self.header.set_title_widget(self.title_label)

        # Menu button
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_tooltip_text("Menu")
        menu = Gio.Menu()
        menu.append("Preferences", "app.preferences")
        menu.append("About Croc GUI", "app.about")
        menu.append("Quit", "app.quit")
        menu_btn.set_menu_model(menu)
        self.header.pack_end(menu_btn)

        # ViewSwitcher
        self.switcher = Adw.ViewSwitcher()
        self.switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)

        # Stack
        self.stack = Adw.ViewStack()
        self.stack.set_vhomogeneous(False)
        toolbar.set_content(self.stack)

        send_p = SendPage(self)
        send_page = self.stack.add_titled(send_p, "send", "Send")
        send_page.set_icon_name("document-send-symbolic")

        recv_p = ReceivePage(self)
        receive_page = self.stack.add_titled(recv_p, "receive", "Receive")
        receive_page.set_icon_name("folder-download-symbolic")

        # Post-configure optional QR scan button (disabled if pyzbar missing)
        if not HAS_QR_SCAN and hasattr(self, "scan_btn"):
            self.scan_btn.set_sensitive(False)
            self.scan_btn.set_tooltip_text("pyzbar not installed")

        self.switcher.set_stack(self.stack)

        # Bottom bar (mobile)
        self.bottom_bar = Adw.ViewSwitcherBar()
        self.bottom_bar.set_stack(self.stack)
        toolbar.add_bottom_bar(self.bottom_bar)

        # Breakpoint
        bp = Adw.Breakpoint()
        bp.set_condition(Adw.BreakpointCondition.parse("max-width: 560sp"))

        def on_narrow(*_):
            self.header.set_title_widget(self.title_label)
            self.bottom_bar.set_reveal(True)

        def on_wide(*_):
            self.header.set_title_widget(self.switcher)
            self.bottom_bar.set_reveal(False)

        bp.connect("apply", on_narrow)
        bp.connect("unapply", on_wide)
        self.win.add_breakpoint(bp)

        def init_layout():
            if self.win.get_realized():
                width = self.win.get_width()
                if width <= 560:
                    on_narrow()
                else:
                    on_wide()
            else:
                GLib.timeout_add(100, init_layout)

        GLib.idle_add(init_layout)

        self.stack.set_visible_child_name("send")

    # Send page extracted – see send_page.SendPage
    def _build_send_page(self) -> Gtk.ScrolledWindow:
        """Deprecated shim."""
        raise RuntimeError("removed")

    def on_drop_file(
        self, drop_target: Gtk.DropTarget, value: Any, x: float, y: float
    ) -> bool:
        """Handle drag-and-drop of files onto the send file list."""
        if isinstance(value, Gdk.FileList):
            for f in value.get_files():
                p = f.get_path()
                if p and p not in self.selected_files:
                    self.selected_files.append(p)

            self.update_file_list()
            return True

        return False

    def on_receive_qr_drop(
        self, drop_target: Gtk.DropTarget, value: Any, x: float, y: float
    ) -> bool:
        """Accept an image drop on the receive page and attempt QR scan."""
        if not HAS_QR_SCAN:
            self.add_toast("pyzbar not installed")
            return False
        if isinstance(value, Gdk.FileList):
            for f in value.get_files():
                p = f.get_path()
                if p:
                    code = scan_qr_from_image_path(p)
                    if code:
                        self.code_entry.set_text(code)
                        self.add_toast(f"Scanned from drop: {code}")
                        # Optionally auto-start receive
                        # self.on_start_receive(None)
                        return True
                    else:
                        self.add_toast("No QR code found in dropped image")
            return True
        return False

    def on_shell_toggle_changed_send(self, row: Adw.SwitchRow, _pspec: Any) -> None:
        """Show or hide the send log panel based on the toggle switch."""
        self.send_log_scroll.set_visible(row.get_active())

    def on_qr_toggle_changed(self, row: Adw.SwitchRow, _pspec: Any) -> None:
        """Show or hide the QR image based on the toggle switch."""
        self.qr_picture.set_visible(row.get_active())

    # Receive page extracted – see receive_page.ReceivePage
    def _build_receive_page(self) -> Gtk.ScrolledWindow:
        """Deprecated shim."""
        raise RuntimeError("removed")

    def on_shell_toggle_changed_receive(self, row: Adw.SwitchRow, _pspec: Any) -> None:
        """Show or hide the receive log panel based on the toggle switch."""
        self.receive_log_scroll.set_visible(row.get_active())

    def _make_switch_row(
        self, key: str, title: str, subtitle: str = ""
    ) -> Adw.SwitchRow:
        """Create a SwitchRow bound to a boolean settings key."""
        row = Adw.SwitchRow(title=title)
        if subtitle:
            row.set_subtitle(subtitle)
        row.set_active(self.settings.get(key, False))
        row.connect(
            "notify::active",
            lambda r, _: self.settings.update({key: r.get_active()})
            or self.save_settings(),  # type: ignore[func-returns-value]  # type: ignore[func-returns-value]
        )
        return row

    def _make_entry_row(self, key: str, title: str, tooltip: str = "") -> Adw.EntryRow:
        """Create an EntryRow bound to a string settings key."""
        row = Adw.EntryRow(title=title)
        row.set_text(self.settings.get(key, ""))
        if tooltip:
            row.set_tooltip_text(tooltip)
        row.connect(
            "changed",
            lambda e: self.settings.update({key: e.get_text().strip()})
            or self.save_settings(),  # type: ignore[func-returns-value]  # type: ignore[func-returns-value]
        )
        return row

    def show_preferences(self, *_) -> None:
        """Open the Preferences dialog (Adw.PreferencesDialog on libadwaita >= 1.5,
        falling back to a plain Gtk.Window on older runtimes)."""
        try:
            dlg = Adw.PreferencesDialog()
            dlg.set_title("Preferences")
            present_target = self.win
        except AttributeError:
            # libadwaita < 1.5: fall back to Gtk.Window
            dlg = None

        if dlg is None:
            pref_win = Gtk.Window(transient_for=self.win, modal=True)
            pref_win.set_title("Preferences")
            pref_win.set_default_size(420, 600)
            pref_win.set_titlebar(Adw.HeaderBar())
            page = Adw.PreferencesPage()
            pref_win.set_child(page)
            self._fill_preferences_page(page, pref_win)
            pref_win.present()
            return

        page = Adw.PreferencesPage()
        self._fill_preferences_page(page, dlg)
        dlg.add(page)
        dlg.present(present_target)

    def _fill_preferences_page(self, page: Adw.PreferencesPage, win) -> None:
        """Populate a PreferencesPage with all settings groups.

        *win* is the containing window or dialog; used only for the reset
        callback that needs to close and reopen the preferences UI.
        """
        # ── Appearance ───────────────────────────────────────────────────────
        appearance = Adw.PreferencesGroup(title="Appearance")
        current = self.settings.get("color_scheme", "default")
        radio_group = None
        for scheme, label, icon in [
            ("default", "Default (follow system)", "preferences-system-symbolic"),
            ("light", "Light", "weather-clear-symbolic"),
            ("dark", "Dark", "weather-clear-night-symbolic"),
        ]:
            row = Adw.ActionRow(title=label)
            row.add_prefix(Gtk.Image.new_from_icon_name(icon))
            radio = Gtk.CheckButton()
            if radio_group is None:
                radio_group = radio
            else:
                radio.set_group(radio_group)
            radio.set_active(current == scheme)
            row.add_suffix(radio)
            radio.connect("toggled", self.on_color_scheme_radio_toggled, scheme)
            row.set_activatable_widget(radio)
            appearance.add(row)
        page.add(appearance)

        # ── Receiving ────────────────────────────────────────────────────────
        receiving = Adw.PreferencesGroup(title="Receiving")
        folder_row = Adw.ActionRow(title="Default save folder", subtitle=self.save_dir)
        folder_row.add_prefix(Gtk.Image.new_from_icon_name("folder-symbolic"))
        folder_btn = Gtk.Button(icon_name="document-open-symbolic")
        folder_btn.set_tooltip_text("Change folder")
        folder_btn.connect("clicked", self.on_change_default_save_folder)
        folder_row.add_suffix(folder_btn)
        receiving.add(folder_row)
        receiving.add(
            self._make_switch_row(
                "yes",
                "Automatically accept incoming transfers",
                subtitle="Passes --yes to croc; skips all confirmation prompts",
            )
        )
        receiving.add(
            self._make_switch_row(
                "overwrite",
                "Overwrite existing files without prompt",
                subtitle="Passes --overwrite to croc",
            )
        )
        page.add(receiving)

        # ── General options ──────────────────────────────────────────────────
        general = Adw.PreferencesGroup(title="General Options")
        general.add(self._make_switch_row("debug", "Debug mode"))
        general.add(self._make_switch_row("no_compress", "Disable compression"))
        general.add(self._make_switch_row("ask", "Prompt sender and recipient"))
        general.add(self._make_switch_row("local", "Force local connections"))
        general.add(self._make_switch_row("internal_dns", "Use internal DNS resolver"))
        general.add(
            self._make_entry_row(
                "multicast",
                "Multicast address for local discovery",
                tooltip="Default: 239.255.255.250",
            )
        )
        general.add(
            self._make_entry_row(
                "ip", "Set sender IP if known", tooltip="e.g. 10.0.0.1:9009, [::1]:9009"
            )
        )
        general.add(
            self._make_entry_row(
                "throttle_upload", "Throttle upload speed", tooltip="e.g. 500k"
            )
        )
        page.add(general)

        # ── Relay and Proxy ──────────────────────────────────────────────────
        relay_proxy = Adw.PreferencesGroup(title="Relay and Proxy")
        relay_proxy.add(
            self._make_entry_row(
                "relay", "Relay address", tooltip="Default: 37.27.244.215:9009"
            )
        )
        relay_proxy.add(
            self._make_entry_row(
                "relay6",
                "IPv6 relay address",
                tooltip="Default: [2a01:4f9:c013:7b04::1]:9009",
            )
        )

        pass_row = Adw.PasswordEntryRow(title="Relay password")
        pass_row.set_text(self.settings.get("pass", ""))
        pass_row.set_tooltip_text("Default: pass123")
        pass_row.connect(
            "changed",
            lambda e: self.settings.update({"pass": e.get_text().strip()})
            or self.save_settings(),  # type: ignore[func-returns-value]
        )
        relay_proxy.add(pass_row)

        relay_proxy.add(self._make_entry_row("socks5", "SOCKS5 proxy"))
        relay_proxy.add(self._make_entry_row("connect", "HTTP proxy"))
        page.add(relay_proxy)

        # ── Sending options ──────────────────────────────────────────────────
        sending = Adw.PreferencesGroup(title="Sending Options")
        sending.add(
            self._make_entry_row(
                "default_code",
                "Default custom transfer code",
                tooltip="Optional – leave empty for a random code",
            )
        )

        hash_options = ["xxhash (default)", "imohash", "md5"]
        hash_row = Adw.ComboRow(title="Hash algorithm")
        hash_row.set_model(Gtk.StringList.new(hash_options))
        current_hash = self.settings.get("hash", "xxhash")
        hash_row.set_selected(
            hash_options.index(
                "xxhash (default)" if current_hash == "xxhash" else current_hash
            )
            if current_hash in ("xxhash", "imohash", "md5")
            else 0
        )
        hash_row.connect(
            "notify::selected",
            lambda c, _: self.settings.update(
                {"hash": c.get_selected_item().get_string().split(" ")[0]}
            )
            or self.save_settings(),  # type: ignore[func-returns-value]
        )
        sending.add(hash_row)

        sending.add(self._make_switch_row("zip_folder", "Zip folder before sending"))
        sending.add(self._make_switch_row("no_local", "Disable local relay"))
        sending.add(self._make_switch_row("no_multi", "Disable multiplexing"))
        sending.add(self._make_switch_row("git", "Respect .gitignore"))

        port_row = Adw.SpinRow(
            title="Base port for relay",
            adjustment=Gtk.Adjustment(
                value=self.settings.get("port", DEFAULT_PORT),
                lower=1,
                upper=65535,
                step_increment=1,
            ),
            climb_rate=1,
        )
        port_row.connect(
            "changed",
            lambda r: self.settings.update({"port": int(r.get_value())})
            or self.save_settings(),  # type: ignore[func-returns-value]
        )
        sending.add(port_row)

        transfers_row = Adw.SpinRow(
            title="Number of ports for transfers",
            adjustment=Gtk.Adjustment(
                value=self.settings.get("transfers", DEFAULT_TRANSFERS),
                lower=1,
                upper=100,
                step_increment=1,
            ),
            climb_rate=1,
        )
        transfers_row.connect(
            "changed",
            lambda r: self.settings.update({"transfers": int(r.get_value())})
            or self.save_settings(),  # type: ignore[func-returns-value]
        )
        sending.add(transfers_row)

        sending.add(
            self._make_switch_row(
                "qr",
                "Show receive code as QR",
                subtitle="Shows QR code in shell output",
            )
        )
        page.add(sending)

        # ── Reset ────────────────────────────────────────────────────────────
        reset_group = Adw.PreferencesGroup(title="Reset")
        reset_row = Adw.ActionRow(title="Reset all settings to default")
        reset_btn = Gtk.Button(label="Reset")
        reset_btn.add_css_class("destructive-action")
        reset_btn.connect(
            "clicked",
            lambda _: (
                self.on_reset_settings(),
                win.close(),
                GLib.idle_add(self.show_preferences),
            ),
        )
        reset_row.add_suffix(reset_btn)
        reset_group.add(reset_row)
        page.add(reset_group)

    def on_reset_settings(self) -> None:
        """Clear all persisted settings and restore UI to defaults."""
        self.settings = {}
        self.save_settings()
        self.apply_color_scheme()
        default_save_dir = get_default_save_dir()
        self.save_dir = default_save_dir
        self.folder_row.set_subtitle(default_save_dir)
        self.add_toast("Settings reset to default")

    # ──────── Send/Receive Logic ────────────────
    def on_add_files(self, included: bool = True) -> None:
        """Open a file-chooser dialog and add or exclude the selected files."""
        dialog = Gtk.FileDialog(
            title="Select Files to " + ("Add" if included else "Exclude")
        )

        def cb(_d, res):
            try:
                files = dialog.open_multiple_finish(res)
                for f in files:
                    p = f.get_path()
                    if included:
                        if p not in self.selected_files:
                            self.selected_files.append(p)
                    else:
                        if p not in self.excluded_items:
                            self.excluded_items.append(p)
                self.update_file_list()
            except GLib.GError:
                pass

        dialog.open_multiple(self.win, None, cb)

    def on_add_folder(self, included: bool = True) -> None:
        """Open a folder-chooser dialog and add or exclude the selected folder."""
        dialog = Gtk.FileDialog(
            title="Select Folder to " + ("Add" if included else "Exclude")
        )

        def cb(_d, res):
            try:
                folder = dialog.select_folder_finish(res)
                if folder:
                    p = folder.get_path()
                    if included:
                        if p not in self.selected_files:
                            self.selected_files.append(p)
                    else:
                        if p not in self.excluded_items:
                            self.excluded_items.append(p)
                    self.update_file_list()
            except GLib.GError:
                pass

        dialog.select_folder(self.win, None, cb)

    def on_add_text(self) -> None:
        """Open a modal editor window for composing text to send via croc --text."""
        text_win = Adw.Window(transient_for=self.win, modal=True)
        text_win.set_title("Add Text to Send")
        text_win.set_default_size(500, 400)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)
        text_win.set_content(toolbar)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(6)
        box.set_margin_bottom(12)
        toolbar.set_content(box)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        text_view = Gtk.TextView(monospace=True, wrap_mode=Gtk.WrapMode.NONE)
        scroll.set_child(text_view)
        box.append(scroll)

        paste_btn = Gtk.Button(label="Paste from clipboard")
        paste_btn.connect(
            "clicked",
            lambda _: self.win.get_clipboard().read_text_async(
                None,
                lambda _, res: text_view.get_buffer().set_text(
                    self.win.get_clipboard().read_text_finish(res) or ""
                ),
            ),
        )
        box.append(paste_btn)

        buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=12, halign=Gtk.Align.END
        )
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: text_win.close())
        buttons.append(cancel_btn)

        ok_btn = Gtk.Button(label="OK")
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect(
            "clicked",
            lambda _: (
                self.set_send_text_from_buffer(text_view.get_buffer()),
                text_win.close(),
                self.update_file_list(),
            ),
        )
        buttons.append(ok_btn)

        box.append(buttons)

        text_win.present()

    def set_send_text_from_buffer(self, buf: Gtk.TextBuffer) -> None:
        """Read the full content of *buf* into ``self.send_text``."""
        start, end = buf.get_bounds()
        self.send_text = buf.get_text(start, end, False)

    def update_file_list(self) -> None:
        """Rebuild the send-page file/exclude/text list from current state."""
        while row := self.files_listbox.get_row_at_index(0):
            self.files_listbox.remove(row)
        for path in self.selected_files:
            name = Path(path).name + (" (folder)" if os.path.isdir(path) else "")
            row = Adw.ActionRow(title=name, subtitle=path)
            row.add_prefix(Gtk.Image.new_from_icon_name("list-add-symbolic"))
            rm = Gtk.Button(icon_name="edit-delete-symbolic")
            rm.add_css_class("flat")
            rm.connect("clicked", lambda _, p=path: self.remove_item(p, included=True))
            row.add_suffix(rm)
            self.files_listbox.append(row)
        for path in self.excluded_items:
            name = Path(path).name + (" (folder)" if os.path.isdir(path) else "")
            row = Adw.ActionRow(title=name, subtitle=path)
            row.add_prefix(Gtk.Image.new_from_icon_name("list-remove-symbolic"))
            rm = Gtk.Button(icon_name="edit-delete-symbolic")
            rm.add_css_class("flat")
            rm.connect("clicked", lambda _, p=path: self.remove_item(p, included=False))
            row.add_suffix(rm)
            self.files_listbox.append(row)
        if self.send_text:
            # Collapse newlines for subtitle
            collapsed_text = " ".join(self.send_text.splitlines())
            subtitle = collapsed_text[:50] + ("..." if len(collapsed_text) > 50 else "")
            row = Adw.ActionRow(title="Text", subtitle=subtitle)
            row.add_prefix(
                Gtk.Image.new_from_icon_name("accessories-text-editor-symbolic")
            )
            rm = Gtk.Button(icon_name="edit-delete-symbolic")
            rm.add_css_class("flat")
            rm.connect(
                "clicked",
                lambda _: setattr(self, "send_text", "") or self.update_file_list(),
            )
            row.add_suffix(rm)
            self.files_listbox.append(row)
        self.send_start_btn.set_sensitive(
            bool(self.selected_files) or bool(self.send_text)
        )

    def remove_item(self, path: str, included: bool = True) -> None:
        """Remove *path* from the included or excluded list and refresh the UI."""
        if included:
            self.selected_files.remove(path)
        else:
            self.excluded_items.remove(path)
        self.update_file_list()

    def on_clear_all(self, _btn: Gtk.Button) -> None:
        """Clear all files, excluded items, and text from the send page."""
        self.selected_files = []
        self.excluded_items = []
        self.send_text = ""
        self.update_file_list()

    def append_log(self, view: Gtk.TextView, text: str) -> None:
        """Append a line of text to the given TextView log and scroll to bottom."""
        buf = view.get_buffer()
        end = buf.get_end_iter()
        buf.insert(end, text + "\n")
        mark = buf.create_mark("end", end, False)
        view.scroll_mark_onscreen(mark)

    def on_start_send(self, _btn: Gtk.Button) -> None:
        """Start a croc send transfer in a background thread."""
        if not self.selected_files and not self.send_text:
            return

        self.send_start_btn.set_visible(False)
        self.send_transfer_box.set_visible(True)
        self.send_spinner.start()

        self._send_transfer = CrocSendTransfer(
            settings=self.settings,
            files=self.selected_files,
            excluded=self.excluded_items,
            text=self.send_text,
            on_log=lambda msg: self.append_log(self.send_log, msg),
            on_code=self.show_code_and_qr,
            on_finished=self._on_send_finished,
        )
        self._send_transfer.start()

    def _on_send_finished(self) -> None:
        """Callback from CrocSendTransfer – reset UI and clear text."""
        self.transfer_finished_send()
        self.send_text = ""
        self.update_file_list()

    def show_code_and_qr(self, code: str) -> None:
        """Display the transfer code and optionally generate a QR image."""
        self.code_label.set_label(code)
        self.transfer_info.set_visible(True)
        if HAS_QR_GEN:
            manager = Adw.StyleManager.get_default()
            is_dark = manager.get_dark()
            tex = generate_qr_texture(code, is_dark)
            if tex:
                self.qr_picture.set_paintable(tex)
        self.qr_picture.set_visible(self.qr_toggle_row.get_active())

    def transfer_finished_send(self) -> None:
        """Reset the send UI after a transfer completes or is cancelled."""
        self.send_spinner.stop()
        self.send_transfer_box.set_visible(False)
        self.send_start_btn.set_visible(True)
        canceled = self._send_transfer.canceled if self._send_transfer else False
        msg = "Transfer cancelled." if canceled else "Transfer finished."
        self.append_log(self.send_log, msg)
        self.transfer_info.set_visible(False)
        self.code_label.set_label("")
        self.qr_picture.set_paintable(None)
        self._send_transfer = None

    def on_cancel_send(self, _btn: Gtk.Button) -> None:
        """Cancel an in-progress send transfer."""
        if self._send_transfer is not None:
            self._send_transfer.cancel()

    def on_start_receive(self, _btn: Gtk.Button | None) -> None:
        """Start a croc receive transfer in a background thread."""
        code = self.code_entry.get_text().strip()
        if not code:
            self.add_toast("Please enter a transfer code")
            return
        self.append_log(self.receive_log, f'Receiving with code "{code}"')
        self.receive_start_btn.set_visible(False)
        self.receive_transfer_box.set_visible(True)
        self.receive_spinner.start()
        self.code_entry.set_sensitive(False)
        self.receive_btn_box.set_sensitive(False)

        self._receive_transfer = CrocReceiveTransfer(
            settings=self.settings,
            code=code,
            save_dir=self.save_dir,
            on_log=lambda msg: self.append_log(self.receive_log, msg),
            on_text_received=self.show_received_text,
            on_transfer_complete=self.show_transfer_complete_popup,
            on_finished=self.transfer_finished_receive,
        )
        self._receive_transfer.start()

    def show_transfer_complete_popup(self) -> None:
        """Show a completion dialog with an option to open the save folder."""
        dialog = Adw.AlertDialog(
            heading="Transfer Complete", body="The files have been received."
        )

        dialog.add_response("close", "Close")
        dialog.add_response("open", "Open Folder")
        dialog.set_response_appearance("open", Adw.ResponseAppearance.SUGGESTED)

        def on_response(d, r):
            if r == "open":
                try:
                    uri = Path(self.save_dir).resolve().as_uri()
                    Gio.AppInfo.launch_default_for_uri(uri, None)
                except Exception as e:
                    logger.warning("Failed to open save folder: %s", e)
                    self.add_toast("Failed to open folder")

        dialog.connect("response", on_response)
        dialog.present(self.win)

    def transfer_finished_receive(self) -> None:
        """Reset the receive UI after a transfer completes or is cancelled."""
        self.receive_spinner.stop()
        self.receive_transfer_box.set_visible(False)
        self.receive_start_btn.set_visible(True)
        self.code_entry.set_sensitive(True)
        self.receive_btn_box.set_sensitive(True)
        canceled = self._receive_transfer.canceled if self._receive_transfer else False
        msg = "Transfer cancelled." if canceled else "Transfer finished."
        self.append_log(self.receive_log, msg)
        self._receive_transfer = None

    def on_cancel_receive(self, _btn: Gtk.Button) -> None:
        """Cancel an in-progress receive transfer."""
        if self._receive_transfer is not None:
            self._receive_transfer.cancel()

    def show_received_text(self, text: str) -> None:
        """Display received text content in a modal window with a proper header bar."""
        text_win = Adw.Window(transient_for=self.win, modal=True)
        text_win.set_title("Received Text")
        text_win.set_default_size(500, 400)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()

        # Copy button lives in the header bar for easy access
        copy_header_btn = Gtk.Button(icon_name="edit-copy-symbolic")
        copy_header_btn.set_tooltip_text("Copy to clipboard")
        copy_header_btn.add_css_class("suggested-action")
        copy_header_btn.connect(
            "clicked",
            lambda _: (
                self.win.get_clipboard().set(text),
                self.add_toast("Text copied to clipboard"),
            ),
        )
        header.pack_end(copy_header_btn)

        toolbar.add_top_bar(header)
        text_win.set_content(toolbar)

        scroll = Gtk.ScrolledWindow(
            vexpand=True, margin_start=12, margin_end=12, margin_top=6, margin_bottom=12
        )
        text_view = Gtk.TextView(
            editable=False, monospace=True, wrap_mode=Gtk.WrapMode.NONE
        )
        buf = text_view.get_buffer()
        buf.set_text(text)
        scroll.set_child(text_view)
        toolbar.set_content(scroll)

        text_win.present()

    # ──────── Helpers ─────────────────────────────────────────────────────
    def on_paste_clipboard(self, _btn: Gtk.Button) -> None:
        """Paste text from the clipboard into the transfer code entry."""
        clipboard = self.win.get_clipboard()

        def cb(_c, res):
            try:
                text = clipboard.read_text_finish(res)
                if text:
                    self.code_entry.set_text(text.strip())
                    self.add_toast("Pasted from clipboard")
            except GLib.GError as e:
                logger.warning("Clipboard read failed: %s", e)
                self.add_toast("Could not read clipboard")

        clipboard.read_text_async(None, cb)

    def on_scan_qr_image(self, _btn: Gtk.Button) -> None:
        """Open a file dialog to scan a QR code from an image file."""
        dialog = Gtk.FileDialog(title="Select QR Code Image")
        filt = Gtk.FileFilter()
        filt.set_name("Images")
        for m in ["image/png", "image/jpeg", "image/webp", "image/bmp"]:
            filt.add_mime_type(m)
        dialog.set_default_filter(filt)

        def cb(_d, res):
            try:
                file = dialog.open_finish(res)
                code = scan_qr_from_image_path(file.get_path())
                if code:
                    self.code_entry.set_text(code)
                    self.add_toast(f"Scanned: {code}")
                else:
                    self.add_toast("No QR code found in image")
            except GLib.GError:
                pass  # User cancelled the file dialog
            except Exception as e:
                logger.warning("QR scan failed: %s", e)
                self.add_toast("QR scan failed")

        dialog.open(self.win, None, cb)

    def on_change_folder(self, _btn: Gtk.Button) -> None:
        """Change the save folder for this session only (not persisted)."""
        dialog = Gtk.FileDialog(title="Choose Save Folder")
        dialog.set_initial_folder(Gio.File.new_for_path(self.save_dir))

        def cb(_d, res):
            try:
                f = dialog.select_folder_finish(res)
                self.save_dir = f.get_path()
                self.folder_row.set_subtitle(self.save_dir)
            except GLib.GError:
                pass

        dialog.select_folder(self.win, None, cb)

    def on_copy_code(self, _btn: Gtk.Button) -> None:
        """Copy the displayed transfer code to the clipboard."""
        code = self.code_label.get_text()
        if code:
            self.win.get_clipboard().set(code)
            self.add_toast("Code copied to clipboard")

    def on_change_default_save_folder(self, _btn: Gtk.Button) -> None:
        """Change the default save folder (persisted to settings)."""
        dialog = Gtk.FileDialog(title="Choose Default Save Folder")
        dialog.set_initial_folder(Gio.File.new_for_path(self.save_dir))

        def cb(_d, res):
            try:
                f = dialog.select_folder_finish(res)
                if f:
                    new = f.get_path()
                    self.save_dir = new
                    self.settings["save_dir"] = new
                    self.folder_row.set_subtitle(new)
                    self.save_settings()
            except GLib.GError:
                pass

        dialog.select_folder(self.win, None, cb)

    def show_about(self, *_: Any) -> None:
        """Show the About dialog (preferring Adw.AboutDialog if available)."""
        # Adw.AboutDialog requires libadwaita >= 1.5 (GNOME 45).
        # Fall back to Adw.AboutWindow on older runtimes.
        common = {
            "application_name": APP_NAME,
            "version": APP_VERSION,
            "developer_name": "Your Name",
            "website": "https://github.com/yourname/croc-gui",
            "issue_url": "https://github.com/yourname/croc-gui/issues",
            "copyright": "© 2025 Your Name",
            "license_type": Gtk.License.GPL_3_0,
            "comments": "Modern GTK4/Libadwaita frontend for croc – secure file transfer made beautiful",
            "application_icon": APP_ID,
            "developers": ["Your Name"],
            "designers": ["Your Name"],
        }
        try:
            about = Adw.AboutDialog(**common)
            about.present(self.win)
        except AttributeError:
            about = Adw.AboutWindow(transient_for=self.win, modal=True, **common)
            about.present()


def main() -> None:
    """Entry point for the croc-gui command."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    CrocGUI().run(sys.argv)


if __name__ == "__main__":
    main()
