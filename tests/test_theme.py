"""Unit tests for theme helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gator.theme import _new_gdk_rgba, rgba_to_hex


def test_rgba_to_hex():
    assert rgba_to_hex((1.0, 0.0, 0.5, 1.0)) == "#ff007f"
    assert rgba_to_hex((1.2, 0.0, 0.0, 1.0)) == "#ff0000"


def test_new_gdk_rgba_has_channels():
    rgba = _new_gdk_rgba()
    assert hasattr(rgba, "red")
    assert hasattr(rgba, "green")
    assert hasattr(rgba, "blue")
    assert hasattr(rgba, "alpha")
