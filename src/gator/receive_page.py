"""receive_page.py – Receive tab widget with GObject signals."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GObject, Gtk, Pango

from .a11y import set_a11y_label
from .i18n import _
from .theme import (
    get_theme_rgba,
    make_success_icon,
    resolve_success_icon_name,
    rgba_to_hex,
)

if TYPE_CHECKING:
    from .settings import GatorSettings

_MAX_LOG_LINES = 400


class ReceivePage(Gtk.Box):
    """Receive page: code entry, folder picker, transfer controls."""

    __gsignals__ = {
        "start-receive": (GObject.SignalFlags.RUN_LAST, None, ()),
        "cancel-receive": (GObject.SignalFlags.RUN_LAST, None, ()),
        "paste-clipboard": (GObject.SignalFlags.RUN_LAST, None, ()),
        "scan-qr": (GObject.SignalFlags.RUN_LAST, None, ()),
        "change-folder": (GObject.SignalFlags.RUN_LAST, None, ()),
        "open-received-folder": (GObject.SignalFlags.RUN_LAST, None, ()),
        "qr-dropped": (GObject.SignalFlags.RUN_LAST, bool, (object,)),
    }

    def __init__(self, settings: GatorSettings, save_dir: str) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.settings = settings
        self._save_dir = save_dir
        self._error_tag_applied = False
        self._receive_success = False
        self._transfer_active = False
        self._scan_enabled = True
        self._build_content()

    def _build_content(self) -> None:
        outer = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_start=12,
            margin_end=12,
            margin_top=12,
            margin_bottom=12,
            vexpand=True,
        )
        clamp = Adw.Clamp(maximum_size=520, tightening_threshold=400)
        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        self.banner = Adw.Banner()
        self.banner.set_button_label(_("Dismiss"))
        self.banner.connect(
            "button-clicked", lambda *_: self.banner.set_revealed(False)
        )
        form.append(self.banner)

        hint = Gtk.Label(
            label=_(
                "Paste the sender’s code, or drop a QR image. Files are saved below."
            ),
            wrap=True,
            xalign=0,
        )
        hint.add_css_class("dim-label")
        form.append(hint)

        group = Gtk.ListBox()
        group.add_css_class("boxed-list")
        group.set_selection_mode(Gtk.SelectionMode.NONE)

        self.code_entry = Adw.EntryRow(title=_("Transfer code"))
        self.code_entry.set_show_apply_button(False)
        self.code_entry.connect("changed", lambda *_: self._on_code_changed())
        key_ctl = Gtk.EventControllerKey()

        def on_code_key(
            _c: Gtk.EventControllerKey, keyval: int, _code: int, _state: int
        ) -> bool:
            if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                self.emit("start-receive")
                return True
            return False

        key_ctl.connect("key-pressed", on_code_key)
        self.code_entry.add_controller(key_ctl)

        paste_btn = Gtk.Button(icon_name="edit-paste-symbolic")
        paste_btn.add_css_class("flat")
        paste_btn.add_css_class("circular")
        paste_btn.set_tooltip_text(_("Paste from clipboard"))
        set_a11y_label(paste_btn, _("Paste from clipboard"))
        paste_btn.connect("clicked", lambda *_: self.emit("paste-clipboard"))
        self.code_entry.add_suffix(paste_btn)

        self.scan_btn = Gtk.Button(icon_name="image-x-generic-symbolic")
        self.scan_btn.add_css_class("flat")
        self.scan_btn.add_css_class("circular")
        self.scan_btn.set_tooltip_text(_("Choose QR image"))
        set_a11y_label(self.scan_btn, _("Choose QR image"))
        self.scan_btn.connect("clicked", lambda *_: self.emit("scan-qr"))
        self.code_entry.add_suffix(self.scan_btn)
        group.append(self.code_entry)

        self.folder_row = Adw.ActionRow(
            title=_("Save to folder"), subtitle=self._save_dir
        )
        self.folder_icon = Gtk.Image.new_from_icon_name("folder-symbolic")
        self.folder_row.add_prefix(self.folder_icon)
        self.folder_row.set_activatable(True)
        self.folder_row.connect("activated", lambda *_: self.emit("change-folder"))
        folder_actions = Gtk.Box(spacing=6)
        self.open_folder_btn = Gtk.Button(icon_name="folder-open-symbolic")
        self.open_folder_btn.add_css_class("flat")
        self.open_folder_btn.add_css_class("circular")
        self.open_folder_btn.set_tooltip_text(_("Open received folder"))
        set_a11y_label(self.open_folder_btn, _("Open received folder"))
        self.open_folder_btn.set_visible(False)
        self.open_folder_btn.connect(
            "clicked", lambda *_: self.emit("open-received-folder")
        )
        change_btn = Gtk.Button(icon_name="document-open-symbolic")
        change_btn.add_css_class("flat")
        change_btn.add_css_class("circular")
        change_btn.set_tooltip_text(_("Change save folder"))
        set_a11y_label(change_btn, _("Change save folder"))
        change_btn.connect("clicked", lambda *_: self.emit("change-folder"))
        self._change_folder_btn = change_btn
        folder_actions.append(self.open_folder_btn)
        folder_actions.append(change_btn)
        self.folder_row.add_suffix(folder_actions)
        group.append(self.folder_row)
        form.append(group)

        self.receive_btn_box = Gtk.Box()  # kept for set_sensitive during transfer

        controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        controls.set_hexpand(True)

        self.receive_idle_box = Gtk.Box()
        self.receive_idle_box.set_halign(Gtk.Align.CENTER)
        self.receive_start_btn = Gtk.Button()
        self.receive_start_btn.add_css_class("suggested-action")
        self.receive_start_btn.add_css_class("pill")
        receive_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        receive_btn_box.append(Gtk.Image.new_from_icon_name("folder-download-symbolic"))
        receive_btn_box.append(Gtk.Label(label=_("Start Receiving")))
        self.receive_start_btn.set_child(receive_btn_box)
        self.receive_start_btn.connect("clicked", lambda *_: self.emit("start-receive"))
        self.receive_idle_box.append(self.receive_start_btn)

        self.receive_transfer_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=8
        )
        self.receive_transfer_box.set_hexpand(True)
        transfer_row = Gtk.Box(spacing=12)
        transfer_row.set_hexpand(True)
        self.receive_status_box = Gtk.Box()
        self.receive_status_box.set_size_request(32, 32)
        self.receive_spinner = Gtk.Spinner()
        self.receive_spinner.set_valign(Gtk.Align.CENTER)
        self.receive_spinner.set_halign(Gtk.Align.CENTER)
        self.receive_success_icon = make_success_icon(self, size=24)
        self.receive_success_icon.set_visible(False)
        self.receive_error_icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
        self.receive_error_icon.set_pixel_size(24)
        self.receive_error_icon.set_visible(False)
        self.receive_status_box.append(self.receive_spinner)
        self.receive_status_box.append(self.receive_success_icon)
        self.receive_status_box.append(self.receive_error_icon)
        self.receive_transfer_label = Gtk.Label(
            label=_("Waiting for sender"),
            ellipsize=Pango.EllipsizeMode.END,
            hexpand=True,
            halign=Gtk.Align.START,
        )
        self.receive_cancel_btn = Gtk.Button()
        self.receive_cancel_btn.set_icon_name("process-stop-symbolic")
        self.receive_cancel_btn.add_css_class("flat")
        self.receive_cancel_btn.add_css_class("circular")
        self.receive_cancel_btn.set_tooltip_text(_("Cancel"))
        set_a11y_label(self.receive_cancel_btn, _("Cancel"))
        self.receive_cancel_btn.connect(
            "clicked", lambda *_: self.emit("cancel-receive")
        )
        transfer_row.append(self.receive_status_box)
        transfer_row.append(self.receive_transfer_label)
        transfer_row.append(self.receive_cancel_btn)
        self.receive_transfer_box.append(transfer_row)
        self.receive_progress = Gtk.ProgressBar()
        self.receive_progress.set_hexpand(True)
        self.receive_progress.set_visible(False)
        set_a11y_label(self.receive_progress, _("Receive progress"))
        self.receive_transfer_box.append(self.receive_progress)
        self.receive_transfer_box.set_visible(False)

        controls.append(self.receive_idle_box)
        controls.append(self.receive_transfer_box)
        form.append(controls)

        self.log_expander = Gtk.Expander(label=_("Shell output"), margin_top=6)
        self.log_expander.set_visible(self.settings.get("show_shell_output", False))
        self.log_expander.set_expanded(False)
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.add_css_class("card")
        log_scroll.set_min_content_height(120)
        self.receive_log = Gtk.TextView(
            editable=False,
            wrap_mode=Gtk.WrapMode.WORD,
            monospace=True,
            top_margin=12,
            bottom_margin=12,
            left_margin=12,
            right_margin=12,
        )
        set_a11y_label(self.receive_log, _("croc command output"))
        log_scroll.set_child(self.receive_log)
        self.log_expander.set_child(log_scroll)
        form.append(self.log_expander)

        clamp.set_child(form)
        outer.append(clamp)

        scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(outer)
        self.append(scroll)

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        drop_target.connect("enter", self._on_drop_enter)
        drop_target.connect("leave", self._on_drop_leave)
        self.add_controller(drop_target)

        self._on_code_changed()

    def _on_code_changed(self) -> None:
        has_code = bool(self.get_code())
        self.receive_start_btn.set_sensitive(has_code and not self._transfer_active)
        if has_code:
            self.code_entry.remove_css_class("error")

    def _on_drop_enter(self, *_args: Any) -> Gdk.DragAction:
        self.add_css_class("gator-drop")
        return Gdk.DragAction.COPY

    def _on_drop_leave(self, *_args: Any) -> None:
        self.remove_css_class("gator-drop")

    def _on_drop(
        self, _target: Gtk.DropTarget, value: Any, _x: float, _y: float
    ) -> bool:
        self.remove_css_class("gator-drop")
        if self._transfer_active:
            return False
        if isinstance(value, Gdk.FileList):
            self.emit("qr-dropped", value)
            return True
        return False

    def get_code(self) -> str:
        return self.code_entry.get_text().strip()

    def set_code(self, code: str) -> None:
        self.code_entry.set_text(code)
        self.code_entry.remove_css_class("error")
        self._on_code_changed()

    def mark_code_error(self) -> None:
        self.code_entry.add_css_class("error")

    def get_save_dir(self) -> str:
        return self._save_dir

    def set_save_dir_subtitle(self, path: str) -> None:
        self._save_dir = path
        self.folder_row.set_subtitle(path)

    def set_scan_enabled(self, enabled: bool, tooltip: str = "") -> None:
        self._scan_enabled = enabled
        self.scan_btn.set_sensitive(enabled and not self._transfer_active)
        if tooltip:
            self.scan_btn.set_tooltip_text(tooltip)

    def set_shell_output_visible(self, visible: bool) -> None:
        self.log_expander.set_visible(visible)

    def show_banner(self, message: str, *, error: bool = False) -> None:
        self.banner.set_title(message)
        if error:
            self.banner.add_css_class("error")
        else:
            self.banner.remove_css_class("error")
        self.banner.set_revealed(True)

    def hide_banner(self) -> None:
        self.banner.set_revealed(False)

    def set_transfer_active(self, active: bool) -> None:
        self._transfer_active = active
        self.receive_idle_box.set_visible(not active)
        self.receive_transfer_box.set_visible(active)
        self.code_entry.set_sensitive(not active)
        self.scan_btn.set_sensitive(self._scan_enabled and not active)
        self._change_folder_btn.set_sensitive(not active)
        self.folder_row.set_activatable(not active)
        if active:
            self.hide_banner()
            self._receive_success = False
            self._update_folder_row_success()
            self.receive_success_icon.set_visible(False)
            self.receive_error_icon.set_visible(False)
            self.receive_spinner.set_visible(True)
            self.receive_spinner.start()
            self.receive_cancel_btn.set_visible(True)
            self.receive_transfer_label.set_label(_("Waiting for sender"))
            self.receive_progress.set_fraction(0.0)
            self.receive_progress.set_visible(False)
        else:
            self.receive_spinner.stop()
            self.receive_progress.set_visible(False)
            self._on_code_changed()

    def set_transfer_phase(self, phase: str) -> None:
        labels = {
            "hashing": _("Hashing"),
            "sending": _("Receiving"),
            "receiving": _("Receiving"),
            "waiting": _("Waiting for sender"),
            "connecting": _("Connecting"),
        }
        if phase in labels:
            self.receive_transfer_label.set_label(labels[phase])
            if phase in ("waiting", "connecting", "hashing"):
                self.receive_progress.pulse()
                self.receive_progress.set_visible(True)

    def show_transfer_complete(
        self,
        *,
        canceled: bool,
        success: bool = True,
        message: str = "",
        files: bool = True,
    ) -> None:
        self.receive_spinner.stop()
        self.receive_cancel_btn.set_visible(False)
        if canceled:
            self.receive_success_icon.set_visible(False)
            self.receive_error_icon.set_visible(False)
            self.receive_spinner.set_visible(False)
            self.receive_transfer_label.set_label(message or _("Transfer cancelled"))
            self.receive_progress.set_visible(False)
        elif success:
            if files:
                self._receive_success = True
                self._update_folder_row_success()
            self.receive_spinner.set_visible(False)
            self.receive_error_icon.set_visible(False)
            self.receive_success_icon.set_visible(True)
            self.receive_transfer_label.set_label(message or _("Transfer finished"))
            self.receive_progress.set_fraction(1.0)
            self.receive_progress.set_visible(True)
        else:
            self.receive_spinner.set_visible(False)
            self.receive_success_icon.set_visible(False)
            self.receive_error_icon.set_visible(True)
            self.receive_transfer_label.set_label(message or _("Transfer failed"))
            self.receive_progress.set_visible(False)
            self.show_banner(message or _("Transfer failed"), error=True)
            if self.log_expander.get_visible():
                self.log_expander.set_expanded(True)

    def _update_folder_row_success(self) -> None:
        self.folder_row.set_subtitle(self._save_dir)
        if self._receive_success:
            self.folder_row.set_title(_("Received successfully"))
            self.folder_icon.set_from_icon_name(resolve_success_icon_name(self))
            self.folder_row.add_css_class("success")
            self.open_folder_btn.set_visible(True)
        else:
            self.folder_row.set_title(_("Save to folder"))
            self.folder_icon.set_from_icon_name("folder-symbolic")
            self.folder_row.remove_css_class("success")
            self.open_folder_btn.set_visible(False)

    def set_progress(self, fraction: float) -> None:
        self.receive_progress.set_fraction(fraction)
        self.receive_progress.set_visible(True)
        pct = int(fraction * 100)
        current = self.receive_transfer_label.get_label()
        base = current.split(" — ")[0] if " — " in current else current
        self.receive_transfer_label.set_label(f"{base} — {pct}%")

    def _ensure_error_tag(self) -> None:
        if self._error_tag_applied:
            return
        error_rgba = get_theme_rgba(self, "error_color")
        self.receive_log.get_buffer().create_tag(
            "error", foreground=rgba_to_hex(error_rgba)
        )
        self._error_tag_applied = True

    def append_log(self, text: str) -> None:
        self._ensure_error_tag()
        buf = self.receive_log.get_buffer()
        if buf.get_line_count() > _MAX_LOG_LINES:
            start = buf.get_start_iter()
            line = buf.get_line_count() - (_MAX_LOG_LINES - 80)
            result = buf.get_iter_at_line(max(0, line))
            end = result[1] if isinstance(result, tuple) else result
            if end is not None:
                buf.delete(start, end)
        end = buf.get_end_iter()
        low = text.lower()
        if (
            low.startswith("error")
            or "code is invalid" in low
            or "peer disconnected" in low
        ):
            buf.insert_with_tags_by_name(end, text + "\n", "error")
        else:
            buf.insert(end, text + "\n")
        mark = buf.create_mark("end", buf.get_end_iter(), False)
        self.receive_log.scroll_mark_onscreen(mark)
