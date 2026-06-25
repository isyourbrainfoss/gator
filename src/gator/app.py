#!/usr/bin/env python3
# Gator – Modern adaptive GTK4/Libadwaita frontend for croc
# © 2026 Gator Contributors – GPL-3.0-or-later
"""Gator application entry and transfer controller."""

from __future__ import annotations

import logging
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
from .qr import HAS_QR_GEN, HAS_QR_SCAN, generate_qr_texture, scan_qr_from_image_path
from .settings import (
    APP_ID,
    APP_NAME,
    APP_VERSION,
    GatorSettings,
    get_default_save_dir,
)
from .theme import qr_colors_for_widget
from .transfer import CrocReceiveTransfer, CrocSendTransfer
from .window import GatorWindow, check_croc_available

logger = logging.getLogger(__name__)


class GatorApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        GLib.set_application_name(APP_NAME)
        GLib.set_prgname("gator")

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

        self.create_action("quit", lambda *_: self.quit(), ["<Ctrl>q"])
        self.create_action("about", self.show_about)
        self.create_action("preferences", self.show_preferences)

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
        if self.win is not None:
            self.win.present()
            return
        self.win = GatorWindow(self, self.settings, self.save_dir)
        check_croc_available(self._on_croc_check_complete)

    def _on_croc_check_complete(self, available: bool) -> None:
        if self.win is None:
            return
        if not available:
            self.win.show_croc_missing()
        else:
            self._setup_main_ui()
        self.win.present()

    def _setup_main_ui(self) -> None:
        assert self.win is not None
        self.send_page, self.receive_page = self.win.build_main_ui()
        self._wire_send_page()
        self._wire_receive_page()
        if not HAS_QR_SCAN:
            self.receive_page.set_scan_enabled(
                False, _("Requires libzbar (QR scan from image)")
            )
        self.send_page.refresh_file_list([], [], "")

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
        p.connect("qr-dropped", self._on_receive_qr_drop)

    def add_toast(self, title: str) -> None:
        if self.win:
            self.win.add_toast(title)

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
        about = Adw.AboutDialog(
            application_name=APP_NAME,
            version=APP_VERSION,
            developer_name="Gator Contributors",
            website="https://github.com/isyourbrainfoss/gator",
            issue_url="https://github.com/isyourbrainfoss/gator/issues",
            copyright="© 2026 Gator Contributors",
            license_type=Gtk.License.GPL_3_0,
            comments=_(
                "Modern GTK4/Libadwaita frontend for croc – "
                "secure file transfer made beautiful"
            ),
            application_icon=APP_ID,
            developers=["Gator Contributors"],
            designers=["Gator Contributors"],
        )
        about.present(self.win)

    def _update_file_list(self) -> None:
        if self.send_page:
            self.send_page.refresh_file_list(
                self.send_page.selected_files,
                self.send_page.excluded_items,
                self.send_text,
            )

    def _on_add_files(self, _page, included: bool) -> None:
        dialog = Gtk.FileDialog(
            title=_("Select Files to ") + (_("Add") if included else _("Exclude"))
        )

        def cb(_d, res):
            try:
                files = dialog.open_multiple_finish(res)
                target = (
                    self.send_page.selected_files
                    if included
                    else self.send_page.excluded_items
                )
                for f in files:
                    p = f.get_path()
                    if p and p not in target:
                        target.append(p)
                self._update_file_list()
            except GLib.GError:
                pass

        dialog.open_multiple(self.win, None, cb)

    def _on_add_folder(self, _page, included: bool) -> None:
        dialog = Gtk.FileDialog(
            title=_("Select Folder to ") + (_("Add") if included else _("Exclude"))
        )

        def cb(_d, res):
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
                    self._update_file_list()
            except GLib.GError:
                pass

        dialog.select_folder(self.win, None, cb)

    def _on_add_text(self, _page) -> None:
        def accept(text: str) -> None:
            self.send_text = text
            self._update_file_list()

        show_add_text_dialog(self.win, accept)

    def _on_clear_all(self, _page) -> None:
        self.send_page.selected_files.clear()
        self.send_page.excluded_items.clear()
        self.send_text = ""
        self.send_page._sent_paths.clear()
        self.send_page._text_sent = False
        self._update_file_list()

    def _on_remove_item(self, _page, path: str, included: bool) -> None:
        target = (
            self.send_page.selected_files if included else self.send_page.excluded_items
        )
        if path in target:
            target.remove(path)
        self._update_file_list()

    def _on_remove_text(self, _page) -> None:
        self.send_text = ""
        self._update_file_list()

    def _on_files_dropped(self, _page, file_list: Gdk.FileList) -> None:
        for f in file_list.get_files():
            p = f.get_path()
            if p and p not in self.send_page.selected_files:
                self.send_page.selected_files.append(p)
        self._update_file_list()

    def _on_start_send(self, _page) -> None:
        if not self.send_page.selected_files and not self.send_text:
            return
        self.send_page.set_transfer_active(True, _("Preparing"))
        self._send_transfer = CrocSendTransfer(
            settings=self.settings,
            files=self.send_page.selected_files,
            excluded=self.send_page.excluded_items,
            text=self.send_text,
            on_log=self.send_page.append_log,
            on_code=self._show_code_and_qr,
            on_finished=self._on_send_finished,
            on_progress=self.send_page.set_progress,
        )
        self._send_transfer.start()

    def _show_code_and_qr(self, code: str) -> None:
        self.send_page.show_code(code)
        if HAS_QR_GEN:
            fg, bg = qr_colors_for_widget(self.send_page)
            tex = generate_qr_texture(code, fg, bg)
            if tex:
                self.send_page.set_qr_paintable(tex)
        self.send_page.set_qr_visible(self.settings.get("show_qr_image", True))

    def _on_send_finished(self) -> None:
        canceled = self._send_transfer.canceled if self._send_transfer else False
        sent_paths = list(self.send_page.selected_files)
        text_sent = bool(self.send_text)
        msg = _("Transfer cancelled.") if canceled else _("Transfer finished.")
        self.send_page.append_log(msg)
        self._send_transfer = None
        self.send_text = ""
        if canceled:
            self.send_page.show_transfer_complete(canceled=True)
            GLib.timeout_add(1500, self._reset_send_controls)
        else:
            self.send_page.mark_items_sent(sent_paths, text_sent=text_sent)
            self.send_page.show_transfer_complete(canceled=False)
            self.add_toast(_("Transfer finished"))
            GLib.timeout_add(2500, self._reset_send_controls)

    def _reset_send_controls(self) -> bool:
        self.send_page.set_transfer_active(False)
        self.send_page.hide_code()
        return False

    def _on_cancel_send(self, _page) -> None:
        if self._send_transfer is not None:
            self._send_transfer.cancel()

    def _on_copy_code(self, _page) -> None:
        code = self.send_page.get_code()
        if code:
            self.win.get_clipboard().set(code)
            self.add_toast(_("Code copied to clipboard"))

    def _on_start_receive(self, _page) -> None:
        code = self.receive_page.get_code()
        if not code:
            self.add_toast(_("Please enter a transfer code"))
            return
        self.receive_page.set_transfer_active(True)
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
        )
        self._receive_transfer.start()

    def _on_receive_finished(self) -> None:
        canceled = self._receive_transfer.canceled if self._receive_transfer else False
        self.receive_page.set_transfer_active(False)
        msg = _("Transfer cancelled.") if canceled else _("Transfer finished.")
        self.receive_page.append_log(msg)
        self._receive_transfer = None

    def _on_cancel_receive(self, _page) -> None:
        if self._receive_transfer is not None:
            self._receive_transfer.cancel()

    def _show_transfer_complete_popup(self) -> None:
        dialog = Adw.AlertDialog(
            heading=_("Transfer Complete"),
            body=_("The files have been received."),
        )
        dialog.add_response("close", _("Close"))
        dialog.add_response("open", _("Open Folder"))
        dialog.set_response_appearance("open", Adw.ResponseAppearance.SUGGESTED)

        def on_response(_d, response: str) -> None:
            if response == "open":
                try:
                    uri = Path(self.receive_page.get_save_dir()).resolve().as_uri()
                    Gio.AppInfo.launch_default_for_uri(uri, None)
                except Exception as e:
                    logger.warning("Failed to open save folder: %s", e)
                    self.add_toast(_("Failed to open folder"))

        dialog.connect("response", on_response)
        dialog.present(self.win)

    def _show_received_text(self, text: str) -> None:
        show_received_text_dialog(
            self.win,
            text,
            on_copied=lambda: self.add_toast(_("Text copied to clipboard")),
        )

    def _on_paste_clipboard(self, _page) -> None:
        clipboard = self.win.get_clipboard()

        def cb(_c, res):
            try:
                value = clipboard.read_text_finish(res)
                if value:
                    self.receive_page.set_code(value.strip())
                    self.add_toast(_("Pasted from clipboard"))
            except GLib.GError as e:
                logger.warning("Clipboard read failed: %s", e)
                self.add_toast(_("Could not read clipboard"))

        clipboard.read_text_async(None, cb)

    def _on_scan_qr_image(self, _page) -> None:
        dialog = Gtk.FileDialog(title=_("Select QR Code Image"))
        filt = Gtk.FileFilter()
        filt.set_name(_("Images"))
        for mime in ["image/png", "image/jpeg", "image/webp", "image/bmp"]:
            filt.add_mime_type(mime)
        dialog.set_default_filter(filt)

        def cb(_d, res):
            try:
                file = dialog.open_finish(res)
                code = scan_qr_from_image_path(file.get_path())
                if code:
                    self.receive_page.set_code(code)
                    self.add_toast(_("Scanned: {}").format(code))
                else:
                    self.add_toast(_("No QR code found in image"))
            except GLib.GError:
                pass
            except Exception as e:
                logger.warning("QR scan failed: %s", e)
                self.add_toast(_("QR scan failed"))

        dialog.open(self.win, None, cb)

    def _on_change_folder(self, _page) -> None:
        dialog = Gtk.FileDialog(title=_("Choose Save Folder"))
        dialog.set_initial_folder(
            Gio.File.new_for_path(self.receive_page.get_save_dir())
        )

        def cb(_d, res):
            try:
                f = dialog.select_folder_finish(res)
                path = f.get_path()
                self.receive_page.set_save_dir_subtitle(path)
            except GLib.GError:
                pass

        dialog.select_folder(self.win, None, cb)

    def _on_change_default_save_folder(self) -> None:
        dialog = Gtk.FileDialog(title=_("Choose Default Save Folder"))
        dialog.set_initial_folder(Gio.File.new_for_path(self.save_dir))

        def cb(_d, res):
            try:
                f = dialog.select_folder_finish(res)
                if f:
                    new = f.get_path()
                    self.save_dir = new
                    self.settings["save_dir"] = new
                    self.settings.save()
                    self.win.update_save_dir(new)
                    if self._prefs_dialog:
                        self._prefs_dialog.update_save_dir_subtitle(new)
            except GLib.GError:
                pass

        dialog.select_folder(self.win, None, cb)

    def _on_receive_qr_drop(self, _page, file_list: Gdk.FileList) -> None:
        if not HAS_QR_SCAN:
            self.add_toast(_("pyzbar not installed"))
            return
        for f in file_list.get_files():
            p = f.get_path()
            if p:
                code = scan_qr_from_image_path(p)
                if code:
                    self.receive_page.set_code(code)
                    self.add_toast(_("Scanned from drop: {}").format(code))
                    return
                self.add_toast(_("No QR code found in dropped image"))


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    GatorApp().run(sys.argv)


if __name__ == "__main__":
    main()
