"""Characterization coverage for the pure CV text/date helpers before they move
from the legacy web shell into ``cvstudio_cv_normalize.py``.

Imports through ``app`` so it passes identically before the extraction
(functions in app.py) and after it (app.py re-exports them).
"""

import os
from pathlib import Path
import tempfile
import unittest

from owner_build_tools.build_protected import write_test_receipt


ROOT = Path(__file__).resolve().parents[1]

_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-cv-helpers-")
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
write_test_receipt(ROOT)
try:
    import app
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE


class CvHelpersCharacterizationTests(unittest.TestCase):
    def test_parse_backend_timeout_seconds(self):
        self.assertEqual(app._cv_parse_backend_timeout_seconds("short cv"), 180)
        self.assertEqual(app._cv_parse_backend_timeout_seconds("x" * 20000), 300)

    def test_match_key_and_token_set(self):
        self.assertEqual(app._cv_match_key("  SAP FICO Consultant!! "), "sapficoconsultant")
        self.assertEqual(app._cv_token_set("SAP FICO Consultant"), {"consultant", "fico", "sap"})

    def test_token_overlap_score(self):
        self.assertAlmostEqual(
            app._cv_token_overlap_score("sap fico consultant", "sap consultant"), 2 / 3
        )
        self.assertEqual(app._cv_token_overlap_score("abc", "xyz"), 0.0)

    def test_date_helpers(self):
        self.assertEqual(app._cv_date_parts("Jan 2019 - Mar 2021"), ("Jan 2019", "Mar 2021"))
        self.assertEqual(
            app._cv_combine_date_ranges(["Jan 2019 - Mar 2021", "Apr 2021 - Present"]),
            "Apr 2021 to Mar 2021",
        )
        self.assertEqual(app._cv_date_sort_point("Mar 2021"), (2021, 3))
        self.assertEqual(app._cv_date_sort_point("Mar 2021", True), (2021, 3))

    def test_plain_bullet_texts(self):
        self.assertEqual(
            app._cv_plain_bullet_texts(["- did x", "* did y", "  "]),
            ["- did x", "* did y", "  "],
        )

    def test_text_similarity(self):
        self.assertEqual(app._cv_text_similarity("the quick brown fox", "the quick red fox"), 0.75)
        self.assertEqual(app._cv_text_similarity("abc", "xyz"), 0.0)

    def test_project_group_sort_key(self):
        self.assertEqual(
            app._cv_project_group_sort_key({"date_range": "Jan 2019 - Mar 2021", "title": "X"}),
            (1, (9998, 12), 0),
        )

    def test_all_helpers_and_constants_reexported(self):
        for name in (
            "_cv_parse_backend_timeout_seconds", "_cv_match_key", "_cv_token_set",
            "_cv_token_overlap_score", "_cv_date_parts", "_cv_combine_date_ranges",
            "_cv_date_sort_point", "_cv_plain_bullet_texts", "_cv_text_similarity",
            "_cv_project_group_sort_key",
        ):
            self.assertTrue(callable(getattr(app, name)), name)
        self.assertIsInstance(app._CV_MONTH_NUMBER, dict)
        self.assertTrue(app._CV_MONTH_NUMBER)


if __name__ == "__main__":
    unittest.main()
