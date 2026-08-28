import inspect
import os
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from frontend_sources import frontend_source
import tempfile
import threading
import unittest
from unittest import mock


_MODULE_TEMPORARY = tempfile.TemporaryDirectory(
    prefix="cvstudio-phase5a-characterization-"
)
_ORIGINAL_DATABASE_OVERRIDE = os.environ.get("CVSTUDIO_DB_PATH")
os.environ["CVSTUDIO_DB_PATH"] = str(
    Path(_MODULE_TEMPORARY.name) / "state" / "cv_studio.sqlite3"
)
from owner_build_tools.build_protected import write_test_receipt

write_test_receipt(Path(__file__).resolve().parents[1])
try:
    import app
finally:
    if _ORIGINAL_DATABASE_OVERRIDE is None:
        os.environ.pop("CVSTUDIO_DB_PATH", None)
    else:
        os.environ["CVSTUDIO_DB_PATH"] = _ORIGINAL_DATABASE_OVERRIDE

from cvstudio_storage import SCHEMA_VERSION


_LONG_RUNNING_ROUTE_CONTRACTS = {
    "/jobadder/poll_token": ({"POST"}, "jobadder_poll_token"),
    "/ppc/outlook/device_poll": ({"POST"}, "ppc_outlook_device_poll"),
    "/ppc/outlook/create_draft": ({"POST"}, "ppc_outlook_create_draft"),
    "/ppc/outlook/create_test_draft": (
        {"POST"},
        "ppc_outlook_create_test_draft",
    ),
    "/onenote/device_poll": ({"POST"}, "onenote_device_poll"),
    "/onenote/desktop_sections": (
        {"GET"},
        "onenote_desktop_sections_route",
    ),
    "/onenote/desktop_pages": ({"GET"}, "onenote_desktop_pages_route"),
    "/onenote/manual_pages": ({"GET"}, "onenote_manual_pages"),
    "/onenote/import_selected": ({"POST"}, "onenote_import_selected"),
    "/onenote/import_recent": ({"POST"}, "onenote_import_recent"),
    "/jobadder/onenote_log_screening": (
        {"POST"},
        "jobadder_onenote_log_screening",
    ),
    "/jobadder/onenote_activity_create_diagnostic": (
        {"POST"},
        "jobadder_onenote_activity_create_diagnostic",
    ),
    "/owner/integration/run": ({"POST"}, "owner_integration_run"),
    "/jobadder/spider_preview_cancel_prefetch": (
        {"POST"},
        "jobadder_spider_preview_cancel_prefetch",
    ),
    "/jobadder/spider_candidate_preview": (
        {"GET"},
        "jobadder_spider_candidate_preview",
    ),
    "/jobadder/spider_search": ({"POST"}, "jobadder_spider_search"),
    "/jobadder/create_candidate": ({"POST"}, "jobadder_create_candidate"),
    "/jobadder/update_candidate": ({"POST"}, "jobadder_update_candidate"),
    "/jobadder/upload_original_cv": (
        {"POST"},
        "jobadder_upload_original_cv",
    ),
    "/jobadder/upload_cv": ({"POST"}, "jobadder_upload_cv"),
    "/restart": ({"POST"}, "restart"),
    "/ocr": ({"POST"}, "ocr_endpoint"),
    "/parse": ({"POST"}, "parse_cv"),
    "/generate-ai": ({"POST"}, "generate_ai"),
    "/lead-finder/test-search-provider": (
        {"POST"},
        "lead_finder_test_search_provider",
    ),
    "/lead-finder/search": ({"POST"}, "lead_finder_search"),
    "/lead-finder/find-people": ({"POST"}, "lead_finder_find_people"),
    "/lead-finder/find-emails": ({"POST"}, "lead_finder_find_emails"),
    "/generate-docx": ({"POST"}, "generate_docx"),
    "/preview-file": ({"POST"}, "preview_file"),
    "/extract-text": ({"POST"}, "extract_text"),
    "/blind": ({"POST"}, "blind_cv"),
    "/jobadder/ppc/placements": ({"POST"}, "jobadder_ppc_placements"),
}


