"""
extractor/text.py
==================
Low-level text extraction for a single page using PyMuPDF's structured
"dict" text extraction, which preserves blocks -> lines -> spans along with
per-span font name, size, and flags (bold/italic bits).

This module deliberately stays "dumb" -- it just flattens the PDF's native
structure into simple Span/Line/Block objects. Higher-level classification
(is this a heading? a paragraph? a list item?) happens in the parser layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import fitz

# PyMuPDF font flag bits (see fitz docs: span["flags"])
_FLAG_ITALIC = 1 << 1
_FLAG_BOLD = 1 << 4  # "superscript"=0, actual bold bit is 1<<4 per PyMuPDF docs


@dataclass
class Span:
    text: str
    font_name: str
    font_size: float
    is_bold: bool
    is_italic: bool
    bbox: tuple  # (x0, y0, x1, y1)


@dataclass
class Line:
    spans: List[Span] = field(default_factory=list)
    bbox: tuple = (0, 0, 0, 0)

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans).strip()

    @property
    def dominant_span(self) -> Span:
        """The span with the most characters -- used to characterize the line."""
        if not self.spans:
            return Span("", "", 0.0, False, False, (0, 0, 0, 0))
        return max(self.spans, key=lambda s: len(s.text))


@dataclass
class Block:
    lines: List[Line] = field(default_factory=list)
    bbox: tuple = (0, 0, 0, 0)
    block_type: str = "text"  # 'text' | 'image'

    @property
    def text(self) -> str:
        return "\n".join(l.text for l in self.lines if l.text)


class TextExtractor:
    """Extracts structured Block/Line/Span data for one page."""

    def extract_blocks(self, page: fitz.Page) -> List[Block]:
        raw = page.get_text("dict")
        blocks: List[Block] = []

        for raw_block in raw.get("blocks", []):
            btype = raw_block.get("type", 0)
            if btype == 1:
                blocks.append(Block(lines=[], bbox=tuple(raw_block.get("bbox", (0, 0, 0, 0))),
                                     block_type="image"))
                continue

            lines: List[Line] = []
            for raw_line in raw_block.get("lines", []):
                spans: List[Span] = []
                for raw_span in raw_line.get("spans", []):
                    text = raw_span.get("text", "")
                    if text == "":
                        continue
                    flags = raw_span.get("flags", 0)
                    spans.append(Span(
                        text=text,
                        font_name=raw_span.get("font", ""),
                        font_size=round(float(raw_span.get("size", 0.0)), 2),
                        is_bold=bool(flags & _FLAG_BOLD) or "bold" in raw_span.get("font", "").lower(),
                        is_italic=bool(flags & _FLAG_ITALIC) or "italic" in raw_span.get("font", "").lower()
                                   or "oblique" in raw_span.get("font", "").lower(),
                        bbox=tuple(raw_span.get("bbox", (0, 0, 0, 0))),
                    ))
                if spans:
                    lines.append(Line(spans=spans, bbox=tuple(raw_line.get("bbox", (0, 0, 0, 0)))))

            if lines:
                blocks.append(Block(lines=lines, bbox=tuple(raw_block.get("bbox", (0, 0, 0, 0))),
                                     block_type="text"))

        return blocks

    def extract_plain_text(self, page: fitz.Page) -> str:
        return page.get_text("text") or ""

    def font_usage(self, blocks: List[Block]) -> dict:
        usage: dict = {}
        for block in blocks:
            for line in block.lines:
                for span in line.spans:
                    if not span.font_name:
                        continue
                    usage[span.font_name] = usage.get(span.font_name, 0) + len(span.text)
        return usage
