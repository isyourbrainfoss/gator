"""send_page.py – Send tab widget with GObject signals."""

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
    from gi.repository import Gdk

    from .settings import GatorSettings


class SendPage(Gtk.Box):
    """Send page: file list, transfer controls, optional QR and log."""

    __gsignals__ = {
        "add-files": (GObject.SignalFlags.RUN_LAST, None, (bool,)),
        "add-folder": (GObject.SignalFlags.RUN_LAST, None, (bool,)),
        "add-text": (GObject.SignalFlags.RUN_LAST, None, ()),
        "clear-all": (GObject.SignalFlags.RUN_LAST, None, ()),
        "start-send": (GObject.SignalFlags.RUN_LAST, None, ()),
        "cancel-send": (GObject.SignalFlags.RUN_LAST, None, ()),
        "copy-code": (GObject.SignalFlags.RUN_LAST, None, ()),
        "files-dropped": (GObject.SignalFlags.RUN_LAST, bool, (object,)),
        "remove-item": (GObject.SignalFlags.RUN_LAST, None, (str, bool)),
        "remove-text": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, settings: GatorSettings) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.settings = settings
        self.selected_files: list[str] = []
        self.excluded_items: list[str] = []
        self.send_text: str = ""
        self._error_tag_applied = False
        self._sent_paths: set[str] = set()
        self._text_sent = False
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

        buttons_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        form.append(buttons_box)
        buttons_row = Gtk.Box(spacing=6, homogeneous=True)
        buttons_box.append(buttons_row)

        self.add_btn = Gtk.MenuButton()
        self.add_btn.add_css_class("suggested-action")
        self.add_btn.add_css_class("pill")
        set_a11y_label(self.add_btn, _("Add"))
        add_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        add_h.append(Gtk.Image.new_from_icon_name("list-add-symbolic"))
        add_h.append(Gtk.Label(label=_("Add")))
        self.add_btn.set_child(add_h)
        add_pop = Gtk.Popover()
        add_vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin_start=12,
            margin_end=12,
            margin_top=12,
            margin_bottom=12,
        )
        for label, icon, signal in [
            (_("Add Files"), "folder-documents-symbolic", "add-files"),
            (_("Add Folder"), "folder-symbolic", "add-folder"),
            (_("Add Text"), "accessories-text-editor-symbolic", "add-text"),
        ]:
            btn = Gtk.Button()
            box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
            box.append(Gtk.Image.new_from_icon_name(icon))
            box.append(Gtk.Label(label=label))
            btn.set_child(box)
            if signal == "add-text":
                btn.connect(
                    "clicked", lambda *_: (self.emit("add-text"), add_pop.popdown())
                )
            elif signal == "add-files":
                btn.connect(
                    "clicked",
                    lambda *_: (self.emit("add-files", True), add_pop.popdown()),
                )
            else:
                btn.connect(
                    "clicked",
                    lambda *_: (self.emit("add-folder", True), add_pop.popdown()),
                )
            add_vbox.append(btn)
        add_pop.set_child(add_vbox)
        self.add_btn.set_popover(add_pop)
        self.add_btn.set_hexpand(True)
        buttons_row.append(self.add_btn)

        self.exclude_btn = Gtk.MenuButton()
        self.exclude_btn.add_css_class("flat")
        set_a11y_label(self.exclude_btn, _("Exclude"))
        exclude_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        exclude_h.append(Gtk.Image.new_from_icon_name("list-remove-symbolic"))
        exclude_h.append(Gtk.Label(label=_("Exclude")))
        self.exclude_btn.set_child(exclude_h)
        exclude_pop = Gtk.Popover()
        exclude_vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin_start=12,
            margin_end=12,
            margin_top=12,
            margin_bottom=12,
        )
        for label, icon, sig in [
            (_("Exclude Files"), "folder-documents-symbolic", "add-files"),
            (_("Exclude Folder"), "folder-symbolic", "add-folder"),
        ]:
            btn = Gtk.Button()
            box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
            box.append(Gtk.Image.new_from_icon_name(icon))
            box.append(Gtk.Label(label=label))
            btn.set_child(box)
            if sig == "add-files":
                btn.connect(
                    "clicked",
                    lambda *_: (self.emit("add-files", False), exclude_pop.popdown()),
                )
            else:
                btn.connect(
                    "clicked",
                    lambda *_: (self.emit("add-folder", False), exclude_pop.popdown()),
                )
            exclude_vbox.append(btn)
        exclude_pop.set_child(exclude_vbox)
        self.exclude_btn.set_popover(exclude_pop)
        self.exclude_btn.set_hexpand(True)
        buttons_row.append(self.exclude_btn)

        self.clear_btn = Gtk.Button()
        self.clear_btn.add_css_class("destructive-action")
        clear_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        clear_h.append(Gtk.Image.new_from_icon_name("edit-clear-symbolic"))
        clear_h.append(Gtk.Label(label=_("Clear All")))
        self.clear_btn.set_child(clear_h)
        self.clear_btn.connect("clicked", lambda *_: self.emit("clear-all"))
        self.clear_btn.set_hexpand(True)
        buttons_box.append(self.clear_btn)

        file_scroll = Gtk.ScrolledWindow()
        file_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        file_scroll.set_propagate_natural_height(True)
        file_scroll.set_vexpand(True)
        self.files_listbox = Gtk.ListBox()
        self.files_listbox.add_css_class("boxed-list")
        self.files_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        placeholder.append(Gtk.Image.new_from_icon_name("folder-open-symbolic"))
        ph_label = Gtk.Label(label=_("No files or folders selected"))
        ph_label.add_css_class("dim-label")
        placeholder.append(ph_label)
        placeholder.set_valign(Gtk.Align.CENTER)
        placeholder.set_margin_top(20)
        self.files_listbox.set_placeholder(placeholder)
        file_scroll.set_child(self.files_listbox)
        form.append(file_scroll)

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        self.files_listbox.add_controller(drop_target)

        controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        controls.set_hexpand(True)

        self.send_idle_box = Gtk.Box()
        self.send_idle_box.set_halign(Gtk.Align.CENTER)
        self.send_start_btn = Gtk.Button()
        self.send_start_btn.add_css_class("suggested-action")
        self.send_start_btn.add_css_class("pill")
        send_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        send_btn_box.append(Gtk.Image.new_from_icon_name("document-send-symbolic"))
        send_btn_box.append(Gtk.Label(label=_("Start Transfer")))
        self.send_start_btn.set_child(send_btn_box)
        self.send_start_btn.set_sensitive(False)
        self.send_start_btn.connect("clicked", lambda *_: self.emit("start-send"))
        self.send_idle_box.append(self.send_start_btn)

        self.send_transfer_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=8
        )
        self.send_transfer_box.set_hexpand(True)
        transfer_row = Gtk.Box(spacing=12)
        transfer_row.set_hexpand(True)
        self.send_status_stack = Gtk.Stack()
        self.send_status_stack.set_size_request(32, 32)
        self.send_spinner = Gtk.Spinner()
        self.send_spinner.set_valign(Gtk.Align.CENTER)
        self.send_success_icon = self._make_sent_icon(size=24)
        self.send_status_stack.add_named(self.send_spinner, "spinner")
        self.send_status_stack.add_named(self.send_success_icon, "success")
        self.send_transfer_label = Gtk.Label(
            label=_("Preparing"),
            ellipsize=Pango.EllipsizeMode.END,
            hexpand=True,
            halign=Gtk.Align.START,
        )
        self.send_cancel_btn = Gtk.Button(label=_("Cancel"))
        self.send_cancel_btn.add_css_class("destructive-action")
        self.send_cancel_btn.connect("clicked", lambda *_: self.emit("cancel-send"))
        transfer_row.append(self.send_status_stack)
        transfer_row.append(self.send_transfer_label)
        transfer_row.append(self.send_cancel_btn)
        self.send_transfer_box.append(transfer_row)
        self.send_progress = Gtk.ProgressBar(show_text=True)
        self.send_progress.set_hexpand(True)
        self.send_progress.set_visible(False)
        self.send_transfer_box.append(self.send_progress)
        self.send_transfer_box.set_visible(False)

        controls.append(self.send_idle_box)
        controls.append(self.send_transfer_box)
        form.append(controls)

        self.transfer_info = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            halign=Gtk.Align.CENTER,
            margin_top=6,
        )
        self.transfer_info.set_visible(False)

        self.code_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.code_label = Gtk.Label(
            xalign=0,
            selectable=True,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            css_classes=["heading", "monospace"],
            hexpand=True,
        )
        self.code_box.append(self.code_label)
        copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
        copy_btn.set_tooltip_text(_("Copy code"))
        set_a11y_label(copy_btn, _("Copy code"))
        copy_btn.connect("clicked", lambda *_: self.emit("copy-code"))
        self.code_box.append(copy_btn)

        qr_clamp = Adw.Clamp(maximum_size=320, tightening_threshold=256)
        self.qr_picture = Gtk.Picture(content_fit=Gtk.ContentFit.SCALE_DOWN)
        self.qr_picture.set_size_request(256, 256)
        self.qr_picture.add_css_class("card")
        self.qr_picture.set_visible(self.settings.get("show_qr_image", True))
        qr_clamp.set_child(self.qr_picture)

        self.transfer_info.append(self.code_box)
        self.transfer_info.append(qr_clamp)
        form.append(self.transfer_info)

        clamp.set_child(form)
        outer.append(clamp)

        self.log_expander = Gtk.Expander(label=_("Shell output"), margin_top=6)
        self.log_expander.set_visible(self.settings.get("show_shell_output", False))
        self.log_expander.set_expanded(True)
        log_scroll = Gtk.ScrolledWindow(vexpand=True)
        log_scroll.add_css_class("background")
        log_scroll.set_min_content_height(200)
        self.send_log = Gtk.TextView(
            editable=False,
            wrap_mode=Gtk.WrapMode.WORD,
            monospace=True,
            top_margin=12,
            bottom_margin=12,
            left_margin=12,
            right_margin=12,
        )
        log_scroll.set_child(self.send_log)
        self.log_expander.set_child(log_scroll)
        outer.append(self.log_expander)

        scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_propagate_natural_width(False)
        scroll.set_child(outer)
        self.append(scroll)

    def _make_sent_icon(self, *, size: int = 16) -> Gtk.Image:
        """Green sent indicator (emblem-ok; symbolic variant is missing in GNOME)."""
        icon = Gtk.Image.new_from_icon_name("emblem-ok")
        icon.set_pixel_size(size)
        icon.set_valign(Gtk.Align.CENTER)
        return icon

    def _on_drop(
        self, drop_target: Gtk.DropTarget, value: Any, _x: float, _y: float
    ) -> bool:
        if isinstance(value, Gdk.FileList):
            self.emit("files-dropped", value)
            return True
        return False

    def _ensure_error_tag(self) -> None:
        if self._error_tag_applied:
            return
        error_rgba = get_theme_rgba(self, "error_color")
        self.send_log.get_buffer().create_tag(
            "error", foreground=rgba_to_hex(error_rgba)
        )
        self._error_tag_applied = True

    def append_log(self, text: str, *, is_error: bool = False) -> None:
        self._ensure_error_tag()
        buf = self.send_log.get_buffer()
        end = buf.get_end_iter()
        if is_error or text.lower().startswith("error"):
            buf.insert_with_tags(end, text + "\n", "error")
        else:
            buf.insert(end, text + "\n")
        mark = buf.create_mark("end", buf.get_end_iter(), False)
        self.send_log.scroll_mark_onscreen(mark)

    def set_shell_output_visible(self, visible: bool) -> None:
        self.log_expander.set_visible(visible)

    def set_qr_visible(self, visible: bool) -> None:
        self.qr_picture.set_visible(visible)

    def set_transfer_active(self, active: bool, label: str = "") -> None:
        self.send_idle_box.set_visible(not active)
        self.send_transfer_box.set_visible(active)
        if active:
            self._sent_paths.clear()
            self._text_sent = False
            self.refresh_file_list(
                self.selected_files,
                self.excluded_items,
                self.send_text,
            )
            self.send_status_stack.set_visible_child_name("spinner")
            self.send_spinner.start()
            self.send_cancel_btn.set_visible(True)
            if label:
                self.send_transfer_label.set_label(label)
            self.send_progress.set_fraction(0.0)
            self.send_progress.set_visible(True)
        else:
            self.send_spinner.stop()
            self.send_progress.set_visible(False)

    def show_transfer_complete(self, *, canceled: bool) -> None:
        self.send_spinner.stop()
        self.send_cancel_btn.set_visible(False)
        if canceled:
            self.send_status_stack.set_visible_child_name("spinner")
            self.send_transfer_label.set_label(_("Transfer cancelled"))
            self.send_progress.set_visible(False)
        else:
            self.send_status_stack.set_visible_child_name("success")
            self.send_transfer_label.set_label(_("Transfer finished"))
            self.send_progress.set_fraction(1.0)
            self.send_progress.set_text(_("Done"))
            self.send_progress.set_visible(True)

    def mark_items_sent(self, paths: list[str], *, text_sent: bool) -> None:
        self._sent_paths = set(paths)
        self._text_sent = text_sent
        self.refresh_file_list(
            self.selected_files,
            self.excluded_items,
            self.send_text,
        )

    def set_transfer_phase(self, phase: str) -> None:
        labels = {
            "hashing": _("Hashing"),
            "sending": _("Sending"),
            "receiving": _("Sending"),
        }
        if phase in labels:
            self.send_transfer_label.set_label(labels[phase])

    def set_progress(self, fraction: float) -> None:
        self.send_progress.set_fraction(fraction)
        self.send_progress.set_text(f"{int(fraction * 100)}%")

    def show_code(self, code: str) -> None:
        self.code_label.set_label(code)
        self.transfer_info.set_visible(True)

    def hide_code(self) -> None:
        self.transfer_info.set_visible(False)
        self.code_label.set_label("")
        self.qr_picture.set_paintable(None)

    def set_qr_paintable(self, paintable: Gdk.Paintable | None) -> None:
        self.qr_picture.set_paintable(paintable)

    def get_code(self) -> str:
        return self.code_label.get_label()

    def refresh_file_list(
        self,
        selected: list[str],
        excluded: list[str],
        send_text: str,
    ) -> None:
        """Rebuild list rows."""
        import os
        from pathlib import Path

        self.selected_files = selected
        self.excluded_items = excluded
        self.send_text = send_text
        while row := self.files_listbox.get_row_at_index(0):
            self.files_listbox.remove(row)

        for path in selected:
            name = Path(path).name + (_(" (folder)") if os.path.isdir(path) else "")
            sent = path in self._sent_paths
            row = Adw.ActionRow(
                title=name,
                subtitle=_("Sent successfully") if sent else path,
            )
            if sent:
                row.add_prefix(self._make_sent_icon())
                row.add_css_class("success")
            else:
                row.add_prefix(Gtk.Image.new_from_icon_name("list-add-symbolic"))
            rm = Gtk.Button(icon_name="edit-delete-symbolic")
            rm.add_css_class("flat")
            set_a11y_label(rm, _("Remove"))
            rm.connect("clicked", lambda _, p=path: self.emit("remove-item", p, True))
            row.add_suffix(rm)
            self.files_listbox.append(row)
        for path in excluded:
            name = Path(path).name + (_(" (folder)") if os.path.isdir(path) else "")
            row = Adw.ActionRow(title=name, subtitle=path)
            row.add_prefix(Gtk.Image.new_from_icon_name("list-remove-symbolic"))
            rm = Gtk.Button(icon_name="edit-delete-symbolic")
            rm.add_css_class("flat")
            set_a11y_label(rm, _("Remove"))
            rm.connect("clicked", lambda _, p=path: self.emit("remove-item", p, False))
            row.add_suffix(rm)
            self.files_listbox.append(row)
        if send_text:
            collapsed = " ".join(send_text.splitlines())
            subtitle = (
                _("Sent successfully")
                if self._text_sent
                else collapsed[:50] + ("..." if len(collapsed) > 50 else "")
            )
            row = Adw.ActionRow(title=_("Text"), subtitle=subtitle)
            if self._text_sent:
                row.add_prefix(self._make_sent_icon())
                row.add_css_class("success")
            else:
                row.add_prefix(
                    Gtk.Image.new_from_icon_name("accessories-text-editor-symbolic")
                )
            rm = Gtk.Button(icon_name="edit-delete-symbolic")
            rm.add_css_class("flat")
            set_a11y_label(rm, _("Remove"))
            rm.connect("clicked", lambda _: self.emit("remove-text"))
            row.add_suffix(rm)
            self.files_listbox.append(row)
        self.send_start_btn.set_sensitive(bool(selected) or bool(send_text))
