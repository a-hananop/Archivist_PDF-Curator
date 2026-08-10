"""
database/queries.py
====================
Convenience read-only queries against a completed document database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def get_document_summary(db_path: Path) -> Dict[str, Any]:
    """Return basic document info plus row counts for the core tables."""
    conn = _connect(db_path)
    try:
        doc = conn.execute("SELECT * FROM documents LIMIT 1").fetchone()
        if doc is None:
            return {}
        summary = dict(doc)

        counts = {}
        for t in ("short_paragraphs", "long_paragraphs", "images"):
            row = conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()
            counts[t] = row["c"] if row else 0

        # Also count any dynamically-created tables (PDF tables and long-paragraph tables)
        all_tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT IN ('documents','short_paragraphs','long_paragraphs','images')"
        ).fetchall()
        counts["dynamic_tables"] = len(all_tables)
        summary["table_counts"] = counts
        return summary
    finally:
        conn.close()


def get_all_short_paragraphs(db_path: Path) -> List[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT heading, text FROM short_paragraphs ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_long_paragraphs(db_path: Path) -> List[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT heading, text FROM long_paragraphs ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_images(db_path: Path) -> List[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT caption, file_path FROM images ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
