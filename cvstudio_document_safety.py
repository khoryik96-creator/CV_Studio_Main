"""Shared document validation and bounded OCR primitives for CV Studio."""

from __future__ import annotations

import io
import threading
import time
from typing import Any
import zipfile


MAX_PDF_PAGES = 80
MAX_OCR_PAGES = 30
MAX_IMAGE_PIXELS = 60_000_000
MAX_ZIP_ENTRIES = 2000
MAX_ZIP_EXPANDED_BYTES = 160 * 1024 * 1024
MAX_ZIP_SINGLE_ENTRY_BYTES = 64 * 1024 * 1024
OCR_SEMAPHORE = threading.BoundedSemaphore(1)
OCR_TOTAL_DEADLINE_SECONDS = 180


def document_validation_status(exc: BaseException) -> int:
    """Map hostile/oversized document failures to a client-safe HTTP status."""
    message = str(exc or "").lower()
    name = type(exc).__name__.lower()
    resource_markers = (
        "safe limit",
        "too many files",
        "oversized internal",
        "unsafe compression",
        "expands beyond",
        "dimensions exceed",
        "decompressionbomb",
        "processing time limit",
        "ocr safe limit",
    )
    if any(marker in message or marker in name for marker in resource_markers):
        return 413
    return 400


def validate_zip_payload(file_bytes: bytes, label: str = "document") -> None:
    """Reject zip bombs and oversized expanded Office/ODT payloads."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise ValueError("{} contains too many files".format(label))
            total = 0
            for info in infos:
                size = max(0, int(info.file_size or 0))
                compressed = max(1, int(info.compress_size or 0))
                total += size
                if size > MAX_ZIP_SINGLE_ENTRY_BYTES:
                    raise ValueError(
                        "{} contains an oversized internal file".format(label)
                    )
                if size > 8 * 1024 * 1024 and size / compressed > 1000:
                    raise ValueError(
                        "{} has an unsafe compression ratio".format(label)
                    )
                if total > MAX_ZIP_EXPANDED_BYTES:
                    raise ValueError(
                        "{} expands beyond the safe limit".format(label)
                    )
    except zipfile.BadZipFile:
        raise ValueError(
            "{} is not a valid ZIP-based document".format(label)
        )


def safe_image_open(file_bytes: bytes):
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    image = Image.open(io.BytesIO(file_bytes))
    width, height = image.size
    if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
        image.close()
        raise ValueError("Image dimensions exceed the safe OCR limit")
    image.load()
    return image


def pdf_page_count(file_bytes: bytes) -> int:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        count = len(pdf.pages)
    if count > MAX_PDF_PAGES:
        raise ValueError(
            "PDF has {} pages; the safe limit is {}".format(count, MAX_PDF_PAGES)
        )
    return count


def ocr_image_text(
    pytesseract: Any,
    image: Any,
    lang: str = "eng",
    timeout: int = 35,
) -> str:
    if not OCR_SEMAPHORE.acquire(timeout=2):
        raise RuntimeError(
            "OCR is already processing another document. "
            "Wait for it to finish and try again."
        )
    try:
        return pytesseract.image_to_string(image, lang=lang, timeout=timeout)
    finally:
        OCR_SEMAPHORE.release()


def render_pdf_page_images(
    file_bytes: bytes,
    first_page: int = 1,
    last_page: int | None = None,
    dpi: int = 220,
    poppler_path: str | None = None,
    timeout: int = 45,
) -> list[Any]:
    """Render a bounded PDF page range using PDFium, then Poppler fallback."""
    first_page = max(1, int(first_page or 1))
    last_page = max(first_page, int(last_page or first_page))
    render_error = None
    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(file_bytes)
        images = []
        try:
            page_count = len(document)
            if first_page > page_count:
                return []
            last_page = min(last_page, page_count)
            scale = max(1.0, min(4.0, float(dpi or 220) / 72.0))
            for page_index in range(first_page - 1, last_page):
                page = document[page_index]
                bitmap = None
                try:
                    bitmap = page.render(scale=scale)
                    image = bitmap.to_pil().copy()
                    images.append(image)
                finally:
                    try:
                        if bitmap is not None:
                            bitmap.close()
                    except Exception:
                        pass
                    try:
                        page.close()
                    except Exception:
                        pass
            return images
        finally:
            try:
                document.close()
            except Exception:
                pass
    except Exception as exc:
        render_error = exc

    try:
        from pdf2image import convert_from_bytes

        return convert_from_bytes(
            file_bytes,
            dpi=min(240, max(120, int(dpi or 220))),
            poppler_path=poppler_path,
            first_page=first_page,
            last_page=last_page,
            thread_count=1,
            timeout=max(5, min(60, int(timeout or 45))),
        )
    except Exception as fallback_exc:
        if render_error is not None:
            raise RuntimeError(
                "Built-in PDF renderer failed ({}); "
                "Poppler fallback failed ({})".format(
                    str(render_error)[:180], str(fallback_exc)[:180]
                )
            )
        raise


def ocr_pdf_pagewise(
    file_bytes: bytes,
    pytesseract: Any,
    poppler_path: str | None = None,
    dpi: int = 220,
) -> str:
    """OCR a bounded PDF one page at a time under a total deadline."""
    count = pdf_page_count(file_bytes)
    if count > MAX_OCR_PAGES:
        raise ValueError(
            "Scanned PDF has {} pages; OCR safe limit is {}".format(
                count, MAX_OCR_PAGES
            )
        )
    if not OCR_SEMAPHORE.acquire(timeout=2):
        raise RuntimeError(
            "OCR is already processing another document. "
            "Wait for it to finish and try again."
        )
    started = time.monotonic()
    parts = []
    try:
        for page_number in range(1, count + 1):
            if time.monotonic() - started > OCR_TOTAL_DEADLINE_SECONDS:
                raise TimeoutError("OCR exceeded the safe processing time limit")
            images = render_pdf_page_images(
                file_bytes,
                dpi=min(240, max(120, int(dpi or 220))),
                poppler_path=poppler_path,
                first_page=page_number,
                last_page=page_number,
                timeout=45,
            )
            if not images:
                continue
            image = images[0]
            try:
                width, height = image.size
                if width * height > MAX_IMAGE_PIXELS:
                    raise ValueError(
                        "PDF page dimensions exceed the safe OCR limit"
                    )
                parts.append(
                    pytesseract.image_to_string(
                        image, lang="eng", timeout=35
                    )
                )
            finally:
                try:
                    image.close()
                except Exception:
                    pass
        return "\n".join(parts)
    finally:
        OCR_SEMAPHORE.release()
