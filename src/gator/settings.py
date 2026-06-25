"""settings.py – Centralised configuration loading, saving, and defaults.

Currently uses a JSON file in the user config dir as the backing store.
This is a non-Flatpak-friendly approach (direct FS writes).

For Flatpak / GSettings migration (see TASKS.md):
  - Add a GSettings XML schema (org.gator.Gator.gschema.xml)
  - Install via Meson + glib-compile-schemas
  - Replace dict access with a Gio.Settings-backed object or adapter
  - Keep this module's JSON path as a fallback when GSettings is unavailable
    (e.g. outside Flatpak or dev runs).

All call sites should go through load_settings() / save_settings() and
the DEFAULTS mapping so that adding new keys or changing defaults has
one place to update.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from gi.repository import GLib

logger = logging.getLogger(__name__)

# ── Application constants (source of truth) ──────────────────────────────────
APP_ID = "org.gator.Gator"
APP_NAME = "Gator"
APP_VERSION = "1.5"

CROC_BINARY = "croc"

# Unset sentinels — Gator omits these flags and lets croc use its own defaults.
DEFAULT_PORT = 0
DEFAULT_TRANSFERS = 0
DEFAULT_MULTICAST = ""
DEFAULT_RELAY = ""
DEFAULT_RELAY6 = ""
DEFAULT_HASH = ""
DEFAULT_CURVE = ""

# Croc built-in defaults (UI hints only; never passed unless the user sets a value).
CROC_DEFAULT_PORT = 9009
CROC_DEFAULT_TRANSFERS = 4
CROC_DEFAULT_MULTICAST = "239.255.255.250"
CROC_DEFAULT_HASH = "xxhash"
CROC_DEFAULT_CURVE = "p256"

# Pre-v10.4 croc relay defaults; clear so both sides use the same croc default.
LEGACY_RELAY = "37.27.244.215:9009"
LEGACY_RELAY6 = "[2a01:4f9:c013:7b04::1]:9009"

# Prefix used by croc when it prints the code (send side)
CODE_IS_PREFIX = "Code is: "

# GSettings schema id (for future migration)
GSETTINGS_SCHEMA_ID = "org.gator.Gator"

# ── Default settings values ──────────────────────────────────────────────────
# Keys here are the canonical set. Values are the baked-in defaults.
DEFAULTS: dict[str, Any] = {
    # Appearance
    "color_scheme": "default",
    # Receiving
    "save_dir": None,  # resolved at runtime to XDG_DOWNLOAD or $HOME
    "yes": True,  # GUI has no terminal prompt; disable in prefs to review each transfer
    "overwrite": False,
    # General
    "debug": False,
    "no_compress": False,
    "ask": False,
    "local": False,
    "internal_dns": False,
    "multicast": DEFAULT_MULTICAST,  # empty → croc default
    "ip": "",
    "throttle_upload": "",
    # Relay / Proxy
    "relay": DEFAULT_RELAY,
    "relay6": DEFAULT_RELAY6,
    "pass": "",  # default inside croc is "pass123" but we leave empty -> croc default
    "socks5": "",
    "connect": "",
    # Sending
    "default_code": "",
    "hash": DEFAULT_HASH,
    "zip_folder": False,
    "no_local": False,
    "no_multi": False,
    "git": False,
    "port": DEFAULT_PORT,
    "transfers": DEFAULT_TRANSFERS,
    "qr": False,
    "show_qr_image": True,
    "show_shell_output": False,
    # Advanced / hidden (rarely exposed in UI)
    "curve": DEFAULT_CURVE,
    "testing": False,
    "quiet": False,
    "disable_clipboard": False,
    "extended_clipboard": False,
}


def get_config_dir() -> Path:
    """Return (and ensure) the directory used for the JSON fallback config."""
    cfg = Path(GLib.get_user_config_dir()) / "gator"
    cfg.mkdir(parents=True, exist_ok=True)
    return cfg


def get_config_file() -> Path:
    return get_config_dir() / "config.json"


def get_default_save_dir() -> str:
    """Resolve the best default save location."""
    d = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
    return d or str(Path.home())


def _resolve_save_dir(settings: dict[str, Any]) -> str:
    sd = settings.get("save_dir")
    if sd:
        return sd
    return get_default_save_dir()


def merge_with_defaults(settings: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict containing defaults + user overrides.

    Does *not* mutate the input.
    """
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in settings.items() if k in DEFAULTS})
    # Special case: save_dir resolution happens at access time in app
    return merged


def reset_to_defaults() -> dict[str, Any]:
    """Return a fresh default settings dict and persist it."""
    s: dict[str, Any] = {}
    save_settings(s)
    return s


