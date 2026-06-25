"""qr.py – Optional QR code generation and scanning helpers."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    import qrcode
    from PIL import Image as PILImage  # type: ignore

    HAS_QR_GEN = True
except Exception:
    HAS_QR_GEN = False
    qrcode = None  # type: ignore
    PILImage = None  # type: ignore


def generate_qr_texture(
    code: str,
    foreground: str,
    background: str,
) -> Any | None:
    """Return a Gdk.Texture for the QR or None on failure / no deps."""
    if not HAS_QR_GEN:
        return None
    try:
        qr = qrcode.QRCode(box_size=10, border=4)  # type: ignore
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


def scan_qr_from_image_path(path: str) -> str | None:
    """Decode first QR found in image file. Returns code str or None."""
    if not HAS_QR_SCAN or PILImage is None:
        return None
    try:
        img = PILImage.open(path).convert("RGB")  # type: ignore
        decoded = decode(img)
        if decoded:
            return decoded[0].data.decode()
    except Exception as e:
        logger.warning("QR scan failed: %s", e)
    return None
