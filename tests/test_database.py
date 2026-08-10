"""Unit tests for the database layer: schema creation, connection lifecycle,
and repository inserts."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database.connection import DatabaseConnection
from database.models import (
    BBox, DocumentRecord, HeadingRecord, MetadataRecord, PageRecord, PageStructure,
    ParagraphRecord,
)
from database.repository import DocumentRepository


class TestDatabaseSchema(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_schema_creates_all_expected_tables(self):
        with DatabaseConnection(self.db_path) as conn:
            cur = conn.connect().execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            )
            tables = {row["name"] for row in cur.fetchall()}

        expected = {
            "documents", "metadata", "pages", "sections", "headings", "paragraphs",
            "lists", "list_items", "tables", "table_rows", "table_cells", "images",
            "links", "captions", "headers", "footers", "fonts", "processing_logs",
        }
        self.assertTrue(expected.issubset(tables))

    def test_foreign_keys_enforced(self):
        with DatabaseConnection(self.db_path) as conn:
            c = conn.connect()
            row = c.execute("PRAGMA foreign_keys;").fetchone()
            self.assertEqual(row[0], 1)


class TestDocumentRepository(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"
        self.db_conn = DatabaseConnection(self.db_path)
        self.db_conn.connect()
        self.db_conn.initialize_schema()
        self.repo = DocumentRepository(self.db_conn)

    def tearDown(self):
        self.db_conn.close()
        self.tmpdir.cleanup()

    def test_create_document(self):
        doc_id = self.repo.create_document(DocumentRecord(
            filename="test.pdf", filepath="/tmp/test.pdf", file_size_bytes=1024,
            page_count=1,
        ))
        self.assertIsInstance(doc_id, int)
        row = self.db_conn.connect().execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        self.assertEqual(row["filename"], "test.pdf")
        self.assertEqual(row["processing_status"], "processing")

    def test_insert_metadata(self):
        self.repo.create_document(DocumentRecord(filename="a.pdf", filepath="/a.pdf"))
        self.repo.insert_metadata([MetadataRecord(key="title", value="My Doc")])
        row = self.db_conn.connect().execute(
            "SELECT value FROM metadata WHERE key='title'"
        ).fetchone()
        self.assertEqual(row["value"], "My Doc")

    def test_insert_page_structure_and_relationships(self):
        self.repo.create_document(DocumentRecord(filename="a.pdf", filepath="/a.pdf"))

        structure = PageStructure(
            page=PageRecord(page_number=1, width=612, height=792, char_count=50, word_count=10,
                             full_text="Heading\nSome paragraph text."),
            headings=[HeadingRecord(text="Heading", level=1, order_index=0, reading_order=0,
                                     bbox=BBox(0, 0, 100, 20))],
            paragraphs=[ParagraphRecord(text="Some paragraph text.", order_index=0,
                                         reading_order=1, bbox=BBox(0, 20, 100, 40))],
        )
        insert_result = self.repo.insert_page_structure(structure)
        page_id = insert_result["page_id"]
        self.assertIsInstance(page_id, int)

        conn = self.db_conn.connect()
        heading_row = conn.execute("SELECT * FROM headings WHERE page_id=?", (page_id,)).fetchone()
        self.assertEqual(heading_row["text"], "Heading")

        para_row = conn.execute("SELECT * FROM paragraphs WHERE page_id=?", (page_id,)).fetchone()
        self.assertEqual(para_row["text"], "Some paragraph text.")

    def test_cascade_delete_removes_children(self):
        doc_id = self.repo.create_document(DocumentRecord(filename="a.pdf", filepath="/a.pdf"))
        structure = PageStructure(page=PageRecord(page_number=1))
        insert_result = self.repo.insert_page_structure(structure)
        page_id = insert_result["page_id"]

        conn = self.db_conn.connect()
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        row = conn.execute("SELECT * FROM pages WHERE id=?", (page_id,)).fetchone()
        self.assertIsNone(row)


if __name__ == "__main__":
    unittest.main()
