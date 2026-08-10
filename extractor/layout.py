"""
extractor/layout.py
====================
Page-geometry-aware extraction: header/footer zone detection.
"""

from __future__ import annotations

from typing import List, Tuple

import fitz

from config import CONFIG
from extractor.text import Block


class LayoutExtractor:
    def get_page_dimensions(self, page: fitz.Page) -> Tuple[float, float, int]:
        rect = page.rect
        rotation = page.rotation or 0
        return float(rect.width), float(rect.height), int(rotation)

    def split_header_body_footer(
        self, blocks: List[Block], page_height: float
    ) -> Tuple[List[Block], List[Block], List[Block]]:
        """Partition text blocks into (header_blocks, body_blocks, footer_blocks)."""
        header_limit = page_height * CONFIG.header_zone_ratio
        footer_limit = page_height * (1 - CONFIG.footer_zone_ratio)

        headers, body, footers = [], [], []
        for block in blocks:
            if block.block_type != "text" or not block.text:
                continue
            y_center = (block.bbox[1] + block.bbox[3]) / 2.0
            if y_center <= header_limit:
                headers.append(block)
            elif y_center >= footer_limit:
                footers.append(block)
            else:
                body.append(block)
        return headers, body, footers
