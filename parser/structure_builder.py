"""
parser/structure_builder.py
=============================
Simplified structure builder that extracts paragraphs (short/long),
images, and tables from a single PDF page.
"""

from __future__ import annotations

from typing import List

import fitz

from database.models import (
    PageStructure, ParagraphRecord, ImageRecord
)
from extractor.images import ExtractedImage, ImageExtractor
from extractor.layout import LayoutExtractor
from extractor.tables import TableExtractor
from extractor.text import Line, TextExtractor
from parser.heading_parser import HeadingParser
from parser.paragraph_parser import ParagraphParser

# Threshold (characters) above which a paragraph is considered "long"
_LONG_PARAGRAPH_THRESHOLD = 300


class StructureBuilder:
    def __init__(self, table_extractor: TableExtractor, image_extractor: ImageExtractor):
        self.text_extractor = TextExtractor()
        self.layout_extractor = LayoutExtractor()
        self.heading_parser = HeadingParser()
        self.paragraph_parser = ParagraphParser()
        self.table_extractor = table_extractor
        self.image_extractor = image_extractor

    def build_page(self, doc: fitz.Document, page: fitz.Page, page_number: int,
                   _section_stack) -> PageStructure:
        """Build a simplified PageStructure for one page."""

        _, height, _ = self.layout_extractor.get_page_dimensions(page)
        blocks = self.text_extractor.extract_blocks(page)
        _, body_blocks, _ = self.layout_extractor.split_header_body_footer(blocks, height)

        # Extract tables first so we can exclude their text from paragraphs
        tables = []
        try:
            tables = self.table_extractor.extract_tables_for_page(page_number - 1)
        except Exception:
            pass

        body_lines: List[Line] = [
            line for b in body_blocks for line in b.lines
            if not self._line_inside_any_table(line, tables)
        ]

        classified = self.heading_parser.classify_lines(body_lines)

        # Collect headings with their vertical position for association
        headings_map = []
        for cl in classified:
            if cl.is_heading:
                headings_map.append((cl.line.bbox, cl.line.text.strip()))

        # Build raw paragraphs
        raw_paragraphs, _ = self.paragraph_parser.build(classified)

        # Convert to ParagraphRecord, attaching nearest heading above each paragraph
        paragraphs: List[ParagraphRecord] = []
        for rp in raw_paragraphs:
            text = rp.text.strip()
            if not text:
                continue
            best_heading = self._find_heading_above(rp.bbox.y0, headings_map)
            is_long = len(text) > _LONG_PARAGRAPH_THRESHOLD
            paragraphs.append(ParagraphRecord(
                heading=best_heading,
                text=text,
                is_long=is_long
            ))

        # Give each table a title from nearest heading above it
        final_tables: List[TableRecord] = []
        for t in tables:
            title = self._find_heading_above(t.bbox.y0, headings_map)
            # Fall back to nearest paragraph text if no heading found
            if not title:
                for rp in raw_paragraphs:
                    if rp.bbox.y1 <= t.bbox.y0:
                        title = rp.text.strip()
            if not title:
                title = "Table"
            if len(title) > 80:
                title = title[:77] + "..."
            t.title = title
            final_tables.append(t)

        # Extract images with captions
        images: List[ImageRecord] = []
        try:
            raw_images = self.image_extractor.extract_images_for_page(doc, page, page_number)
            for img in raw_images:
                img_y = (img.bbox.y0 + img.bbox.y1) / 2.0
                caption = self._find_nearest_caption(img_y, raw_paragraphs)
                images.append(ImageRecord(
                    caption=caption,
                    file_path=img.file_path
                ))
        except Exception:
            pass

        return PageStructure(
            paragraphs=paragraphs,
            tables=final_tables,
            images=images
        )

    # -- helpers ---------------------------------------------------------------

    def _line_inside_any_table(self, line: Line, tables) -> bool:
        if not tables:
            return False
        lx0, ly0, lx1, ly1 = line.bbox
        cx, cy = (lx0 + lx1) / 2.0, (ly0 + ly1) / 2.0
        margin = 2.0
        for t in tables:
            if (t.bbox.x0 - margin <= cx <= t.bbox.x1 + margin
                    and t.bbox.y0 - margin <= cy <= t.bbox.y1 + margin):
                return True
        return False

    @staticmethod
    def _find_heading_above(item_top: float, headings_map: list) -> str:
        """Return the text of the nearest heading that sits above item_top."""
        best_heading = ""
        best_y1 = -1.0
        for h_bbox, h_text in headings_map:
            h_bottom = h_bbox[3]
            if h_bottom <= item_top and h_bottom > best_y1:
                best_y1 = h_bottom
                best_heading = h_text
        return best_heading

    @staticmethod
    def _find_nearest_caption(img_y: float, raw_paragraphs: list) -> str:
        """Find a figure/image caption paragraph closest to the image vertically."""
        best_caption = ""
        best_dist = float("inf")
        for rp in raw_paragraphs:
            text = rp.text.strip().lower()
            if text.startswith(("figure", "fig.", "fig ", "image")) and len(rp.text) < 300:
                p_y = (rp.bbox.y0 + rp.bbox.y1) / 2.0
                dist = abs(p_y - img_y)
                if dist < best_dist:
                    best_dist = dist
                    best_caption = rp.text.strip()
        return best_caption
