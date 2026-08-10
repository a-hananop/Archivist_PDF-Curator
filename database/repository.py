"""
database/repository.py
=======================
Simplified data-access layer for the custom schema.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Dict, List, Optional

from config import CONFIG
from database.connection import DatabaseConnection
from database.models import (
    DocumentRecord, PageStructure,
)
from utils.logger import logger


class DocumentRepository:
    def __init__(self, db_conn: DatabaseConnection):
        self.db_conn = db_conn
        self.document_id: Optional[int] = None

    def create_document(self, record: DocumentRecord) -> int:
        with self.db_conn.transaction() as tx:
            cur = tx.execute(
                """
                INSERT INTO documents
                    (filename, filepath, file_size_bytes, file_hash_sha256,
                     page_count, is_encrypted, processing_status,
                     processing_started_at)
                VALUES (?, ?, ?, ?, ?, ?, 'processing', datetime('now'))
                """,
                (
                    record.filename, record.filepath, record.file_size_bytes,
                    record.file_hash_sha256, record.page_count,
                    int(record.is_encrypted),
                ),
            )
            self.document_id = cur.lastrowid
        logger.info(f"Created document row id={self.document_id} for {record.filename}")
        return self.document_id

    def finalize_document(self, status: str, duration_sec: float,
                           error_message: Optional[str] = None,
                           page_count: Optional[int] = None) -> None:
        with self.db_conn.transaction() as tx:
            tx.execute(
                """
                UPDATE documents
                SET processing_status = ?,
                    processing_completed_at = datetime('now'),
                    processing_duration_sec = ?,
                    error_message = ?,
                    page_count = COALESCE(?, page_count)
                WHERE id = ?
                """,
                (status, duration_sec, error_message, page_count, self.document_id),
            )

    def insert_page_structure(self, structure: PageStructure) -> None:
        """Insert paragraphs and tables/images for a page."""
        with self.db_conn.transaction() as tx:
            self._insert_paragraphs(tx, structure.paragraphs)
            self._insert_images(tx, structure.images)
            self._insert_tables(tx, structure.tables)

    def _insert_paragraphs(self, tx: sqlite3.Connection, paragraphs: list) -> None:
        short_rows = []
        long_rows = []
        
        for p in paragraphs:
            if p.is_long:
                long_rows.append((self.document_id, p.heading, p.text))
            else:
                short_rows.append((self.document_id, p.heading, p.text))
        
        if short_rows:
            tx.executemany(
                "INSERT INTO short_paragraphs (document_id, heading, text) VALUES (?, ?, ?)",
                short_rows
            )
            
        if long_rows:
            # Insert into the general long_paragraphs table
            tx.executemany(
                "INSERT INTO long_paragraphs (document_id, heading, text) VALUES (?, ?, ?)",
                long_rows
            )
            
            # AND ALSO CREATE A SEPARATE TABLE FOR EACH LONG PARAGRAPH!
            # The user requested: "When I click on a long paragraph, only that particular long paragraph should be displayed properly."
            for doc_id, heading, text in long_rows:
                safe_title = self._sanitize_table_name(heading or "Long Paragraph")
                # Append a short excerpt to ensure uniqueness if needed, or rely on auto-incrementing if conflicts arise
                safe_title = self._get_unique_table_name(tx, safe_title)
                
                create_stmt = f'CREATE TABLE "{safe_title}" (heading TEXT, text TEXT)'
                tx.execute(create_stmt)
                tx.execute(f'INSERT INTO "{safe_title}" (heading, text) VALUES (?, ?)', (heading, text))


    def _insert_images(self, tx: sqlite3.Connection, images: list) -> None:
        if not images:
            return
        rows = [(self.document_id, img.caption, img.file_path) for img in images]
        tx.executemany(
            "INSERT INTO images (document_id, caption, file_path) VALUES (?, ?, ?)",
            rows
        )

    def _insert_tables(self, tx: sqlite3.Connection, tables: list) -> None:
        """Dynamically create a SQLite table for each PDF table and insert its data."""
        for table in tables:
            safe_title = self._sanitize_table_name(table.title)
            safe_title = self._get_unique_table_name(tx, safe_title)

            if not table.rows:
                continue

            num_cols = max(len(row.cells) for row in table.rows)
            if num_cols == 0:
                continue

            # Find where the header ends and data begins.
            # All rows up to and including the is_header_row are header rows.
            # Merge them column-by-column into a single header name.
            header_end = 0
            for i, row in enumerate(table.rows):
                if row.is_header_row:
                    header_end = i
                    break

            # Collect header rows (rows 0 .. header_end inclusive)
            header_rows = table.rows[:header_end + 1]
            data_rows = table.rows[header_end + 1:]

            # Build column names by merging each column across all header rows
            col_names = []
            for col_idx in range(num_cols):
                parts = []
                for hrow in header_rows:
                    for cell in hrow.cells:
                        if cell.col_index == col_idx and cell.text.strip():
                            parts.append(cell.text.strip())
                merged = " ".join(parts).strip()
                col_names.append(self._sanitize_col_name(merged) if merged else f"Col_{col_idx+1}")

            # Ensure column name uniqueness (handles truncation collisions too)
            used: set = set()
            unique_cols = []
            for c in col_names:
                if c not in used:
                    used.add(c)
                    unique_cols.append(c)
                else:
                    counter = 1
                    candidate = f"{c}_{counter}"
                    while candidate in used:
                        counter += 1
                        candidate = f"{c}_{counter}"
                    used.add(candidate)
                    unique_cols.append(candidate)
            col_names = unique_cols

            col_defs = ", ".join([f'"{c}" TEXT' for c in col_names])
            create_stmt = f'CREATE TABLE "{safe_title}" ({col_defs})'
            try:
                tx.execute(create_stmt)
            except Exception as exc:
                logger.warning(f"Could not create table '{safe_title}': {exc}")
                continue

            # Insert data rows
            if data_rows:
                placeholders = ", ".join(["?"] * num_cols)
                insert_stmt = f'INSERT INTO "{safe_title}" VALUES ({placeholders})'

                rows_data = []
                for row in data_rows:
                    row_data = [""] * num_cols
                    for cell in row.cells:
                        if cell.col_index < num_cols:
                            row_data[cell.col_index] = cell.text
                    rows_data.append(tuple(row_data))

                tx.executemany(insert_stmt, rows_data)


    def _sanitize_table_name(self, name: str) -> str:
        name = name.strip()
        if not name:
            return "Table"
        # Remove characters that might break SQLite (quotes)
        name = name.replace('"', '').replace("'", "")
        # Truncate if insanely long
        return name[:100]
        
    def _sanitize_col_name(self, name: str) -> str:
        name = name.strip().replace('"', '').replace("'", "")
        if not name:
            return "Column"
        return name[:50]

    def _get_unique_table_name(self, tx: sqlite3.Connection, base_name: str) -> str:
        cur = tx.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0].lower() for row in cur.fetchall()}
        
        name = base_name
        counter = 1
        while name.lower() in existing_tables:
            name = f"{base_name} ({counter})"
            counter += 1
        return name
