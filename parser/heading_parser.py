"""
parser/heading_parser.py
=========================
Classifies text lines as headings (and assigns a heading *level*) purely
from typographic signal: font size relative to the page's body-text
median, boldness, line length/shape (headings are short, don't end with a
comma, etc.), and position.

This is a heuristic classifier, not a layout-ML model -- it is tuned to be
conservative (favoring precision over recall) so that body paragraphs
don't get mis-tagged as headings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from config import CONFIG
from extractor.text import Line
from utils.helpers import median


@dataclass
class ClassifiedLine:
    line: Line
    is_heading: bool
    heading_level: int
    is_list_item: bool
    list_marker: Optional[str]
    list_type: Optional[str]  # 'bullet' | 'numbered'
    section_local_index: Optional[int] = None  # set later by structure_builder


_BULLET_MARKERS = ("•", "◦", "▪", "‣", "-", "*", "·", "●", "○")


def _looks_like_numbered_marker(token: str) -> bool:
    token = token.strip()
    if not token:
        return False
    # A real marker always ends with a delimiter: "1.", "1)", "1.2.", "(1)", "a.", "i."
    if not token.endswith((".", ")")):
        return False
    stripped = token.rstrip(".)").lstrip("(")
    if not stripped:
        return False
    if stripped.replace(".", "").isdigit():
        return True
    # Single lower/upper-case letter markers: "a.", "A)", but not short real words.
    if len(stripped) == 1 and stripped.isalpha():
        return True
    roman = set("ivxlcdm")
    if len(stripped) <= 4 and set(stripped.lower()) <= roman:
        return True
    return False


class HeadingParser:
    def __init__(self, heading_size_delta: float = None):
        self.heading_size_delta = heading_size_delta or CONFIG.heading_size_delta

    def classify_lines(self, lines: List[Line]) -> List[ClassifiedLine]:
        body_size = self._estimate_body_font_size(lines)
        size_levels = self._build_size_level_map(lines, body_size)

        classified: List[ClassifiedLine] = []
        for line in lines:
            text = line.text
            if not text:
                continue

            dom = line.dominant_span
            size = round(dom.font_size, 1)
            larger_than_body = size >= body_size + self.heading_size_delta

            # A line in a visibly larger font is treated as a heading candidate
            # even if it starts with what looks like a list marker (e.g. a
            # numbered chapter title "1. Introduction") -- font size takes
            # priority over marker-shape when the two heuristics disagree.
            if larger_than_body:
                is_heading, level = self._classify_heading(text, dom, body_size, size_levels)
                if is_heading:
                    classified.append(ClassifiedLine(
                        line=line, is_heading=True, heading_level=level,
                        is_list_item=False, list_marker=None, list_type=None,
                    ))
                    continue

            list_type, marker = self._detect_list_marker(text)
            is_list_item = list_type is not None

            is_heading = False
            level = 0
            if not is_list_item:
                is_heading, level = self._classify_heading(text, dom, body_size, size_levels)

            classified.append(ClassifiedLine(
                line=line, is_heading=is_heading, heading_level=level,
                is_list_item=is_list_item, list_marker=marker, list_type=list_type,
            ))
        return classified

    # -- internals ------------------------------------------------------------
    def _estimate_body_font_size(self, lines: List[Line]) -> float:
        sizes = [line.dominant_span.font_size for line in lines if line.text]
        return median(sizes, default=10.0)

    def _build_size_level_map(self, lines: List[Line], body_size: float) -> dict:
        """Map distinct "large" font sizes (descending) to heading levels 1..N."""
        distinct_sizes = sorted(
            {round(line.dominant_span.font_size, 1) for line in lines
             if line.text and line.dominant_span.font_size >= body_size + self.heading_size_delta},
            reverse=True,
        )
        return {size: idx + 1 for idx, size in enumerate(distinct_sizes[:6])}

    def _classify_heading(self, text: str, dom, body_size: float, size_levels: dict):
        if len(text) > 180:
            return False, 0
        if text.endswith((",", ";")):
            return False, 0

        # Reject anything that is mostly numeric -- data values and
        # statistics (e.g. "371.67", "431.24 Badin") are never real
        # document headings, even when rendered in a large/bold font as
        # part of a chart or infographic. Without this guard, chart pages
        # with no real "body text" to compare against (every line is a
        # short data label) misclassify their data values as headings.
        digit_count = sum(1 for c in text if c.isdigit())
        digit_ratio = digit_count / max(len(text.replace(" ", "")), 1)
        if digit_ratio > 0.3:
            return False, 0

        size = round(dom.font_size, 1)
        larger_than_body = size >= body_size + self.heading_size_delta
        is_bold = dom.is_bold
        is_short = len(text.split()) <= 20
        is_titlecase_or_upper = text.isupper() or text.istitle()

        if larger_than_body and is_short:
            level = size_levels.get(size, 1)
            return True, level

        # Bold-but-not-larger-than-body headings (e.g. a bold section label
        # set in the same size as body text) are only trusted when the font
        # is at least body-sized -- bold text meaningfully SMALLER than the
        # page's body font (common in chart/infographic labels, axis
        # captions, and data callouts) is virtually never a real heading,
        # and without this floor those tiny bold labels flood the document
        # with false headings.
        not_smaller_than_body = size >= body_size - 0.5
        absolute_size_floor = size >= 7.5
        if (is_bold and is_short and not_smaller_than_body and absolute_size_floor
                and (is_titlecase_or_upper or text.endswith(":")) and not text.endswith(".")):
            return True, max(size_levels.values(), default=0) + 1 if size_levels else 4

        return False, 0

    def _detect_list_marker(self, text: str):
        stripped = text.strip()
        if not stripped:
            return None, None

        first_token, _, rest = stripped.partition(" ")

        if first_token in _BULLET_MARKERS or (len(first_token) == 1 and first_token in "•◦▪‣●○-*·"):
            return "bullet", first_token

        if _looks_like_numbered_marker(first_token) and rest:
            return "numbered", first_token

        return None, None
