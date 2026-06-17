"""receive_page.py – Receive tab extracted into a widget subclass.

See send_page.py for rationale.  Widget references are poked back onto the
owning CrocGUI instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

if TYPE_CHECKING:
    from croc_gui import CrocGUI


class ReceivePage(Gtk.ScrolledWindow):
    """Encapsulates the entire "Receive" page UI."""

    def __init__(self, app: CrocGUI) -> None:
        super().__init__()
        # Use AUTOMATIC horizontally so the page can shrink below its natural width
        # on narrow windows (prevents AdwToastOverlay "exceeds" warnings).
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.app = app
        self._build_content()

    def _build_content(self) -> None:
        outer = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin_start=6,
            margin_end=6,
            margin_top=6,
            margin_bottom=6,
        )
        clamp = Adw.Clamp(maximum_size=900, tightening_threshold=720)
        form = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin_start=6,
            margin_end=6,
            margin_top=6,
            margin_bottom=6,
        )

        self.app.code_entry = Adw.EntryRow(title="Transfer code")
        self.app.code_entry.set_show_apply_button(True)
        self.app.code_entry.connect("apply", lambda *_: self.app.on_start_receive(None))
        form.append(self.app.code_entry)

        self.app.receive_btn_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=6
        )
        paste_btn = Gtk.Button()
        paste_box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
        paste_box.append(Gtk.Image.new_from_icon_name("edit-paste-symbolic"))
        paste_box.append(Gtk.Label(label="Paste from Clipboard"))
        paste_btn.set_child(paste_box)
        paste_btn.connect("clicked", self.app.on_paste_clipboard)
        self.app.receive_btn_box.append(paste_btn)

        scan_btn = Gtk.Button()
        scan_box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
        scan_box.append(Gtk.Image.new_from_icon_name("camera-photo-symbolic"))
        scan_box.append(Gtk.Label(label="Scan QR from Image"))
        scan_btn.set_child(scan_box)
        scan_btn.connect("clicked", self.app.on_scan_qr_image)
        self.app.scan_btn = scan_btn  # exposed for post-config in CrocGUI
        self.app.receive_btn_box.append(scan_btn)
        form.append(self.app.receive_btn_box)

        self.app.folder_row = Adw.ActionRow(
            title="Save to folder", subtitle=self.app.save_dir
        )
        self.app.folder_row.add_prefix(Gtk.Image.new_from_icon_name("folder-symbolic"))
        change_btn = Gtk.Button(icon_name="document-open-symbolic")
        change_btn.set_tooltip_text("Change folder")
        change_btn.connect("clicked", self.app.on_change_folder)
        self.app.folder_row.add_suffix(change_btn)
        form.append(self.app.folder_row)

        # Shell toggle for receive
        toggles_group = Adw.PreferencesGroup()
        self.app.receive_shell_toggle_row = Adw.SwitchRow(title="Show shell output")
        self.app.receive_shell_toggle_row.set_active(True)
        self.app.receive_shell_toggle_row.connect(
            "notify::active", self.app.on_shell_toggle_changed_receive
        )
        toggles_group.add(self.app.receive_shell_toggle_row)
        form.append(toggles_group)

        controls = Gtk.CenterBox()
        self.app.receive_start_btn = Gtk.Button()
        self.app.receive_start_btn.add_css_class("suggested-action")
        self.app.receive_start_btn.add_css_class("pill")
        receive_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        receive_btn_box.append(Gtk.Image.new_from_icon_name("folder-download-symbolic"))
        receive_btn_box.append(Gtk.Label(label="Start Receiving"))
        self.app.receive_start_btn.set_child(receive_btn_box)
        self.app.receive_start_btn.connect("clicked", self.app.on_start_receive)
        controls.set_center_widget(self.app.receive_start_btn)
        self.app.receive_transfer_box = Gtk.Box(spacing=12)
        self.app.receive_spinner = Gtk.Spinner()
        self.app.receive_spinner.set_size_request(32, 32)
        self.app.receive_transfer_label = Gtk.Label(label="Waiting for sender")
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.add_css_class("destructive-action")
        cancel_btn.connect("clicked", self.app.on_cancel_receive)
        self.app.receive_transfer_box.append(self.app.receive_spinner)
        self.app.receive_transfer_box.append(self.app.receive_transfer_label)
        self.app.receive_transfer_box.append(cancel_btn)
        self.app.receive_transfer_box.set_visible(False)
        controls.set_end_widget(self.app.receive_transfer_box)
        form.append(controls)

        clamp.set_child(form)
        outer.append(clamp)

        # Log
        log_scroll = Gtk.ScrolledWindow(vexpand=True)
        log_scroll.add_css_class("background")
        log_scroll.set_min_content_height(400)
        self.app.receive_log = Gtk.TextView(
            editable=False,
            wrap_mode=Gtk.WrapMode.WORD,
            monospace=True,
            top_margin=12,
            bottom_margin=12,
            left_margin=12,
            right_margin=12,
        )
        log_scroll.set_child(self.app.receive_log)
        outer.append(log_scroll)
        self.app.receive_log_scroll = log_scroll

        # Drag-and-drop support for QR images (P4 stretch)
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self.app.on_receive_qr_drop)
        self.add_controller(drop_target)

        self.set_child(outer)
