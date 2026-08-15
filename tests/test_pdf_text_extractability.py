"""A non-empty PDF text layer is not automatically a usable one.

Some PDFs (LibreOffice -> Ghostscript exports are the classic case) embed subset
fonts with no ToUnicode map, so the text extracts to unmapped-glyph noise —
"(cid:N)" tokens from pdfminer/pdfplumber, or raw control-code glyph indices from
other extractors. That noise is non-empty, so a bare "did we get text?" check
passes and OCR is wrongly skipped, leaving the CV unreadable. These tests lock in
the detector that routes such layers to OCR, while never misrouting genuine text
(including non-Latin scripts) into it.
"""

import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from owner_build_tools import build_protected


_MODULE_TEMPORARY = None
if "app" not in sys.modules:
    _MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-pdf-extract-")
    _original_database_override = os.environ.get("CVSTUDIO_DB_PATH")
    _receipt_environment_key = "LOCALAPPDATA" if os.name == "nt" else "HOME"
    _original_receipt_environment = os.environ.get(_receipt_environment_key)
    os.environ["CVSTUDIO_DB_PATH"] = str(
        Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
    )
    os.environ[_receipt_environment_key] = str(
        Path(_MODULE_TEMPORARY.name) / "receipt-state"
    )
    try:
        build_protected.write_test_receipt(
            Path(__file__).resolve().parents[1], os.environ.copy()
        )
        import app
    finally:
        if _original_database_override is None:
            os.environ.pop("CVSTUDIO_DB_PATH", None)
        else:
            os.environ["CVSTUDIO_DB_PATH"] = _original_database_override
        if _original_receipt_environment is None:
            os.environ.pop(_receipt_environment_key, None)
        else:
            os.environ[_receipt_environment_key] = _original_receipt_environment
else:
    import app


class PdfTextExtractabilityTests(unittest.TestCase):
    def test_cid_token_layer_is_unextractable(self):
        # pdfplumber/pdfminer emit "(cid:N)" for every glyph without a ToUnicode map.
        text = "".join("(cid:%d)" % (i % 40 + 1) for i in range(400))
        self.assertTrue(app._pdf_text_looks_unextractable(text))

    def test_control_code_layer_is_unextractable(self):
        # Other extractors emit raw glyph-index control codes for the same PDFs.
        text = "".join(chr(i % 20 + 1) for i in range(2000))
        self.assertTrue(app._pdf_text_looks_unextractable(text))

    def test_replacement_char_layer_is_unextractable(self):
        text = "�" * 2000
        self.assertTrue(app._pdf_text_looks_unextractable(text))

    def test_plain_english_text_is_extractable(self):
        text = (
            "Mohd Fazli\nSoftware Engineer with eight years of experience in "
            "network support and Linux administration. Email fazli@example.com. "
            "Education: BSc Computer Science. Skills: Cisco, TCP/IP, Python."
        )
        self.assertFalse(app._pdf_text_looks_unextractable(text))

    def test_non_latin_text_is_not_misrouted_to_ocr(self):
        # Real CJK text carries none of the artifacts and must not be flagged
        # (flagging it would push a valid CV into English-only OCR and degrade it).
        text = (
            "张伟 软件工程师 八年工作经验 电子邮件 zhang@example.com "
            "教育 计算机科学学士 技能 网络管理 Linux 系统 项目管理"
        )
        self.assertFalse(app._pdf_text_looks_unextractable(text))

    def test_occasional_cid_token_in_real_text_is_still_extractable(self):
        text = (
            "John Smith Senior Engineer (cid:12) at Acme with ten years of "
            "experience in cloud and data platforms and regional team leadership."
        )
        self.assertFalse(app._pdf_text_looks_unextractable(text))

    def test_empty_and_short_text_is_not_flagged(self):
        self.assertFalse(app._pdf_text_looks_unextractable(""))
        self.assertFalse(app._pdf_text_looks_unextractable("   "))
        self.assertFalse(app._pdf_text_looks_unextractable("Mohd Fazli"))


class _FakePdfPage:
    width = 600
    height = 800

    def __init__(self, text="", *, images=None, curves=None, rects=None, chars=None):
        self._text = text
        self.images = list(images or [])
        self.curves = list(curves or [])
        self.rects = list(rects or [])
        self.chars = list(chars or [])

    def extract_text(self):
        return self._text


def _outlined_shapes(count=400, bands=6):
    shapes = []
    for index in range(count):
        band = index % bands
        top = 40 + band * 100
        shapes.append({"top": top, "bottom": top + 8, "x0": 40, "x1": 500})
    return shapes


