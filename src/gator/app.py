#!/usr/bin/env python3
# Gator – Modern adaptive GTK4/Libadwaita frontend for croc
# © 2026 Gator Contributors – GPL-3.0-or-later
"""Gator application entry and transfer controller."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from .dialogs import show_add_text_dialog, show_received_text_dialog
from .i18n import _
from .preferences import PreferencesDialog
from .qr import (
    HAS_QR_GEN,
    HAS_QR_SCAN,
    QR_SCAN_HINT,
    generate_qr_texture,
    scan_qr_from_image_path,
)
from .settings import (
    APP_ID,
    APP_NAME,
    APP_VERSION,
    GatorSettings,
    get_default_save_dir,
)
from .theme import load_app_css, qr_colors_for_widget
from .transfer import (
    ERROR_FAILED,
    ERROR_INVALID_CODE,
    ERROR_PEER,
    ERROR_PERMISSION,
    ERROR_REFUSED,
    ERROR_RELAY,
    ERROR_SPAWN,
    CrocReceiveTransfer,
    CrocSendTransfer,
    normalize_croc_code,
)
from .window import GatorWindow, check_croc_available

logger = logging.getLogger(__name__)

_ERROR_COPY = {
    ERROR_INVALID_CODE: _(
        "This code isn’t valid. Check it, or ask the sender for a new one."
    ),
    ERROR_PEER: _("The other device disconnected before the transfer finished."),
    ERROR_REFUSED: _(
        "A file with that name already exists. Enable overwrite or rename in Preferences."
    ),
    ERROR_RELAY: _(
        "Couldn’t reach the relay. Check your network or the relay address in Preferences."
    ),
    ERROR_PERMISSION: _(
        "Gator can’t write to this folder. Choose a folder you have access to."
    ),
    ERROR_SPAWN: _("Couldn’t start croc. Is it installed and on your PATH?"),
    ERROR_FAILED: _("The transfer could not be completed."),
}


class GatorApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        GLib.set_application_name(APP_NAME)
        GLib.set_prgname(APP_ID)
        self.set_default_icon_name(APP_ID)

        self.settings = GatorSettings()
        self.apply_color_scheme()
        self.save_dir = self.settings.get("save_dir") or get_default_save_dir()

        self.win: GatorWindow | None = None
        self.send_page = None
        self.receive_page = None
        self._prefs_dialog: PreferencesDialog | None = None
        self._send_transfer: CrocSendTransfer | None = None
        self._receive_transfer: CrocReceiveTransfer | None = None
        self.send_text: str = ""
        self._inhibit_cookie = 0
        self._reset_send_source = 0
        self._reset_receive_source = 0
        self._closing = False

        self.create_action("quit", self._on_quit_action, ["<Ctrl>q"])
        self.create_action("about", self.show_about)
        self.create_action("preferences", self.show_preferences, ["<Ctrl>comma"])
        self.create_action("shortcuts", self.show_shortcuts, ["<Ctrl>question"])

    def create_action(
        self, name: str, callback: Any, accels: list[str] | None = None
    ) -> None:
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if accels:
            self.set_accels_for_action(f"app.{name}", accels)

    def apply_color_scheme(self) -> None:
        scheme = self.settings.get("color_scheme", "default")
        manager = Adw.StyleManager.get_default()
        if scheme == "light":
            manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        elif scheme == "dark":
            manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

    def do_activate(self) -> None:
        load_app_css()
        if self.win is not None:
            self.win.present()
            return
        self.win = GatorWindow(self, self.settings, self.save_dir)
        self.win.connect("close-request", self._on_close_request)
        self.win.show_checking_croc()
        self.win.present()
        check_croc_available(self._on_croc_check_complete)

    def _on_croc_check_complete(self, available: bool) -> None:
        if self.win is None:
            return
        if not available:
            self.win.show_croc_missing(on_retry=self._retry_croc_check)
        else:
            self._setup_main_ui()
        self.win.present()

    def _retry_croc_check(self) -> None:
        if self.win is None:
            return
        self.win.show_checking_croc()
        check_croc_available(self._on_croc_check_complete)

    def _setup_main_ui(self) -> None:
        assert self.win is not None
        self.send_page, self.receive_page = self.win.build_main_ui()
        self._wire_send_page()
        self._wire_receive_page()
        self._setup_window_actions()
        if not HAS_QR_SCAN:
            self.receive_page.set_scan_enabled(False, _(QR_SCAN_HINT))
        self.send_page.refresh_file_list(
            self.send_page.selected_files, self.send_page.excluded_items, self.send_text
        )

    def _setup_window_actions(self) -> None:
        if self.win is None:
            return

        def add_win_action(name: str, callback: Any, accels: list[str]) -> None:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.win.add_action(action)
            self.set_accels_for_action(f"win.{name}", accels)

        add_win_action("start", lambda *_: self._on_shortcut_start(), ["<Ctrl>Return"])
        add_win_action("cancel", lambda *_: self._on_shortcut_cancel(), ["Escape"])
        add_win_action(
            "copy-code", lambda *_: self._on_copy_code(None), ["<Ctrl><Shift>c"]
        )
        add_win_action(
            "paste-code", lambda *_: self._on_shortcut_paste(), ["<Ctrl><Shift>v"]
        )
        add_win_action(
            "add-files", lambda *_: self._on_shortcut_add_files(), ["<Ctrl>o"]
        )
        add_win_action(
            "tab-send", lambda *_: self.win.set_visible_tab("send"), ["<Alt>1"]
        )
        add_win_action(
            "tab-receive", lambda *_: self.win.set_visible_tab("receive"), ["<Alt>2"]
        )

    def _on_shortcut_start(self) -> None:
        if self.win is None:
            return
        if self.win.visible_tab() == "receive":
            self._on_start_receive(self.receive_page)
        else:
            self._on_start_send(self.send_page)

    def _on_shortcut_cancel(self) -> None:
        if self._send_transfer is not None:
            self._send_transfer.cancel()
        elif self._receive_transfer is not None:
            self._receive_transfer.cancel()

    def _wire_send_page(self) -> None:
        p = self.send_page
        p.connect("add-files", self._on_add_files)
        p.connect("add-folder", self._on_add_folder)
        p.connect("add-text", self._on_add_text)
        p.connect("clear-all", self._on_clear_all)
        p.connect("start-send", self._on_start_send)
        p.connect("cancel-send", self._on_cancel_send)
        p.connect("copy-code", self._on_copy_code)
        p.connect("files-dropped", self._on_files_dropped)
        p.connect("remove-item", self._on_remove_item)
        p.connect("remove-text", self._on_remove_text)

    def _wire_receive_page(self) -> None:
        p = self.receive_page
        p.connect("start-receive", self._on_start_receive)
        p.connect("cancel-receive", self._on_cancel_receive)
        p.connect("paste-clipboard", self._on_paste_clipboard)
        p.connect("scan-qr", self._on_scan_qr_image)
        p.connect("change-folder", self._on_change_folder)
        p.connect("open-received-folder", self._on_open_received_folder)
        p.connect("qr-dropped", self._on_receive_qr_drop)

    def add_toast(self, title: str) -> None:
        if self.win:
            self.win.add_toast(title)

    def _notify(self, title: str, body: str = "") -> None:
        if self.win is not None and self.win.is_active():
            self.add_toast(title)
            return
        notification = Gio.Notification.new(title)
        if body:
            notification.set_body(body)
        self.send_notification("gator-transfer", notification)

    def _error_text(self, kind: str | None) -> str:
        if kind and kind in _ERROR_COPY:
            return _ERROR_COPY[kind]
        return _ERROR_COPY[ERROR_FAILED]

    def _set_busy_title(self, busy: bool, label: str = "") -> None:
        if self.win is None:
            return
        self.win.set_title(f"{label} — {APP_NAME}" if busy and label else APP_NAME)

    def _set_inhibit(self, inhibit: bool) -> None:
        if inhibit and not self._inhibit_cookie:
            flags = (
                Gtk.ApplicationInhibitFlags.LOGOUT | Gtk.ApplicationInhibitFlags.SUSPEND
            )
            self._inhibit_cookie = self.inhibit(
                self.win, flags, _("A file transfer is in progress")
            )
        elif not inhibit and self._inhibit_cookie:
            self.uninhibit(self._inhibit_cookie)
            self._inhibit_cookie = 0

    def _transfer_active(self) -> bool:
        return self._send_transfer is not None or self._receive_transfer is not None

    def _on_quit_action(self, *_args: Any) -> None:
        if self.win is not None and self._transfer_active():
            self._confirm_quit()
            return
        self._cancel_all_transfers()
        self.quit()

    def _on_close_request(self, _win: Gtk.Window) -> bool:
        if self._transfer_active():
            self._confirm_quit()
            return True
        self._cancel_all_transfers()
        return False

    def _confirm_quit(self) -> None:
        dialog = Adw.AlertDialog(
            heading=_("Cancel transfer and quit?"),
            body=_("A file transfer is still in progress."),
        )
        dialog.add_response("stay", _("Keep transferring"))
        dialog.add_response("quit", _("Quit"))
        dialog.set_response_appearance("quit", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("stay")
        dialog.set_close_response("stay")

        def on_response(_d: Adw.AlertDialog, response: str) -> None:
            if response == "quit":
                self._cancel_all_transfers()
                self.quit()

        dialog.connect("response", on_response)
        dialog.present(self.win)

    def _cancel_all_transfers(self) -> None:
        if self._send_transfer is not None:
            self._send_transfer.cancel()
        if self._receive_transfer is not None:
            self._receive_transfer.cancel()
        self._set_inhibit(False)

    def show_preferences(self, *_args: Any) -> None:
        self._prefs_dialog = PreferencesDialog(
            self.settings,
            self.save_dir,
            on_color_scheme_changed=lambda _s: self.apply_color_scheme(),
            on_show_qr_changed=lambda v: (
                self.send_page.set_qr_visible(v) if self.send_page else None
            ),
            on_show_shell_changed=self._on_shell_output_changed,
            on_change_default_folder=self._on_change_default_save_folder,
            on_reset=self._on_reset_settings,
        )
        self._prefs_dialog.present(self.win)

    def show_shortcuts(self, *_args: Any) -> None:
        try:
            if not hasattr(Adw, "ShortcutsDialog"):
                raise AttributeError("ShortcutsDialog")
            dialog = Adw.ShortcutsDialog()
            section = Adw.ShortcutsSection(title=APP_NAME)
            for title, accel in [
                (_("Quit"), "<Ctrl>q"),
                (_("Preferences"), "<Ctrl>comma"),
                (_("Start transfer"), "<Ctrl>Return"),
                (_("Cancel transfer"), "Escape"),
                (_("Add files"), "<Ctrl>o"),
                (_("Copy code"), "<Ctrl><Shift>c"),
                (_("Paste code"), "<Ctrl><Shift>v"),
                (_("Send tab"), "<Alt>1"),
                (_("Receive tab"), "<Alt>2"),
            ]:
                section.add(Adw.ShortcutsItem(title=title, accelerator=accel))
            dialog.add(section)
            dialog.present(self.win)
        except (AttributeError, TypeError):
            self.add_toast(
                _(
                    "Ctrl+Q quit · Ctrl+, preferences · Ctrl+Enter start · "
                    "Esc cancel · Alt+1 send · Alt+2 receive"
                )
            )

    def _on_shell_output_changed(self, visible: bool) -> None:
        if self.send_page:
            self.send_page.set_shell_output_visible(visible)
        if self.receive_page:
            self.receive_page.set_shell_output_visible(visible)

    def _on_reset_settings(self) -> None:
        self.settings.clear()
        self.settings.save()
        self.apply_color_scheme()
        self.save_dir = get_default_save_dir()
        if self.win:
            self.win.update_save_dir(self.save_dir)
        if self._prefs_dialog:
            self._prefs_dialog.update_save_dir_subtitle(self.save_dir)
        self._on_shell_output_changed(self.settings.get("show_shell_output", False))
        if self.send_page:
            self.send_page.set_qr_visible(self.settings.get("show_qr_image", True))
        self.add_toast(_("Settings reset to default"))

    def show_about(self, *_args: Any) -> None:
        comments = _(
            "Modern GTK4/Libadwaita frontend for croc – "
            "secure file transfer made beautiful"
        )
        debug = (
            f"Gator {APP_VERSION}\n"
            f"QR generate: {HAS_QR_GEN}\n"
            f"QR scan: {HAS_QR_SCAN}\n"
        )
        kwargs: dict[str, Any] = {
            "application_name": APP_NAME,
            "version": APP_VERSION,
            "developer_name": "Gator Contributors",
            "website": "https://github.com/isyourbrainfoss/gator",
            "issue_url": "https://github.com/isyourbrainfoss/gator/issues",
            "copyright": "© 2026 Gator Contributors",
            "license_type": Gtk.License.GPL_3_0,
            "comments": comments,
            "application_icon": APP_ID,
            "developers": ["Gator Contributors"],
            "designers": ["Gator Contributors"],
        }
        if hasattr(Adw, "AboutDialog"):
            about = Adw.AboutDialog(**kwargs)
            if hasattr(about, "set_debug_info"):
                about.set_debug_info(debug)
            about.present(self.win)
            return
        about = Adw.AboutWindow(**kwargs)
        about.set_transient_for(self.win)
        about.present()

    def _update_file_list(self) -> None:
        if self.send_page:
            self.send_page.refresh_file_list(
                self.send_page.selected_files,
                self.send_page.excluded_items,
                self.send_text,
            )

    def _on_add_files(self, _page: Any, included: bool) -> None:
        if self._send_transfer is not None:
            return
        title = _("Select files to add") if included else _("Select files to exclude")
        dialog = Gtk.FileDialog(title=title)

        def cb(_d: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            try:
                files = dialog.open_multiple_finish(res)
                target = (
                    self.send_page.selected_files
                    if included
                    else self.send_page.excluded_items
                )
                added = 0
                for f in files:
                    p = f.get_path()
                    if p and p not in target:
                        target.append(p)
                        added += 1
                    elif p is None:
                        self.add_toast(
                            _(
                                "Gator can’t access that file. Use Add Files, or copy it to Downloads."
                            )
                        )
                self._update_file_list()
                if added == 0 and files.get_n_items() == 0:
                    pass
            except GLib.GError as e:
                if not _is_dismissed(e):
                    self.add_toast(_("Couldn’t open the file picker."))

        dialog.open_multiple(self.win, None, cb)

    def _on_add_folder(self, _page: Any, included: bool) -> None:
        if self._send_transfer is not None:
            return
        title = _("Select folder to add") if included else _("Select folder to exclude")
        dialog = Gtk.FileDialog(title=title)

        def cb(_d: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            try:
                folder = dialog.select_folder_finish(res)
                if folder:
                    p = folder.get_path()
                    target = (
                        self.send_page.selected_files
                        if included
                        else self.send_page.excluded_items
                    )
                    if p and p not in target:
                        target.append(p)
                    elif p is None:
                        self.add_toast(
                            _(
                                "Gator can’t access that folder. Copy it to Downloads or Documents."
                            )
                        )
                    self._update_file_list()
            except GLib.GError as e:
                if not _is_dismissed(e):
                    self.add_toast(_("Couldn’t open the folder picker."))

        dialog.select_folder(self.win, None, cb)

    def _on_add_text(self, _page: Any) -> None:
        def accept(text: str) -> None:
            self.send_text = text
            self._update_file_list()

        show_add_text_dialog(self.win, accept, initial=self.send_text)

    def _on_clear_all(self, _page: Any) -> None:
        if self._send_transfer is not None:
            return
        self.send_page.selected_files.clear()
        self.send_page.excluded_items.clear()
        self.send_text = ""
        self.send_page._sent_paths.clear()
        self.send_page._text_sent = False
        self._update_file_list()

    def _on_remove_item(self, _page: Any, path: str, included: bool) -> None:
        target = (
            self.send_page.selected_files if included else self.send_page.excluded_items
        )
        if path in target:
            target.remove(path)
        self._update_file_list()

    def _on_remove_text(self, _page: Any) -> None:
        self.send_text = ""
        self._update_file_list()

    def _on_files_dropped(self, _page: Any, file_list: Gdk.FileList) -> None:
        if self._send_transfer is not None:
            return
        added = 0
        skipped = 0
        for f in file_list.get_files():
            p = f.get_path()
            if p and p not in self.send_page.selected_files:
                self.send_page.selected_files.append(p)
                added += 1
            elif p is None:
                skipped += 1
        self._update_file_list()
        if skipped and not added:
            self.add_toast(
                _(
                    "Gator can’t access that file. Use Add Files, or copy it to Downloads."
                )
            )
        elif added == 0:
            self.add_toast(_("Nothing usable was dropped"))

    def _on_start_send(self, _page: Any) -> None:
        if self._send_transfer is not None:
            return
        if self._receive_transfer is not None:
            self.add_toast(_("Finish the current receive first"))
            return
        if not self.send_page.selected_files and not self.send_text:
            return
        if self.send_page.selected_files and self.send_text:
            self.add_toast(_("Sending files; text is omitted when files are selected."))
        self._clear_reset_source("send")
        self.send_page.set_transfer_active(True, _("Preparing"))
        self._set_busy_title(True, _("Sending"))
        self._set_inhibit(True)
        self._send_transfer = CrocSendTransfer(
            settings=self.settings,
            files=self.send_page.selected_files,
            excluded=self.send_page.excluded_items,
            text=self.send_text,
            on_log=self.send_page.append_log,
            on_code=self._show_code_and_qr,
            on_finished=self._on_send_finished,
            on_progress=self.send_page.set_progress,
            on_status=self.send_page.set_transfer_phase,
        )
        self._send_transfer.start()

    def _show_code_and_qr(self, code: str) -> None:
        self.send_page.show_code(code)
        if self.win:
            self.win.get_clipboard().set(code)
            self.add_toast(_("Code copied to clipboard"))
        if HAS_QR_GEN and self.settings.get("show_qr_image", True):
            fg, bg = qr_colors_for_widget(self.send_page)
            tex = generate_qr_texture(code, fg, bg)
            if tex:
                self.send_page.set_qr_paintable(tex)
            else:
                self.send_page.set_qr_paintable(None)
                self.add_toast(
                    _(
                        "Couldn’t create a QR code. You can still copy the transfer code."
                    )
                )
        else:
            self.send_page.set_qr_paintable(None)

    def _on_send_finished(self) -> None:
        t = self._send_transfer
        canceled = t.canceled if t else False
        success = bool(t and t.success)
        kind = t.error_kind if t else None
        sent_paths = list(self.send_page.selected_files)
        text_sent = bool(self.send_text) and not sent_paths
        self._send_transfer = None
        self._set_inhibit(self._transfer_active())
        self._set_busy_title(self._transfer_active())
        if canceled:
            self.send_page.append_log(_("Transfer cancelled."))
            self.send_page.show_transfer_complete(canceled=True)
            self._schedule_reset("send", 1500)
        elif success:
            self.send_page.append_log(_("Transfer finished."))
            self.send_page.mark_items_sent(sent_paths, text_sent=text_sent)
            self.send_page.show_transfer_complete(canceled=False, success=True)
            self._notify(_("Transfer finished"), _("Your files were sent."))
            self._schedule_reset("send", 2500)
        else:
            msg = self._error_text(kind)
            self.send_page.append_log(msg, is_error=True)
            self.send_page.show_transfer_complete(
                canceled=False, success=False, message=msg
            )
            self._notify(_("Transfer failed"), msg)
            self._schedule_reset("send", 4000, hide_code=True)

    def _schedule_reset(
        self, side: str, delay_ms: int, *, hide_code: bool = True
    ) -> None:
        self._clear_reset_source(side)

        def reset() -> bool:
            if side == "send":
                self._reset_send_source = 0
                if self.send_page:
                    self.send_page.set_transfer_active(False)
                    if hide_code:
                        self.send_page.hide_code()
            else:
                self._reset_receive_source = 0
                if self.receive_page:
                    self.receive_page.set_transfer_active(False)
            return False

        source = GLib.timeout_add(delay_ms, reset)
        if side == "send":
            self._reset_send_source = source
        else:
            self._reset_receive_source = source

    def _clear_reset_source(self, side: str) -> None:
        if side == "send" and self._reset_send_source:
            GLib.source_remove(self._reset_send_source)
            self._reset_send_source = 0
        elif side == "receive" and self._reset_receive_source:
            GLib.source_remove(self._reset_receive_source)
            self._reset_receive_source = 0

    def _on_cancel_send(self, _page: Any) -> None:
        if self._send_transfer is not None:
            self._send_transfer.cancel()

    def _on_shortcut_add_files(self) -> None:
        if self._send_transfer is not None:
            return
        self._on_add_files(None, True)

    def _on_shortcut_paste(self) -> None:
        if self.win is None or self.win.visible_tab() != "receive":
            return
        if self._receive_transfer is not None:
            return
        self._on_paste_clipboard(None)

    def _on_copy_code(self, _page: Any) -> None:
        if not self.send_page:
            return
        code = self.send_page.get_code()
        if code and self.win:
            self.win.get_clipboard().set(code)
            self.add_toast(_("Code copied to clipboard"))

    def _on_start_receive(self, _page: Any) -> None:
        if self._receive_transfer is not None:
            return
        if self._send_transfer is not None:
            self.add_toast(_("Finish the current send first"))
            return
        code = normalize_croc_code(self.receive_page.get_code())
        if not code:
            self.receive_page.mark_code_error()
            self.add_toast(_("Enter a transfer code to start receiving."))
            return
        self.receive_page.set_code(code)
        self._clear_reset_source("receive")
        self.receive_page.set_transfer_active(True)
        self._set_busy_title(True, _("Receiving"))
        self._set_inhibit(True)
        save_dir = self.receive_page.get_save_dir()
        self._receive_transfer = CrocReceiveTransfer(
            settings=self.settings,
            code=code,
            save_dir=save_dir,
            on_log=self.receive_page.append_log,
            on_text_received=self._show_received_text,
            on_transfer_complete=self._show_transfer_complete_popup,
            on_finished=self._on_receive_finished,
            on_progress=self.receive_page.set_progress,
            on_status=self.receive_page.set_transfer_phase,
        )
        self._receive_transfer.start()

    def _on_receive_finished(self) -> None:
        t = self._receive_transfer
        canceled = t.canceled if t else False
        success = bool(t and t.success)
        kind = t.error_kind if t else None
        self._receive_transfer = None
        self._set_inhibit(self._transfer_active())
        self._set_busy_title(self._transfer_active())
        if canceled:
            self.receive_page.append_log(_("Transfer cancelled."))
            self.receive_page.show_transfer_complete(canceled=True)
            self._schedule_reset("receive", 1500)
        elif success:
            self.receive_page.append_log(_("Transfer finished."))
            got_files = bool(t and getattr(t, "received_files", False))
            self.receive_page.show_transfer_complete(
                canceled=False, success=True, files=got_files
            )
            if got_files:
                self._notify(_("Transfer finished"), _("Files saved."))
            else:
                self._notify(_("Transfer finished"), _("Text received."))
            self._schedule_reset("receive", 2500)
        else:
            msg = self._error_text(kind)
            if kind == ERROR_INVALID_CODE:
                self.receive_page.mark_code_error()
            self.receive_page.append_log(msg)
            self.receive_page.show_transfer_complete(
                canceled=False, success=False, message=msg, files=False
            )
            self._notify(_("Transfer failed"), msg)
            self._schedule_reset("receive", 4000)

    def _on_cancel_receive(self, _page: Any) -> None:
        if self._receive_transfer is not None:
            self._receive_transfer.cancel()

    def _open_receive_folder(self) -> None:
        try:
            uri = Path(self.receive_page.get_save_dir()).resolve().as_uri()
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except Exception as e:
            logger.warning("Failed to open save folder: %s", e)
            self.add_toast(_("Couldn’t open the folder."))

    def _on_open_received_folder(self, _page: Any) -> None:
        self._open_receive_folder()

    def _show_transfer_complete_popup(self) -> None:
        if self.win is None or self.win.is_active():
            toast = Adw.Toast(title=_("Files received"))
            toast.set_button_label(_("Open Folder"))
            toast.connect("button-clicked", lambda *_: self._open_receive_folder())
            if self.win:
                self.win.toast_overlay.add_toast(toast)
            return
        self._notify(_("Files received"), _("Saved to the receive folder."))

    def _show_received_text(self, text: str) -> None:
        show_received_text_dialog(
            self.win,
            text,
            on_copied=lambda: self.add_toast(_("Text copied to clipboard")),
        )

    def _on_paste_clipboard(self, _page: Any) -> None:
        if self.win is None or self.receive_page is None:
            return
        clipboard = self.win.get_clipboard()

        def cb(_c: Gdk.Clipboard, res: Gio.AsyncResult) -> None:
            try:
                value = clipboard.read_text_finish(res)
                if value:
                    self.receive_page.set_code(normalize_croc_code(value))
                    self.add_toast(_("Pasted from clipboard"))
                else:
                    self.add_toast(_("Clipboard is empty"))
            except GLib.GError as e:
                logger.warning("Clipboard read failed: %s", e)
                self.add_toast(_("Couldn’t read the clipboard"))

        clipboard.read_text_async(None, cb)

    def _on_scan_qr_image(self, _page: Any) -> None:
        if not HAS_QR_SCAN:
            self.add_toast(_(QR_SCAN_HINT))
            return
        dialog = Gtk.FileDialog(title=_("Select QR code image"))
        filt = Gtk.FileFilter()
        filt.set_name(_("Images"))
        for mime in ["image/png", "image/jpeg", "image/webp", "image/bmp", "image/gif"]:
            filt.add_mime_type(mime)
        dialog.set_default_filter(filt)

        def cb(_d: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            try:
                file = dialog.open_finish(res)
                path = file.get_path()
                if not path:
                    self.add_toast(_("Couldn’t read that image."))
                    return
                code = scan_qr_from_image_path(path)
                if code:
                    self.receive_page.set_code(normalize_croc_code(code))
                    self.add_toast(_("QR code applied"))
                else:
                    self.add_toast(_("No QR code found in this image"))
            except GLib.GError as e:
                if not _is_dismissed(e):
                    self.add_toast(_("Couldn’t open the file picker."))
            except Exception as e:
                logger.warning("QR scan failed: %s", e)
                self.add_toast(_("Couldn’t read that image."))

        dialog.open(self.win, None, cb)

    def _on_change_folder(self, _page: Any) -> None:
        dialog = Gtk.FileDialog(title=_("Choose save folder"))
        dialog.set_initial_folder(
            Gio.File.new_for_path(self.receive_page.get_save_dir())
        )

        def cb(_d: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            try:
                f = dialog.select_folder_finish(res)
                path = f.get_path()
                if not path:
                    self.add_toast(
                        _(
                            "Gator can’t use that folder. Choose Downloads, Documents, or Pictures."
                        )
                    )
                    return
                self.receive_page.set_save_dir_subtitle(path)
                self.save_dir = path
                self.settings["save_dir"] = path
                self.settings.save()
            except GLib.GError as e:
                if not _is_dismissed(e):
                    self.add_toast(_("Couldn’t open the folder picker."))

        dialog.select_folder(self.win, None, cb)

    def _on_change_default_save_folder(self) -> None:
        dialog = Gtk.FileDialog(title=_("Choose default save folder"))
        dialog.set_initial_folder(Gio.File.new_for_path(self.save_dir))

        def cb(_d: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            try:
                f = dialog.select_folder_finish(res)
                if f:
                    new = f.get_path()
                    if not new:
                        self.add_toast(
                            _(
                                "Gator can’t use that folder. Choose Downloads, Documents, or Pictures."
                            )
                        )
                        return
                    self.save_dir = new
                    self.settings["save_dir"] = new
                    self.settings.save()
                    self.win.update_save_dir(new)
                    if self._prefs_dialog:
                        self._prefs_dialog.update_save_dir_subtitle(new)
            except GLib.GError as e:
                if not _is_dismissed(e):
                    self.add_toast(_("Couldn’t open the folder picker."))

        dialog.select_folder(self.win, None, cb)

    def _on_receive_qr_drop(self, _page: Any, file_list: Gdk.FileList) -> None:
        if not HAS_QR_SCAN:
            self.add_toast(_(QR_SCAN_HINT))
            return
        found = None
        saw_image = False
        for f in file_list.get_files():
            p = f.get_path()
            if not p:
                continue
            info = Gio.File.new_for_path(p).query_info(
                "standard::content-type", Gio.FileQueryInfoFlags.NONE, None
            )
            ctype = info.get_content_type() or ""
            if not ctype.startswith("image/"):
                continue
            saw_image = True
            code = scan_qr_from_image_path(p)
            if code:
                found = code
                break
        if found:
            self.receive_page.set_code(normalize_croc_code(found))
            self.add_toast(_("QR code applied"))
        elif saw_image:
            self.add_toast(_("No QR code found in this image"))
        else:
            self.add_toast(_("Drop a QR image to fill the transfer code"))


def _is_dismissed(error: GLib.GError) -> bool:
    message = (error.message or "").lower()
    return "dismissed" in message or "cancelled" in message or "canceled" in message


def main() -> None:
    log_level = logging.WARNING
    if os.environ.get("GATOR_LOG", "").lower() in ("1", "true", "debug", "yes"):
        log_level = logging.DEBUG
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s %(name)s: %(message)s",
    )
    GatorApp().run(sys.argv)


if __name__ == "__main__":
    main()
