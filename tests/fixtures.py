"""
tests/fixtures.py
==================
Generates small synthetic PDF files (using PyMuPDF) so the test suite has
no external file dependencies. Covers: a simple text document with
headings/paragraphs/lists, a document with a table, a multi-page document,
an empty-text (blank) page, and a 1-page document.
"""

from __future__ import annotations

from pathlib import Path

import fitz


def make_simple_pdf(path: Path) -> Path:
    """A 2-page PDF with a title, headings, paragraphs, and a bullet list."""
    doc = fitz.open()

    page = doc.new_page()
    page.insert_text((72, 72), "Sample Report Title", fontsize=24, fontname="helv")
    page.insert_text((72, 110), "1. Introduction", fontsize=16, fontname="helv")
    page.insert_text((72, 140),
                      "This is the first paragraph of the introduction section describing the",
                      fontsize=11, fontname="helv")
    page.insert_text((72, 158),
                      "purpose of this document in plain body text that spans two lines.",
                      fontsize=11, fontname="helv")
    page.insert_text((72, 190), "Key points:", fontsize=11, fontname="helv")
    page.insert_text((90, 210), "- First bullet point item", fontsize=11, fontname="helv")
    page.insert_text((90, 228), "- Second bullet point item", fontsize=11, fontname="helv")
    page.insert_text((90, 246), "- Third bullet point item", fontsize=11, fontname="helv")
    page.insert_link({
        "kind": fitz.LINK_URI, "from": fitz.Rect(72, 260, 200, 275),
        "uri": "https://example.com",
    })
    page.insert_text((72, 270), "Visit example.com for more.", fontsize=10, fontname="helv")

    page2 = doc.new_page()
    page2.insert_text((72, 100), "2. Methodology", fontsize=16, fontname="helv")
    page2.insert_text((72, 130), "This section explains the methodology used in the study.",
                       fontsize=11, fontname="helv")

    doc.save(str(path))
    doc.close()
    return path


def make_table_pdf(path: Path) -> Path:
    """A 1-page PDF containing a simple ruled table."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Financial Summary", fontsize=18, fontname="helv")

    # Draw a simple 3x3 ruled grid so pdfplumber's line-based strategy can find it.
    x0, y0, cell_w, cell_h = 72, 120, 120, 24
    rows, cols = 3, 3
    for r in range(rows + 1):
        y = y0 + r * cell_h
        page.draw_line(fitz.Point(x0, y), fitz.Point(x0 + cols * cell_w, y))
    for c in range(cols + 1):
        x = x0 + c * cell_w
        page.draw_line(fitz.Point(x, y0), fitz.Point(x, y0 + rows * cell_h))

    headers = ["Quarter", "Revenue", "Profit"]
    data = [["Q1", "100000", "20000"], ["Q2", "120000", "25000"]]
    for c, text in enumerate(headers):
        page.insert_text((x0 + c * cell_w + 5, y0 + 16), text, fontsize=10, fontname="helv")
    for r, row in enumerate(data, start=1):
        for c, text in enumerate(row):
            page.insert_text((x0 + c * cell_w + 5, y0 + r * cell_h + 16), text,
                              fontsize=10, fontname="helv")

    doc.save(str(path))
    doc.close()
    return path


def make_multi_page_pdf(path: Path, num_pages: int = 5) -> Path:
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1} Heading", fontsize=16, fontname="helv")
        page.insert_text((72, 100), f"This is body text for page {i + 1} of the document.",
                          fontsize=11, fontname="helv")
    doc.save(str(path))
    doc.close()
    return path


def make_blank_pdf(path: Path) -> Path:
    """A 1-page PDF with no text at all (simulates a scanned/image page)."""
    doc = fitz.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()
    return path


def make_multi_table_pdf(path: Path) -> Path:
    """A 1-page PDF with TWO distinct ruled tables, each with a heading and
    a caption, used to verify tables are kept separate and correctly
    linked to their own section/caption."""
    doc = fitz.open()
    page = doc.new_page()

    page.insert_text((72, 72), "Quarterly Report", fontsize=20, fontname="helv")

    # --- Section 1 + Table 1 ---
    page.insert_text((72, 110), "1. Revenue", fontsize=14, fontname="helv")
    page.insert_text((72, 132), "Table 1: Revenue by Quarter", fontsize=10, fontname="helv")

    x0, y0, cell_w, cell_h = 72, 150, 100, 20
    rows, cols = 2, 2
    for r in range(rows + 1):
        y = y0 + r * cell_h
        page.draw_line(fitz.Point(x0, y), fitz.Point(x0 + cols * cell_w, y))
    for c in range(cols + 1):
        x = x0 + c * cell_w
        page.draw_line(fitz.Point(x, y0), fitz.Point(x, y0 + rows * cell_h))
    headers1 = ["Quarter", "Revenue"]
    data1 = [["Q1", "50000"]]
    for c, text in enumerate(headers1):
        page.insert_text((x0 + c * cell_w + 4, y0 + 14), text, fontsize=9, fontname="helv")
    for r, row in enumerate(data1, start=1):
        for c, text in enumerate(row):
            page.insert_text((x0 + c * cell_w + 4, y0 + r * cell_h + 14), text,
                              fontsize=9, fontname="helv")

    # --- Section 2 + Table 2 ---
    page.insert_text((72, 230), "2. Expenses", fontsize=14, fontname="helv")
    page.insert_text((72, 252), "Table 2: Expenses by Quarter", fontsize=10, fontname="helv")

    y0b = 270
    for r in range(rows + 1):
        y = y0b + r * cell_h
        page.draw_line(fitz.Point(x0, y), fitz.Point(x0 + cols * cell_w, y))
    for c in range(cols + 1):
        x = x0 + c * cell_w
        page.draw_line(fitz.Point(x, y0b), fitz.Point(x, y0b + rows * cell_h))
    headers2 = ["Quarter", "Expenses"]
    data2 = [["Q1", "30000"]]
    for c, text in enumerate(headers2):
        page.insert_text((x0 + c * cell_w + 4, y0b + 14), text, fontsize=9, fontname="helv")
    for r, row in enumerate(data2, start=1):
        for c, text in enumerate(row):
            page.insert_text((x0 + c * cell_w + 4, y0b + r * cell_h + 14), text,
                              fontsize=9, fontname="helv")

    doc.save(str(path))
    doc.close()
    return path


def make_empty_pdf(path: Path) -> Path:
    """A .pdf file with zero pages -- an edge case the validator must catch."""
    doc = fitz.open()
    doc.save(str(path))
    doc.close()
    return path
