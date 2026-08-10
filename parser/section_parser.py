"""
parser/section_parser.py
==========================
Builds the section hierarchy from classified headings.

Sections can span page boundaries (a section started on page 3 might
continue onto page 4 before the next heading appears), so this parser
keeps a small piece of state -- a stack of "currently open" section levels
-- that persists across pages for the lifetime of a single document. That
state is owned by a `SectionStack` instance created once per document and
handed to `SectionParser.build()` for every page.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from database.models import SectionRecord
from parser.heading_parser import ClassifiedLine


@dataclass
class _OpenSection:
    level: int
    db_id: Optional[int]      # real db id once committed (set by caller after insert)
    local_index: Optional[int]  # index within the page currently being built (pre-insert)


class SectionStack:
    """Tracks open section levels across the whole document."""

    def __init__(self):
        self._stack: List[_OpenSection] = []

    def reset_local_indices(self) -> None:
        """Call at the start of building a new page's sections."""
        for open_sec in self._stack:
            open_sec.local_index = None  # will be re-pointed if referenced on this page

    def parent_for_level(self, level: int) -> Tuple[Optional[int], Optional[int]]:
        """Return (parent_local_index, parent_db_id) for a new section at `level`."""
        while self._stack and self._stack[-1].level >= level:
            self._stack.pop()
        if not self._stack:
            return None, None
        top = self._stack[-1]
        return top.local_index, top.db_id

    def push(self, level: int, local_index: int) -> None:
        self._stack.append(_OpenSection(level=level, db_id=None, local_index=local_index))

    def resolve_db_ids(self, local_index_to_db_id: dict) -> None:
        """After a page's sections are committed, resolve db ids for the stack."""
        for open_sec in self._stack:
            if open_sec.local_index is not None:
                open_sec.db_id = local_index_to_db_id.get(open_sec.local_index, open_sec.db_id)
                open_sec.local_index = None


class SectionParser:
    def build(self, classified_lines: List[ClassifiedLine], stack: SectionStack) -> List[SectionRecord]:
        stack.reset_local_indices()
        sections: List[SectionRecord] = []

        order = 0
        for cl in classified_lines:
            if not cl.is_heading:
                continue

            parent_local_index, parent_db_id = stack.parent_for_level(cl.heading_level)
            local_index = len(sections)

            sections.append(SectionRecord(
                title=cl.line.text.strip(),
                level=cl.heading_level,
                order_index=order,
                parent_local_index=parent_local_index,
                parent_db_id=parent_db_id if parent_local_index is None else None,
            ))
            stack.push(cl.heading_level, local_index)
            order += 1

        return sections
