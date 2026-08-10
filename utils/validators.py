"""
utils/validators.py
====================
Pre-flight validation for PDF files, plus small data-sanity helpers used
throughout the extraction/parsing pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


@dataclass
class ValidationResult:
    is_valid: bool
    is_encrypted: bool = False
    is_empty: bool = False
    page_count: int = 0
    error: Optional[str] = None


def validate_pdf(path: Path) -> ValidationResult:
    """Open the PDF just far enough to classify it before real processing.

    Never raises -- all failure modes are captured in the returned
    ValidationResult so the caller can decide how to proceed / log it.
    """
    path = Path(path)

    if not path.exists():
        return ValidationResult(is_valid=False, error=f"File not found: {path}")

    if path.stat().st_size == 0:
        return ValidationResult(is_valid=False, is_empty=True, error="File is 0 bytes")

    try:
        doc = fitz.open(str(path))
    except Exception as exc:  # noqa: BLE001 - we want to catch any PDF corruption issue
        return ValidationResult(is_valid=False, error=f"Failed to open PDF: {exc}")

    try:
        if doc.is_encrypted:
            # Try an empty-password unlock (common for "restricted" PDFs).
            if not doc.authenticate(""):
                doc.close()
                return ValidationResult(
                    is_valid=False, is_encrypted=True,
                    error="PDF is password protected and could not be opened with an empty password",
                )

        page_count = doc.page_count
        if page_count == 0:
            doc.close()
            return ValidationResult(is_valid=False, is_empty=True, page_count=0,
                                     error="PDF has zero pages")

        doc.close()
        return ValidationResult(is_valid=True, page_count=page_count)

    except Exception as exc:  # noqa: BLE001
        try:
            doc.close()
        except Exception:
            pass
        return ValidationResult(is_valid=False, error=f"Error inspecting PDF: {exc}")


def is_blank_text(text: Optional[str]) -> bool:
    return text is None or not text.strip()


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
