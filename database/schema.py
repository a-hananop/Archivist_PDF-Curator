"""
database/schema.py
===================
Simplified schema for PDF parsing based on user request.
"""

SCHEMA_STATEMENTS = [
    # ------------------------------------------------------------------ #
    # documents
    # ------------------------------------------------------------------ #
    """
    CREATE TABLE IF NOT EXISTS documents (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        filename            TEXT NOT NULL,
        filepath            TEXT NOT NULL,
        file_size_bytes     INTEGER,
        file_hash_sha256    TEXT,
        page_count          INTEGER NOT NULL DEFAULT 0,
        is_encrypted        INTEGER NOT NULL DEFAULT 0,
        processing_status   TEXT NOT NULL DEFAULT 'pending',
        processing_started_at   TEXT,
        processing_completed_at TEXT,
        processing_duration_sec REAL,
        error_message       TEXT,
        created_at          TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,

    # ------------------------------------------------------------------ #
    # short_paragraphs
    # ------------------------------------------------------------------ #
    """
    CREATE TABLE IF NOT EXISTS short_paragraphs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        heading         TEXT,
        text            TEXT NOT NULL
    );
    """,

    # ------------------------------------------------------------------ #
    # long_paragraphs
    # ------------------------------------------------------------------ #
    """
    CREATE TABLE IF NOT EXISTS long_paragraphs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        heading         TEXT,
        text            TEXT NOT NULL
    );
    """,

    # ------------------------------------------------------------------ #
    # images
    # ------------------------------------------------------------------ #
    """
    CREATE TABLE IF NOT EXISTS images (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        caption         TEXT,
        file_path       TEXT
    );
    """
]

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_short_paragraphs_document ON short_paragraphs(document_id);",
    "CREATE INDEX IF NOT EXISTS idx_long_paragraphs_document ON long_paragraphs(document_id);",
    "CREATE INDEX IF NOT EXISTS idx_images_document ON images(document_id);",
]

def get_full_schema_sql() -> str:
    """Return the complete schema (tables + indexes) as one SQL script."""
    return "\n".join(SCHEMA_STATEMENTS) + "\n" + "\n".join(INDEX_STATEMENTS)
