"""Internationalization helpers for Gator."""

from __future__ import annotations

import gettext
import locale
import os
from pathlib import Path

DOMAIN = "gator"
LOCALEDIR = os.environ.get(
    "GATOR_LOCALEDIR",
    str(Path(__file__).resolve().parents[2] / "share" / "locale"),
)

try:
    locale.bindtextdomain(DOMAIN, LOCALEDIR)
    locale.textdomain(DOMAIN)
    gettext.bindtextdomain(DOMAIN, LOCALEDIR)
    gettext.textdomain(DOMAIN)
    _gettext = gettext.gettext
except (AttributeError, OSError):
    _gettext = gettext.gettext


def _(message: str) -> str:
    """Translate *message* when a catalog is installed."""
    return _gettext(message)
