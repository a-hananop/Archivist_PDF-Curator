"""Unit tests for the extraction layer: metadata, text/font spans, tables,
and layout (header/footer + links)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import fitz

from extractor.layout import LayoutExtractor
from extractor.metadata import MetadataExtractor
from extractor.pdf_loader import PDFLoader
from extractor.tables import TableExtractor
from extractor.text import TextExtractor
from tests.fixtures import make_simple_pdf, make_table_pdf


class TestPDFLoader(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_page_count_and_hash(self):
        pdf_path = make_simple_pdf(self.tmp_path / "simple.pdf")
        with PDFLoader(pdf_path) as loader:
            self.assertEqual(loader.page_count, 2)
            h = loader.file_hash()
            self.assertEqual(len(h), 64)  # sha256 hex digest length

    def test_iter_pages_yields_all_pages(self):
        pdf_path = make_simple_pdf(self.tmp_path / "simple.pdf")
        with PDFLoader(pdf_path) as loader:
            pages = list(loader.iter_pages())
            self.assertEqual(len(pages), 2)


class TestMetadataExtractor(unittest.TestCase):
    def test_extract_returns_page_count(self):
        tmpdir = tempfile.TemporaryDirectory()
        try:
            pdf_path = make_simple_pdf(Path(tmpdir.name) / "simple.pdf")
            doc = fitz.open(str(pdf_path))
            records = MetadataExtractor().extract(doc)
            doc.close()
            keys = {r.key for r in records}
            self.assertIn("page_count", keys)
        finally:
            tmpdir.cleanup()


class TestTextExtractor(unittest.TestCase):
    def test_extract_blocks_has_text_and_fonts(self):
        tmpdir = tempfile.TemporaryDirectory()
        try:
            pdf_path = make_simple_pdf(Path(tmpdir.name) / "simple.pdf")
            doc = fitz.open(str(pdf_path))
            page = doc.load_page(0)
            extractor = TextExtractor()
            blocks = extractor.extract_blocks(page)
            self.assertGreater(len(blocks), 0)

            all_text = " ".join(b.text for b in blocks)
            self.assertIn("Sample Report Title", all_text)

            fonts = extractor.font_usage(blocks)
            self.assertGreater(len(fonts), 0)
            doc.close()
        finally:
            tmpdir.cleanup()


class TestLayoutExtractor(unittest.TestCase):
    def test_links_extracted(self):
        tmpdir = tempfile.TemporaryDirectory()
        try:
            pdf_path = make_simple_pdf(Path(tmpdir.name) / "simple.pdf")
            doc = fitz.open(str(pdf_path))
            page = doc.load_page(0)
            links = LayoutExtractor().extract_links(page)
            self.assertEqual(len(links), 1)
            self.assertEqual(links[0].link_type, "uri")
            self.assertEqual(links[0].uri, "https://example.com")
            doc.close()
        finally:
            tmpdir.cleanup()

    def test_page_dimensions(self):
        tmpdir = tempfile.TemporaryDirectory()
        try:
            pdf_path = make_simple_pdf(Path(tmpdir.name) / "simple.pdf")
            doc = fitz.open(str(pdf_path))
            page = doc.load_page(0)
            width, height, rotation = LayoutExtractor().get_page_dimensions(page)
            self.assertGreater(width, 0)
            self.assertGreater(height, 0)
            doc.close()
        finally:
            tmpdir.cleanup()


class TestTableExtractor(unittest.TestCase):
    def test_extracts_ruled_table(self):
        tmpdir = tempfile.TemporaryDirectory()
        try:
            pdf_path = make_table_pdf(Path(tmpdir.name) / "table.pdf")
            with TableExtractor(pdf_path) as extractor:
                tables = extractor.extract_tables_for_page(0)
            self.assertGreaterEqual(len(tables), 1)
            table = tables[0]
            self.assertGreaterEqual(table.num_rows, 2)
            self.assertGreaterEqual(table.num_cols, 2)
        finally:
            tmpdir.cleanup()


if __name__ == "__main__":
    unittest.main()
