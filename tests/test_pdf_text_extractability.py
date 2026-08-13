"""A non-empty PDF text layer is not automatically a usable one.

Some PDFs (LibreOffice -> Ghostscript exports are the classic case) embed subset
fonts with no ToUnicode map, so the text extracts to unmapped-glyph noise —
"(cid:N)" tokens from pdfminer/pdfplumber, or raw control-code glyph indices from
other extractors. That noise is non-empty, so a bare "did we get text?" check
passes and OCR is wrongly skipped, leaving the CV unreadable. These tests lock in
the detector that routes such layers to OCR, while never misrouting genuine text
(including non-Latin scripts) into it.
"""

import os
from pathlib import Path
import sys
import tempfile
import unittest

from owner_build_tools import build_protected


_MODULE_TEMPORARY = None
if "app" not in sys.modules:
    _MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-pdf-extract-")
    _original_database_override = os.environ.get("CVSTUDIO_DB_PATH")
    os.environ["CVSTUDIO_DB_PATH"] = str(
        Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
    )
    build_protected.write_test_receipt(Path(__file__).resolve().parents[1])
    try:
        import app
    finally:
        if _original_database_override is None:
            os.environ.pop("CVSTUDIO_DB_PATH", None)
        else:
            os.environ["CVSTUDIO_DB_PATH"] = _original_database_override
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


def tearDownModule():
    if _MODULE_TEMPORARY is not None:
        _MODULE_TEMPORARY.cleanup()


if __name__ == "__main__":
    unittest.main()
