"""
database/connection.py
=======================
SQLite connection lifecycle management: one dedicated connection per PDF
document database, tuned pragmas for write-heavy incremental inserts, and
a transaction context manager used by the repository layer.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from config import CONFIG
from database.schema import get_full_schema_sql
from utils.logger import logger


class DatabaseConnection:
    """Wraps a single sqlite3 connection for one document's .db file."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    # -- lifecycle ---------------------------------------------------------
    def connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn

        conn = sqlite3.connect(str(self.db_path), timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(f"PRAGMA journal_mode = {CONFIG.sqlite_journal_mode};")
        conn.execute(f"PRAGMA synchronous = {CONFIG.sqlite_synchronous};")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA cache_size = -20000;")  # ~20MB page cache

        self._conn = conn
        logger.debug(f"Opened SQLite connection: {self.db_path}")
        return conn

    # All tables that may exist in either old or new schema versions
    _ALL_KNOWN_TABLES = [
        # New schema
        "short_paragraphs", "long_paragraphs", "images",
        # Old schema tables (to be wiped on upgrade)
        "paragraphs", "headings", "sections", "pages", "tables", "table_rows",
        "table_cells", "lists", "list_items", "links", "captions", "headers",
        "footers", "fonts", "metadata", "processing_logs", "documents",
    ]

    def initialize_schema(self) -> None:
        """Initialize the database schema.

        If the database has an incompatible old schema, all known tables are
        explicitly dropped before the new schema is applied. This works even
        when the database file is locked and cannot be deleted.
        """
        conn = self.connect()

        # Detect whether this db already has the current schema
        schema_is_current = False
        try:
            conn.execute("SELECT 1 FROM short_paragraphs LIMIT 1")
            schema_is_current = True
        except Exception:
            pass

        if not schema_is_current:
            logger.info(f"Old or empty schema detected in {self.db_path.name} -- migrating to new schema")
            # First try to delete the file for a clean start
            self.close()
            try:
                if self.db_path.exists():
                    self.db_path.unlink()
                    logger.info(f"Deleted old database: {self.db_path.name}")
                conn = self.connect()
            except OSError:
                # File is locked — fall back to dropping tables in-place
                logger.warning(f"Could not delete {self.db_path.name} (file locked) — dropping tables in-place")
                conn = self.connect()
                # Disable FK checks so we can drop in any order
                conn.execute("PRAGMA foreign_keys = OFF;")
                # Drop any dynamically-created tables first (PDF tables / long paragraph tables)
                dynamic = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT IN ({})".format(
                        ",".join("?" * len(self._ALL_KNOWN_TABLES))
                    ),
                    self._ALL_KNOWN_TABLES,
                ).fetchall()
                for row in dynamic:
                    conn.execute(f'DROP TABLE IF EXISTS "{row[0]}"')
                # Drop all known tables
                for t in self._ALL_KNOWN_TABLES:
                    conn.execute(f"DROP TABLE IF EXISTS {t}")
                conn.execute("PRAGMA foreign_keys = ON;")

        conn.executescript(get_full_schema_sql())
        logger.debug(f"Schema ready: {self.db_path}")

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.execute("PRAGMA optimize;")
            except sqlite3.Error:
                pass
            self._conn.close()
            self._conn = None
            logger.debug(f"Closed SQLite connection: {self.db_path}")

    # -- transactions --------------------------------------------------------
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Explicit BEGIN/COMMIT block; rolls back on any exception."""
        conn = self.connect()
        conn.execute("BEGIN;")
        try:
            yield conn
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise

    # -- context manager protocol --------------------------------------------
    def __enter__(self) -> "DatabaseConnection":
        self.connect()
        self.initialize_schema()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
