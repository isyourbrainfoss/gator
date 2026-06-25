"""Basic tests for qr helpers (must tolerate missing optional deps)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gator.qr import (
    HAS_QR_GEN,
    HAS_QR_SCAN,
    generate_qr_texture,
    scan_qr_from_image_path,
)


def test_flags_are_bools():
    assert isinstance(HAS_QR_GEN, bool)
    assert isinstance(HAS_QR_SCAN, bool)


def test_generate_graceful_without_deps(monkeypatch):
    # Even if deps present, we can force off for test of path
    monkeypatch.setattr("gator.qr.HAS_QR_GEN", False)
    assert generate_qr_texture("hello", "#000000", "#ffffff") is None


def test_scan_graceful(tmp_path):
    p = tmp_path / "no.png"
    p.write_bytes(b"not an image really")
    # Should not raise
    res = scan_qr_from_image_path(str(p))
    assert res is None or isinstance(res, str)
