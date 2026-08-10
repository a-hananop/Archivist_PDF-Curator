"""Unit tests for the content-aware table header detection added to
extractor/tables.py: multi-row header consolidation, "no header at all"
for continuation pages, false-positive table rejection for prose text,
and numeric-vs-label row classification."""

from __future__ import annotations

import unittest
from pathlib import Path

from extractor.tables import TableExtractor


class TestRowNumericRatio(unittest.TestCase):
    def setUp(self):
        self.te = TableExtractor(Path("/nonexistent.pdf"))

    def test_pure_data_row_is_fully_numeric(self):
        row = ["194.30", "2.8", "181.00", "2.8", "374.90", "1.5"]
        self.assertEqual(self.te._row_numeric_ratio(row), 1.0)

    def test_label_row_is_not_numeric(self):
        row = ["District", "Area", "Share", "Production"]
        self.assertEqual(self.te._row_numeric_ratio(row), 0.0)

    def test_district_name_plus_numbers_is_mostly_numeric(self):
        row = ["Attock", "194.30", "2.8", "181.00", "2.8"]
        self.assertAlmostEqual(self.te._row_numeric_ratio(row), 4 / 5)

    def test_year_range_is_not_treated_as_numeric(self):
        # "2023-24" is all digits/hyphen but is a categorical year LABEL,
        # not a data value -- must not be counted as numeric.
        row = ["2023-24", "2024-25"]
        self.assertEqual(self.te._row_numeric_ratio(row), 0.0)

    def test_empty_row_returns_zero(self):
        self.assertEqual(self.te._row_numeric_ratio(["", "", ""]), 0.0)


class TestHeaderRowDetection(unittest.TestCase):
    def setUp(self):
        self.te = TableExtractor(Path("/nonexistent.pdf"))

    def test_single_header_row_detected(self):
        grid = [
            ["District", "Area", "Production"],
            ["Attock", "194.30", "374.90"],
            ["Rawalpindi", "167.10", "413.80"],
        ]
        self.assertEqual(self.te._detect_header_row(grid), 0)

    def test_multi_row_header_finds_last_header_row(self):
        # Mirrors the real CAP report structure: a blank/label row, a year
        # row, a column-label row, THEN data.
        grid = [
            ["", "Area", "", "", "", "Production", "", "", ""],
            ["Province/", "2023-24", "", "2024-25", "", "2023-24", "", "2024-25", ""],
            ["PUNJAB", "000'hectares", "% Share", "000'hectares", "% Share",
             "000'Tons", "% Share", "000'Tons", "% Share"],
            ["Attock", "194.30", "2.8", "181.00", "2.8", "374.90", "1.5", "262.00", "1.2"],
            ["Rawalpindi", "167.10", "2.4", "166.00", "2.5", "413.80", "1.7", "276.00", "1.3"],
        ]
        self.assertEqual(self.te._detect_header_row(grid), 2)

    def test_continuation_page_has_no_header(self):
        # A continuation page of a multi-page table: every row is data,
        # the header only appeared once on the table's first page.
        grid = [
            ["Charsada", "28.57", "30.3", "28.59", "31.8"],
            ["Nowshera", "2.80", "3.0", "2.81", "3.1"],
            ["Bajour", "0.00", "0.0", "0.00", "0.0"],
        ]
        self.assertIsNone(self.te._detect_header_row(grid))

    def test_keyword_fallback_for_pure_text_table(self):
        grid = [
            ["District", "Name", "Total"],
            ["North Region", "Zone A", "Report"],
            ["South Region", "Zone B", "Summary"],
        ]
        self.assertEqual(self.te._detect_header_row(grid), 0)


class TestConsolidateHeader(unittest.TestCase):
    def setUp(self):
        self.te = TableExtractor(Path("/nonexistent.pdf"))

    def test_multi_row_header_merged_into_single_row(self):
        grid = [
            ["", "Area", "", "Production", ""],
            ["Province/", "2023-24", "2024-25", "2023-24", "2024-25"],
            ["Attock", "194.30", "181.00", "374.90", "262.00"],
            ["Rawalpindi", "167.10", "166.00", "413.80", "276.00"],
        ]
        new_grid, header_idx = self.te._consolidate_header(grid)

        self.assertEqual(header_idx, 0)
        # The two header-ish rows should be merged into row 0.
        self.assertIn("Area", new_grid[0][1])
        self.assertIn("2023-24", new_grid[0][1])
        # Data rows should follow immediately, with no leftover header
        # fragment rows in between.
        self.assertEqual(new_grid[1], ["Attock", "194.30", "181.00", "374.90", "262.00"])
        self.assertEqual(len(new_grid), 3)  # 1 header + 2 data rows

    def test_no_header_case_returns_grid_unchanged(self):
        grid = [
            ["Charsada", "28.57", "30.3"],
            ["Nowshera", "2.80", "3.0"],
        ]
        new_grid, header_idx = self.te._consolidate_header(grid)
        self.assertIsNone(header_idx)
        self.assertEqual(new_grid, grid)


class TestLooksLikeRealTable(unittest.TestCase):
    def setUp(self):
        self.te = TableExtractor(Path("/nonexistent.pdf"))

    def test_rejects_wrapped_prose_masquerading_as_table(self):
        # This is exactly the failure mode seen on the CAP report's
        # foreword page: pdfplumber's unruled "text" strategy chops a
        # normal sentence into short whitespace-delimited fragments that
        # superficially look like table cells.
        grid = [
            ["The ag", "riculture sector", "is cons", "idered as key"],
            ["country along", "with mitigating t", "he con", "cerns of food"],
            ["rural poverty a", "lleviation and em", "ploym", "ent generation"],
        ]
        self.assertFalse(self.te._looks_like_real_table(grid))

    def test_accepts_genuine_numeric_data_grid(self):
        grid = [
            ["Attock", "194.30", "2.8", "181.00", "2.8"],
            ["Rawalpindi", "167.10", "2.4", "166.00", "2.5"],
            ["Muree", "5.30", "0.1", "3.00", "0.0"],
        ]
        self.assertTrue(self.te._looks_like_real_table(grid))

    def test_rejects_single_row_grid(self):
        self.assertFalse(self.te._looks_like_real_table([["a", "b", "c"]]))

    def test_rejects_mostly_empty_grid(self):
        grid = [["", "", "Attock", ""], ["", "", "", ""], ["", "", "", ""]]
        self.assertFalse(self.te._looks_like_real_table(grid))


if __name__ == "__main__":
    unittest.main()
