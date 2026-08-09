"""Spider (AI Crawler) document byte-signature classification and preview shaping.

Behaviour-preserving extraction of the pure, stateless document helpers from the
legacy web shell: magic-byte content-kind classification (legacy .doc / PDF /
zip / image), legacy-.doc identification with a metadata fallback, image-format
extension detection, the recovered-text quality gate, and the visual-preview
search-text/state shaping used by the AI Crawler side panel.

These are classification and shaping helpers only — none of the actual
document *decode* logic (Antiword, native OLE piece-table recovery, OCR, PDFium
rendering) lives here; that stays in the shell where it needs subprocess and
native-runtime dependencies.

Pure functions of their inputs - no Flask, no globals, no network, no JobAdder
or provider access. Depends only on the stateless helpers already extracted into
``cvstudio_spider_boolean`` and ``cvstudio_spider_summary``. This module never
imports ``app``.
"""

import io
import re

from cvstudio_spider_boolean import _spider_clean_doc_text_for_preview
from cvstudio_spider_summary import _spider_filename_from_disposition


# ---------------------------------------------------------------------------
# Byte-signature classification
# ---------------------------------------------------------------------------

def _spider_is_legacy_word_doc_bytes(raw):
    """Detect legacy binary Word .doc downloads even when JobAdder labels them octet-stream.

    Browser preview cannot embed .doc directly, so Spider must first recognise old
    OLE Word files, then convert or fall back to extracted text.
    """
    raw = raw or b""
    if not raw.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return False
    try:
        import olefile as _olefile
        ole = _olefile.OleFileIO(io.BytesIO(raw))
        try:
            return ole.exists('WordDocument')
        finally:
            ole.close()
    except Exception:
        # Still let the verified Antiword path inspect it; JobAdder often serves
        # legacy .doc as generic application/octet-stream without a usable name.
        return True


def _document_content_kind(raw):
    """Return a strong byte-signature classification before metadata fallback."""
    raw = raw or b""
    if _spider_is_legacy_word_doc_bytes(raw):
        return "legacy_doc"
    if raw.startswith(b"%PDF"):
        return "pdf"
    if raw[:2] == b"PK":
        return "zip"
    if (
        raw.startswith(b"\x89PNG\r\n\x1a\n")
        or raw.startswith(b"\xff\xd8\xff")
        or raw.startswith((b"II*\x00", b"MM\x00*", b"BM", b"RIFF"))
    ):
        return "image"
    return ""


def _document_is_legacy_doc(raw, content_type="", filename=""):
    """Apply strong byte identity before legacy-DOC metadata fallback."""

    content_kind = _document_content_kind(raw)
    if content_kind:
        return content_kind == "legacy_doc"
    ctype = str(content_type or "").lower()
    name = _spider_filename_from_disposition(
        filename,
        filename,
    ).lower()
    return "msword" in ctype or name.endswith(".doc")


def _document_image_extension(raw):
    raw = raw or b""
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if raw.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if raw.startswith((b"II*\x00", b"MM\x00*")):
        return ".tif"
    if raw.startswith(b"BM"):
        return ".bmp"
    if raw.startswith(b"RIFF"):
        return ".webp"
    return ".img"


# ---------------------------------------------------------------------------
# Recovered-text quality gate
# ---------------------------------------------------------------------------

def _spider_doc_text_quality_ok(text):
    text = _spider_clean_doc_text_for_preview(text)
    if len(text) < 80:
        return False
    sample = text[:6000]
    visible = sum(1 for c in sample if not c.isspace()) or 1
    bad = sum(1 for c in sample if (ord(c) > 0xFFFF) or (ord(c) >= 0x3000 and not ('\u4e00' <= c <= '\u9fff')))
    signals = len(re.findall(r'(?i)\b(name|email|e-mail|phone|mobile|experience|education|skills|work|project|position|summary|profile)\b|@', sample))
    return (bad / visible) < 0.25 and signals >= 1


# ---------------------------------------------------------------------------
# Visual-preview search-text and state shaping
# ---------------------------------------------------------------------------

def _spider_search_text_from_visual_payload(visual):
    """Reuse PDFium text and avoid a second PDF parser pass."""
    if isinstance(visual, dict):
        full_text = _spider_clean_doc_text_for_preview(str(visual.get("visual_search_text") or ""))[:30000]
        if full_text:
            return full_text, "PDFium visual/search text layer"
    layers = (visual or {}).get("visual_text_layers") if isinstance(visual, dict) else None
    if not isinstance(layers, list):
        return "", ""
    parts = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        text = str(layer.get("text") or "").strip()
        if text:
            parts.append(text)
        if sum(len(part) for part in parts) >= 30000:
            break
    text = _spider_clean_doc_text_for_preview("\n".join(parts))[:30000]
    if text:
        return text, "PDFium visual text layer"
    return "", ""


def _spider_prefetch_should_defer_ocr(raw, content_type="", filename=""):
    """Defer only strongly identified PDF/image bytes or metadata fallbacks."""
    content_kind = _document_content_kind(raw)
    if content_kind:
        return content_kind in {"pdf", "image"}
    ctype = str(content_type or "").lower()
    name = str(filename or "").lower()
    return bool(
        "pdf" in ctype
        or "image/" in ctype
        or name.endswith((".pdf", ".png", ".jpg", ".jpeg"))
    )


def _spider_apply_visual_search_state(visual, search_text, search_source):
    payload = dict(visual or {})
    payload.pop("visual_search_text", None)
    payload["search_text"] = str(search_text or "")[:30000]
    if not payload["search_text"]:
        payload["search_note"] = str(search_source or "Visual CV loaded, but no searchable text could be extracted.")[:200]
    return payload