def validate_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Clamp / normalise a few known fields. Returns a (possibly new) dict."""
    s = dict(settings)
    # Port: 0 = unset (croc default)
    try:
        p = int(s.get("port", DEFAULT_PORT))
        s["port"] = 0 if p <= 0 else max(1, min(65535, p))
    except Exception:
        s["port"] = DEFAULT_PORT
    # Transfers: 0 = unset (croc default)
    try:
        t = int(s.get("transfers", DEFAULT_TRANSFERS))
        s["transfers"] = 0 if t <= 0 else max(1, min(100, t))
    except Exception:
        s["transfers"] = DEFAULT_TRANSFERS
    # Multicast: empty = croc default
    s["multicast"] = (s.get("multicast") or "").strip()
    # Hash: empty = croc default; otherwise whitelist
    h = (s.get("hash") or "").strip()
    if h and h not in ("xxhash", "imohash", "md5"):
        s["hash"] = DEFAULT_HASH
    else:
        s["hash"] = h
    # Curve: empty = croc default
    s["curve"] = (s.get("curve") or "").strip()
    # Color scheme
    if s.get("color_scheme") not in ("default", "light", "dark"):
        s["color_scheme"] = "default"
    return s


PY_TO_GS = {
    "color_scheme": "color-scheme",
    "save_dir": "save-dir",
    "no_compress": "no-compress",
    "internal_dns": "internal-dns",
    "throttle_upload": "throttle-upload",
    "default_code": "default-code",
    "zip_folder": "zip-folder",
    "no_local": "no-local",
    "no_multi": "no-multi",
    "disable_clipboard": "disable-clipboard",
    "extended_clipboard": "extended-clipboard",
    "show_qr_image": "show-qr-image",
    "show_shell_output": "show-shell-output",
}
GS_TO_PY = {v: k for k, v in PY_TO_GS.items()}


class GatorSettings(dict):
    """Settings container that prefers GSettings (for Flatpak/GNOME) and
    falls back to JSON file. Acts mostly like a dict for compatibility.
    """

    def __init__(self) -> None:
        super().__init__()
        self._gsettings: Any = None
        self._json_file: Path | None = None

        try:
            from gi.repository import Gio

            source = Gio.SettingsSchemaSource.get_default()
            if (
                source is not None
                and source.lookup(GSETTINGS_SCHEMA_ID, True) is not None
            ):
                self._gsettings = Gio.Settings.new(GSETTINGS_SCHEMA_ID)
            else:
                raise RuntimeError("GSettings schema not installed")
        except Exception:
            self._gsettings = None
            self._json_file = get_config_file()
            raw: dict[str, Any] = {}
            if self._json_file.is_file():
                try:
                    with open(self._json_file) as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        raw = data
                except Exception as e:
                    logger.warning("Could not load JSON settings: %s", e)
            merged = merge_with_defaults(raw)
            validated = validate_settings(merged)
            super().update(validated)
        self._migrate_stale_settings()

    def _migrate_stale_settings(self) -> None:
        if self.get("relay") == LEGACY_RELAY:
            self["relay"] = ""
        if self.get("relay6") == LEGACY_RELAY6:
            self["relay6"] = ""
        # Older Gator versions baked croc defaults into settings; clear them.
        if self.get("multicast") == CROC_DEFAULT_MULTICAST:
            self["multicast"] = ""
        if self.get("hash") == CROC_DEFAULT_HASH:
            self["hash"] = ""
        if self.get("curve") == CROC_DEFAULT_CURVE:
            self["curve"] = ""
        if self.get("port") == CROC_DEFAULT_PORT:
            self["port"] = 0
        if self.get("transfers") == CROC_DEFAULT_TRANSFERS:
            self["transfers"] = 0

    def _gs_key(self, py_key: str) -> str:
        return PY_TO_GS.get(py_key, py_key.replace("_", "-"))

    def __getitem__(self, key: str) -> Any:
        if self._gsettings is not None:
            gkey = self._gs_key(key)
            try:
                # Check key exists in schema to avoid hard GIO errors
                if gkey not in self._gsettings.list_keys():
                    raise KeyError(gkey)
                variant = self._gsettings.get_value(gkey)
                val = variant.unpack()
                if key == "save_dir" and not val:
                    return get_default_save_dir()
                return val
            except Exception as e:
                logger.debug("GSettings read failed for %s: %s", key, e)
        try:
            return super().__getitem__(key)
        except KeyError:
            return DEFAULTS.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        if self._gsettings is not None:
            gkey = self._gs_key(key)
            try:
                if gkey not in self._gsettings.list_keys():
                    logger.warning(
                        "GSettings key %s missing from installed schema; "
                        "rebuild/reinstall the app to persist this setting",
                        gkey,
                    )
                    super().__setitem__(key, value)
                    return
                if isinstance(value, bool):
                    self._gsettings.set_boolean(gkey, value)
                elif isinstance(value, (int, float)):
                    self._gsettings.set_int(gkey, int(value))
                else:
                    self._gsettings.set_string(
                        gkey, str(value) if value is not None else ""
                    )
                return
            except Exception as e:
                logger.warning("GSettings write failed for %s: %s", key, e)
        super().__setitem__(key, value)
        if self._json_file:
            self.save()

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except Exception:
            return default

    def update(self, other: dict[str, Any] = None, **kwargs: Any) -> None:  # type: ignore[override]
        if other is not None:
            for k, v in other.items():
                self[k] = v
        for k, v in kwargs.items():
            self[k] = v
        if not self._gsettings and self._json_file:
            self.save()

    def clear(self) -> None:
        if self._gsettings is not None:
            for py_key, default_val in DEFAULTS.items():
                try:
                    self[py_key] = default_val
                except Exception:
                    pass
        else:
            super().clear()
            if self._json_file:
                self.save()

    def save(self) -> None:
        """Persist if using JSON fallback."""
        if self._gsettings is not None:
            # GSettings persists automatically
            return
        if self._json_file:
            try:
                # Only persist keys that differ from defaults or are user set
                to_save = {k: v for k, v in self.items() if v != DEFAULTS.get(k)}
                with open(self._json_file, "w") as f:
                    json.dump(to_save, f, indent=2)
            except OSError as e:
                logger.error("Could not save JSON settings: %s", e)

    def reset_to_defaults(self) -> None:
        self.clear()


# Backwards-compatible functions (used by some old call sites and wrappers)
def load_settings() -> dict[str, Any]:
    """Return a snapshot. Prefer the GatorSettings instance where possible."""
    s = GatorSettings()
    return dict(s)


def save_settings(settings: dict[str, Any]) -> None:
    """Best-effort save for dict snapshots."""
    s = GatorSettings()
    for k, v in settings.items():
        s[k] = v
    s.save()


def get_settings() -> dict[str, Any]:
    """Return current settings (merged/validated)."""
    return dict(GatorSettings())
