"""
extractor/pdf_loader.py
========================
Thin, memory-conscious wrapper around a PyMuPDF (fitz) document.

Only one `fitz.Page` object is ever alive at a time when iterating -- the
generator yields, is consumed by the processor, and PyMuPDF's own page
cache is periodically cleared for very large documents so memory doesn't
grow unbounded across thousands of pages.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterator, Optional

import fitz  # PyMuPDF

from config import CONFIG
from utils.logger import logger


class PDFLoader:
    """Opens a PDF once and exposes safe, streaming page access."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._doc: Optional[fitz.Document] = None

    def open(self) -> fitz.Document:
        if self._doc is not None:
            return self._doc
        doc = fitz.open(str(self.path))
        if doc.is_encrypted:
            doc.authenticate("")
        self._doc = doc
        return doc

    def close(self) -> None:
        if self._doc is not None:
            self._doc.close()
            self._doc = None

    @property
    def page_count(self) -> int:
        return self.open().page_count

    @property
    def is_large_pdf(self) -> bool:
        return self.page_count >= CONFIG.large_pdf_page_threshold

    def file_hash(self, chunk_size: int = 1024 * 1024) -> str:
        """SHA-256 of the file, computed in chunks to avoid loading it whole."""
        h = hashlib.sha256()
        with open(self.path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def iter_pages(self) -> Iterator[fitz.Page]:
        """Yield pages one at a time; periodically flushes PyMuPDF's cache."""
        doc = self.open()
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            yield page
            # For very large documents, drop PyMuPDF's internal caches every
            # `chunk_size` pages to keep resident memory flat.
            if self.is_large_pdf and (page_index + 1) % CONFIG.chunk_size == 0:
                doc._reset_page_refs() if hasattr(doc, "_reset_page_refs") else None

    def get_document_metadata(self) -> dict:
        return dict(self.open().metadata or {})

    def __enter__(self) -> "PDFLoader":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
