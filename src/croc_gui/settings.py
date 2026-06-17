"""settings.py – Centralised configuration loading, saving, and defaults.

Currently uses a JSON file in the user config dir as the backing store.
This is a non-Flatpak-friendly approach (direct FS writes).

For Flatpak / GSettings migration (see TASKS.md):
  - Add a GSettings XML schema (org.croc.CrocGUI.gschema.xml)
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
APP_ID = "org.croc.CrocGUI"
APP_NAME = "Croc GUI"
APP_VERSION = "1.2"

CROC_BINARY = "croc"

DEFAULT_PORT = 9009
DEFAULT_TRANSFERS = 4
DEFAULT_MULTICAST = "239.255.255.250"
DEFAULT_RELAY = "37.27.244.215:9009"
DEFAULT_RELAY6 = "[2a01:4f9:c013:7b04::1]:9009"

# Prefix used by croc when it prints the code (send side)
CODE_IS_PREFIX = "Code is: "

# GSettings schema id (for future migration)
GSETTINGS_SCHEMA_ID = "org.croc.CrocGUI"

# ── Default settings values ──────────────────────────────────────────────────
# Keys here are the canonical set. Values are the baked-in defaults.
DEFAULTS: dict[str, Any] = {
    # Appearance
    "color_scheme": "default",
    # Receiving
    "save_dir": None,  # resolved at runtime to XDG_DOWNLOAD or $HOME
    "yes": False,
    "overwrite": False,
    # General
    "debug": False,
    "no_compress": False,
    "ask": False,
    "local": False,
    "internal_dns": False,
    "multicast": DEFAULT_MULTICAST,
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
    "hash": "xxhash",
    "zip_folder": False,
    "no_local": False,
    "no_multi": False,
    "git": False,
    "port": DEFAULT_PORT,
    "transfers": DEFAULT_TRANSFERS,
    "qr": False,
    # Advanced / hidden (rarely exposed in UI)
    "curve": "p256",
    "testing": False,
    "quiet": False,
    "disable_clipboard": False,
    "extended_clipboard": False,
}


def get_config_dir() -> Path:
    """Return (and ensure) the directory used for the JSON fallback config."""
    cfg = Path(GLib.get_user_config_dir()) / "croc-gui"
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
    # Port
    try:
        p = int(s.get("port", DEFAULT_PORT))
        s["port"] = max(1, min(65535, p))
    except Exception:
        s["port"] = DEFAULT_PORT
    # Transfers
    try:
        t = int(s.get("transfers", DEFAULT_TRANSFERS))
        s["transfers"] = max(1, min(100, t))
    except Exception:
        s["transfers"] = DEFAULT_TRANSFERS
    # Multicast: if empty reset to default
    mc = (s.get("multicast") or "").strip()
    if not mc:
        s["multicast"] = DEFAULT_MULTICAST
    # Hash whitelist
    if s.get("hash") not in ("xxhash", "imohash", "md5"):
        s["hash"] = "xxhash"
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
}
GS_TO_PY = {v: k for k, v in PY_TO_GS.items()}


class CrocSettings(dict):
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

    def _gs_key(self, py_key: str) -> str:
        return PY_TO_GS.get(py_key, py_key.replace("_", "-"))

    def __getitem__(self, key: str) -> Any:
        if self._gsettings is not None:
            gkey = self._gs_key(key)
            try:
                # Try types in likely order
                try:
                    return self._gsettings.get_boolean(gkey)
                except Exception:
                    pass
                try:
                    return self._gsettings.get_int(gkey)
                except Exception:
                    pass
                val = self._gsettings.get_string(gkey)
                if key == "save_dir" and not val:
                    return get_default_save_dir()
                if val == "" and key in DEFAULTS:
                    # fall back for empty string keys that have meaningful defaults
                    return DEFAULTS[key]
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
    """Return a snapshot. Prefer the CrocSettings instance where possible."""
    s = CrocSettings()
    return dict(s)


def save_settings(settings: dict[str, Any]) -> None:
    """Best-effort save for dict snapshots."""
    s = CrocSettings()
    for k, v in settings.items():
        s[k] = v
    s.save()


def get_settings() -> dict[str, Any]:
    """Return current settings (merged/validated)."""
    return dict(CrocSettings())


def reset_to_defaults() -> dict[str, Any]:
    s = CrocSettings()
    s.reset_to_defaults()
    return dict(s)
