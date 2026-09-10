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
        for start_index, start in enumerate(months):
            for end_index, end in enumerate(months):
                start_date = start + " 2026" if start_index <= end_index else start
                expected = f"{start_date} to {end} 2026"
                cases.extend([
                    [f"1 {start} - 28 {end} 2026", expected],
                    [f"{start} 1 - {end} 28, 2026", expected],
                    [f"{start} - {end} 2026", expected],
                ])
        for space in ("\u00a0", "\u1680", "\u2000", "\u2007", "\u2009", "\u202f", "\u205f", "\u3000"):
            for month in months:
                cases.extend([
                    [f"1{space}{month}{space}2021 - Present", f"{month} 2021 to Present"],
                    [f"{month}{space}1,{space}2021 - Present", f"{month} 2021 to Present"],
                ])
            self.assertEqual(
                cn._cv_pretranslate_iso_dates(f"Apr 2022-11{space}Jul 2026"),
                f"Apr 2022-11{space}Jul 2026",
            )
        for newline in ("\n", "\r\n", "\u2028", "\u2029"):
            cases.append([f"2020-06{newline}Jun 2021", "Jun 2020 Jun 2021"])
            self.assertEqual(
                cn._cv_pretranslate_iso_dates(f"2020-06{newline}Jun 2021"),
                f"Jun 2020{newline}Jun 2021",
            )
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
                    [f"{day} {month}, 2020 - Present", f"{month} 2020 to Present"],
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
