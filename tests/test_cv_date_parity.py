"""One shared contract for Python, browser preview and direct Word generation."""
import json
from pathlib import Path
import subprocess
import unittest

import cvstudio_cv_normalize as cn

ROOT = Path(__file__).resolve().parents[1]


class CvDateParityTests(unittest.TestCase):
    def test_all_three_normalizers_preserve_dates_and_are_idempotent(self):
        cases = json.loads((ROOT / "tests/fixtures/cv_date_cases.json").read_text(encoding="utf-8"))
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for month in months:
            # Every potentially day-like short year, including mixed precision.
            for year in range(32):
                short = f"{year:02}"
                cases.extend([
                    [f"{month} {short} - Dec 99", f"{month} {short} to Dec 99"],
                    [f"{month} {short} - Dec 2026", f"{month} {short} to Dec 2026"],
                ])
            for day in ("1", "11", "21st"):
                cases.extend([
                    [f"{day} {month} 2020 - Present", f"{month} 2020 to Present"],
                    [f"{month} {day}, 2020 - Present", f"{month} 2020 to Present"],
                ])
        inputs = [case[0] for case in cases] + [case[1] for case in cases]
        result = subprocess.run(
            ["node", str(ROOT / "tests/test_cv_date_parity.js"), "--probe"],
            input=json.dumps(inputs), text=True, encoding="utf-8", capture_output=True,
            check=True, timeout=30, cwd=ROOT,
        )
        actual_js = json.loads(result.stdout)
        for index, (value, expected) in enumerate(cases):
            with self.subTest(value=value):
                self.assertEqual(cn._normalize_cv_date_range(value), expected)
                self.assertEqual(cn._normalize_cv_date_range(expected), expected)
                self.assertEqual(actual_js[index], {"generator": expected, "browser": expected})
                self.assertEqual(actual_js[index + len(cases)], actual_js[index])
