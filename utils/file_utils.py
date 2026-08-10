"""
utils/file_utils.py
====================
Filesystem helpers: discovering PDFs, deriving output paths, safe directory
creation, human-readable size formatting.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List


def discover_pdfs(path: Path) -> List[Path]:
    """Return a sorted list of PDF file paths.

    If `path` is a file, returns [path] (if it is a .pdf). If it is a
    directory, returns every .pdf file found directly inside it (non
    recursive by design, to keep behaviour predictable for CLI users).
    """
    path = Path(path)
    if path.is_file():
        return [path] if path.suffix.lower() == ".pdf" else []

    if path.is_dir():
        return sorted(p for p in path.glob("*.pdf") if p.is_file())

    return []


def sanitize_filename(name: str) -> str:
    """Strip characters that are unsafe for filenames across platforms."""
    name = name.strip()
    name = re.sub(r"[^\w\-. ]", "_", name)
    name = re.sub(r"\s+", "_", name)
    return name or "document"


def derive_db_path(pdf_path: Path, output_dir: Path) -> Path:
    """Given `Invoices.pdf`, return `<output_dir>/Invoices.db`."""
    stem = sanitize_filename(Path(pdf_path).stem)
    return Path(output_dir) / f"{stem}.db"


def derive_images_dir(pdf_path: Path, output_dir: Path, images_subdir: str) -> Path:
    stem = sanitize_filename(Path(pdf_path).stem)
    d = Path(output_dir) / images_subdir / stem
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_dir(path: Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"
