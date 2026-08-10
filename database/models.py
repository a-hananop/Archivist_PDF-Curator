"""
database/models.py
===================
Simplified dataclasses that mirror the new SQLite schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DocumentRecord:
    filename: str
    filepath: str
    file_size_bytes: int = 0
    file_hash_sha256: str = ""
    page_count: int = 0
    is_encrypted: bool = False
    processing_status: str = "pending"


@dataclass
class ParagraphRecord:
    heading: str
    text: str
    is_long: bool = False


@dataclass
class ImageRecord:
    caption: str
    file_path: str


@dataclass
class TableCellRecord:
    row_index: int
    col_index: int
    text: str = ""


@dataclass
class TableRowRecord:
    row_index: int
    is_header_row: bool = False
    cells: list = field(default_factory=list)  # List[TableCellRecord]


@dataclass
class TableRecord:
    title: str = "Untitled Table"
    rows: list = field(default_factory=list)  # List[TableRowRecord]


@dataclass
class PageStructure:
    """Everything extracted & parsed for a single page, ready for insertion."""
    paragraphs: list = field(default_factory=list)     # List[ParagraphRecord]
    tables: list = field(default_factory=list)          # List[TableRecord]
    images: list = field(default_factory=list)          # List[ImageRecord]
