"""Preferences dialog for Gator."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from .a11y import set_a11y_label
from .i18n import _
from .settings import DEFAULT_PORT, DEFAULT_TRANSFERS

if TYPE_CHECKING:
    from .settings import GatorSettings


class PreferencesDialog:
    """Build and present the Adw.PreferencesDialog."""

    def __init__(
        self,
        settings: GatorSettings,
        save_dir: str,
        *,
        on_color_scheme_changed: Callable[[str], None],
        on_show_qr_changed: Callable[[bool], None],
        on_show_shell_changed: Callable[[bool], None],
        on_change_default_folder: Callable[[], None],
        on_reset: Callable[[], None],
    ) -> None:
        self.settings = settings
        self.save_dir = save_dir
        self._on_color_scheme_changed = on_color_scheme_changed
        self._on_show_qr_changed = on_show_qr_changed
        self._on_show_shell_changed = on_show_shell_changed
        self._on_change_default_folder = on_change_default_folder
        self._on_reset = on_reset
        self.default_folder_row: Adw.ActionRow | None = None

    def present(self, parent: Gtk.Window) -> None:
        dlg = Adw.PreferencesDialog()
        dlg.set_title(_("Preferences"))
        page = Adw.PreferencesPage()
        self._fill_page(page, dlg)
        dlg.add(page)
        dlg.present(parent)

    def update_save_dir_subtitle(self, path: str) -> None:
        self.save_dir = path
        if self.default_folder_row is not None:
            self.default_folder_row.set_subtitle(path)

    def _make_switch_row(
        self, key: str, title: str, subtitle: str = ""
    ) -> Adw.SwitchRow:
        row = Adw.SwitchRow(title=title)
        if subtitle:
            row.set_subtitle(subtitle)
        row.set_active(self.settings.get(key, False))
        row.connect(
            "notify::active",
            lambda r, _: self.settings.update({key: r.get_active()})
            or self.settings.save(),  # type: ignore[func-returns-value]
        )
        return row

    def _make_entry_row(self, key: str, title: str, tooltip: str = "") -> Adw.EntryRow:
        row = Adw.EntryRow(title=title)
        row.set_text(self.settings.get(key, ""))
        if tooltip:
            row.set_tooltip_text(tooltip)
        row.connect(
            "changed",
            lambda e: self.settings.update({key: e.get_text().strip()})
            or self.settings.save(),  # type: ignore[func-returns-value]
        )
        return row

    def _on_color_scheme_radio_toggled(
        self, button: Gtk.CheckButton, scheme: str
    ) -> None:
        if not button.get_active():
            return
        if self.settings.get("color_scheme") == scheme:
            return
        self.settings["color_scheme"] = scheme
        self.settings.save()
        self._on_color_scheme_changed(scheme)

    def _fill_page(self, page: Adw.PreferencesPage, dlg: Adw.PreferencesDialog) -> None:
        appearance = Adw.PreferencesGroup(title=_("Appearance"))
        current = self.settings.get("color_scheme", "default")
        radio_group = None
        for scheme, label, icon in [
            ("default", _("Default (follow system)"), "preferences-system-symbolic"),
            ("light", _("Light"), "weather-clear-symbolic"),
            ("dark", _("Dark"), "weather-clear-night-symbolic"),
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
            radio.connect("toggled", self._on_color_scheme_radio_toggled, scheme)
            row.set_activatable_widget(radio)
            appearance.add(row)
        page.add(appearance)

        interface = Adw.PreferencesGroup(title=_("Interface"))
        qr_row = self._make_switch_row(
            "show_qr_image",
            _("Show QR image"),
            subtitle=_("Display the QR code for the generated transfer code"),
        )
        qr_row.connect(
            "notify::active",
            lambda r, *_: self._on_show_qr_changed(r.get_active()),
        )
        interface.add(qr_row)

        shell_row = self._make_switch_row(
            "show_shell_output",
            _("Show shell output"),
            subtitle=_("Show detailed output from the croc command"),
        )
        shell_row.connect(
            "notify::active",
            lambda r, *_: self._on_show_shell_changed(r.get_active()),
        )
        interface.add(shell_row)
        page.add(interface)

        receiving = Adw.PreferencesGroup(title=_("Receiving"))
        self.default_folder_row = Adw.ActionRow(
            title=_("Default save folder"), subtitle=self.save_dir
        )
        self.default_folder_row.add_prefix(
            Gtk.Image.new_from_icon_name("folder-symbolic")
        )
        folder_btn = Gtk.Button(icon_name="document-open-symbolic")
        folder_btn.set_tooltip_text(_("Change folder"))
        set_a11y_label(folder_btn, _("Change folder"))
        folder_btn.connect("clicked", lambda *_: self._on_change_default_folder())
        self.default_folder_row.add_suffix(folder_btn)
        receiving.add(self.default_folder_row)
        receiving.add(
            self._make_switch_row(
                "yes",
                _("Automatically accept incoming transfers"),
                subtitle=_("Passes --yes to croc; skips all confirmation prompts"),
            )
        )
        receiving.add(
            self._make_switch_row(
                "overwrite",
                _("Overwrite existing files without prompt"),
                subtitle=_("Passes --overwrite to croc"),
            )
        )
        page.add(receiving)

        general = Adw.PreferencesGroup(title=_("General Options"))
        general.add(self._make_switch_row("debug", _("Debug mode")))
        general.add(self._make_switch_row("no_compress", _("Disable compression")))
        general.add(self._make_switch_row("ask", _("Prompt sender and recipient")))
        general.add(self._make_switch_row("local", _("Force local connections")))
        general.add(
            self._make_switch_row("internal_dns", _("Use internal DNS resolver"))
        )
        general.add(
            self._make_entry_row(
                "multicast",
                _("Multicast address for local discovery"),
                tooltip="239.255.255.250",
            )
        )
        general.add(
            self._make_entry_row(
                "ip",
                _("Set sender IP if known"),
                tooltip="10.0.0.1:9009, [::1]:9009",
            )
        )
        general.add(
            self._make_entry_row(
                "throttle_upload",
                _("Throttle upload speed"),
                tooltip="500k",
            )
        )
        page.add(general)

        relay_proxy = Adw.PreferencesGroup(title=_("Relay and Proxy"))
        relay_proxy.add(
            self._make_entry_row(
                "relay", _("Relay address"), tooltip="37.27.244.215:9009"
            )
        )
        relay_proxy.add(
            self._make_entry_row(
                "relay6",
                _("IPv6 relay address"),
                tooltip="[2a01:4f9:c013:7b04::1]:9009",
            )
        )
        pass_row = Adw.PasswordEntryRow(title=_("Relay password"))
        pass_row.set_text(self.settings.get("pass", ""))
        pass_row.set_tooltip_text(_("Default: pass123"))
        pass_row.connect(
            "changed",
            lambda e: self.settings.update({"pass": e.get_text().strip()})
            or self.settings.save(),  # type: ignore[func-returns-value]
        )
        relay_proxy.add(pass_row)
        relay_proxy.add(self._make_entry_row("socks5", _("SOCKS5 proxy")))
        relay_proxy.add(self._make_entry_row("connect", _("HTTP proxy")))
        page.add(relay_proxy)

        sending = Adw.PreferencesGroup(title=_("Sending Options"))
        sending.add(
            self._make_entry_row(
                "default_code",
                _("Default custom transfer code"),
                tooltip=_("Optional – leave empty for a random code"),
            )
        )
        hash_options = [_("xxhash (default)"), "imohash", "md5"]
        hash_row = Adw.ComboRow(title=_("Hash algorithm"))
        hash_row.set_model(Gtk.StringList.new(hash_options))
        current_hash = self.settings.get("hash", "xxhash")
        hash_row.set_selected(
            hash_options.index(
                _("xxhash (default)") if current_hash == "xxhash" else current_hash
            )
            if current_hash in ("xxhash", "imohash", "md5")
            else 0
        )

        def on_hash_changed(c: Adw.ComboRow, *_: Any) -> None:
            label = c.get_selected_item().get_string()
            hash_val = "xxhash" if label.startswith("xxhash") else label
            self.settings.update({"hash": hash_val})
            self.settings.save()

        hash_row.connect("notify::selected", on_hash_changed)
        sending.add(hash_row)
        sending.add(self._make_switch_row("zip_folder", _("Zip folder before sending")))
        sending.add(self._make_switch_row("no_local", _("Disable local relay")))
        sending.add(self._make_switch_row("no_multi", _("Disable multiplexing")))
        sending.add(self._make_switch_row("git", _("Respect .gitignore")))
        port_row = Adw.SpinRow(
            title=_("Base port for relay"),
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
            or self.settings.save(),  # type: ignore[func-returns-value]
        )
        sending.add(port_row)
        transfers_row = Adw.SpinRow(
            title=_("Number of ports for transfers"),
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
            or self.settings.save(),  # type: ignore[func-returns-value]
        )
        sending.add(transfers_row)
        sending.add(
            self._make_switch_row(
                "qr",
                _("Show receive code as QR"),
                subtitle=_("Shows QR code in shell output"),
            )
        )
        page.add(sending)

        reset_group = Adw.PreferencesGroup(title=_("Reset"))
        reset_row = Adw.ActionRow(title=_("Reset all settings to default"))
        reset_btn = Gtk.Button(label=_("Reset"))
        reset_btn.add_css_class("destructive-action")
        reset_btn.connect(
            "clicked",
            lambda *_: (self._on_reset(), dlg.close()),
        )
        reset_row.add_suffix(reset_btn)
        reset_group.add(reset_row)
        page.add(reset_group)
