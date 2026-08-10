"""
extractor/metadata.py
======================
Extracts document-level metadata: standard PDF Info dictionary fields plus
whatever PyMuPDF surfaces (XMP-derived fields included when present).
"""

from __future__ import annotations

from typing import List

import fitz

from database.models import MetadataRecord

# Keys PyMuPDF's `doc.metadata` always provides (values may be empty strings).
_STANDARD_KEYS = [
    "title", "author", "subject", "keywords", "creator", "producer",
    "creationDate", "modDate", "trapped", "format", "encryption",
]


class MetadataExtractor:
    def extract(self, doc: fitz.Document) -> List[MetadataRecord]:
        records: List[MetadataRecord] = []
        meta = doc.metadata or {}

        for key in _STANDARD_KEYS:
            value = meta.get(key)
            if value:
                records.append(MetadataRecord(key=key, value=str(value)))

        # Any extra keys PyMuPDF included beyond the standard set.
        for key, value in meta.items():
            if key not in _STANDARD_KEYS and value:
                records.append(MetadataRecord(key=key, value=str(value)))

        records.append(MetadataRecord(key="page_count", value=str(doc.page_count)))

        try:
            toc = doc.get_toc()
            records.append(MetadataRecord(key="has_table_of_contents", value=str(bool(toc))))
            if toc:
                records.append(MetadataRecord(key="toc_entry_count", value=str(len(toc))))
        except Exception:
            pass

        return records
