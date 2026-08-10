"""
processors/page_processor.py
==============================
Processes exactly one page: builds its PageStructure via the
StructureBuilder. A single bad page must never abort the whole document.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import fitz

from database.models import PageStructure
from parser.structure_builder import StructureBuilder
from utils.logger import logger


@dataclass
class PageProcessingResult:
    success: bool
    structure: Optional[PageStructure] = None
    error: Optional[str] = None


class PageProcessor:
    def __init__(self, structure_builder: StructureBuilder):
        self.structure_builder = structure_builder

    def process(self, doc: fitz.Document, page: fitz.Page,
                page_number: int) -> PageProcessingResult:
        try:
            structure = self.structure_builder.build_page(doc, page, page_number, None)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Page {page_number}: structure build failed: {exc}")
            return PageProcessingResult(success=False, error=str(exc))

        return PageProcessingResult(success=True, structure=structure)
