"""
processors/chunk_processor.py
===============================
Breaks a document's page stream into fixed-size chunks so that:
  * progress can be reported at a sensible granularity,
  * memory can be proactively reclaimed (gc.collect()) between chunks for
    very large / image-heavy PDFs,
  * a periodic "checkpoint" log line gives visibility into long-running
    jobs without flooding the log with one line per page.
"""

from __future__ import annotations

import gc
from typing import Iterator, List, Tuple

import fitz

from config import CONFIG
from utils.logger import logger


class ChunkProcessor:
    def __init__(self, chunk_size: int = None):
        self.chunk_size = chunk_size or CONFIG.chunk_size

    def iter_page_chunks(self, doc: fitz.Document) -> Iterator[List[Tuple[int, fitz.Page]]]:
        """Yield lists of (page_number [1-indexed], fitz.Page) tuples."""
        chunk: List[Tuple[int, fitz.Page]] = []
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            chunk.append((page_index + 1, page))
            if len(chunk) >= self.chunk_size:
                yield chunk
                chunk = []
                gc.collect()
        if chunk:
            yield chunk
            gc.collect()

    def checkpoint(self, pages_done: int, total_pages: int) -> None:
        pct = (pages_done / total_pages * 100) if total_pages else 0.0
        logger.info(f"Checkpoint: {pages_done}/{total_pages} pages processed ({pct:.1f}%)")
