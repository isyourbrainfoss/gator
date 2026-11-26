"""Unit tests for settings module (no GTK widgets involved)."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import gator.settings as S


def test_defaults_present():
    assert "port" in S.DEFAULTS
    assert S.DEFAULTS["port"] == 0
    assert S.DEFAULTS["transfers"] == 0
    assert S.DEFAULTS["multicast"] == ""
    assert S.DEFAULTS["hash"] == ""
    assert S.DEFAULTS["curve"] == ""
    assert S.DEFAULTS["color_scheme"] == "default"
    assert S.DEFAULTS["rename"] is False


def test_bundled_croc_version_pin():
    assert S.BUNDLED_CROC_VERSION == "11.6.6"
    root = Path(__file__).resolve().parents[1]
    archive = (
        "https://github.com/schollz/croc/archive/refs/tags/"
        f"v{S.BUNDLED_CROC_VERSION}.tar.gz"
    )
    sha = "7b70ea161a1d6343b4499c81280d9650fadb1c298d3be96bbc54a2e8d8cd0c21"
    for name in ("org.gator.Gator.yml", "org.gator.Gator.devel.yml"):
        text = (root / name).read_text()
        assert archive in text
        assert sha in text
    ci = (root / ".github/workflows/ci.yml").read_text()
    tarball = f"croc_v{S.BUNDLED_CROC_VERSION}_Linux-64bit.tar.gz"
    assert tarball in ci
    assert f"download/v{S.BUNDLED_CROC_VERSION}/{tarball}" in ci


def test_parse_croc_version_output():
    assert S.parse_croc_version_output("croc version v11.6.6\n") == "11.6.6"
    assert S.parse_croc_version_output("croc version 11.6.6") == "11.6.6"
    assert S.parse_croc_version_output("  croc version v11.6.6  ") == "11.6.6"
    assert S.parse_croc_version_output("croc version v11.6.6-1-gabcdef") == (
        "11.6.6-1-gabcdef"
    )
    assert S.parse_croc_version_output("") is None
    assert S.parse_croc_version_output("croc: command not found") is None


def test_format_croc_version_label():
    S.set_runtime_croc_version(None)
    assert S.format_croc_version_label("croc version v11.6.6") == "croc v11.6.6"
    assert S.format_croc_version_label("croc version 11.6.6\n") == "croc v11.6.6"
    assert S.format_croc_version_label("11.6.5") == "croc v11.6.5"
    assert S.format_croc_version_label("v11.6.5") == "croc v11.6.5"
    assert S.format_croc_version_label(None) == f"croc v{S.BUNDLED_CROC_VERSION}"
    assert S.format_croc_version_label("") == f"croc v{S.BUNDLED_CROC_VERSION}"
    assert S.format_croc_version_label("not a version") == (
        f"croc v{S.BUNDLED_CROC_VERSION}"
    )


def test_runtime_croc_version_overrides_pin():
    S.set_runtime_croc_version(None)
    try:
        assert S.get_runtime_croc_version() is None
        assert S.croc_version_label() == "croc v11.6.6"
        S.set_runtime_croc_version("croc version v11.6.5")
        assert S.get_runtime_croc_version() == "11.6.5"
        assert S.croc_version_label() == "croc v11.6.5"
        S.set_runtime_croc_version("not croc")
        assert S.get_runtime_croc_version() is None
        assert S.croc_version_label() == "croc v11.6.6"
    finally:
        S.set_runtime_croc_version(None)


def test_about_text_includes_croc_version():
    comments = S.about_comments("Secure file transfer made beautiful", "croc v11.6.6")
    assert comments == "Secure file transfer made beautiful\ncroc v11.6.6"
    assert comments.splitlines()[-1] == "croc v11.6.6"
    debug = S.about_debug_info("1.6.4", True, False, "croc v11.6.6")
    assert "Gator 1.6.4\n" in debug
    assert "croc v11.6.6\n" in debug
    assert "QR generate: True\n" in debug
    assert "QR scan: False\n" in debug
    # No runtime probe yet: comments and debug fall back to the pin.
    S.set_runtime_croc_version(None)
    assert S.about_comments("Hello").endswith("\ncroc v11.6.6")
    assert "croc v11.6.6" in S.about_debug_info("1.6.4", False, False)


def test_app_version_matches_project_metadata():
    """About dialog version must track meson.build / pyproject.toml."""
    import re

    root = Path(__file__).resolve().parents[1]
    meson = re.search(
        r"version:\s*'([^']+)'", (root / "meson.build").read_text()
    ).group(1)
    pyproj = re.search(
        r'^version\s*=\s*"([^"]+)"', (root / "pyproject.toml").read_text(), re.M
    ).group(1)
    assert S.APP_VERSION == meson == pyproj


def test_validate_clamps_port():
    s = {"port": 999999}
    out = S.validate_settings(s)
    assert out["port"] == 65535

    s = {"port": 0}
    out = S.validate_settings(s)
    assert out["port"] == 0


def test_validate_hash():
    assert S.validate_settings({"hash": "foo"})["hash"] == ""
    assert S.validate_settings({"hash": ""})["hash"] == ""
    assert S.validate_settings({"hash": "imohash"})["hash"] == "imohash"
    assert S.validate_settings({"hash": "highway"})["hash"] == "highway"


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
