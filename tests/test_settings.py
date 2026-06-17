"""Unit tests for settings module (no GTK widgets involved)."""

from unittest.mock import patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import croc_gui.settings as S


def test_defaults_present():
    assert "port" in S.DEFAULTS
    assert S.DEFAULTS["port"] == S.DEFAULT_PORT
    assert S.DEFAULTS["color_scheme"] == "default"


def test_validate_clamps_port():
    s = {"port": 999999}
    out = S.validate_settings(s)
    assert out["port"] == 65535

    s = {"port": 0}
    out = S.validate_settings(s)
    assert out["port"] == 1


def test_validate_hash():
    assert S.validate_settings({"hash": "foo"})["hash"] == "xxhash"
    assert S.validate_settings({"hash": "imohash"})["hash"] == "imohash"


def test_merge_with_defaults():
    user = {"port": 1234, "foo": "bar"}  # foo ignored
    m = S.merge_with_defaults(user)
    assert m["port"] == 1234
    assert m["color_scheme"] == "default"
    assert "foo" not in m


def test_load_save_roundtrip(tmp_path, monkeypatch):
    # Force the module to use a temp config dir/file
    fake_cfg_dir = tmp_path / "cfg"
    fake_file = fake_cfg_dir / "config.json"
    fake_cfg_dir.mkdir(parents=True, exist_ok=True)

    with (
        patch.object(S, "get_config_dir", return_value=fake_cfg_dir),
        patch.object(S, "get_config_file", return_value=fake_file),
    ):
        data = {"port": 4321, "debug": True}
        S.save_settings(data)
        assert fake_file.is_file()
        loaded = S.load_settings()
        assert loaded["port"] == 4321
        assert loaded["debug"] is True


def test_get_default_save_dir():
    d = S.get_default_save_dir()
    assert isinstance(d, str) and len(d) > 0
