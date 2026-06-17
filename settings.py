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


def load_settings() -> dict[str, Any]:
    """Load settings from JSON (or return {} on any problem).

    The returned dict is a plain mutable dict (no live binding).
    Callers are expected to call save_settings after mutation.
    """
    cfg = get_config_file()
    if cfg.is_file():
        try:
            with open(cfg) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            logger.warning("Config file did not contain a dict; resetting")
            return {}
        except json.JSONDecodeError as e:
            logger.warning("Config file is corrupt, resetting to defaults: %s", e)
            return {}
        except OSError as e:
            logger.warning("Could not read config file: %s", e)
            return {}
    return {}


def save_settings(settings: dict[str, Any]) -> None:
    """Persist *settings* to the JSON config file."""
    cfg = get_config_file()
    try:
        with open(cfg, "w") as f:
            json.dump(settings, f, indent=2)
    except OSError as e:
        logger.error("Could not save settings: %s", e)
        # Note: GUI layer adds a toast via idle_add in its wrapper if needed.


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


def get_settings() -> dict[str, Any]:
    """Convenience: load + merge + validate (non-mutating result)."""
    raw = load_settings()
    merged = merge_with_defaults(raw)
    return validate_settings(merged)


# ── GSettings adapter skeleton (not wired by default) ────────────────────────
#
# def load_settings_gsettings() -> dict[str, Any]:
#     """Attempt to load via Gio.Settings (Flatpak-friendly). Falls back to JSON."""
#     try:
#         from gi.repository import Gio
#         settings = Gio.Settings.new(GSETTINGS_SCHEMA_ID)
#         # Example: read known keys and map to our dict shape...
#         # (schema keys would use - instead of _ or follow our naming)
#         # For now this is illustrative.
#         return {}  # real impl would populate from settings.get_*()
#     except Exception:
#         return load_settings()
#
# A matching org.croc.CrocGUI.gschema.xml would live under data/ and be
# compiled/installed by Meson.  See TASKS.md.
