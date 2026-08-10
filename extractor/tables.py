"""
extractor/tables.py
====================
Table extraction using Camelot, which is materially better than pdfplumber
for both ruled (lattice) and unruled (stream) tables commonly found in
government statistical reports.

Strategy:
  1. Try `lattice` mode first (for tables with visible border lines).
  2. If no tables found, fall back to `stream` mode (for borderless tables).

Camelot returns a pandas DataFrame per table, which we convert into our
internal TableRecord / TableRowRecord / TableCellRecord dataclasses so the
rest of the pipeline is unaffected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import camelot
import pandas as pd

from utils.logger import logger


@dataclass
class _BBox:
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0


@dataclass
class TableCellRecord:
    row_index: int
    col_index: int
    text: str = ""


@dataclass
class TableRowRecord:
    row_index: int
    is_header_row: bool = False
    cells: list = field(default_factory=list)


@dataclass
class TableRecord:
    title: str = "Table"
    rows: list = field(default_factory=list)
    table_index: int = 0
    num_rows: int = 0
    num_cols: int = 0
    extraction_method: str = "camelot"
    order_index: int = 0
    bbox: _BBox = field(default_factory=_BBox)
    section_id: object = None


class TableExtractor:
    """Extracts tables from a PDF using Camelot (lattice then stream)."""

    def __init__(self, pdf_path: Path):
        self.pdf_path = Path(pdf_path)

    def open(self):
        return self

    def close(self):
        pass

    def extract_tables_for_page(self, page_index_zero_based: int) -> List[TableRecord]:
        """Extract tables for a single page (0-indexed) into TableRecords."""
        # Camelot uses 1-based page numbers
        page_num = str(page_index_zero_based + 1)
        pdf_str = str(self.pdf_path)

        raw_tables = []
        flavor_used = "lattice"

        # --- Try lattice (ruled/bordered tables) first ---
        try:
            result = camelot.read_pdf(pdf_str, pages=page_num, flavor="lattice")
            lattice_tables = list(result)
            # Only accept lattice results if they have meaningful data rows (>3).
            # If lattice only picks up the header box but not the data rows below,
            # we fall through to stream mode which captures the full table.
            meaningful = [t for t in lattice_tables if len(t.df) > 3]
            if meaningful:
                raw_tables = meaningful
                flavor_used = "lattice"
        except Exception as exc:
            logger.warning(f"Camelot lattice failed on page {page_num}: {exc}")

        # --- Fall back to stream (borderless or partial-border tables) ---
        if not raw_tables:
            try:
                result = camelot.read_pdf(
                    pdf_str, pages=page_num, flavor="stream",
                    edge_tol=50,
                    row_tol=10,
                )
                if len(result) > 0:
                    raw_tables = list(result)
                    flavor_used = "stream"
            except Exception as exc:
                logger.warning(f"Camelot stream failed on page {page_num}: {exc}")

        records: List[TableRecord] = []
        for t_idx, camelot_table in enumerate(raw_tables):
            try:
                record = self._convert_table(camelot_table, t_idx, flavor_used)
                if record is not None:
                    records.append(record)
            except Exception as exc:
                logger.warning(f"Failed converting table {t_idx} on page {page_num}: {exc}")

        return records

    def _convert_table(self, camelot_table, t_idx: int, flavor: str) -> Optional[TableRecord]:
        """Convert a camelot Table object into a TableRecord."""
        df: pd.DataFrame = camelot_table.df

        # Drop rows where every cell is empty
        df = df.replace("", pd.NA).dropna(how="all").fillna("")
        df = df.reset_index(drop=True)

        if df.empty or len(df) < 1:
            return None

        num_rows = len(df)
        num_cols = len(df.columns)

        # Detect which row is the header (first non-empty row that is
        # predominantly text, or simply row 0 if all rows have data).
        header_row_idx = self._detect_header_row(df)

        rows: List[TableRowRecord] = []
        for r_idx in range(num_rows):
            is_header = (r_idx == header_row_idx)
            cells = []
            for c_idx in range(num_cols):
                raw = str(df.iloc[r_idx, c_idx])
                # Camelot uses \n for multi-line cells; join with space
                text = " ".join(raw.split("\n")).strip()
                cells.append(TableCellRecord(
                    row_index=r_idx, col_index=c_idx, text=text
                ))
            rows.append(TableRowRecord(
                row_index=r_idx, is_header_row=is_header, cells=cells
            ))

        # Get bbox from camelot (it's in PDF coordinate space)
        try:
            x1, y1, x2, y2 = camelot_table._bbox
            bbox = _BBox(x1, y1, x2, y2)
        except Exception:
            bbox = _BBox()

        return TableRecord(
            table_index=t_idx,
            num_rows=num_rows,
            num_cols=num_cols,
            extraction_method=f"camelot:{flavor}",
            order_index=t_idx,
            bbox=bbox,
            rows=rows,
        )

    @staticmethod
    def _detect_header_row(df: pd.DataFrame) -> Optional[int]:
        """Return the index of the header row, or None if not detectable.

        Heuristic: the header row is the last row (from the top) where the
        majority of cells are non-numeric text before the first all-numeric
        data row begins.
        """
        import re
        numeric_pat = re.compile(r"^[\d.,\-+%() ]+$")

        def is_data_row(row_series) -> bool:
            non_empty = [str(v).strip() for v in row_series if str(v).strip()]
            if not non_empty:
                return False
            numeric = [v for v in non_empty if numeric_pat.match(v)]
            return len(numeric) / len(non_empty) >= 0.5

        # Find first data row
        first_data = None
        for i in range(min(20, len(df))):
            if is_data_row(df.iloc[i]):
                first_data = i
                break

        if first_data is None or first_data == 0:
            return None

        # Walk backwards from first_data to find last non-empty text row
        for j in range(first_data - 1, -1, -1):
            non_empty = [str(v).strip() for v in df.iloc[j] if str(v).strip()]
            if non_empty:
                return j

        return None

    def __enter__(self) -> "TableExtractor":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