_COMPATIBILITY_SIGNATURES = {
    "_document_validation_status": "(exc)",
    "_validate_zip_payload": "(file_bytes, label='document')",
    "_safe_image_open": "(file_bytes)",
    "_pdf_page_count": "(file_bytes)",
    "_ocr_image_text": "(pytesseract, image, lang='eng', timeout=35)",
    "_render_pdf_page_images": (
        "(file_bytes, first_page=1, last_page=None, dpi=220, "
        "poppler_path=None, timeout=45)"
    ),
    "_ocr_pdf_pagewise": (
        "(file_bytes, pytesseract, poppler_path=None, dpi=220)"
    ),
    "_cvstudio_system_memory_status": "()",
    "_cvstudio_dependency_status": "()",
    "_cvstudio_redact_support_text": "(text)",
    "_cvstudio_sanitize_browser_diagnostics": "(payload)",
    "_phase2a_usage_secret_field": "(key)",
    "_phase2a_usage_safe_value": "(value, depth=0)",
    "_phase2a_usage_records": "(payload)",
    "_phase2a_ppc_metadata": "(payload)",
    "_phase2b_record_array": "(payload, maximum, normalizer)",
    "_phase2b_browser_settings": "(payload)",
    "_phase2b_browser_setting_keys": "(payload)",
}