class PdfPageRoutingTests(unittest.TestCase):
    """OCR decisions are page-aware and require visible-content evidence."""

    def test_short_exact_text_without_missing_content_is_preserved(self):
        page = _FakePdfPage(chars=[{"text": c} for c in "Jane Doe"])
        text = "Jane Doe | jane@example.com | +60 12-345 6789 | C++ | C#"
        self.assertEqual(app._pdf_page_ocr_reason(page, text), "")

    def test_large_scanned_image_with_no_text_routes_only_that_page_to_ocr(self):
        page = _FakePdfPage(
            images=[{"x0": 0, "x1": 600, "top": 0, "bottom": 800}]
        )
        self.assertEqual(app._pdf_page_ocr_reason(page, ""), "sparse-visual")

    def test_readable_header_over_scanned_body_still_routes_that_page(self):
        page = _FakePdfPage(
            images=[{"x0": 0, "x1": 600, "top": 160, "bottom": 800}]
        )
        header = "Candidate profile and contact information " * 4
        self.assertLess(sum(c.isalpha() for c in header), 400)
        self.assertEqual(app._pdf_page_ocr_reason(page, header), "sparse-visual")

    def test_outlined_vector_page_routes_to_ocr(self):
        page = _FakePdfPage(
            curves=_outlined_shapes(),
            chars=[{"text": ""}] * 40,
        )
        text = "LOKMAN HAKIM BIN SUHAIMI\n" + ("\n" * 40)
        self.assertEqual(app._pdf_page_ocr_reason(page, text), "sparse-visual")

    def test_blank_page_does_not_trigger_ocr(self):
        self.assertEqual(app._pdf_page_ocr_reason(_FakePdfPage(), ""), "")

    def test_cid_page_routes_to_ocr_but_valid_non_latin_page_does_not(self):
        cid = "".join("(cid:%d)" % (i % 30 + 1) for i in range(300))
        cjk = "资深系统工程师负责企业基础设施运维管理项目交付团队管理" * 10
        self.assertEqual(
            app._pdf_page_ocr_reason(_FakePdfPage(), cid), "unextractable"
        )
        self.assertEqual(app._pdf_page_ocr_reason(_FakePdfPage(), cjk), "")

    def test_mixed_pages_preserve_good_text_and_original_order(self):
        pages = [
            {"text": "Readable English first page", "ocr_reason": ""},
            {"text": "(cid:1)(cid:2)" * 50, "ocr_reason": "unextractable"},
            {"text": "可读取的中文页面", "ocr_reason": ""},
            {"text": "Candidate Name", "ocr_reason": "sparse-visual"},
        ]
        merged = app._merge_pdf_page_texts(
            pages,
            {2: "Recovered second page", 4: "Candidate Name\nRecovered history"},
        )
        self.assertEqual(
            merged.split("\n\n"),
            [
                "Readable English first page",
                "Recovered second page",
                "可读取的中文页面",
                "Candidate Name\nRecovered history",
            ],
        )

    def test_sparse_visual_ocr_must_add_content_before_replacing_exact_text(self):
        pages = [{"text": "Jane Doe jane@example.com C++ C#", "ocr_reason": "sparse-visual"}]
        self.assertEqual(
            app._merge_pdf_page_texts(pages, {1: "Jane Doe jane@example.com C+ C"}),
            pages[0]["text"],
        )

    def test_extract_route_ocrs_only_broken_pages_and_preserves_order(self):
        cid = "".join("(cid:%d)" % (i % 30 + 1) for i in range(300))
        pages = [
            _FakePdfPage("Readable English first page with exact jane@example.com C++"),
            _FakePdfPage(cid),
            _FakePdfPage("可读取的中文页面保持原样" * 10),
            _FakePdfPage(
                "Candidate Name",
                curves=_outlined_shapes(),
                chars=[{"text": ""}] * 40,
            ),
        ]
        opened = mock.MagicMock()
        opened.__enter__.return_value.pages = pages
        ocr_pages = {
            2: "Recovered second page",
            4: "Candidate Name\nRecovered history and certifications",
        }
        headers = {"X-CV-Studio-Request": "1", "Host": "localhost:5000"}

        with (
            mock.patch("pdfplumber.open", return_value=opened),
            # pytesseract is an optional runtime import inside the route. Stub the
            # module so this test exercises the routing/merge logic itself instead
            # of silently depending on whether OCR happens to be installed here.
            mock.patch.dict(sys.modules, {"pytesseract": mock.MagicMock()}),
            mock.patch.object(app, "_pdf_page_count", return_value=4),
            mock.patch.object(app, "_find_mandatory_tesseract", return_value="tesseract"),
            mock.patch.object(
                app, "_ocr_pdf_pages_pagewise", return_value=ocr_pages
            ) as ocr,
            mock.patch.object(app, "_extract_pdf_bullet_levels", return_value=[]),
        ):
            response = app.app.test_client().post(
                "/extract-text",
                data={"file": (io.BytesIO(b"%PDF-1.4\nfixture"), "mixed.pdf")},
                headers=headers,
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        text = response.get_json()["text"]
        expected = [
            "Readable English first page with exact jane@example.com C++",
            "Recovered second page",
            "可读取的中文页面保持原样" * 10,
            "Candidate Name\nRecovered history and certifications",
        ]
        positions = [text.index(value) for value in expected]
        self.assertEqual(positions, sorted(positions))
        ocr.assert_called_once()
        self.assertEqual(ocr.call_args.args[2], [2, 4])

    def test_extract_route_does_not_ocr_valid_short_exact_text(self):
        exact = "Jane Doe | jane@example.com | +60 12-345 6789 | C++ | C#"
        opened = mock.MagicMock()
        opened.__enter__.return_value.pages = [_FakePdfPage(exact)]
        headers = {"X-CV-Studio-Request": "1", "Host": "localhost:5000"}

        with (
            mock.patch("pdfplumber.open", return_value=opened),
            mock.patch.object(app, "_pdf_page_count", return_value=1),
            mock.patch.object(app, "_ocr_pdf_pages_pagewise") as ocr,
            mock.patch.object(app, "_extract_pdf_bullet_levels", return_value=[]),
        ):
            response = app.app.test_client().post(
                "/extract-text",
                data={"file": (io.BytesIO(b"%PDF-1.4\nfixture"), "short.pdf")},
                headers=headers,
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertIn("jane@example.com", response.get_json()["text"])
        self.assertIn("C++", response.get_json()["text"])
        ocr.assert_not_called()


class PdfOcrOutageFallbackTests(unittest.TestCase):
    """An OCR outage must not discard pages that extracted perfectly.

    Page-aware routing sends a document to OCR when ANY single page looks
    scanned or outlined — a CV whose first page carries a banner/photo above a
    short contact block qualifies. Before page-aware routing such a document
    never reached OCR at all, so failing the whole request when OCR is
    unavailable would lose text the extractor already had.
    """

    _HEADERS = {"X-CV-Studio-Request": "1", "Host": "localhost:5000"}

    def _post(self, pages, filename):
        opened = mock.MagicMock()
        opened.__enter__.return_value.pages = pages
        with (
            mock.patch("pdfplumber.open", return_value=opened),
            mock.patch.object(app, "_pdf_page_count", return_value=len(pages)),
            mock.patch.object(
                app,
                "_ocr_pdf_pages_pagewise",
                side_effect=RuntimeError("Tesseract is not installed."),
            ),
            mock.patch.object(app, "_find_mandatory_tesseract", return_value="tesseract"),
            mock.patch.dict(sys.modules, {"pytesseract": mock.MagicMock()}),
            mock.patch.object(app, "_extract_pdf_bullet_levels", return_value=[]),
        ):
            return app.app.test_client().post(
                "/extract-text",
                data={"file": (io.BytesIO(b"%PDF-1.4\nfixture"), filename)},
                headers=self._HEADERS,
                content_type="multipart/form-data",
            )

    def test_ocr_outage_still_returns_the_pages_that_extracted(self):
        body = "Senior Engineer at Acme delivering cloud infrastructure. " * 12
        pages = [
            # Banner/photo header above a short contact block -> routed to OCR.
            _FakePdfPage(
                "Jane Doe\njane@example.com\n+60 12-345 6789",
                images=[{"x0": 0, "x1": 600, "top": 0, "bottom": 300}],
            ),
            _FakePdfPage(body),
            _FakePdfPage(body),
        ]
        response = self._post(pages, "mixed.pdf")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        text = payload["text"]
        # The good pages survive, and the OCR-routed page keeps its exact text
        # rather than being replaced by nothing.
        self.assertIn("Senior Engineer at Acme", text)
        self.assertIn("jane@example.com", text)
        self.assertTrue(payload["partial_extraction"])
        self.assertEqual(payload["ocr_unavailable_pages"], [1])
        self.assertIn("may be incomplete", payload["warning"])

    def test_name_fragment_cannot_make_a_scanned_cv_look_complete(self):
        pages = [
            _FakePdfPage(
                "Jane Doe",
                images=[{"x0": 0, "x1": 600, "top": 0, "bottom": 300}],
            ),
            _FakePdfPage(
                "", images=[{"x0": 0, "x1": 600, "top": 0, "bottom": 800}]
            ),
            _FakePdfPage(
                "", images=[{"x0": 0, "x1": 600, "top": 0, "bottom": 800}]
            ),
        ]
        response = self._post(pages, "mostly-scanned.pdf")

        self.assertEqual(response.status_code, 400)
        self.assertIn("OCR failed", response.get_json()["error"])

    def test_ocr_outage_on_a_fully_unusable_document_still_reports_failure(self):
        # Nothing was recoverable, so the actionable OCR error must still surface.
        pages = [
            _FakePdfPage("", images=[{"x0": 0, "x1": 600, "top": 0, "bottom": 800}])
        ]
        response = self._post(pages, "scan.pdf")

        self.assertEqual(response.status_code, 400)
        self.assertIn("OCR failed", response.get_json()["error"])


def tearDownModule():
    if _MODULE_TEMPORARY is not None:
        _MODULE_TEMPORARY.cleanup()


if __name__ == "__main__":
    unittest.main()
