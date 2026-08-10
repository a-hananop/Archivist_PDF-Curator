# PDF Structured DB Agent

A production-ready, memory-efficient agent that reads PDF documents,
extracts everything it can find, and stores it in a **dedicated SQLite database per PDF**.

```
Invoices.pdf   ->   output/Invoices.db
Research.pdf   ->   output/Research.db
Book.pdf       ->   output/Book.db
```

Handles everything from 1-page invoices to 1000+ page books, with
page-by-page streaming so memory stays flat regardless of document size.

## What gets extracted

- **Paragraphs**: Separated into `short_paragraphs` and `long_paragraphs` with their corresponding headings.
- **Tables**: Extracted using **Camelot** (lattice & stream modes). Each table in the PDF becomes its **own dynamic flat table** in the SQLite database, named after the table's real title, with actual column names perfectly preserved.
- **Images**: Extracted and saved to disk, with references stored in an `images` table.

## Installation

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Table Extraction Dependencies (Camelot)
This project uses Camelot for high-accuracy table extraction, which requires Ghostscript for processing bordered tables:
- **Windows**: Download and install the 64-bit Ghostscript installer from [ghostscript.com](https://www.ghostscript.com/releases/gsdnld.html).
- **macOS**: `brew install ghostscript`
- **Linux (Ubuntu)**: `sudo apt-get install ghostscript`

Optional OCR support (for scanned PDFs with no text layer):
```bash
pip install pytesseract
# plus the tesseract-ocr binary itself, e.g.:
#   macOS:   brew install tesseract
#   Ubuntu:  sudo apt-get install tesseract-ocr
#   Windows: https://github.com/UB-Mannheim/tesseract/wiki
```

Copy `.env.example` to `.env` if you want to override any default setting.

## Usage

```bash
# Process a single PDF
python app.py input/sample.pdf

# Process every PDF in a folder
python app.py input/

# Custom output directory
python app.py input/sample.pdf -o my_output/

# Skip image extraction (faster, smaller output/ folder)
python app.py input/ --no-images

# Enable OCR fallback for scanned pages
python app.py input/ --ocr

# Inspect an already-generated database
python app.py --summary output/sample.db
```

`main.py` is an equivalent alias: `python main.py input/sample.pdf` works
identically to `app.py`.

Every run prints a summary:
```
======================================================================
PDF STRUCTURED DB AGENT -- PROCESSING SUMMARY
======================================================================
[  OK   ] sample.pdf                               pages=2/2  time=0.09s
           -> output/sample.db
----------------------------------------------------------------------
Total: 1  Succeeded: 1  Failed: 0  Time: 0.09s
======================================================================
```

Exit code is `0` if everything succeeded, `2` if any PDF failed, `1` for a
usage error.

## Project structure

```
pdf_structured_db_agent/
├── app.py                  CLI entry point
├── main.py                 Alias for app.py
├── config.py                Central configuration (env-overridable)
├── requirements.txt
├── .env.example
│
├── input/                   Drop PDFs here (or point the CLI elsewhere)
├── output/                  Generated .db files + extracted images
├── logs/                    Rotating log files
│
├── extractor/                Raw PDF -> structural primitives
│   ├── pdf_loader.py          Memory-safe PyMuPDF wrapper
│   ├── metadata.py            Document metadata
│   ├── text.py                Blocks/lines/spans + fonts
│   ├── layout.py               Page geometry, header/footer zones, links
│   ├── tables.py               Camelot-based table extraction (lattice/stream)
│   ├── images.py               Embedded image extraction
│   └── ocr.py                  Optional Tesseract fallback
│
├── parser/                    Structural primitives -> document semantics
│   ├── heading_parser.py       Heading/list classification heuristics
│   ├── paragraph_parser.py     Paragraph & list grouping
│   ├── section_parser.py       Cross-page section hierarchy
│   └── structure_builder.py    Orchestrates one page's full structure
│
├── database/                  Everything SQLite
│   ├── schema.py               Flat DDL structure (paragraphs, images, docs)
│   ├── connection.py           Tuned connection + transactions
│   ├── models.py                Dataclasses mirroring the schema
│   ├── repository.py            Batched, transactional inserts + dynamic tables
│   └── queries.py               Read-side convenience queries
│
├── processors/                 Orchestration
│   ├── document_processor.py    One PDF -> one .db, start to finish
│   ├── page_processor.py         One page, with OCR fallback
│   ├── chunk_processor.py        Memory-bounded page batching
│   └── pipeline.py               Fans out across a folder of PDFs
│
├── utils/
│   ├── logger.py                loguru-backed logging (stdlib fallback)
│   ├── validators.py             PDF validation
│   ├── file_utils.py              Path helpers
│   └── helpers.py                 Timing, batching, stats helpers
│
├── tests/                     Unit + end-to-end tests
└── docs/
    ├── architecture.md
    ├── database_design.md
    └── workflow.md
```

## Performance & memory

* Pages are streamed one at a time -- the full PDF is never loaded into memory.
* Each page's structured content is inserted in its own SQLite transaction immediately after extraction.
* For PDFs at or above `PDF_AGENT_LARGE_PDF_THRESHOLD` pages (default 200), a `gc.collect()` runs after every `PDF_AGENT_CHUNK_SIZE` pages (default 25) to keep resident memory flat across thousands of pages.
* SQLite runs in WAL mode with a tuned page cache for fast incremental writes.

## Error handling

Corrupted PDFs, empty PDFs, password-protected PDFs (empty-password unlock is attempted automatically), missing metadata, broken pages, unreadable tables, and image extraction failures are all caught and logged -- processing continues for every other page/PDF whenever possible. A document's final status is `completed`, `partial` (some pages failed but the database is still usable), or `failed` (the PDF couldn't be opened at all).

## Querying the results

You can query the `.db` file directly with DB Browser for SQLite or any client. The database uses a highly accessible **flat structure**:
- `short_paragraphs` / `long_paragraphs` for categorized text content.
- `images` for extracted graphics.
- **Dynamic Tables**: Each table found in the PDF gets its own dedicated SQLite table, populated with exact column names and full data rows!
