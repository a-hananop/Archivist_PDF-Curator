# Architecture

## Overview

The PDF Structured DB Agent turns each PDF into its own SQLite database
through a five-layer pipeline:

```
CLI (app.py / main.py)
        |
        v
Pipeline (processors/pipeline.py)
        |  discovers PDFs, iterates, aggregates results
        v
DocumentProcessor (processors/document_processor.py)
        |  owns the lifecycle of ONE pdf -> ONE db
        v
ChunkProcessor -> PageProcessor -> StructureBuilder
        |            |                  |
        |            |                  +-- TextExtractor / LayoutExtractor
        |            |                  +-- HeadingParser / SectionParser / ParagraphParser
        |            |                  +-- TableExtractor (pdfplumber)
        |            |                  +-- ImageExtractor
        |            +-- OCRExtractor (optional fallback)
        v
DocumentRepository (database/repository.py)
        |  batched, transactional inserts
        v
SQLite .db file (one per PDF)
```

## Layers

### Extractor layer (`extractor/`)
Talks directly to the PDF bytes. `pdf_loader.py` wraps PyMuPDF for
memory-safe page streaming; `text.py` flattens PyMuPDF's block/line/span
structure; `layout.py` derives page geometry, header/footer bands, and
hyperlinks; `tables.py` wraps pdfplumber's table finder; `images.py`
extracts and writes embedded images to disk; `ocr.py` is an optional
Tesseract fallback for scanned pages.

This layer knows nothing about "headings" or "paragraphs" -- it only
returns raw structural primitives (spans, blocks, tables, images, links).

### Parser layer (`parser/`)
Classifies the raw primitives into document-semantic concepts:
* `heading_parser.py` -- is this line a heading (and what level), a bullet,
  or a numbered list item, based on font-size/boldness/shape heuristics.
* `paragraph_parser.py` -- groups consecutive body lines into paragraphs,
  and consecutive list-item lines into lists.
* `section_parser.py` -- builds the section hierarchy from headings,
  tracking a `SectionStack` that persists **across pages** so sections
  spanning multiple pages get correctly nested parent/child relationships.
* `structure_builder.py` -- orchestrates all of the above plus the table,
  image, and link extractors into one `PageStructure` per page.

### Database layer (`database/`)
* `schema.py` -- the full normalized DDL (18 tables).
* `connection.py` -- one tuned SQLite connection per document, WAL mode,
  transaction context manager.
* `models.py` -- plain dataclasses mirroring the schema, passed between
  parser and repository.
* `repository.py` -- all inserts, one transaction per page, batched with
  `executemany()`.
* `queries.py` -- convenience read-only helpers for downstream consumers.

### Processor layer (`processors/`)
Coordinates everything for one document (`document_processor.py`), streams
pages in memory-bounded chunks (`chunk_processor.py`), and processes each
page with OCR fallback (`page_processor.py`). `pipeline.py` is the
highest-level entry point that fans this out across every PDF in a folder.

## Memory model

For large PDFs (page count >= `PDF_AGENT_LARGE_PDF_THRESHOLD`, default
200):
* Pages are loaded one at a time via `PDFLoader.iter_pages()` /
  `ChunkProcessor.iter_page_chunks()` -- the full document is never
  materialized in memory.
* Every page's structured content is inserted into SQLite immediately
  (one transaction per page) rather than accumulated and flushed at the
  end.
* `gc.collect()` runs after each chunk (`PDF_AGENT_CHUNK_SIZE` pages,
  default 25) to keep resident memory flat across thousands of pages.
* Image bytes are streamed straight to disk, never held in Python objects
  longer than one page's processing.

## Error handling philosophy

Every layer is designed so a single bad page, bad table, or bad image
never aborts the whole document:
* `PageProcessor.process()` catches all exceptions and returns a
  `PageProcessingResult(success=False, error=...)` instead of raising.
* `DocumentProcessor._run()` continues to the next page on a failed page,
  recording a `processing_logs` row and a warning.
* The document's final `processing_status` reflects reality: `completed`
  (zero page failures), `partial` (some pages failed but the db was still
  produced), or `failed` (the PDF could not be opened/validated at all).
