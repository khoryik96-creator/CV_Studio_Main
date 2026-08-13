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


class PdfTextSparsityTests(unittest.TestCase):
    """A near-empty text layer over image/outlined-vector pages (only a name and
    bullet glyphs extract) is non-empty but not formattable, and must route to
    OCR — while a genuine text CV, in any script, never trips the floor.
    """

    def test_name_and_bullets_only_over_several_pages_is_too_sparse(self):
        # Mirrors the reported "Microsoft Print to PDF" CV: a name plus a scatter
        # of private-use bullet glyphs across four pages, nothing else.
        text = "LOKMAN HAKIM BIN SUHAIMI\n" + (" \n" * 60)
        self.assertTrue(app._pdf_text_is_too_sparse(text, 4))

    def test_empty_layer_is_too_sparse(self):
        self.assertTrue(app._pdf_text_is_too_sparse("", 3))
        self.assertTrue(app._pdf_text_is_too_sparse(" \n \n", 2))

    def test_full_english_cv_is_not_sparse(self):
        page = (
            "Senior System Engineer at KPJ Healthcare Berhad, administered and "
            "supported enterprise infrastructure across on-premises and private "
            "cloud, covering virtualization, storage, backup, and operating "
            "systems, ensuring high availability and SLA compliance. "
        )
        self.assertFalse(app._pdf_text_is_too_sparse(page * 4, 4))

    def test_short_single_page_cv_is_not_sparse(self):
        text = (
            "John Smith. Software Engineer with ten years of experience in cloud "
            "infrastructure, networking, Linux administration, Python automation, "
            "and cross-functional team leadership. Email john@example.com. "
            "Education: BSc Computer Science, UTM. Skills: AWS, Cisco, Docker."
        )
        self.assertFalse(app._pdf_text_is_too_sparse(text, 1))

    def test_real_length_cjk_page_is_not_sparse(self):
        # A genuine one-page Chinese CV carries hundreds of hanzi (all counted as
        # letters), well above the per-page floor — never misrouted into OCR.
        text = (
            "资深系统工程师，负责企业基础设施的运维与管理，涵盖虚拟化、存储、"
            "备份和操作系统，确保高可用性和服务水平协议合规。管理多种虚拟化平台，"
            "包括威睿、纽塔尼克斯和微软超威平台，确保高可用性和性能。支持存储区域网络"
            "和网络附加存储解决方案，维护存储性能、容量和可靠性。负责备份平台的运维，"
            "确保数据保护、恢复就绪和策略合规。为视窗和林纳克斯系统提供管理和支持。"
            "教育背景：计算机科学学士。技能：网络管理、系统架构、项目交付、团队管理。"
        )
        self.assertFalse(app._pdf_text_is_too_sparse(text, 1))

    def test_sparsity_ignores_cid_tokens(self):
        # "(cid:N)" tokens are not real letters; a page full of them is still sparse.
        text = "".join("(cid:%d)" % (i % 30 + 1) for i in range(300))
        self.assertTrue(app._pdf_text_is_too_sparse(text, 1))

    def test_text_cv_padded_with_image_pages_is_not_sparse(self):
        # A usable text layer must never be sent to OCR just because the document
        # carries many image pages (a portfolio, a design deck, scanned
        # certificates). Scaling the floor with the total page count would judge
        # this 15-page file against 1500 letters and misroute it; the ceiling
        # keeps the bar at a page's worth of real text.
        one_page_cv = (
            "Regional Delivery Manager with twelve years leading infrastructure "
            "programmes across South East Asia, covering virtualization, storage "
            "and service management for enterprise clients. "
        ) * 4
        self.assertGreater(sum(c.isalpha() for c in one_page_cv), 400)
        self.assertFalse(app._pdf_text_is_too_sparse(one_page_cv, 15))
        self.assertFalse(app._pdf_text_is_too_sparse(one_page_cv, 40))

    def test_sparse_layer_still_routes_to_ocr_at_high_page_counts(self):
        # The ceiling must not let a genuinely unextractable layer through: a
        # name-only layer is sparse whatever the page count.
        self.assertTrue(app._pdf_text_is_too_sparse("Mohd Faizal Ab Aziz", 4))
        self.assertTrue(app._pdf_text_is_too_sparse("Mohd Faizal Ab Aziz", 40))

    def test_sparsity_floor_is_capped(self):
        # The floor rises with page count only up to the ceiling.
        self.assertEqual(app._PDF_SPARSE_LETTER_CEILING, 400)
        just_over = "a" * (app._PDF_SPARSE_LETTER_CEILING + 1)
        just_under = "a" * (app._PDF_SPARSE_LETTER_CEILING - 1)
        self.assertFalse(app._pdf_text_is_too_sparse(just_over, 99))
        self.assertTrue(app._pdf_text_is_too_sparse(just_under, 99))
        # A single page keeps the original, stricter per-page floor.
        self.assertTrue(app._pdf_text_is_too_sparse("a" * 99, 1))
        self.assertFalse(app._pdf_text_is_too_sparse("a" * 101, 1))


def tearDownModule():
    if _MODULE_TEMPORARY is not None:
        _MODULE_TEMPORARY.cleanup()


if __name__ == "__main__":
    unittest.main()
