"""
extractor/ocr.py
=================
Optional OCR fallback for scanned pages (pages with no usable text layer).
Only activated when `CONFIG.enable_ocr` is True AND pytesseract/Pillow are
importable AND the tesseract binary is available on PATH -- otherwise the
page is simply logged as "scanned / no text layer" and processing
continues without OCR (per the "processing should continue whenever
possible" requirement).
"""

from __future__ import annotations

from typing import Optional

import fitz

from config import CONFIG
from utils.logger import logger

_OCR_AVAILABLE: Optional[bool] = None


def ocr_is_available() -> bool:
    global _OCR_AVAILABLE
    if _OCR_AVAILABLE is not None:
        return _OCR_AVAILABLE

    if not CONFIG.enable_ocr:
        _OCR_AVAILABLE = False
        return False

    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
        pytesseract.get_tesseract_version()
        _OCR_AVAILABLE = True
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"OCR requested but unavailable ({exc}); continuing without OCR.")
        _OCR_AVAILABLE = False

    return _OCR_AVAILABLE


class OCRExtractor:
    """Rasterizes a page and runs Tesseract OCR on it."""

    def extract_text(self, page: fitz.Page) -> str:
        if not ocr_is_available():
            return ""

        import io
        import pytesseract
        from PIL import Image

        try:
            zoom = CONFIG.ocr_dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
            img_bytes = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(image)
            return text or ""
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"OCR failed on page {page.number + 1}: {exc}")
            return ""
