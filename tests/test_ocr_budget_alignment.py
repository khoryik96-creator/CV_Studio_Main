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
import threading
import unittest
from pathlib import Path

import cvstudio_document_safety as document_safety

_ROOT = Path(__file__).resolve().parents[1]
_VENDOR = _ROOT / "vendor" / "cvstudio"


def _server_ocr_deadline_seconds():
    source = (_ROOT / "cvstudio_document_safety.py").read_text(encoding="utf-8")
    match = re.search(r"^OCR_TOTAL_DEADLINE_SECONDS\s*=\s*(\d+)", source, re.M)
    assert match, "OCR_TOTAL_DEADLINE_SECONDS not found in cvstudio_document_safety.py"
    return int(match.group(1))


def _server_max_in_flight_page_seconds():
    source = (_ROOT / "cvstudio_document_safety.py").read_text(encoding="utf-8")
    values = []
    for name in ("OCR_PAGE_RENDER_TIMEOUT_SECONDS", "OCR_PAGE_TEXT_TIMEOUT_SECONDS"):
        match = re.search(r"^{}\s*=\s*(\d+)".format(name), source, re.M)
        assert match, "{} not found in cvstudio_document_safety.py".format(name)
        values.append(int(match.group(1)))
    return sum(values)


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


def _extract_text_call_contexts():
    contexts = []
    for path in sorted(_VENDOR.glob("*.js")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if "'/extract-text'" not in line:
                continue
            contexts.append((path.name, index + 1, "\n".join(lines[index:index + 32])))
    return contexts


class OcrBudgetAlignmentTests(unittest.TestCase):
    def test_client_budget_exceeds_server_ocr_deadline(self):
        client_ms = _client_extract_budget_ms()
        # The total deadline is checked between page operations. The browser
        # must also cover the maximum render + Tesseract work already in flight
        # when that deadline is reached.
        server_ms = (
            _server_ocr_deadline_seconds()
            + _server_max_in_flight_page_seconds()
        ) * 1000
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

    def test_every_extract_text_consumer_handles_partial_ocr_success(self):
        offenders = []
        for name, number, context in _extract_text_call_contexts():
            if not re.search(
                r"cv(?:ShowExtractionWarning|RequireCompleteExtraction)\s*\(",
                context,
            ):
                offenders.append("{}:{}".format(name, number))
        self.assertEqual(
            offenders,
            [],
            "These /extract-text consumers can silently treat a partial OCR "
            "response as complete: {}".format(", ".join(offenders)),
        )

    def test_automated_mutating_workflows_reject_partial_extraction(self):
        contexts = {
            name: context for name, _number, context in _extract_text_call_contexts()
        }
        for name in ("batch-format.js", "create-profile.js"):
            self.assertIn(
                "cvRequireCompleteExtraction(",
                contexts[name],
                "{} must not generate/upload from an incomplete CV".format(name),
            )


class OcrDeadlineBehaviorTests(unittest.TestCase):
    class _Clock:
        def __init__(self):
            self.value = 0.0

        def monotonic(self):
            return self.value

        def advance(self, seconds):
            self.value += float(seconds)

    class _Image:
        size = (100, 100)

        def close(self):
            return None

    def test_late_page_cannot_add_a_full_ocr_call_after_rendering(self):
        clock = self._Clock()
        render_timeouts = []
        ocr_timeouts = []

        def render(*_args, **kwargs):
            render_timeouts.append(kwargs["timeout"])
            # Simulate the old worst case even when the caller gives the final
            # page a smaller remaining-time budget.
            clock.advance(45)
            return [self._Image()]

        class Tesseract:
            @staticmethod
            def image_to_string(_image, lang, timeout):
                self.assertEqual(lang, "eng")
                ocr_timeouts.append(timeout)
                clock.advance(35)
                return "page text"

        semaphore = threading.BoundedSemaphore(1)
        with self.assertRaises(TimeoutError):
            document_safety.ocr_pdf_pages_pagewise(
                b"pdf",
                Tesseract(),
                page_numbers=[1, 2, 3],
                pdf_page_count=lambda _raw: 3,
                render_pdf_page_images=render,
                ocr_semaphore=semaphore,
                max_ocr_pages=30,
                max_image_pixels=60_000_000,
                deadline_seconds=180,
                monotonic=clock.monotonic,
            )

        self.assertEqual(ocr_timeouts, [35, 35])
        self.assertEqual(render_timeouts[:2], [45, 45])
        self.assertLess(render_timeouts[2], 45)
        self.assertLessEqual(clock.value, 225)
        self.assertTrue(semaphore.acquire(timeout=0))
        semaphore.release()

    def test_selected_pages_are_returned_by_original_page_number(self):
        rendered = []

        def render(*_args, **kwargs):
            rendered.append(kwargs["first_page"])
            return [self._Image()]

        class Tesseract:
            @staticmethod
            def image_to_string(_image, lang, timeout):
                return "ocr page {}".format(rendered[-1])

        result = document_safety.ocr_pdf_pages_pagewise(
            b"pdf",
            Tesseract(),
            page_numbers=[3, 1, 3],
            pdf_page_count=lambda _raw: 4,
            render_pdf_page_images=render,
            ocr_semaphore=threading.BoundedSemaphore(1),
            max_ocr_pages=30,
            max_image_pixels=60_000_000,
            deadline_seconds=180,
        )

        self.assertEqual(rendered, [1, 3])
        self.assertEqual(result, {1: "ocr page 1", 3: "ocr page 3"})

    def test_selected_pages_use_the_ocr_limit_not_total_pdf_pages(self):
        result = document_safety.ocr_pdf_pages_pagewise(
            b"pdf",
            type(
                "Tesseract",
                (),
                {"image_to_string": staticmethod(lambda *_args, **_kwargs: "fixed")},
            )(),
            page_numbers=[40],
            pdf_page_count=lambda _raw: 40,
            render_pdf_page_images=lambda *_args, **_kwargs: [self._Image()],
            ocr_semaphore=threading.BoundedSemaphore(1),
            max_ocr_pages=30,
            max_image_pixels=60_000_000,
            deadline_seconds=180,
        )
        self.assertEqual(result, {40: "fixed"})


if __name__ == "__main__":
    unittest.main()