class Phase5APersistentJobsCharacterizationTests(unittest.TestCase):
    @staticmethod
    def _headers(request_id):
        return {
            "X-AI-Crawler-Code": "fixture-unlocked",
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": request_id,
        }

    def test_long_running_route_inventory_and_global_contracts_are_exact(self):
        rules = {rule.rule: rule for rule in app.app.url_map.iter_rules()}
        self.assertEqual(len(rules), 118)
        for path, (methods, endpoint) in _LONG_RUNNING_ROUTE_CONTRACTS.items():
            self.assertIn(path, rules)
            self.assertEqual(rules[path].methods & {"GET", "POST"}, methods)
            self.assertEqual(rules[path].endpoint, endpoint)
        self.assertFalse(any(path.startswith("/jobs") for path in rules))
        self.assertEqual(
            [item.__name__ for item in app.app.before_request_funcs.get(None, [])],
            [
                "_assign_cvstudio_request_id",
                "_reject_declared_oversize_request",
                "_reject_non_local_host_header",
                "_require_ai_spend_browser_session",
                "_reject_cross_site_unsafe_request",
            ],
        )
        self.assertEqual(app.app.config["MAX_CONTENT_LENGTH"], 80 * 1024 * 1024)
        self.assertEqual(SCHEMA_VERSION, 10)

    def test_compatibility_signatures_and_initialization_order_are_exact(self):
        self.assertEqual(
            {
                name: str(inspect.signature(getattr(app, name)))
                for name in _COMPATIBILITY_SIGNATURES
            },
            _COMPATIBILITY_SIGNATURES,
        )
        source = Path(app.__file__).read_text(encoding="utf-8-sig")
        ordered_markers = [
            "_CVSTUDIO_STORAGE = CVStudioStorage()",
            "_CVSTUDIO_STORAGE.initialize()",
            "_RUNTIME_STATE_DIR =",
            "_write_runtime_pid_file()",
            "threading.Thread(target=_watchdog, daemon=True).start()",
            "app = _create_modular_monolith_app(__name__, static_folder=None)",
            "_OCR_SEMAPHORE = threading.BoundedSemaphore(1)",
            "def _document_validation_status(exc):",
            "_OWNER_INTEGRATION_REPORT_LOCK = threading.RLock()",
            '@app.route("/owner/integration/run", methods=["POST"])',
            "_PHASE2A_USAGE_MAX_RECORDS = 250000",
            '@app.route("/storage/usage-history", methods=["GET"])',
            "def _phase2b_record_array(payload, maximum, normalizer):",
        ]
        positions = [source.index(marker) for marker in ordered_markers]
        self.assertEqual(positions, sorted(positions))

    def test_existing_preview_prefetch_success_and_cancellation_fields(self):
        client = app.app.test_client()

        with (
            mock.patch.object(app, "_ai_crawler_lock_allowed", return_value=True),
            mock.patch.object(
                app, "_ja_refresh_access_token", return_value="<fixture-token>"
            ),
            mock.patch.object(
                app, "_spider_candidate_attachment_records", return_value=[]
            ),
            mock.patch.object(
                app, "_spider_preview_payload_cache_get", return_value=None
            ),
            mock.patch.object(
                app,
                "_spider_fetch_candidate_detail",
                return_value={
                    "firstName": "Fixture",
                    "lastName": "Candidate",
                    "position": "Analyst",
                },
            ),
            mock.patch.object(
                app,
                "_spider_get_ja_raw",
                return_value=(b"", "application/octet-stream", ""),
            ),
            mock.patch.object(
                app, "_spider_visual_preview_payload", return_value=None
            ),
            mock.patch.object(
                app,
                "_spider_extract_text_from_download",
                return_value=("", "fixture empty payload"),
            ),
            mock.patch.object(app, "_spider_preview_payload_cache_put"),
        ):
            response = client.get(
                "/jobadder/spider_candidate_preview"
                "?candidate_id=fixture-candidate&prefetch=1",
                headers=self._headers("phase5a-preview-success"),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.get_json()),
            {
                "ok",
                "candidate_id",
                "name",
                "mode",
                "source",
                "note",
                "preview_text",
                "search_text",
                "tried",
                "attachment_fingerprint",
                "preview_cache_hit",
                "preview_partial",
                "preview_variant",
            },
        )

        with (
            mock.patch.object(app, "_ai_crawler_lock_allowed", return_value=True),
            mock.patch.object(
                app, "_ja_refresh_access_token", return_value="<fixture-token>"
            ),
            mock.patch.object(
                app,
                "_spider_candidate_attachment_records",
                side_effect=app._SpiderPreviewCancelled("fixture cancellation"),
            ),
        ):
            response = client.get(
                "/jobadder/spider_candidate_preview"
                "?candidate_id=fixture-candidate&prefetch=1",
                headers=self._headers("phase5a-preview-cancel"),
            )
        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertEqual(
            set(payload),
            {
                "ok",
                "error",
                "message",
                "code",
                "retryable",
                "request_id",
                "severity",
                "prefetch_cancelled",
            },
        )
        self.assertEqual(payload["code"], "PREVIEW_PREFETCH_SUPERSEDED")
        self.assertTrue(payload["prefetch_cancelled"])

    def test_preview_cancel_endpoint_and_generation_are_process_local(self):
        original_generation = app._spider_preview_background_generation()
        response = app.app.test_client().post(
            "/jobadder/spider_preview_cancel_prefetch",
            json={},
            headers=self._headers("phase5a-preview-cancel-endpoint"),
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.get_data(), b"")
        self.assertEqual(
            app._spider_preview_background_generation(),
            original_generation + 1,
        )

    def test_existing_in_memory_task_and_idempotency_state_is_ephemeral(self):
        self.assertIsInstance(app._ja_oauth_sessions, dict)
        self.assertIsInstance(app._ms_graph_device_store, dict)
        self.assertIsInstance(app._OUTLOOK_SERVICE._device_store, dict)
        self.assertIsInstance(app._OUTLOOK_SERVICE._draft_cache, dict)
        self.assertIsInstance(app._SPIDER_RESUME_TEXT_CACHE, dict)
        self.assertIsInstance(app._OWNER_INTEGRATION_LAST_REPORT, dict)
        self.assertIsInstance(app._ppc_detail_cache, dict)

        original = dict(app._OUTLOOK_SERVICE._draft_cache)
        event = threading.Event()
        try:
            app._OUTLOOK_SERVICE._draft_cache.clear()
            app._OUTLOOK_SERVICE._draft_cache["fixture-request"] = {
                "payload_hash": "fixture-hash",
                "in_progress": True,
                "started_at": 1,
                "cached_at": 1,
                "event": event,
            }
            app._OUTLOOK_SERVICE._draft_request_complete(
                "fixture-request",
                "fixture-hash",
                {"ok": True, "draft_id": "fixture-draft"},
            )
            completed = app._OUTLOOK_SERVICE._draft_cache["fixture-request"]
            self.assertEqual(
                set(completed),
                {"payload_hash", "result", "cached_at", "in_progress", "event"},
            )
            self.assertFalse(completed["in_progress"])
            self.assertEqual(completed["result"]["draft_id"], "fixture-draft")
            self.assertTrue(event.is_set())

            app._OUTLOOK_SERVICE._draft_request_fail("fixture-request")
            self.assertNotIn(
                "fixture-request", app._OUTLOOK_SERVICE._draft_cache
            )
        finally:
            app._OUTLOOK_SERVICE._draft_cache.clear()
            app._OUTLOOK_SERVICE._draft_cache.update(original)

    def test_frontend_background_orchestration_state_is_page_process_local(self):
        # Frontend JS now lives in vendor/cvstudio/*.js modules; search the
        # combined source (index.html + modules) so moved markers are found.
        source = frontend_source()
        markers = [
            "window._theSpiderPreviewPrefetchQueue = [];",
            "window._theSpiderPreviewPrefetchRunning = false;",
            "window._theSpiderPreviewPrefetchCurrentPromise = null;",
            "window._theSpiderPreviewPrefetchStopReason = '';",
            "var TAB_RUN_COUNTS = {};",
            "var TAB_RUN_SEQ = {};",
            "var _oneNoteRows = [];",
            "var _batchFiles = [];",
            "var _batchRunning = false;",
            "var _batchBlobs = [];",
        ]
        for marker in markers:
            self.assertIn(marker, source)
        self.assertNotIn("cvstudio_persistent_jobs", source)
        self.assertNotIn("fetch('/jobs", source)
        self.assertNotIn('fetch("/jobs', source)


def tearDownModule():
    _MODULE_TEMPORARY.cleanup()


if __name__ == "__main__":
    unittest.main()
