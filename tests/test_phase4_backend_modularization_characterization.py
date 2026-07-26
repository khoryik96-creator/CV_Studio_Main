import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest import mock


_MODULE_TEMPORARY = tempfile.TemporaryDirectory(prefix="cvstudio-phase4-characterization-")
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

from cvstudio_storage import (
    BrowserSettingsRepository,
    CVStudioStorage,
    OneNoteSavedLinkRepository,
    OneNoteTransferRepository,
    PPCMetadataRepository,
    UsageHistoryRepository,
)


_SELECTED_ROUTES = {
    "/storage/usage-history": ({"GET"}, "phase2a_usage_history_read"),
    "/storage/usage-history/import": ({"POST"}, "phase2a_usage_history_import"),
    "/storage/usage-history/upsert": ({"POST"}, "phase2a_usage_history_upsert"),
    "/storage/usage-history/clear": ({"POST"}, "phase2a_usage_history_clear"),
    "/storage/ppc-metadata": ({"GET"}, "phase2a_ppc_metadata_read"),
    "/storage/ppc-metadata/import": ({"POST"}, "phase2a_ppc_metadata_import"),
    "/storage/ppc-metadata/upsert": ({"POST"}, "phase2a_ppc_metadata_upsert"),
    "/storage/ppc-metadata/clear": ({"POST"}, "phase2a_ppc_metadata_clear"),
    "/storage/onenote-transfer-records": ({"GET"}, "phase2b_onenote_transfer_read"),
    "/storage/onenote-transfer-records/import": ({"POST"}, "phase2b_onenote_transfer_import"),
    "/storage/onenote-transfer-records/replace": ({"POST"}, "phase2b_onenote_transfer_replace"),
    "/storage/onenote-transfer-records/clear": ({"POST"}, "phase2b_onenote_transfer_clear"),
    "/storage/onenote-saved-links": ({"GET"}, "phase2b_onenote_links_read"),
    "/storage/onenote-saved-links/import": ({"POST"}, "phase2b_onenote_links_import"),
    "/storage/onenote-saved-links/replace": ({"POST"}, "phase2b_onenote_links_replace"),
    "/storage/browser-settings": ({"GET"}, "phase2b_browser_settings_read"),
    "/storage/browser-settings/import": ({"POST"}, "phase2b_browser_settings_import"),
    "/storage/browser-settings/upsert": ({"POST"}, "phase2b_browser_settings_upsert"),
    "/storage/browser-settings/delete": ({"POST"}, "phase2b_browser_settings_delete"),
    "/diagnostics/runtime": ({"GET"}, "cvstudio_runtime_diagnostics"),
    "/diagnostics/clear_preview_cache": ({"POST"}, "cvstudio_clear_preview_cache"),
    "/diagnostics/support_bundle": ({"POST"}, "cvstudio_support_bundle"),
    "/ocr/health": ({"GET"}, "ocr_health"),
    "/ocr": ({"POST"}, "ocr_endpoint"),
    "/parse": ({"POST"}, "parse_cv"),
    "/preview-file": ({"POST"}, "preview_file"),
    "/extract-text": ({"POST"}, "extract_text"),
    "/blind": ({"POST"}, "blind_cv"),
}


