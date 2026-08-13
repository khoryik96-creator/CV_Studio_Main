"""The browser's /extract-text budget must outlast the server's OCR ceiling.

Aborting a /extract-text request does not stop the work: Flask runs the OCR to
completion and holds the single OCR semaphore while doing so. So a client that
gives up early does not just lose its own extraction -- it leaves the semaphore
held, and the next upload fails fast with "OCR is already processing another
document". In a batch that turns one slow scanned CV into a run of failures.

These tests pin the contract across the two languages: every /extract-text call
site must use the shared client budget, and that budget must exceed the server's
total OCR deadline.
"""

import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_VENDOR = _ROOT / "vendor" / "cvstudio"


def _server_ocr_deadline_seconds():
    source = (_ROOT / "cvstudio_document_safety.py").read_text(encoding="utf-8")
    match = re.search(r"^OCR_TOTAL_DEADLINE_SECONDS\s*=\s*(\d+)", source, re.M)
    assert match, "OCR_TOTAL_DEADLINE_SECONDS not found in cvstudio_document_safety.py"
    return int(match.group(1))


def _client_extract_budget_ms():
    source = (_VENDOR / "runtime-core.js").read_text(encoding="utf-8")
    match = re.search(r"var CV_EXTRACT_TEXT_TIMEOUT_MS\s*=\s*(\d+)", source)
    assert match, "CV_EXTRACT_TEXT_TIMEOUT_MS not found in runtime-core.js"
    return int(match.group(1))


def _extract_text_call_lines():
    lines = []
    for path in sorted(_VENDOR.glob("*.js")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "'/extract-text'" in line:
                lines.append((path.name, number, line.strip()))
    return lines


class OcrBudgetAlignmentTests(unittest.TestCase):
    def test_client_budget_exceeds_server_ocr_deadline(self):
        client_ms = _client_extract_budget_ms()
        server_ms = _server_ocr_deadline_seconds() * 1000
        self.assertGreater(
            client_ms,
            server_ms,
            "The browser must wait longer than the server can spend on OCR, or an "
            "aborted upload strands the OCR semaphore and fails the next one.",
        )

    def test_every_timed_extract_text_call_uses_the_shared_budget(self):
        offenders = []
        for name, number, line in _extract_text_call_lines():
            if "fetchWithTimeout" not in line:
                continue  # untimed fetch() never aborts early, so it cannot strand OCR
            if "CV_EXTRACT_TEXT_TIMEOUT_MS" not in line:
                offenders.append("{}:{} {}".format(name, number, line))
        self.assertEqual(
            offenders,
            [],
            "These /extract-text calls use their own timeout instead of "
            "CV_EXTRACT_TEXT_TIMEOUT_MS, so they can drift back under the OCR "
            "deadline:\n" + "\n".join(offenders),
        )

    def test_extract_text_call_sites_are_still_present(self):
        # Guards the test itself: if the call sites move or are renamed, the
        # check above would silently pass over an empty set.
        self.assertGreaterEqual(len(_extract_text_call_lines()), 5)


if __name__ == "__main__":
    unittest.main()
