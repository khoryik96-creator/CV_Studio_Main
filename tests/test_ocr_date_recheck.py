"""Local alternate scans may repair one digit, never replace other OCR content."""
import threading
import unittest
from unittest import mock

import cvstudio_document_safety as safety


BAD = "Technical Specialist\nContoso Systems | Aug 2017 - May 2015\nKept primary duty.\n"
GOOD = BAD.replace("2017", "2011")


class OcrDateRecheckTests(unittest.TestCase):
    class Image:
        size = (200, 200)
        def close(self):
            self.closed = True

    def run_ocr(self, texts, render=None, clock=lambda: 0, pages=(2,)):
        images = []
        def default_render(*args, **kwargs):
            image = self.Image()
            images.append(image)
            return [image]
        renderer = mock.Mock(side_effect=render or default_render)
        provider = mock.Mock()
        provider.image_to_string.side_effect = texts
        semaphore = threading.BoundedSemaphore(1)
        with mock.patch.object(safety, "rendered_pdf_page_is_visually_blank", return_value=False):
            result = safety.ocr_pdf_pages_pagewise(b"synthetic", provider, page_numbers=pages,
                pdf_page_count=lambda _: 3, render_pdf_page_images=renderer, ocr_semaphore=semaphore,
                max_ocr_pages=30, max_image_pixels=40000, deadline_seconds=180, monotonic=clock)
        self.assertTrue(semaphore.acquire(blocking=False))
        semaphore.release()
        self.assertTrue(all(getattr(image, "closed", False) for image in images))
        return result, renderer, provider

    def test_two_agreeing_alternate_scans_repair_only_the_erroneous_year(self):
        result, renderer, provider = self.run_ocr([BAD, GOOD.replace("Kept primary duty.", "Unreliable alternate wording."), GOOD])
        self.assertEqual(result, {2: GOOD})
        self.assertEqual([call.kwargs["dpi"] for call in renderer.call_args_list], [220, 150, 160])
        self.assertEqual(provider.image_to_string.call_count, 3)

    def test_valid_dates_need_no_extra_scan(self):
        result, renderer, _ = self.run_ocr([GOOD])
        self.assertEqual(result, {2: GOOD})
        self.assertEqual(renderer.call_count, 1)

    def test_disagreement_changed_employer_title_month_end_or_multiple_digits_keeps_original(self):
        for alternate in (BAD, GOOD.replace("2011", "2012"), GOOD.replace("Contoso", "Northwind"),
                          GOOD.replace("Technical", "Other"), GOOD.replace("Aug", "Sep"),
                          GOOD.replace("May 2015", "May 2016"), GOOD.replace("2011", "2001"), GOOD + GOOD):
            with self.subTest(alternate=alternate):
                self.assertEqual(self.run_ocr([BAD, GOOD, alternate])[0], {2: BAD})

    def test_optional_recheck_failure_keeps_successful_primary_ocr(self):
        result, _, _ = self.run_ocr([BAD, RuntimeError("alternate OCR failed")])
        self.assertEqual(result, {2: BAD})

    def test_primary_ocr_failure_remains_visible(self):
        with self.assertRaisesRegex(RuntimeError, "primary failure"):
            self.run_ocr([RuntimeError("primary failure")])

    def test_repeated_primary_headers_are_not_corrected(self):
        result, renderer, _ = self.run_ocr([BAD + BAD])
        self.assertEqual(result, {2: BAD + BAD})
        self.assertEqual(renderer.call_count, 1)
        self.assertEqual(safety._ocr_repair_header_dates(BAD + BAD, [GOOD, GOOD]), BAD + BAD)

    def test_even_agreeing_scans_cannot_replace_multiple_year_digits(self):
        changed = GOOD.replace("2011", "2001")
        self.assertEqual(safety._ocr_repair_header_dates(BAD, [changed, changed]), BAD)

    def test_extra_scans_stop_after_two_suspect_pages(self):
        result, renderer, provider = self.run_ocr([BAD, BAD, BAD, GOOD, GOOD, GOOD, GOOD], pages=(1, 2, 3))
        self.assertEqual(result, {1: GOOD, 2: GOOD, 3: BAD})
        self.assertEqual(provider.image_to_string.call_count, 7)
        self.assertEqual(renderer.call_count, 7)
        self.assertEqual([call.kwargs["dpi"] for call in renderer.call_args_list], [220, 220, 220, 150, 160, 150, 160])

    def test_primary_pages_finish_before_optional_rechecks_use_remaining_time(self):
        elapsed = [0]
        images = []
        def render(*args, **kwargs):
            image = self.Image()
            images.append(image)
            elapsed[0] += 40
            return [image]
        result, renderer, _ = self.run_ocr([BAD, BAD, BAD, GOOD, GOOD], render=render,
            clock=lambda: elapsed[0], pages=(1, 2, 3))
        self.assertEqual(result, {1: BAD, 2: BAD, 3: BAD})
        self.assertEqual([call.kwargs["dpi"] for call in renderer.call_args_list[:3]], [220, 220, 220])
        self.assertEqual([call.kwargs["first_page"] for call in renderer.call_args_list[:3]], [1, 2, 3])
        self.assertTrue(all(image.closed for image in images))

    def test_optional_failure_after_primary_pages_keeps_the_complete_document(self):
        result, renderer, _ = self.run_ocr([BAD, BAD, GOOD, TimeoutError("optional deadline")], pages=(1, 2, 3))
        self.assertEqual(result, {1: BAD, 2: BAD, 3: GOOD})
        self.assertEqual([call.kwargs["dpi"] for call in renderer.call_args_list[:3]], [220, 220, 220])

    def test_month_omissions_do_not_count_as_january_or_december_agreement(self):
        primary = BAD.replace("Aug", "Jan").replace("May", "Dec")
        corrected = primary.replace("2017", "2011")
        for alternate in (corrected.replace("Jan ", ""), corrected.replace("Dec ", ""),
                          corrected.replace("Jan ", "").replace("Dec ", "")):
            for alternatives in ([alternate, alternate], [corrected, alternate]):
                with self.subTest(alternatives=alternatives):
                    self.assertEqual(safety._ocr_repair_header_dates(primary, alternatives), primary)

    def test_explicit_months_cannot_be_added_to_year_only_primary_consensus(self):
        primary = "Analyst\nContoso Systems | 2017 - 2015\n"
        for alternate in ("Analyst\nContoso Systems | Jan 2011 - 2015\n",
                          "Analyst\nContoso Systems | 2011 - Dec 2015\n"):
            with self.subTest(alternate=alternate):
                self.assertEqual(safety._ocr_repair_header_dates(primary, [alternate, alternate]), primary)

    def test_equivalent_full_month_names_and_year_only_ranges_still_agree(self):
        primary = BAD.replace("Aug", "Jan").replace("May", "Dec")
        corrected = primary.replace("2017", "2011")
        self.assertEqual(safety._ocr_repair_header_dates(primary,
            [corrected.replace("Jan", "January").replace("Dec", "December"), corrected]), corrected)
        primary = "Analyst\nContoso Systems | 2017 - 2015\n"
        corrected = primary.replace("2017", "2011")
        self.assertEqual(safety._ocr_repair_header_dates(primary, [corrected, corrected]), corrected)

    def test_optional_scans_share_the_primary_deadline_and_have_short_timeouts(self):
        result, renderer, provider = self.run_ocr([BAD, GOOD, GOOD], clock=lambda: 0)
        self.assertEqual(result, {2: GOOD})
        self.assertTrue(all(call.kwargs["timeout"] <= 10 for call in renderer.call_args_list[1:]))
        self.assertTrue(all(call.kwargs["timeout"] <= 10 for call in provider.image_to_string.call_args_list[1:]))

    def test_optional_scans_are_skipped_when_document_time_is_nearly_used_up(self):
        ticks = iter([0, 0, 0, 0, 170])
        result, renderer, _ = self.run_ocr([BAD], clock=lambda: next(ticks, 170))
        self.assertEqual(result, {2: BAD})
        self.assertEqual(renderer.call_count, 1)

    def test_oversized_alternate_images_are_closed_and_not_ocrd(self):
        images = []
        def render(*args, **kwargs):
            image = self.Image()
            if kwargs["dpi"] != 220:
                image.size = (10000, 10000)
            images.append(image)
            return [image]
        result, _, provider = self.run_ocr([BAD], render=render)
        self.assertEqual(result, {2: BAD})
        self.assertEqual(provider.image_to_string.call_count, 1)
        self.assertTrue(all(image.closed for image in images))
