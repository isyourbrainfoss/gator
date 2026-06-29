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


def test_qr_roundtrip_black_on_white(tmp_path):
    if not HAS_QR_GEN or not HAS_QR_SCAN:
        return
    import qrcode
    from PIL import ImageOps

    code = "1234-lion-stop-sofia"
    img = qrcode.make(code, error_correction=qrcode.constants.ERROR_CORRECT_H)
    path = tmp_path / "qr.png"
    img.save(path)
    assert scan_qr_from_image_path(str(path)) == code

    # Inverted (light-on-dark) photos should still decode
    inverted = ImageOps.invert(img.convert("L")).convert("RGB")
    inv_path = tmp_path / "qr-inverted.png"
    inverted.save(inv_path)
    assert scan_qr_from_image_path(str(inv_path)) == code
