"""Tests for enriched table context (section/caption linking) and the
Markdown/CSV table export utilities."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database.exporters import export_tables_csv_bundle, export_tables_markdown, render_table_block
from database.queries import get_tables_with_context
from processors.document_processor import DocumentProcessor
from tests.fixtures import make_multi_table_pdf, make_table_pdf


class TestTableContext(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.processor = DocumentProcessor(output_dir=self.tmp_path / "output")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_two_tables_stay_separate_with_own_section_and_caption(self):
        pdf_path = make_multi_table_pdf(self.tmp_path / "quarterly.pdf")
        result = self.processor.process(pdf_path)
        self.assertTrue(result.success)

        tables = get_tables_with_context(result.db_path)
        self.assertEqual(len(tables), 2)

        t1, t2 = tables
        self.assertEqual(t1["section_title"], "1. Revenue")
        self.assertEqual(t2["section_title"], "2. Expenses")

        self.assertIsNotNone(t1["caption"])
        self.assertIn("Revenue", t1["caption"])
        self.assertIsNotNone(t2["caption"])
        self.assertIn("Expenses", t2["caption"])

        # Captions must not have absorbed the table's own cell text.
        self.assertLess(len(t1["caption"]), 60)
        self.assertLess(len(t2["caption"]), 60)

    def test_table_headers_and_rows_split_correctly(self):
        pdf_path = make_table_pdf(self.tmp_path / "table.pdf")
        result = self.processor.process(pdf_path)
        tables = get_tables_with_context(result.db_path)
        self.assertEqual(len(tables), 1)

        t = tables[0]
        self.assertEqual(t["headers"], ["Quarter", "Revenue", "Profit"])
        self.assertEqual(len(t["rows"]), 2)
        self.assertEqual(t["rows"][0], ["Q1", "100000", "20000"])

    def test_table_pdf_with_no_ruled_lines_produces_no_false_tables(self):
        # simple.pdf (from the other fixture module) has no ruled tables at
        # all -- verifies the unruled-strategy false-positive filter works
        # end-to-end and doesn't eat real paragraph/heading text.
        from tests.fixtures import make_simple_pdf
        pdf_path = make_simple_pdf(self.tmp_path / "simple.pdf")
        result = self.processor.process(pdf_path)
        tables = get_tables_with_context(result.db_path)
        self.assertEqual(len(tables), 0)


class TestTableExport(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.processor = DocumentProcessor(output_dir=self.tmp_path / "output")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_markdown_export_renders_each_table_as_separate_section(self):
        pdf_path = make_multi_table_pdf(self.tmp_path / "quarterly.pdf")
        result = self.processor.process(pdf_path)

        md_path = export_tables_markdown(result.db_path)
        self.assertTrue(md_path.exists())
        content = md_path.read_text(encoding="utf-8")

        self.assertIn("### Table 1", content)
        self.assertIn("### Table 2", content)
        self.assertIn("**Section:** 1. Revenue", content)
        self.assertIn("**Section:** 2. Expenses", content)
        # Each table has its own markdown grid with a header row separator.
        self.assertEqual(content.count("| --- | --- |"), 2)

    def test_csv_bundle_writes_one_file_per_table(self):
        pdf_path = make_multi_table_pdf(self.tmp_path / "quarterly.pdf")
        result = self.processor.process(pdf_path)

        csv_files = export_tables_csv_bundle(result.db_path)
        self.assertEqual(len(csv_files), 2)
        for f in csv_files:
            self.assertTrue(f.exists())

        content0 = csv_files[0].read_text(encoding="utf-8")
        self.assertIn("Quarter", content0)

    def test_render_table_block_pads_short_rows(self):
        table = {
            "page_number": 1, "num_rows": 2, "num_cols": 3,
            "extraction_method": "pdfplumber:lines_strict",
            "section_title": None, "caption": None,
            "headers": ["A", "B", "C"],
            "rows": [["1", "2"]],  # short row -- should be padded
        }
        block = render_table_block(table, display_index=1)
        self.assertIn("| 1 | 2 |  |", block)

    def test_export_on_document_with_no_tables_still_produces_valid_file(self):
        from tests.fixtures import make_simple_pdf
        pdf_path = make_simple_pdf(self.tmp_path / "simple.pdf")
        result = self.processor.process(pdf_path)

        md_path = export_tables_markdown(result.db_path)
        content = md_path.read_text(encoding="utf-8")
        self.assertIn("Total tables: 0", content)
        self.assertIn("No tables were detected", content)


if __name__ == "__main__":
    unittest.main()
