#!/usr/bin/env python3
"""
app.py
======
Command-line interface for the PDF Structured DB Agent.

Usage
-----
    python app.py input/sample.pdf
    python app.py input/                      # process every PDF in a folder
    python app.py input/sample.pdf -o output/  # custom output directory
    python app.py input/ --no-images           # skip image extraction
    python app.py input/ --ocr                 # enable OCR fallback for scanned pages
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config import CONFIG
from processors.pipeline import Pipeline
from utils.logger import logger


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.py",
        description="Extract structured content from PDF files into per-document SQLite databases.",
    )
    parser.add_argument(
        "input", nargs="?", type=str,
        help="Path to a PDF file or a folder containing PDF files.",
    )
    parser.add_argument(
        "-o", "--output", type=str, default=None,
        help=f"Output directory for generated .db files (default: {CONFIG.output_dir}).",
    )
    parser.add_argument(
        "--no-images", action="store_true",
        help="Disable image extraction (faster, smaller output/ folder).",
    )
    parser.add_argument(
        "--ocr", action="store_true",
        help="Enable OCR fallback for pages with no extractable text layer "
             "(requires pytesseract + the tesseract binary).",
    )
    return parser


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    if not args.input:
        build_arg_parser().print_help()
        return 1

    if args.no_images:
        object.__setattr__(CONFIG, "extract_images", False)
    if args.ocr:
        object.__setattr__(CONFIG, "enable_ocr", True)

    output_dir = Path(args.output) if args.output else CONFIG.output_dir

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input path does not exist: {input_path}")
        return 1

    pipeline = Pipeline(output_dir=output_dir)
    summary = pipeline.run(input_path)
    summary.print_report()

    return 0 if summary.failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
