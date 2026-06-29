"""qr.py – Optional QR code generation and scanning helpers."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    import qrcode
    from PIL import Image as PILImage  # type: ignore
    from PIL import ImageEnhance, ImageOps  # type: ignore
    from qrcode.constants import ERROR_CORRECT_H  # type: ignore

    HAS_QR_GEN = True
except Exception:
    HAS_QR_GEN = False
    qrcode = None  # type: ignore
    PILImage = None  # type: ignore
    ImageEnhance = None  # type: ignore
    ImageOps = None  # type: ignore
    ERROR_CORRECT_H = None  # type: ignore


def generate_qr_texture(
    code: str,
    foreground: str,
    background: str,
) -> Any | None:
    """Return a Gdk.Texture for the QR or None on failure / no deps."""
    if not HAS_QR_GEN:
        return None
    try:
        qr = qrcode.QRCode(  # type: ignore
            box_size=10,
            border=4,
            error_correction=ERROR_CORRECT_H,
        )
        qr.add_data(code)
        qr.make(fit=True)
        img = qr.make_image(fill_color=foreground, back_color=background)
        import io

        from gi.repository import Gdk, GLib

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Gdk.Texture.new_from_bytes(GLib.Bytes.new(buf.getvalue()))
    except Exception as e:
        logger.warning("QR generation failed: %s", e)
        return None


_lib_path = os.environ.get("LD_LIBRARY_PATH", "")
if "/app/lib" not in _lib_path:
    os.environ["LD_LIBRARY_PATH"] = "/app/lib:" + _lib_path

try:
    from pyzbar.pyzbar import decode  # type: ignore

    HAS_QR_SCAN = True
except Exception:
    HAS_QR_SCAN = False
    decode = None  # type: ignore


def _decode_first(image: Any) -> str | None:
    if decode is None:
        return None
    for result in decode(image):
        data = result.data.decode("utf-8", errors="replace").strip()
        if data:
            return data
    return None


def _scan_variants(image: Any) -> str | None:
    """Try several preprocessed variants (photos of screens need extra passes)."""
    if PILImage is None or ImageOps is None or ImageEnhance is None:
        return None
    try:
        base = ImageOps.exif_transpose(image)
    except Exception:
        base = image

    variants: list[Any] = []
    rgb = base.convert("RGB")
    gray = base.convert("L")
    variants.extend([rgb, gray, ImageOps.invert(gray)])
    try:
        variants.append(ImageOps.autocontrast(gray))
    except Exception:
        pass
    try:
        variants.append(ImageEnhance.Contrast(gray).enhance(2.0))
    except Exception:
        pass

    width, height = rgb.size
    long_edge = max(width, height)
    scales = [1.0]
    if long_edge > 1600:
        scales.append(1600 / long_edge)
    if long_edge < 400:
        scales.append(400 / long_edge)

    for variant in variants:
        for scale in scales:
            candidate = variant
            if scale != 1.0:
                new_size = (
                    max(1, int(width * scale)),
                    max(1, int(height * scale)),
                )
                resample = getattr(PILImage, "Resampling", PILImage).LANCZOS
                candidate = variant.resize(new_size, resample)
            found = _decode_first(candidate)
            if found:
                return found
    return None


def scan_qr_from_image_path(path: str) -> str | None:
    """Decode first QR found in image file. Returns code str or None."""
    if not HAS_QR_SCAN or PILImage is None:
        return None
    try:
        with PILImage.open(path) as img:
            return _scan_variants(img)
    except Exception as e:
        logger.warning("QR scan failed for %s: %s", path, e)
    return None
