"""Smoke test: the application object must construct (regression for a
startup AttributeError that crashed every launch, including the Flatpak)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_gator_app_constructs(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("HOME", str(tmp_path))
    try:
        from gator.app import GatorApp
    except (ImportError, ValueError) as e:  # pragma: no cover - missing GTK/Adw
        pytest.skip(f"GTK/libadwaita unavailable: {e}")
    app = GatorApp()
    assert app.get_application_id() == "org.gator.Gator"
    assert app.lookup_action("quit") is not None
