"""
parser/paragraph_parser.py
============================
Groups classified lines into paragraphs. Uses internal dataclasses so
it does not depend on the database models layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from parser.heading_parser import ClassifiedLine


@dataclass
class RawBBox:
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0


@dataclass
class RawParagraph:
    text: str
    bbox: RawBBox = field(default_factory=RawBBox)


class ParagraphParser:
    def build(self, classified_lines: List[ClassifiedLine]) -> Tuple[List[RawParagraph], list]:
        """Returns (paragraphs, []) — lists are no longer tracked separately."""
        paragraphs: List[RawParagraph] = []
        buffer_lines: List[ClassifiedLine] = []

        def flush_paragraph():
            if not buffer_lines:
                return
            text = " ".join(cl.line.text for cl in buffer_lines).strip()
            if not text:
                buffer_lines.clear()
                return
            x0 = min(cl.line.bbox[0] for cl in buffer_lines)
            y0 = min(cl.line.bbox[1] for cl in buffer_lines)
            x1 = max(cl.line.bbox[2] for cl in buffer_lines)
            y1 = max(cl.line.bbox[3] for cl in buffer_lines)
            paragraphs.append(RawParagraph(text=text, bbox=RawBBox(x0, y0, x1, y1)))
            buffer_lines.clear()

        for cl in classified_lines:
            if cl.is_heading:
                flush_paragraph()
                continue
            # Treat list items and body text the same — just collect text
            buffer_lines.append(cl)

        flush_paragraph()
        return paragraphs, []
