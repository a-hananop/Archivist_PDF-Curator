"""Unit tests for utils/validators.py -- PDF validation edge cases."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.fixtures import make_blank_pdf, make_simple_pdf
from utils.validators import validate_pdf


class TestValidators(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_valid_pdf(self):
        pdf_path = make_simple_pdf(self.tmp_path / "simple.pdf")
        result = validate_pdf(pdf_path)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.page_count, 2)
        self.assertIsNone(result.error)

    def test_missing_file(self):
        result = validate_pdf(self.tmp_path / "does_not_exist.pdf")
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.error)

    def test_zero_byte_file(self):
        empty_file = self.tmp_path / "empty.pdf"
        empty_file.write_bytes(b"")
        result = validate_pdf(empty_file)
        self.assertFalse(result.is_valid)
        self.assertTrue(result.is_empty)

    def test_corrupted_pdf(self):
        corrupted = self.tmp_path / "corrupted.pdf"
        corrupted.write_bytes(b"%PDF-1.4 this is not a real pdf structure at all")
        result = validate_pdf(corrupted)
        self.assertFalse(result.is_valid)

    def test_blank_page_pdf_is_still_valid(self):
        pdf_path = make_blank_pdf(self.tmp_path / "blank.pdf")
        result = validate_pdf(pdf_path)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.page_count, 1)


if __name__ == "__main__":
    unittest.main()
