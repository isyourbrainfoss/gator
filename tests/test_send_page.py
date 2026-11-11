"""Send page: secondary actions stay out of the way until there is a selection."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def send_page(tmp_path, monkeypatch):
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        # Building GTK widgets without a display segfaults (headless CI).
        pytest.skip("no display for GTK widgets")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("HOME", str(tmp_path))
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw

        Adw.init()
        from gator.send_page import SendPage
        from gator.settings import GatorSettings
    except (ImportError, ValueError, RuntimeError) as e:  # pragma: no cover
        pytest.skip(f"GTK/libadwaita unavailable: {e}")
    return SendPage(GatorSettings())


def test_empty_page_hides_exclude_and_clear(send_page):
    assert not send_page.exclude_btn.get_visible()
    assert not send_page.clear_btn.get_visible()
    assert not send_page.send_start_btn.get_sensitive()
    assert send_page.send_start_btn.get_tooltip_text()


def test_selection_reveals_exclude_and_clear(send_page, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hi")
    send_page.refresh_file_list([str(f)], [], "")
    assert send_page.exclude_btn.get_visible()
    assert send_page.clear_btn.get_visible()
    assert send_page.send_start_btn.get_sensitive()
    assert send_page.send_start_btn.get_tooltip_text() is None


def test_text_only_shows_clear_but_not_exclude(send_page):
    send_page.refresh_file_list([], [], "hello")
    assert not send_page.exclude_btn.get_visible()
    assert send_page.clear_btn.get_visible()
