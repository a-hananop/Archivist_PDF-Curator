"""
processors/document_processor.py
==================================
Top-level orchestration for turning ONE PDF into ONE SQLite database.

Flow
----
1. Validate the PDF (corrupted / empty / encrypted checks).
2. Create <output>/<stem>.db and initialize its schema.
3. Extract & insert document metadata.
4. Stream pages through PageProcessor, inserting each page's structure.
5. Finalize the document row with status + timing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from config import CONFIG
from database.connection import DatabaseConnection
from database.models import DocumentRecord
from database.repository import DocumentRepository
from extractor.images import ImageExtractor
from extractor.pdf_loader import PDFLoader
from extractor.tables import TableExtractor
from parser.structure_builder import StructureBuilder
from processors.chunk_processor import ChunkProcessor
from processors.page_processor import PageProcessor
from utils.file_utils import derive_db_path, derive_images_dir
from utils.helpers import format_duration, timer
from utils.logger import logger
from utils.validators import validate_pdf


@dataclass
class DocumentProcessingResult:
    pdf_path: Path
    db_path: Optional[Path] = None
    success: bool = False
    status: str = "pending"
    pages_processed: int = 0
    pages_failed: int = 0
    total_pages: int = 0
    duration_sec: float = 0.0
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class DocumentProcessor:
    def __init__(self, output_dir: Path = None):
        self.output_dir = Path(output_dir or CONFIG.output_dir)

    def process(self, pdf_path: Path) -> DocumentProcessingResult:
        pdf_path = Path(pdf_path)
        result = DocumentProcessingResult(pdf_path=pdf_path)

        validation = validate_pdf(pdf_path)
        if not validation.is_valid:
            result.status = "failed"
            result.error = validation.error
            logger.error(f"{pdf_path.name}: validation failed -- {validation.error}")
            return result

        db_path = derive_db_path(pdf_path, self.output_dir)
        result.db_path = db_path
        result.total_pages = validation.page_count

        with timer() as t:
            try:
                self._run(pdf_path, db_path, validation.page_count, result)
            except Exception as exc:  # noqa: BLE001
                result.status = "failed"
                result.error = str(exc)
                logger.exception(f"{pdf_path.name}: unrecoverable error during processing")

        result.duration_sec = t.elapsed
        if result.status not in ("failed",):
            result.status = "completed" if result.pages_failed == 0 else "partial"
        result.success = result.status in ("completed", "partial")

        logger.info(
            f"{pdf_path.name}: {result.status} -- "
            f"{result.pages_processed}/{result.total_pages} pages in {format_duration(result.duration_sec)}"
        )
        return result

    def _run(self, pdf_path: Path, db_path: Path, page_count: int,
              result: DocumentProcessingResult) -> None:
        images_dir = derive_images_dir(pdf_path, self.output_dir, CONFIG.images_subdir)
        run_timer_cm = timer()
        run_timer = run_timer_cm.__enter__()

        with DatabaseConnection(db_path) as db_conn:
            repo = DocumentRepository(db_conn)

            loader = PDFLoader(pdf_path)
            table_extractor = TableExtractor(pdf_path)
            image_extractor = ImageExtractor(images_dir) if CONFIG.extract_images else _NullImageExtractor()
            structure_builder = StructureBuilder(table_extractor, image_extractor)
            page_processor = PageProcessor(structure_builder)
            chunk_processor = ChunkProcessor()

            try:
                doc = loader.open()
                table_extractor.open()

                file_size = pdf_path.stat().st_size
                doc_record = DocumentRecord(
                    filename=pdf_path.name, filepath=str(pdf_path.resolve()),
                    file_size_bytes=file_size, file_hash_sha256=loader.file_hash(),
                    page_count=page_count, is_encrypted=doc.is_encrypted,
                )
                repo.create_document(doc_record)

                pages_done = 0

                for chunk in chunk_processor.iter_page_chunks(doc):
                    for page_number, page in chunk:
                        page_result = page_processor.process(doc, page, page_number)

                        if not page_result.success:
                            result.pages_failed += 1
                            result.warnings.append(f"Page {page_number}: {page_result.error}")
                            continue

                        try:
                            repo.insert_page_structure(page_result.structure)
                            result.pages_processed += 1
                        except Exception as exc:  # noqa: BLE001
                            result.pages_failed += 1
                            result.warnings.append(f"Page {page_number}: DB insert failed: {exc}")
                            logger.error(f"Page {page_number}: DB insert failed: {exc}")

                        pages_done += 1

                    chunk_processor.checkpoint(pages_done, page_count)

            finally:
                loader.close()
                table_extractor.close()

            run_timer_cm.__exit__(None, None, None)
            repo.finalize_document(
                status="completed" if result.pages_failed == 0 else "partial",
                duration_sec=run_timer.elapsed,
                page_count=result.pages_processed + result.pages_failed,
            )


class _NullImageExtractor:
    """No-op stand-in used when image extraction is disabled via config."""

    def extract_images_for_page(self, *_args, **_kwargs):
        return []
