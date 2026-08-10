"""
config.py
=========
Central configuration for the PDF Structured DB Agent.

All tunables live here (or can be overridden via environment variables / .env
file). Nothing elsewhere in the codebase should hard-code paths or magic
numbers that belong here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    # --- Directories -----------------------------------------------------
    base_dir: Path = Path(__file__).resolve().parent
    input_dir: Path = field(default_factory=lambda: Path(
        os.getenv("PDF_AGENT_INPUT_DIR", "input")))
    output_dir: Path = field(default_factory=lambda: Path(
        os.getenv("PDF_AGENT_OUTPUT_DIR", "output")))
    logs_dir: Path = field(default_factory=lambda: Path(
        os.getenv("PDF_AGENT_LOGS_DIR", "logs")))
    images_subdir: str = "images"

    # --- Processing --------------------------------------------------------
    # Number of pages processed together before an incremental DB commit.
    chunk_size: int = field(default_factory=lambda: _env_int("PDF_AGENT_CHUNK_SIZE", 25))
    # Number of rows batched per executemany() call.
    batch_insert_size: int = field(default_factory=lambda: _env_int("PDF_AGENT_BATCH_SIZE", 500))
    # Above this page count the agent switches to low-memory streaming mode.
    large_pdf_page_threshold: int = field(
        default_factory=lambda: _env_int("PDF_AGENT_LARGE_PDF_THRESHOLD", 200))

    # --- Feature toggles -----------------------------------------------------
    extract_images: bool = field(default_factory=lambda: _env_bool("PDF_AGENT_EXTRACT_IMAGES", True))
    enable_ocr: bool = field(default_factory=lambda: _env_bool("PDF_AGENT_ENABLE_OCR", False))
    ocr_dpi: int = field(default_factory=lambda: _env_int("PDF_AGENT_OCR_DPI", 200))
    # A page is treated as "scanned" (no extractable text layer) if the
    # number of extracted characters is below this threshold.
    min_chars_for_text_page: int = field(
        default_factory=lambda: _env_int("PDF_AGENT_MIN_CHARS_PAGE", 10))

    # --- Heading / layout heuristics ----------------------------------------
    # A text span is considered a heading candidate if its font size is at
    # least this many points larger than the page's median body font size.
    heading_size_delta: float = field(
        default_factory=lambda: _env_float("PDF_AGENT_HEADING_DELTA", 1.5))
    # Fraction of page height (from top/bottom) considered the header/footer band.
    header_zone_ratio: float = field(default_factory=lambda: _env_float("PDF_AGENT_HEADER_ZONE", 0.08))
    footer_zone_ratio: float = field(default_factory=lambda: _env_float("PDF_AGENT_FOOTER_ZONE", 0.08))

    # --- Logging -------------------------------------------------------------
    log_level: str = field(default_factory=lambda: os.getenv("PDF_AGENT_LOG_LEVEL", "INFO"))
    log_to_console: bool = field(default_factory=lambda: _env_bool("PDF_AGENT_LOG_CONSOLE", True))
    log_file_rotation: str = field(default_factory=lambda: os.getenv("PDF_AGENT_LOG_ROTATION", "10 MB"))
    log_file_retention: str = field(default_factory=lambda: os.getenv("PDF_AGENT_LOG_RETENTION", "10 days"))

    # --- Database ------------------------------------------------------------
    sqlite_journal_mode: str = field(default_factory=lambda: os.getenv("PDF_AGENT_JOURNAL_MODE", "WAL"))
    sqlite_synchronous: str = field(default_factory=lambda: os.getenv("PDF_AGENT_SYNCHRONOUS", "NORMAL"))

    def resolve(self) -> "Config":
        """Return a copy with directories made absolute & created on disk."""
        input_dir = (self.base_dir / self.input_dir).resolve()
        output_dir = (self.base_dir / self.output_dir).resolve()
        logs_dir = (self.base_dir / self.logs_dir).resolve()
        for d in (input_dir, output_dir, logs_dir):
            d.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "input_dir", input_dir)
        object.__setattr__(self, "output_dir", output_dir)
        object.__setattr__(self, "logs_dir", logs_dir)
        return self


CONFIG = Config().resolve()
