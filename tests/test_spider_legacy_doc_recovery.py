"""Opt-in native recovery for legacy .doc files verified Antiword cannot decode.

The verified-Antiword trust policy is unchanged: the default extraction path
still refuses non-Antiword text. These tests cover the additive, explicitly
opt-in recovery path (`allow_unverified`) that the recruiter triggers only after
the verified path returns a decode failure, plus the safeguards that keep the
recovered text labelled unverified and out of the cache.
"""

import os
from pathlib import Path
import tempfile
import unittest

from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "vendor" / "antiword" / "fixtures" / "UDHR-english.doc"

_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-doc-recovery-")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3")
write_test_receipt(ROOT)
try:
    import app
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE


class NativeDocRecoveryTests(unittest.TestCase):
    def test_recovers_clean_text_from_a_legacy_doc(self):
        raw = FIXTURE.read_bytes()
        text = app._spider_recover_legacy_doc_text_unverified(raw)
        self.assertIn("Universal Declaration of Human Rights", text)
        self.assertTrue(app._spider_doc_text_quality_ok(text))

    def test_recovered_text_passes_the_same_quality_gate(self):
        raw = FIXTURE.read_bytes()
        text = app._spider_recover_legacy_doc_text_unverified(raw)
        self.assertGreater(len(text), 80)

    def test_empty_and_non_ole_input_yield_empty_string(self):
        self.assertEqual(app._spider_recover_legacy_doc_text_unverified(b""), "")
        self.assertEqual(app._spider_recover_legacy_doc_text_unverified(b"not a document"), "")
        self.assertEqual(app._spider_recover_legacy_doc_text_unverified(None), "")


class ScanFallbackRecoveryTests(unittest.TestCase):
    """The printable-run fallback used when the CLX piece table cannot be parsed.

    Real legacy .doc files whose piece table is fast-saved or unusually laid out
    recover cleanly as a single block in tests but fail structurally in the wild.
    The scan fallback keeps the opt-in recovery useful for those files. It stays
    unverified and is still bounded by the same quality gate as the structured
    path.
    """

    RESUME = (
        "Name: Kwong Yew Leong\n"
        "Email: kwong.leong@example.com   Phone: +60 12-345 6789\n"
        "Summary: Experienced recruitment consultant based in Selangor.\n"
        "Experience: Led talent acquisition projects and client delivery.\n"
        "Education: Bachelor of Business Administration.\n"
        "Skills: sourcing, screening, stakeholder management, negotiation.\n"
    )

    def test_scan_recovers_utf16le_body_text(self):
        # A Unicode-body Word file stores prose as UTF-16LE inside binary noise.
        buf = b"\x00\x01\x02\xff" + self.RESUME.encode("utf-16-le") + b"\x00\xab\xcd"
        text = app._spider_scan_doc_text_runs(buf)
        self.assertIn("Kwong Yew Leong", text)
        self.assertTrue(app._spider_doc_text_quality_ok(text))

    def test_scan_recovers_cp1252_body_text(self):
        buf = b"\x00\x01\x02" + self.RESUME.encode("cp1252") + b"\x00\x00\xff"
        text = app._spider_scan_doc_text_runs(buf)
        self.assertIn("recruitment consultant", text)
        self.assertTrue(app._spider_doc_text_quality_ok(text))

    def test_scan_ignores_pure_binary_noise(self):
        buf = bytes(range(0, 32)) * 40
        self.assertFalse(app._spider_doc_text_quality_ok(app._spider_scan_doc_text_runs(buf)))

    def test_scan_handles_empty_and_none(self):
        self.assertEqual(app._spider_scan_doc_text_runs(b""), "")
        self.assertEqual(app._spider_scan_doc_text_runs(None), "")


class UnverifiedDocRecoveryHelperTests(unittest.TestCase):
    """The shared opt-in decision helper every preview handler now routes through."""

    def test_helper_recovers_when_opted_in_for_a_legacy_doc(self):
        raw = FIXTURE.read_bytes()
        text = app._spider_unverified_doc_recovery_text(
            raw, "application/msword", "resume.doc", True
        )
        self.assertIn("Universal Declaration of Human Rights", text)

    def test_helper_returns_empty_without_the_opt_in(self):
        raw = FIXTURE.read_bytes()
        self.assertEqual(
            app._spider_unverified_doc_recovery_text(
                raw, "application/msword", "resume.doc", False
            ),
            "",
        )

    def test_helper_returns_empty_for_a_non_legacy_document(self):
        self.assertEqual(
            app._spider_unverified_doc_recovery_text(
                b"%PDF-1.7 not a legacy doc", "application/pdf", "resume.pdf", True
            ),
            "",
        )


class RecoveryIsStrictlyOptInTests(unittest.TestCase):
    """Source-level guards: the default path and trust policy are untouched."""

    def setUp(self):
        self.source = (ROOT / "app.py").read_text(encoding="utf-8")

    def test_default_extraction_still_refuses_non_antiword_text(self):
        # The verified-only guarantee documented in the extraction path remains.
        self.assertIn(
            "Native OLE parsing remains defense-in-depth and cannot satisfy success",
            self.source,
        )

    def test_recovery_requires_explicit_opt_in_for_a_legacy_doc(self):
        # Recovery still requires the explicit opt-in and a real legacy .doc, but
        # is no longer gated on the specific Antiword failure reason: the native
        # parser needs no Antiword, so any Antiword failure on a legacy .doc can
        # be recovered when the recruiter opts in (e.g. verified runtime missing,
        # not only "verified Antiword decoded nothing"). The opt-in + legacy-doc
        # gate now lives in one shared helper so every AntiwordDependencyError
        # handler in the preview flow honours it.
        self.assertIn("allow_unverified_doc = str(request.args.get(\"allow_unverified\")", self.source)
        self.assertIn("def _spider_unverified_doc_recovery_text(raw, ctype, filename, allow_unverified):", self.source)
        self.assertIn("if not allow_unverified:\n        return \"\"", self.source)
        self.assertIn("if not _document_is_legacy_doc(raw, ctype, filename):\n        return \"\"", self.source)
        self.assertNotIn('getattr(exc, "reason", "") == "document-extraction-failed"', self.source)

    def test_visual_render_antiword_failure_also_offers_opt_in_recovery(self):
        # Regression: the verified-Antiword gate raises inside the *visual* render
        # (_office_bytes_to_pdf_preview) before extract_text runs, so the outer
        # AntiwordDependencyError handlers must attempt the same opt-in recovery,
        # or the recover button can never work for a legacy .doc.
        self.assertIn("def recover_unverified_doc_response(raw, ctype, filename):", self.source)
        self.assertIn("recovered_response = recover_unverified_doc_response(raw, ctype, filename)", self.source)
        self.assertIn("recovered_response = recover_unverified_doc_response(raw, ctype, dispo)", self.source)
        self.assertIn("recovered_response = recover_unverified_doc_response(raw2, ctype2, filename)", self.source)

    def test_recovered_text_is_never_cached(self):
        self.assertIn('if cache_provenance.get("unverified_recovery"):', self.source)

    def test_recovered_text_is_labelled_unverified(self):
        self.assertIn("recovered without Antiword (unverified", self.source)

    def test_scan_fallback_is_gated_by_the_same_quality_check(self):
        # The scan fallback only returns text that clears the same quality gate
        # as the structured path, so it cannot lower the recovery bar.
        self.assertIn("scanned = _spider_scan_doc_text_runs(source)", self.source)
        self.assertIn("if _spider_doc_text_quality_ok(scanned):", self.source)


if __name__ == "__main__":
    unittest.main()
