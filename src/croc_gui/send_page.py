"""send_page.py – Send tab extracted into a widget subclass.

_build_send_page logic has been moved here.  To keep the controller code
in CrocGUI unchanged we assign created widgets back onto app (e.g.
app.files_listbox, app.send_log, ...).  The page owns the tree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk, Pango

if TYPE_CHECKING:
    from .app import CrocGUI


class SendPage(Gtk.ScrolledWindow):
    """Encapsulates the entire "Send" page UI.

    After construction, the owning CrocGUI instance has many of its
    ``self.xxx`` widget references populated so existing handler methods
    continue to work.
    """

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

        # Buttons box
        buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        form.append(buttons_box)

        # Add button
        self.app.add_btn = Gtk.MenuButton()
        self.app.add_btn.add_css_class("suggested-action")
        self.app.add_btn.add_css_class("pill")
        add_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        add_h.append(Gtk.Image.new_from_icon_name("list-add-symbolic"))
        add_h.append(Gtk.Label(label="Add"))
        self.app.add_btn.set_child(add_h)
        add_pop = Gtk.Popover()
        add_vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin_start=12,
            margin_end=12,
            margin_top=12,
            margin_bottom=12,
        )
        files_btn = Gtk.Button()
        files_box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
        files_box.append(Gtk.Image.new_from_icon_name("folder-documents-symbolic"))
        files_box.append(Gtk.Label(label="Add Files"))
        files_btn.set_child(files_box)
        files_btn.connect(
            "clicked",
            lambda *_: (self.app.on_add_files(included=True), add_pop.popdown()),
        )
        add_vbox.append(files_btn)
        folder_btn = Gtk.Button()
        folder_box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
        folder_box.append(Gtk.Image.new_from_icon_name("folder-symbolic"))
        folder_box.append(Gtk.Label(label="Add Folder"))
        folder_btn.set_child(folder_box)
        folder_btn.connect(
            "clicked",
            lambda *_: (self.app.on_add_folder(included=True), add_pop.popdown()),
        )
        add_vbox.append(folder_btn)
        text_btn = Gtk.Button()
        text_box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
        text_box.append(
            Gtk.Image.new_from_icon_name("accessories-text-editor-symbolic")
        )
        text_box.append(Gtk.Label(label="Add Text"))
        text_btn.set_child(text_box)
        text_btn.connect(
            "clicked", lambda *_: (self.app.on_add_text(), add_pop.popdown())
        )
        add_vbox.append(text_btn)
        add_pop.set_child(add_vbox)
        self.app.add_btn.set_popover(add_pop)
        buttons_box.append(self.app.add_btn)

        # Exclude button – "flat" not "destructive-action"
        self.app.exclude_btn = Gtk.MenuButton()
        self.app.exclude_btn.add_css_class("flat")
        exclude_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        exclude_h.append(Gtk.Image.new_from_icon_name("list-remove-symbolic"))
        exclude_h.append(Gtk.Label(label="Exclude"))
        self.app.exclude_btn.set_child(exclude_h)
        exclude_pop = Gtk.Popover()
        exclude_vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin_start=12,
            margin_end=12,
            margin_top=12,
            margin_bottom=12,
        )
        ex_files_btn = Gtk.Button()
        ex_files_box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
        ex_files_box.append(Gtk.Image.new_from_icon_name("folder-documents-symbolic"))
        ex_files_box.append(Gtk.Label(label="Exclude Files"))
        ex_files_btn.set_child(ex_files_box)
        ex_files_btn.connect(
            "clicked",
            lambda *_: (self.app.on_add_files(included=False), exclude_pop.popdown()),
        )
        exclude_vbox.append(ex_files_btn)
        ex_folder_btn = Gtk.Button()
        ex_folder_box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
        ex_folder_box.append(Gtk.Image.new_from_icon_name("folder-symbolic"))
        ex_folder_box.append(Gtk.Label(label="Exclude Folder"))
        ex_folder_btn.set_child(ex_folder_box)
        ex_folder_btn.connect(
            "clicked",
            lambda *_: (self.app.on_add_folder(included=False), exclude_pop.popdown()),
        )
        exclude_vbox.append(ex_folder_btn)
        exclude_pop.set_child(exclude_vbox)
        self.app.exclude_btn.set_popover(exclude_pop)
        buttons_box.append(self.app.exclude_btn)

        # Clear all button
        self.app.clear_btn = Gtk.Button()
        self.app.clear_btn.add_css_class("destructive-action")
        clear_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        clear_h.append(Gtk.Image.new_from_icon_name("edit-clear-symbolic"))
        clear_h.append(Gtk.Label(label="Clear All"))
        self.app.clear_btn.set_child(clear_h)
        self.app.clear_btn.connect("clicked", self.app.on_clear_all)
        buttons_box.append(self.app.clear_btn)

        # File list
        file_scroll = Gtk.ScrolledWindow()
        file_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        file_scroll.set_propagate_natural_height(True)
        file_scroll.set_vexpand(True)
        self.app.files_listbox = Gtk.ListBox()
        self.app.files_listbox.add_css_class("boxed-list")
        self.app.files_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        placeholder.append(Gtk.Image.new_from_icon_name("folder-open-symbolic"))
        placeholder.append(Gtk.Label(label="No files or folders selected"))
        placeholder.get_last_child().add_css_class("dim-label")
        placeholder.set_valign(Gtk.Align.CENTER)
        placeholder.set_margin_top(20)
        self.app.files_listbox.set_placeholder(placeholder)
        file_scroll.set_child(self.app.files_listbox)
        form.append(file_scroll)

        # Drop target for drag and drop (delegates to app)
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self.app.on_drop_file)
        self.app.files_listbox.add_controller(drop_target)

        # Toggles group
        toggles_group = Adw.PreferencesGroup()
        self.app.qr_toggle_row = Adw.SwitchRow(title="Show QR image")
        self.app.qr_toggle_row.set_active(True)
        self.app.qr_toggle_row.connect("notify::active", self.app.on_qr_toggle_changed)
        toggles_group.add(self.app.qr_toggle_row)

        self.app.shell_toggle_row = Adw.SwitchRow(title="Show shell output")
        self.app.shell_toggle_row.set_active(True)
        self.app.shell_toggle_row.connect(
            "notify::active", self.app.on_shell_toggle_changed_send
        )
        toggles_group.add(self.app.shell_toggle_row)
        form.append(toggles_group)

        # Controls
        controls = Gtk.CenterBox()
        self.app.send_start_btn = Gtk.Button()
        self.app.send_start_btn.add_css_class("suggested-action")
        self.app.send_start_btn.add_css_class("pill")
        send_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        send_btn_box.append(Gtk.Image.new_from_icon_name("document-send-symbolic"))
        send_btn_box.append(Gtk.Label(label="Start Transfer"))
        self.app.send_start_btn.set_child(send_btn_box)
        self.app.send_start_btn.set_sensitive(False)
        self.app.send_start_btn.connect("clicked", self.app.on_start_send)
        controls.set_center_widget(self.app.send_start_btn)
        self.app.send_transfer_box = Gtk.Box(spacing=12)
        self.app.send_spinner = Gtk.Spinner()
        self.app.send_spinner.set_size_request(32, 32)
        self.app.send_transfer_label = Gtk.Label(label="Preparing")
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.add_css_class("destructive-action")
        cancel_btn.connect("clicked", self.app.on_cancel_send)
        self.app.send_transfer_box.append(self.app.send_spinner)
        self.app.send_transfer_box.append(self.app.send_transfer_label)
        self.app.send_transfer_box.append(cancel_btn)
        self.app.send_transfer_box.set_visible(False)
        controls.set_end_widget(self.app.send_transfer_box)
        form.append(controls)

        # Transfer info container
        self.app.transfer_info = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            halign=Gtk.Align.CENTER,
            margin_top=6,
        )
        self.app.transfer_info.set_visible(False)

        self.app.code_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.app.code_label = Gtk.Label(
            xalign=0,
            selectable=True,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            css_classes=["heading", "monospace"],
        )
        self.app.code_box.append(self.app.code_label)
        copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
        copy_btn.set_tooltip_text("Copy code")
        copy_btn.connect("clicked", self.app.on_copy_code)
        self.app.code_box.append(copy_btn)

        qr_clamp = Adw.Clamp(maximum_size=320, tightening_threshold=256)
        self.app.qr_picture = Gtk.Picture(content_fit=Gtk.ContentFit.SCALE_DOWN)
        self.app.qr_picture.set_size_request(256, 256)
        self.app.qr_picture.add_css_class("card")
        self.app.qr_picture.set_visible(False)
        qr_clamp.set_child(self.app.qr_picture)

        self.app.transfer_info.append(self.app.code_box)
        self.app.transfer_info.append(qr_clamp)
        form.append(self.app.transfer_info)

        clamp.set_child(form)
        outer.append(clamp)

        # Log
        log_scroll = Gtk.ScrolledWindow(vexpand=True)
        log_scroll.add_css_class("background")
        log_scroll.set_min_content_height(400)
        self.app.send_log = Gtk.TextView(
            editable=False,
            wrap_mode=Gtk.WrapMode.WORD,
            monospace=True,
            top_margin=12,
            bottom_margin=12,
            left_margin=12,
            right_margin=12,
        )
        self.app.send_log.get_buffer().create_tag("error", foreground="#ff5555")
        log_scroll.set_child(self.app.send_log)
        outer.append(log_scroll)
        self.app.send_log_scroll = log_scroll

        self.set_child(outer)