class Phase4BackendModularizationCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory(prefix="cvstudio-phase4-case-")
        self.storage = CVStudioStorage(
            Path(self._temporary.name) / "state" / "cv_studio.sqlite3"
        )
        self.storage.initialize()
        self.original_repositories = (
            app._CVSTUDIO_STORAGE,
            app._CVSTUDIO_USAGE_REPOSITORY,
            app._CVSTUDIO_PPC_REPOSITORY,
            app._CVSTUDIO_ONENOTE_TRANSFER_REPOSITORY,
            app._CVSTUDIO_ONENOTE_LINK_REPOSITORY,
            app._CVSTUDIO_BROWSER_SETTINGS_REPOSITORY,
        )
        app._CVSTUDIO_STORAGE = self.storage
        app._CVSTUDIO_USAGE_REPOSITORY = UsageHistoryRepository(self.storage)
        app._CVSTUDIO_PPC_REPOSITORY = PPCMetadataRepository(self.storage)
        app._CVSTUDIO_ONENOTE_TRANSFER_REPOSITORY = OneNoteTransferRepository(
            self.storage
        )
        app._CVSTUDIO_ONENOTE_LINK_REPOSITORY = OneNoteSavedLinkRepository(
            self.storage
        )
        app._CVSTUDIO_BROWSER_SETTINGS_REPOSITORY = BrowserSettingsRepository(
            self.storage
        )
        self.client = app.app.test_client()

    def tearDown(self):
        (
            app._CVSTUDIO_STORAGE,
            app._CVSTUDIO_USAGE_REPOSITORY,
            app._CVSTUDIO_PPC_REPOSITORY,
            app._CVSTUDIO_ONENOTE_TRANSFER_REPOSITORY,
            app._CVSTUDIO_ONENOTE_LINK_REPOSITORY,
            app._CVSTUDIO_BROWSER_SETTINGS_REPOSITORY,
        ) = self.original_repositories
        self._temporary.cleanup()

    @staticmethod
    def _headers(request_id):
        return {
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": request_id,
        }

    def _assert_success_fields(self, response, expected):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.get_json()), set(expected))

    def _assert_invalid_payload(self, response, request_id):
        payload = response.get_json()
        self.assertEqual(response.status_code, 400)
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
            },
        )
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "STORAGE_PAYLOAD_INVALID")
        self.assertEqual(payload["request_id"], request_id)

    def test_selected_route_methods_endpoints_and_global_boundaries_are_exact(self):
        rules = {rule.rule: rule for rule in app.app.url_map.iter_rules()}
        self.assertEqual(len(rules), 107)
        for path, (methods, endpoint) in _SELECTED_ROUTES.items():
            self.assertIn(path, rules)
            self.assertEqual(rules[path].methods & {"GET", "POST"}, methods)
            self.assertEqual(rules[path].endpoint, endpoint)
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
        self.assertTrue({"/parse", "/blind"}.issubset(app._AI_SPEND_EXACT_PATHS))

    def test_storage_bridge_success_and_error_response_fields_are_exact(self):
        headers = self._headers("phase4-storage-characterization")

        self._assert_success_fields(
            self.client.get("/storage/usage-history", headers=headers),
            {"ok", "records", "request_id", "legacy_preserved"},
        )
        self._assert_success_fields(
            self.client.post(
                "/storage/usage-history/import",
                json={
                    "records": [
                        {
                            "id": "phase4-usage",
                            "type": "fixture",
                            "access_token": "<fixture-credential>",
                        }
                    ]
                },
                headers=headers,
            ),
            {"ok", "imported", "records", "request_id", "legacy_preserved"},
        )
        self.assertNotIn(
            "access_token",
            self.client.get("/storage/usage-history", headers=headers).get_json()[
                "records"
            ][0],
        )
        self._assert_success_fields(
            self.client.post(
                "/storage/usage-history/upsert",
                json={"records": [{"id": "phase4-usage", "type": "updated"}]},
                headers=headers,
            ),
            {"ok", "written", "request_id", "legacy_preserved"},
        )
        self._assert_success_fields(
            self.client.post("/storage/usage-history/clear", headers=headers),
            {"ok", "request_id", "legacy_preserved"},
        )

        self._assert_success_fields(
            self.client.get("/storage/ppc-metadata", headers=headers),
            {"ok", "metadata", "request_id", "legacy_preserved"},
        )
        ppc_payload = {
            "metadata": {
                "placement-fixture": {
                    "payment": "Paid",
                    "guaranteeMonths": "3",
                    "updatedAt": "2026-07-23T00:00:00Z",
                }
            }
        }
        self._assert_success_fields(
            self.client.post(
                "/storage/ppc-metadata/import", json=ppc_payload, headers=headers
            ),
            {"ok", "imported", "metadata", "request_id", "legacy_preserved"},
        )
        self._assert_success_fields(
            self.client.post(
                "/storage/ppc-metadata/upsert", json=ppc_payload, headers=headers
            ),
            {"ok", "written", "request_id", "legacy_preserved"},
        )
        self._assert_success_fields(
            self.client.post("/storage/ppc-metadata/clear", headers=headers),
            {"ok", "request_id", "legacy_preserved"},
        )

        transfer = {
            "records": [
                {
                    "id": "phase4-transfer",
                    "ts": "2026-07-23T00:00:00Z",
                    "status": "Transferred",
                }
            ]
        }
        self._assert_success_fields(
            self.client.get("/storage/onenote-transfer-records", headers=headers),
            {"ok", "records", "request_id", "legacy_preserved"},
        )
        self._assert_success_fields(
            self.client.post(
                "/storage/onenote-transfer-records/import",
                json=transfer,
                headers=headers,
            ),
            {"ok", "imported", "records", "request_id", "legacy_preserved"},
        )
        self._assert_success_fields(
            self.client.post(
                "/storage/onenote-transfer-records/replace",
                json=transfer,
                headers=headers,
            ),
            {"ok", "written", "request_id", "legacy_preserved"},
        )
        self._assert_success_fields(
            self.client.post(
                "/storage/onenote-transfer-records/clear", headers=headers
            ),
            {"ok", "request_id", "legacy_preserved"},
        )

        links = {
            "links": [
                {
                    "id": "phase4-link",
                    "name": "Fixture link",
                    "kind": "page",
                    "link": "onenote:fixture",
                }
            ]
        }
        self._assert_success_fields(
            self.client.get("/storage/onenote-saved-links", headers=headers),
            {"ok", "links", "request_id", "legacy_preserved"},
        )
        self._assert_success_fields(
            self.client.post(
                "/storage/onenote-saved-links/import", json=links, headers=headers
            ),
            {"ok", "imported", "links", "request_id", "legacy_preserved"},
        )
        self._assert_success_fields(
            self.client.post(
                "/storage/onenote-saved-links/replace", json=links, headers=headers
            ),
            {"ok", "written", "request_id", "legacy_preserved"},
        )

        settings = {"settings": {"hy_provider": "deepseek"}}
        self._assert_success_fields(
            self.client.get("/storage/browser-settings", headers=headers),
            {"ok", "settings", "request_id", "legacy_preserved"},
        )
        self._assert_success_fields(
            self.client.post(
                "/storage/browser-settings/import", json=settings, headers=headers
            ),
            {"ok", "imported", "settings", "request_id", "legacy_preserved"},
        )
        self._assert_success_fields(
            self.client.post(
                "/storage/browser-settings/upsert", json=settings, headers=headers
            ),
            {"ok", "written", "request_id", "legacy_preserved"},
        )
        self._assert_success_fields(
            self.client.post(
                "/storage/browser-settings/delete",
                json={"keys": ["hy_provider"]},
                headers=headers,
            ),
            {"ok", "deleted", "request_id", "legacy_preserved"},
        )

        invalid_cases = (
            ("/storage/usage-history/import", {"records": "invalid"}),
            ("/storage/ppc-metadata/import", {"metadata": []}),
            ("/storage/onenote-transfer-records/replace", {"records": "invalid"}),
            ("/storage/onenote-saved-links/replace", {"links": "invalid"}),
            (
                "/storage/browser-settings/upsert",
                {"settings": {"access_token": "<fixture-credential>"}},
            ),
            ("/storage/browser-settings/delete", {"keys": ["access_token"]}),
        )
        for index, (path, payload) in enumerate(invalid_cases):
            request_id = "phase4-storage-invalid-{}".format(index)
            self._assert_invalid_payload(
                self.client.post(
                    path, json=payload, headers=self._headers(request_id)
                ),
                request_id,
            )

    def test_diagnostics_shapes_bundle_contents_and_redaction_are_exact(self):
        request_id = "phase4-diagnostics-characterization"
        headers = self._headers(request_id)
        runtime = self.client.get(
            "/diagnostics/runtime",
            headers={"X-CV-Studio-Request-ID": request_id},
        )
        self._assert_success_fields(
            runtime,
            {
                "ok",
                "product",
                "version",
                "generated_at",
                "request_id",
                "instance_id",
                "root_hash",
                "pid",
                "port",
                "runtime_mode",
                "runtime_process",
                "platform",
                "memory",
                "cache",
                "durable_storage",
                "dependencies",
                "connections",
                "install_receipt",
            },
        )
        self.assertEqual(runtime.get_json()["request_id"], request_id)

        cleared = self.client.post(
            "/diagnostics/clear_preview_cache", headers=headers
        )
        self._assert_success_fields(cleared, {"ok", "request_id", "cache"})

        runtime_log = Path(self._temporary.name) / "runtime.log"
        runtime_log.write_text(
            "Authorization: Bearer <fixture-credential> "
            "email=fixture.person@example.invalid /candidates/12345678",
            encoding="utf-8",
        )
        with mock.patch.object(app, "_RUNTIME_LOG_PATH", str(runtime_log)):
            bundle = self.client.post(
                "/diagnostics/support_bundle",
                json={
                    "browser": {
                        "active_tab": "stats<script>",
                        "local_storage_keys": ["safe-key", "access_token"],
                        "recent_api_errors": [
                            {
                                "status": 500,
                                "path": "/candidate?id=private",
                                "message": "fixture.person@example.invalid",
                            }
                        ],
                    }
                },
                headers=headers,
            )
        self.assertEqual(bundle.status_code, 200)
        self.assertEqual(bundle.mimetype, "application/zip")
        with zipfile.ZipFile(io.BytesIO(bundle.data)) as archive:
            names = set(archive.namelist())
            self.assertTrue(
                {
                    "runtime.json",
                    "browser.json",
                    "BACKBURNER_ROADMAP.md",
                    "README.txt",
                    "runtime.log.tail.txt",
                }.issubset(names)
            )
            browser = json.loads(archive.read("browser.json"))
            combined = b"\n".join(archive.read(name) for name in names).decode(
                "utf-8", errors="replace"
            )
        self.assertEqual(browser["active_tab"], "statsscript")
        self.assertEqual(browser["local_storage_keys"], ["safe-key"])
        self.assertNotIn("<fixture-credential>", combined)
        self.assertNotIn("fixture.person@example.invalid", combined)
        self.assertNotIn("/candidates/12345678", combined)

    def test_document_safety_helpers_and_route_error_contracts_are_exact(self):
        self.assertEqual(app._MAX_PDF_PAGES, 80)
        self.assertEqual(app._MAX_OCR_PAGES, 30)
        self.assertEqual(app._MAX_IMAGE_PIXELS, 60_000_000)
        self.assertEqual(
            app._document_validation_status(
                ValueError("Document expands beyond the safe limit")
            ),
            413,
        )
        self.assertEqual(
            app._document_validation_status(ValueError("Document is invalid")),
            400,
        )
        valid_zip = io.BytesIO()
        with zipfile.ZipFile(valid_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", "<document/>")
        self.assertIsNone(app._validate_zip_payload(valid_zip.getvalue(), "DOCX"))
        with self.assertRaisesRegex(ValueError, "not a valid ZIP-based document"):
            app._validate_zip_payload(b"not-a-zip", "DOCX")

        headers = self._headers("phase4-document-characterization")
        expected_errors = {
            "/ocr": "No file provided. Send multipart form-data field named 'file'.",
            "/preview-file": "No file uploaded",
            "/extract-text": "No file uploaded",
        }
        for path, error in expected_errors.items():
            response = self.client.post(path, headers=headers)
            payload = response.get_json()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(payload["error"], error)
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
                },
            )
            self.assertEqual(payload["code"], "INVALID_REQUEST")

        paid_client = app.app.test_client()
        blocked = paid_client.post("/parse", headers=headers)
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.get_json()["code"], "AI_SPEND_SESSION_REQUIRED")
        home = paid_client.get("/")
        home.close()
        for path in ("/parse", "/blind"):
            response = paid_client.post(path, headers=headers)
            payload = response.get_json()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(payload["error"], "Invalid JSON body")
            self.assertEqual(payload["code"], "INVALID_REQUEST")

        unsafe = app.app.test_client().post("/preview-file")
        self.assertEqual(unsafe.status_code, 403)
        self.assertEqual(unsafe.get_json()["code"], "UNSAFE_LOCAL_REQUEST")

    def test_storage_bridge_resolves_app_compatibility_dependencies_per_call(self):
        headers = self._headers("phase4-storage-rebinding")
        with mock.patch.object(app, "_phase2a_usage_records", return_value=None):
            response = self.client.post(
                "/storage/usage-history/import",
                json={"records": []},
                headers=headers,
            )
        self._assert_invalid_payload(response, "phase4-storage-rebinding")

        with app.app.test_request_context("/storage/usage-history"):
            with mock.patch.object(
                app, "_cvstudio_current_request_id", return_value="rebound-storage-id"
            ):
                response = app.phase2a_usage_history_read()
        self.assertEqual(response.get_json()["request_id"], "rebound-storage-id")

        marker = object()
        with app.app.test_request_context(
            "/storage/usage-history/import",
            method="POST",
            json={"records": "invalid"},
        ):
            with mock.patch.object(
                app, "_cvstudio_error_payload", return_value=marker
            ):
                self.assertIs(app.phase2a_usage_history_import(), marker)

        with mock.patch.object(app, "BROWSER_SETTING_KEYS", frozenset()):
            self.assertIsNone(
                app._phase2b_browser_setting_keys(["hy_provider"])
            )
        with mock.patch.object(
            app.BrowserSettingsRepository,
            "normalize_value",
            return_value=None,
        ):
            self.assertIsNone(
                app._phase2b_browser_settings({"hy_provider": "deepseek"})
            )

    def test_diagnostics_service_resolves_app_dependencies_per_call(self):
        with app.app.test_request_context(
            "/diagnostics/clear_preview_cache", method="POST"
        ):
            with (
                mock.patch.object(
                    app,
                    "_cvstudio_current_request_id",
                    return_value="rebound-diagnostics-id",
                ),
                mock.patch.object(app, "_spider_preview_cancel_background_work"),
                mock.patch.object(app, "_spider_resume_text_cache_clear"),
                mock.patch.object(
                    app, "_spider_preview_cache_stats", return_value={}
                ),
            ):
                response = app.cvstudio_clear_preview_cache()
        self.assertEqual(
            response.get_json()["request_id"], "rebound-diagnostics-id"
        )

        with app.app.test_request_context(
            "/diagnostics/support_bundle", method="POST", json={}
        ):
            with (
                mock.patch.object(app, "_CVSTUDIO_VERSION", "v-rebound"),
                mock.patch.object(
                    app,
                    "_cvstudio_sanitize_browser_diagnostics",
                    return_value={"rebound_sanitizer": True},
                ),
            ):
                response = app.cvstudio_support_bundle()
        try:
            self.assertIn(
                "cv_studio_diagnostic_bundle_v-rebound_",
                response.headers["Content-Disposition"],
            )
            response.direct_passthrough = False
            with zipfile.ZipFile(io.BytesIO(response.get_data())) as archive:
                self.assertEqual(
                    json.loads(archive.read("browser.json")),
                    {"rebound_sanitizer": True},
                )
        finally:
            response.close()

        marker = object()
        with app.app.test_request_context(
            "/diagnostics/support_bundle", method="POST", json={}
        ):
            with mock.patch.object(app, "send_file", return_value=marker):
                self.assertIs(app.cvstudio_support_bundle(), marker)

    def test_document_safety_adapters_resolve_app_dependencies_per_call(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("one.txt", "fixture")
        with mock.patch.object(app, "_MAX_ZIP_ENTRIES", 0):
            with self.assertRaisesRegex(ValueError, "contains too many files"):
                app._validate_zip_payload(payload.getvalue(), "fixture")

        class FakeSemaphore:
            def __init__(self):
                self.acquire_calls = 0
                self.release_calls = 0

            def acquire(self, timeout=None):
                self.acquire_calls += 1
                return True

            def release(self):
                self.release_calls += 1

        class FakeImage:
            size = (10, 10)

            def close(self):
                pass

        semaphore = FakeSemaphore()
        pytesseract = mock.Mock()
        pytesseract.image_to_string.return_value = "fixture OCR"
        with (
            mock.patch.object(app, "_OCR_SEMAPHORE", semaphore),
            mock.patch.object(app, "_pdf_page_count", return_value=1) as count,
            mock.patch.object(
                app,
                "_render_pdf_page_images",
                return_value=[FakeImage()],
            ) as render,
        ):
            result = app._ocr_pdf_pagewise(b"fixture", pytesseract)
        self.assertEqual(result, "fixture OCR")
        count.assert_called_once_with(b"fixture")
        render.assert_called_once()
        self.assertEqual(semaphore.acquire_calls, 1)
        self.assertEqual(semaphore.release_calls, 1)


def tearDownModule():
    _MODULE_TEMPORARY.cleanup()


if __name__ == "__main__":
    unittest.main()
