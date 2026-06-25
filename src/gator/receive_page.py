"""receive_page.py – Receive tab widget with GObject signals."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GObject, Gtk, Pango

from .a11y import set_a11y_label
from .i18n import _
from .theme import get_theme_rgba, rgba_to_hex

if TYPE_CHECKING:
    from .settings import GatorSettings


class ReceivePage(Gtk.Box):
    """Receive page: code entry, folder picker, transfer controls."""

    __gsignals__ = {
        "start-receive": (GObject.SignalFlags.RUN_LAST, None, ()),
        "cancel-receive": (GObject.SignalFlags.RUN_LAST, None, ()),
        "paste-clipboard": (GObject.SignalFlags.RUN_LAST, None, ()),
        "scan-qr": (GObject.SignalFlags.RUN_LAST, None, ()),
        "change-folder": (GObject.SignalFlags.RUN_LAST, None, ()),
        "qr-dropped": (GObject.SignalFlags.RUN_LAST, bool, (object,)),
    }

    def __init__(self, settings: GatorSettings, save_dir: str) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.settings = settings
        self._save_dir = save_dir
        self._error_tag_applied = False
        self._build_content()

    def _build_content(self) -> None:
        outer = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin_start=6,
            margin_end=6,
            margin_top=6,
            margin_bottom=6,
            vexpand=True,
        )
        clamp = Adw.Clamp(maximum_size=900, tightening_threshold=720)
        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        self.code_entry = Adw.EntryRow(title=_("Transfer code"))
        self.code_entry.set_show_apply_button(True)
        self.code_entry.connect("apply", lambda *_: self.emit("start-receive"))
        form.append(self.code_entry)

        self.receive_btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        paste_btn = Gtk.Button()
        paste_box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
        paste_box.append(Gtk.Image.new_from_icon_name("edit-paste-symbolic"))
        paste_box.append(Gtk.Label(label=_("Paste from Clipboard")))
        paste_btn.set_child(paste_box)
        paste_btn.connect("clicked", lambda *_: self.emit("paste-clipboard"))
        self.receive_btn_box.append(paste_btn)

        self.scan_btn = Gtk.Button()
        scan_box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
        scan_box.append(Gtk.Image.new_from_icon_name("camera-photo-symbolic"))
        scan_box.append(Gtk.Label(label=_("Scan QR from Image")))
        self.scan_btn.set_child(scan_box)
        self.scan_btn.connect("clicked", lambda *_: self.emit("scan-qr"))
        self.receive_btn_box.append(self.scan_btn)
        form.append(self.receive_btn_box)

        self.folder_row = Adw.ActionRow(
            title=_("Save to folder"), subtitle=self._save_dir
        )
        self.folder_row.add_prefix(Gtk.Image.new_from_icon_name("folder-symbolic"))
        change_btn = Gtk.Button(icon_name="document-open-symbolic")
        change_btn.set_tooltip_text(_("Change folder"))
        set_a11y_label(change_btn, _("Change folder"))
        change_btn.connect("clicked", lambda *_: self.emit("change-folder"))
        self.folder_row.add_suffix(change_btn)
        form.append(self.folder_row)

        controls = Gtk.CenterBox()
        self.receive_start_btn = Gtk.Button()
        self.receive_start_btn.add_css_class("suggested-action")
        self.receive_start_btn.add_css_class("pill")
        receive_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        receive_btn_box.append(Gtk.Image.new_from_icon_name("folder-download-symbolic"))
        receive_btn_box.append(Gtk.Label(label=_("Start Receiving")))
        self.receive_start_btn.set_child(receive_btn_box)
        self.receive_start_btn.connect("clicked", lambda *_: self.emit("start-receive"))
        controls.set_center_widget(self.receive_start_btn)

        self.receive_transfer_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=6
        )
        transfer_row = Gtk.Box(spacing=12)
        self.receive_spinner = Gtk.Spinner()
        self.receive_spinner.set_size_request(32, 32)
        self.receive_transfer_label = Gtk.Label(
            label=_("Waiting for sender"),
            ellipsize=Pango.EllipsizeMode.END,
            hexpand=True,
        )
        cancel_btn = Gtk.Button(label=_("Cancel"))
        cancel_btn.add_css_class("destructive-action")
        cancel_btn.connect("clicked", lambda *_: self.emit("cancel-receive"))
        transfer_row.append(self.receive_spinner)
        transfer_row.append(self.receive_transfer_label)
        transfer_row.append(cancel_btn)
        self.receive_transfer_box.append(transfer_row)
        self.receive_progress = Gtk.ProgressBar(show_text=True)
        self.receive_progress.set_visible(False)
        self.receive_transfer_box.append(self.receive_progress)
        self.receive_transfer_box.set_visible(False)
        controls.set_end_widget(self.receive_transfer_box)
        form.append(controls)

        clamp.set_child(form)
        outer.append(clamp)

        self.log_expander = Gtk.Expander(label=_("Shell output"), margin_top=6)
        self.log_expander.set_visible(self.settings.get("show_shell_output", False))
        self.log_expander.set_expanded(True)
        log_scroll = Gtk.ScrolledWindow(vexpand=True)
        log_scroll.add_css_class("background")
        log_scroll.set_min_content_height(200)
        self.receive_log = Gtk.TextView(
            editable=False,
            wrap_mode=Gtk.WrapMode.WORD,
            monospace=True,
            top_margin=12,
            bottom_margin=12,
            left_margin=12,
            right_margin=12,
        )
        log_scroll.set_child(self.receive_log)
        self.log_expander.set_child(log_scroll)
        outer.append(self.log_expander)

        scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_propagate_natural_width(False)
        scroll.set_child(outer)
        self.append(scroll)

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        self.add_controller(drop_target)

    def _on_drop(
        self, _target: Gtk.DropTarget, value: Any, _x: float, _y: float
    ) -> bool:
        if isinstance(value, Gdk.FileList):
            self.emit("qr-dropped", value)
            return True
        return False

    def get_code(self) -> str:
        return self.code_entry.get_text().strip()

    def set_code(self, code: str) -> None:
        self.code_entry.set_text(code)

    def get_save_dir(self) -> str:
        return self._save_dir

    def set_save_dir_subtitle(self, path: str) -> None:
        self._save_dir = path
        self.folder_row.set_subtitle(path)

    def set_scan_enabled(self, enabled: bool, tooltip: str = "") -> None:
        self.scan_btn.set_sensitive(enabled)
        if tooltip:
            self.scan_btn.set_tooltip_text(tooltip)

    def set_shell_output_visible(self, visible: bool) -> None:
        self.log_expander.set_visible(visible)

    def set_transfer_active(self, active: bool) -> None:
        self.receive_start_btn.set_visible(not active)
        self.receive_transfer_box.set_visible(active)
        self.code_entry.set_sensitive(not active)
        self.receive_btn_box.set_sensitive(not active)
        if active:
            self.receive_spinner.start()
            self.receive_progress.set_fraction(0.0)
            self.receive_progress.set_visible(True)
        else:
            self.receive_spinner.stop()
            self.receive_progress.set_visible(False)

    def set_progress(self, fraction: float) -> None:
        self.receive_progress.set_fraction(fraction)
        self.receive_progress.set_text(f"{int(fraction * 100)}%")

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
        end = buf.get_end_iter()
        if text.lower().startswith("error"):
            buf.insert_with_tags(end, text + "\n", "error")
        else:
            buf.insert(end, text + "\n")
        mark = buf.create_mark("end", buf.get_end_iter(), False)
        self.receive_log.scroll_mark_onscreen(mark)
