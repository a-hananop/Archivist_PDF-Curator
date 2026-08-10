# Database Design

Every PDF gets exactly one SQLite database (`<pdf-stem>.db` in the output
directory). The schema is fully normalized with foreign keys, indexes, and
`ON DELETE CASCADE` throughout.

## Entity-relationship overview

```
documents (1)
  |-- metadata (N)            key/value PDF metadata
  |-- fonts (N)                font inventory + usage counts
  |-- processing_logs (N)      structured log lines
  |
  +-- pages (N)
        |-- headers (N)
        |-- footers (N)
        |-- sections (N, self-referencing via parent_section_id)
        |     |-- headings (N)
        |     |-- paragraphs (N)
        |     |-- lists (N) -- list_items (N)
        |     +-- tables (N)
        |
        |-- headings (N, also linked to a section)
        |-- paragraphs (N, also linked to a section)
        |-- lists (N) -- list_items (N)
        |-- tables (N) -- table_rows (N) -- table_cells (N)
        |-- images (N)
        |-- links (N)
        +-- captions (N, polymorphic: related_type + related_id -> image|table)
```

## Table reference

| Table | Purpose | Key columns |
|---|---|---|
| `documents` | One row per PDF. Tracks processing status/timing. | `id`, `filename`, `page_count`, `processing_status` |
| `metadata` | Flexible key/value PDF metadata (Title, Author, CreationDate, ...). | `document_id`, `key`, `value` |
| `pages` | One row per PDF page. | `document_id`, `page_number`, `width`, `height`, `full_text` |
| `sections` | Hierarchical grouping built from headings. Self-referencing via `parent_section_id`. | `page_id`, `parent_section_id`, `title`, `level` |
| `headings` | Every detected heading/sub-heading, with font info and reading order. | `page_id`, `section_id`, `text`, `level`, `font_size`, `is_bold` |
| `paragraphs` | Reconstructed paragraphs (merged from consecutive lines). | `page_id`, `section_id`, `text`, `font_size` |
| `lists` / `list_items` | Bullet and numbered lists. | `list_type`, `item_index` |
| `tables` / `table_rows` / `table_cells` | Fully normalized table grid. | `num_rows`, `num_cols`, `row_index`, `col_index` |
| `images` | Extracted images, referenced by file path (bytes live on disk, not in SQLite). | `file_path`, `width`, `height`, `format` |
| `links` | Both external URI links and internal go-to-page links. | `link_type`, `uri`, `target_page` |
| `captions` | Figure/table captions, polymorphically linked via `related_type` + `related_id`. | `related_type`, `related_id`, `text` |
| `headers` / `footers` | Running header/footer text per page (margin-band heuristic). | `page_id`, `text` |
| `fonts` | Document-level font inventory with usage counts. | `font_name`, `usage_count` |
| `processing_logs` | Structured processing events for auditing/debugging. | `level`, `message`, `page_number` |

## Design decisions

* **`document_id` denormalized onto every content table.** Every table
  below `pages` also carries `document_id` directly (not just `page_id`),
  so queries scoped to "everything in this document" never need a join
  through `pages`.
* **Bounding boxes stored as four flat columns** (`bbox_x0`, `bbox_y0`,
  `bbox_x1`, `bbox_y1`) rather than a nested structure -- keeps SQLite
  queries and indexes simple.
* **`reading_order` on headings/paragraphs** preserves the
  top-to-bottom, left-to-right flow PDFs don't guarantee natively (e.g.
  multi-column layouts).
* **Tables use a fully relational grid** (`table_rows` -> `table_cells`)
  rather than a single JSON/CSV blob, so individual cells are queryable
  and joinable like any other structured data.
* **Captions are polymorphic** (`related_type` + `related_id`) rather than
  having separate `image_captions`/`table_captions` tables, since a
  caption's shape is identical either way.
* **Indexes** exist on every foreign key plus the columns used for common
  lookups (`page_number`, `order_index`), so both `WHERE document_id = ?`
  and `ORDER BY page_number, order_index` style queries stay fast even on
  documents with thousands of pages.

## Example queries

```sql
-- All headings in reading order
SELECT p.page_number, h.level, h.text
FROM headings h JOIN pages p ON p.id = h.page_id
ORDER BY p.page_number, h.order_index;

-- Reconstruct a table as a grid
SELECT row_index, col_index, text
FROM table_cells WHERE table_id = ?
ORDER BY row_index, col_index;

-- Full-text-ish search across paragraphs
SELECT p.page_number, pa.text
FROM paragraphs pa JOIN pages p ON p.id = pa.page_id
WHERE pa.text LIKE '%budget%';

-- Section outline (top-level only)
SELECT title, level FROM sections WHERE parent_section_id IS NULL ORDER BY order_index;
```

See `database/queries.py` for ready-made Python helpers wrapping queries
like these.
