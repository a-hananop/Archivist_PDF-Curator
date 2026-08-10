"""Unit tests for the heading/paragraph/section parsing heuristics."""

from __future__ import annotations

import unittest

from extractor.text import Line, Span
from parser.heading_parser import HeadingParser
from parser.paragraph_parser import ParagraphParser
from parser.section_parser import SectionParser, SectionStack


def _line(text, size=11.0, bold=False, y=0.0):
    span = Span(text=text, font_name="helv", font_size=size, is_bold=bold,
                is_italic=False, bbox=(0, y, 200, y + size))
    return Line(spans=[span], bbox=(0, y, 200, y + size))


class TestHeadingParser(unittest.TestCase):
    def test_large_font_detected_as_heading(self):
        lines = [
            _line("Document Title", size=24, y=0),
            _line("This is a normal paragraph sentence with body text.", size=11, y=30),
        ]
        classified = HeadingParser().classify_lines(lines)
        self.assertTrue(classified[0].is_heading)
        self.assertFalse(classified[1].is_heading)

    def test_bullet_list_detected(self):
        lines = [_line("- A bullet point here", size=11, y=0)]
        classified = HeadingParser().classify_lines(lines)
        self.assertTrue(classified[0].is_list_item)
        self.assertEqual(classified[0].list_type, "bullet")

    def test_numbered_list_detected(self):
        lines = [_line("1. First numbered item", size=11, y=0)]
        classified = HeadingParser().classify_lines(lines)
        self.assertTrue(classified[0].is_list_item)
        self.assertEqual(classified[0].list_type, "numbered")

    def test_long_sentence_not_a_heading_even_if_bold(self):
        long_text = " ".join(["word"] * 30)
        lines = [_line(long_text, size=11, bold=True, y=0)]
        classified = HeadingParser().classify_lines(lines)
        self.assertFalse(classified[0].is_heading)


class TestParagraphParser(unittest.TestCase):
    def test_consecutive_body_lines_merge_into_one_paragraph(self):
        lines = [
            _line("This is the first line of a paragraph", y=0),
            _line("and this is the continuation on the next line.", y=15),
        ]
        classified = HeadingParser().classify_lines(lines)
        paragraphs, lists = ParagraphParser().build(classified)
        self.assertEqual(len(paragraphs), 1)
        self.assertIn("first line", paragraphs[0].text)
        self.assertIn("continuation", paragraphs[0].text)

    def test_heading_breaks_paragraph_grouping(self):
        lines = [
            _line("Intro paragraph text goes here for testing purposes today.", y=0),
            _line("A New Section Heading", size=20, y=20),
            _line("Body text after the heading begins here for the section.", y=45),
        ]
        classified = HeadingParser().classify_lines(lines)
        paragraphs, _ = ParagraphParser().build(classified)
        self.assertEqual(len(paragraphs), 2)

    def test_list_items_grouped_together(self):
        lines = [_line(f"- item {i}", y=i * 15) for i in range(3)]
        classified = HeadingParser().classify_lines(lines)
        paragraphs, lists = ParagraphParser().build(classified)
        self.assertEqual(len(lists), 1)
        self.assertEqual(len(lists[0].items), 3)


class TestSectionParser(unittest.TestCase):
    def test_sections_built_from_headings_with_hierarchy(self):
        lines = [
            _line("Chapter One", size=24, y=0),
            _line("Some intro text for chapter one right here.", y=30),
            _line("Sub Section A", size=16, y=50),
            _line("Body text under sub section A goes here today.", y=70),
        ]
        classified = HeadingParser().classify_lines(lines)
        stack = SectionStack()
        sections = SectionParser().build(classified, stack)
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0].level, 1)
        self.assertIsNone(sections[0].parent_local_index)
        self.assertEqual(sections[1].parent_local_index, 0)


if __name__ == "__main__":
    unittest.main()
