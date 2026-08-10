"""
processors/pipeline.py
========================
Highest-level entry point: given a file or folder path, discovers all
PDFs, runs the DocumentProcessor over each one, and reports an overall
summary. This is what the CLI (app.py / main.py) calls into.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover - tqdm is a listed dependency but degrade gracefully
    def tqdm(iterable, **kwargs):
        return iterable

from processors.document_processor import DocumentProcessingResult, DocumentProcessor
from utils.file_utils import discover_pdfs
from utils.helpers import format_duration
from utils.logger import logger


@dataclass
class PipelineSummary:
    results: List[DocumentProcessingResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.success)

    @property
    def total_duration(self) -> float:
        return sum(r.duration_sec for r in self.results)

    def print_report(self) -> None:
        print("\n" + "=" * 70)
        print("PDF STRUCTURED DB AGENT -- PROCESSING SUMMARY")
        print("=" * 70)
        for r in self.results:
            status_icon = {"completed": "OK", "partial": "PARTIAL", "failed": "FAILED"}.get(r.status, "?")
            print(f"[{status_icon:^7}] {r.pdf_path.name:<40} "
                  f"pages={r.pages_processed}/{r.total_pages}  "
                  f"time={format_duration(r.duration_sec)}")
            if r.db_path and r.success:
                print(f"           -> {r.db_path}")
            if r.error:
                print(f"           error: {r.error}")
            for w in r.warnings[:5]:
                print(f"           warning: {w}")
            if len(r.warnings) > 5:
                print(f"           ... and {len(r.warnings) - 5} more warnings")
        print("-" * 70)
        print(f"Total: {self.total}  Succeeded: {self.succeeded}  Failed: {self.failed}  "
              f"Time: {format_duration(self.total_duration)}")
        print("=" * 70 + "\n")


class Pipeline:
    def __init__(self, output_dir: Path = None):
        self.processor = DocumentProcessor(output_dir=output_dir)

    def run(self, input_path: Path) -> PipelineSummary:
        pdfs = discover_pdfs(Path(input_path))
        summary = PipelineSummary()

        if not pdfs:
            logger.warning(f"No PDF files found at: {input_path}")
            return summary

        logger.info(f"Discovered {len(pdfs)} PDF file(s) to process")

        for pdf_path in tqdm(pdfs, desc="Processing PDFs", unit="pdf"):
            result = self.processor.process(pdf_path)
            summary.results.append(result)

        return summary
