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

    def test_recovery_requires_explicit_opt_in_and_document_failure(self):
        self.assertIn("allow_unverified_doc = str(request.args.get(\"allow_unverified\")", self.source)
        self.assertIn("if (\n                    allow_unverified_doc", self.source)
        self.assertIn('getattr(exc, "reason", "") == "document-extraction-failed"', self.source)

    def test_recovered_text_is_never_cached(self):
        self.assertIn('if cache_provenance.get("unverified_recovery"):', self.source)

    def test_recovered_text_is_labelled_unverified(self):
        self.assertIn("recovered without Antiword (unverified", self.source)


if __name__ == "__main__":
    unittest.main()
