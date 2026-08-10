"""
extractor/images.py
====================
Image extraction using PyMuPDF. Images are written to disk under
`output/images/<pdf_stem>/pageN_imgM.<ext>` and referenced from the
database by file path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import fitz

from utils.logger import logger


@dataclass
class ExtractedImageBBox:
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0


@dataclass
class ExtractedImage:
    """Internal image result — carries file_path and bbox for caption matching."""
    file_path: str = ""
    bbox: ExtractedImageBBox = field(default_factory=ExtractedImageBBox)


class ImageExtractor:
    def __init__(self, images_dir: Path):
        self.images_dir = Path(images_dir)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def extract_images_for_page(self, doc: fitz.Document, page: fitz.Page,
                                 page_number: int) -> List[ExtractedImage]:
        records: List[ExtractedImage] = []
        image_list = page.get_images(full=True)
        if not image_list:
            return records

        rects_by_xref = {}
        for xref, *_ in image_list:
            try:
                rects = page.get_image_rects(xref)
                if rects:
                    rects_by_xref[xref] = rects[0]
            except Exception:
                pass

        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
            except Exception as exc:
                logger.warning(f"Failed to extract image xref={xref} on page {page_number}: {exc}")
                continue

            ext = base_image.get("ext", "png")
            image_bytes = base_image.get("image", b"")
            if not image_bytes:
                continue

            filename = f"page{page_number}_img{img_index}.{ext}"
            file_path = self.images_dir / filename
            try:
                with open(file_path, "wb") as f:
                    f.write(image_bytes)
            except OSError as exc:
                logger.warning(f"Could not write image {file_path}: {exc}")
                continue

            rect = rects_by_xref.get(xref)
            bbox = ExtractedImageBBox(rect.x0, rect.y0, rect.x1, rect.y1) if rect else ExtractedImageBBox()

            records.append(ExtractedImage(
                file_path=str(file_path),
                bbox=bbox,
            ))

        return records
