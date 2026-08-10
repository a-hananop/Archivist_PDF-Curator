"""End-to-end tests: run the full pipeline against synthetic PDFs and
verify the generated .db files contain the expected structured data."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database.queries import get_all_headings, get_all_tables, get_document_summary
from processors.document_processor import DocumentProcessor
from tests.fixtures import (
    make_blank_pdf, make_multi_page_pdf, make_simple_pdf, make_table_pdf,
)


class TestEndToEndProcessing(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.output_dir = self.tmp_path / "output"
        self.processor = DocumentProcessor(output_dir=self.output_dir)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_simple_pdf_produces_expected_db(self):
        pdf_path = make_simple_pdf(self.tmp_path / "simple.pdf")
        result = self.processor.process(pdf_path)

        self.assertTrue(result.success)
        self.assertEqual(result.status, "completed")
        self.assertTrue(result.db_path.exists())
        self.assertEqual(result.pages_processed, 2)

        summary = get_document_summary(result.db_path)
        self.assertEqual(summary["filename"], "simple.pdf")
        self.assertGreaterEqual(summary["table_counts"]["headings"], 1)
        self.assertGreaterEqual(summary["table_counts"]["paragraphs"], 1)
        self.assertGreaterEqual(summary["table_counts"]["lists"], 1)
        self.assertGreaterEqual(summary["table_counts"]["links"], 1)

    def test_headings_extracted_in_reading_order(self):
        pdf_path = make_simple_pdf(self.tmp_path / "simple2.pdf")
        result = self.processor.process(pdf_path)
        headings = get_all_headings(result.db_path)
        texts = [h["text"] for h in headings]
        self.assertTrue(any("Introduction" in t for t in texts))
        self.assertTrue(any("Methodology" in t for t in texts))

    def test_table_pdf_extracts_grid(self):
        pdf_path = make_table_pdf(self.tmp_path / "table.pdf")
        result = self.processor.process(pdf_path)
        self.assertTrue(result.success)

        tables = get_all_tables(result.db_path)
        self.assertGreaterEqual(len(tables), 1)
        grid = tables[0]["grid"]
        flat = [cell for row in grid for cell in row]
        self.assertTrue(any("Revenue" in c for c in flat))

    def test_multi_page_pdf_all_pages_processed(self):
        pdf_path = make_multi_page_pdf(self.tmp_path / "multi.pdf", num_pages=8)
        result = self.processor.process(pdf_path)
        self.assertEqual(result.pages_processed, 8)
        self.assertEqual(result.total_pages, 8)

        conn = sqlite3.connect(str(result.db_path))
        count = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        conn.close()
        self.assertEqual(count, 8)

    def test_blank_page_pdf_does_not_crash(self):
        pdf_path = make_blank_pdf(self.tmp_path / "blank.pdf")
        result = self.processor.process(pdf_path)
        self.assertTrue(result.success)
        self.assertEqual(result.pages_processed, 1)

    def test_each_pdf_gets_its_own_db(self):
        pdf1 = make_simple_pdf(self.tmp_path / "invoices.pdf")
        pdf2 = make_table_pdf(self.tmp_path / "research.pdf")
        r1 = self.processor.process(pdf1)
        r2 = self.processor.process(pdf2)

        self.assertNotEqual(r1.db_path, r2.db_path)
        self.assertEqual(r1.db_path.name, "invoices.db")
        self.assertEqual(r2.db_path.name, "research.db")

    def test_nonexistent_pdf_returns_failed_result(self):
        result = self.processor.process(self.tmp_path / "missing.pdf")
        self.assertFalse(result.success)
        self.assertEqual(result.status, "failed")


if __name__ == "__main__":
    unittest.main()
