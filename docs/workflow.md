# Processing Workflow

Step-by-step trace of what happens when you run:

```
python app.py input/sample.pdf
```

## 1. Discovery
`Pipeline.run()` calls `discover_pdfs()`, which resolves the input path to
a list of one or more `.pdf` files (a single file, or every `.pdf` directly
inside a folder).

## 2. Per-document setup
For each PDF, `DocumentProcessor.process()`:
1. Runs `validate_pdf()` -- checks the file exists, isn't zero bytes,
   opens cleanly with PyMuPDF, isn't password-locked (or unlocks with an
   empty password), and has at least one page. Invalid PDFs short-circuit
   here with `status="failed"` and a clear error message; nothing else in
   the pipeline is touched.
2. Derives the output path: `output/<pdf-stem>.db`.
3. Opens a `DatabaseConnection`, which creates the file and runs the full
   schema (`CREATE TABLE IF NOT EXISTS ...` x18, then indexes).

## 3. Document-level extraction
* `PDFLoader.file_hash()` computes a streamed SHA-256 of the PDF (for
  dedup/audit purposes) without loading the whole file into memory.
* `MetadataExtractor.extract()` pulls the standard Info dictionary fields
  (Title, Author, Subject, Creator, Producer, dates, ...) plus a
  table-of-contents presence check.
* A `documents` row and its `metadata` rows are inserted immediately.

## 4. Page-by-page streaming
`ChunkProcessor.iter_page_chunks()` yields pages in groups of
`PDF_AGENT_CHUNK_SIZE` (default 25). For each page, in order:

1. **Text extraction** (`TextExtractor`): PyMuPDF's structured "dict" mode
   gives blocks -> lines -> spans, each with font name/size/bold/italic
   and a bounding box.
2. **Layout split** (`LayoutExtractor`): lines are partitioned into
   header-zone / body / footer-zone based on vertical position.
3. **Heading & list classification** (`HeadingParser`): every body line is
   scored against the page's median body font size; larger/bolder/short
   lines become heading candidates (with a level assigned by relative
   size); lines starting with a bullet or numbered marker become list
   items (font-size heading detection takes priority when the two signals
   disagree, e.g. a numbered chapter title like "1. Introduction").
4. **Section building** (`SectionParser` + a document-level
   `SectionStack`): each heading opens a new section at its level, closing
   any open sections at an equal-or-deeper level. This stack persists
   across pages so a section can correctly span a page break.
5. **Paragraph & list grouping** (`ParagraphParser`): consecutive
   non-heading, non-list body lines are merged into paragraphs;
   consecutive list-item lines of the same type are grouped into a list.
6. **Tables** (`TableExtractor` / pdfplumber): ruled tables are found
   first with a strict line-based strategy, falling back to a
   whitespace/text-based strategy if nothing is found; each table becomes
   a fully relational row/cell grid.
7. **Images** (`ImageExtractor`): every embedded image on the page is
   extracted via PyMuPDF and written to
   `output/images/<pdf-stem>/pageN_imgM.<ext>`; the database stores only
   the file path and metadata (dimensions, format, size).
8. **Links** (`LayoutExtractor.extract_links`): both external URI links
   and internal go-to-page links, with their bounding box.
9. **Captions**: paragraphs starting with "Figure", "Table", or "Image"
   are flagged as captions.
10. **OCR fallback** (optional, `--ocr`): if a page's extracted text is
    below `PDF_AGENT_MIN_CHARS_PAGE` characters (looks scanned) and OCR is
    enabled, the page is rasterized and run through Tesseract; recovered
    text replaces the page's stored text.

All of this is assembled into one `PageStructure` object per page.

## 5. Insertion
`DocumentRepository.insert_page_structure()` inserts the entire page's
structure in **one SQLite transaction**: the page row, its sections
(resolving parent links either to a section on the same page or an
already-committed section from an earlier page), headings, paragraphs,
lists + list items, images, tables + rows + cells, links, captions, and
header/footer text. A failure partway through rolls the whole page back --
never a half-written page.

After each chunk, `gc.collect()` runs and a checkpoint log line reports
progress (`N/total pages processed`).

## 6. Finalization
Once every page has been attempted (successes and failures alike), the
`documents` row is updated with:
* `processing_status`: `completed` if every page succeeded, `partial` if
  some pages failed but the database is still usable, `failed` only if the
  PDF couldn't be opened at all.
* `processing_completed_at`, `processing_duration_sec`.
* Accumulated font usage counts are flushed to the `fonts` table.

## 7. Reporting
`Pipeline.run()` collects a `DocumentProcessingResult` per PDF and
`PipelineSummary.print_report()` prints a per-file status line (with page
counts, timing, output path, and up to 5 warnings) plus an overall totals
line. The process exit code is `0` if every PDF succeeded, `2` if any
failed, `1` for a usage/input error.
