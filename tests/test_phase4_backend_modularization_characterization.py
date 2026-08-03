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
        self.assertEqual(len(rules), 116)
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

    def test_legacy_doc_requires_and_uses_verified_antiword(self):
        fixture = (
            Path(__file__).resolve().parents[1]
            / "vendor"
            / "antiword"
            / "fixtures"
            / "UDHR-english.doc"
        ).read_bytes()
        visual_limit = 12 * 1024 * 1024
        oversized_fixture = fixture + (
            b"\0" * (visual_limit + 1 - len(fixture))
        )
        headers = self._headers("antiword-functional-route")
        response = self.client.post(
            "/extract-text",
            data={"file": (io.BytesIO(fixture), "verification.doc")},
            headers=headers,
            content_type="multipart/form-data",
        )
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertIn("Universal Declaration of Human Rights", payload["text"])
        self.assertNotIn("\ufffd", payload["text"])

        mislabeled_route = self.client.post(
            "/extract-text",
            data={"file": (io.BytesIO(fixture), "misleading-resume.txt")},
            headers=headers,
            content_type="multipart/form-data",
        )
        mislabeled_payload = mislabeled_route.get_json()
        self.assertEqual(mislabeled_route.status_code, 200)
        self.assertTrue(mislabeled_payload["ok"])
        self.assertIn(
            "Universal Declaration of Human Rights",
            mislabeled_payload["text"],
        )
        self.assertNotIn("\ufffd", mislabeled_payload["text"])

        real_import = __import__

        def reject_optional_ocr_imports(name, *args, **kwargs):
            if name == "pytesseract" or name == "PIL" or name.startswith("PIL."):
                raise ImportError("forced missing optional OCR dependency")
            return real_import(name, *args, **kwargs)

        with mock.patch(
            "builtins.__import__",
            side_effect=reject_optional_ocr_imports,
        ):
            ocr = self.client.post(
                "/ocr",
                data={"file": (io.BytesIO(fixture), "verification.doc")},
                headers=headers,
                content_type="multipart/form-data",
            )
        self.assertEqual(ocr.status_code, 200)
        self.assertIn(
            "Universal Declaration of Human Rights",
            ocr.get_json()["text"],
        )
        with mock.patch.object(app, "_find_soffice_binary", return_value=None):
            preview = self.client.post(
                "/preview-file",
                data={"file": (io.BytesIO(fixture), "verification.doc")},
                headers=headers,
                content_type="multipart/form-data",
            )
        self.assertEqual(preview.status_code, 200)
        self.assertNotEqual(
            preview.get_json().get("code"),
            "ANTIWORD_DEPENDENCY_UNAVAILABLE",
        )
        spider_text, spider_source = app._spider_extract_text_from_download(
            fixture,
            "application/msword",
            "verification.doc",
        )
        self.assertIn("Universal Declaration of Human Rights", spider_text)
        self.assertEqual(spider_source, "downloaded legacy DOC resume")

        with tempfile.TemporaryDirectory(
            prefix="cvstudio-antiword-ambient-home-"
        ) as ambient:
            ambient_resources = Path(ambient) / ".antiword"
            ambient_resources.mkdir()
            (ambient_resources / "UTF-8.txt").write_text(
                "untrusted mapping",
                encoding="utf-8",
            )
            (ambient_resources / "fontnames").write_text(
                "untrusted font mapping",
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ,
                {
                    "HOME": ambient,
                    "ANTIWORDHOME": str(ambient_resources),
                },
                clear=False,
            ):
                antiword_binary = app._require_verified_antiword()
                child_environment = app._antiword_env_for_binary(
                    antiword_binary
                )
                ambient_text, ambient_source = (
                    app._spider_extract_text_from_download(
                        fixture,
                        "application/msword",
                        "verification.doc",
                    )
                )
            self.assertNotIn("ANTIWORDHOME", child_environment)
            self.assertEqual(
                Path(child_environment["HOME"]),
                Path(antiword_binary).resolve(),
            )
            self.assertIn(
                "Universal Declaration of Human Rights",
                ambient_text,
            )
            self.assertEqual(
                ambient_source,
                "downloaded legacy DOC resume",
            )

        mislabeled_text, mislabeled_source = (
            app._spider_extract_text_from_download(
                fixture,
                "text/plain; charset=utf-8",
                "misleading-resume.txt",
            )
        )
        self.assertIn(
            "Universal Declaration of Human Rights",
            mislabeled_text,
        )
        self.assertNotIn("\ufffd", mislabeled_text)
        self.assertEqual(
            mislabeled_source,
            "downloaded legacy DOC resume",
        )

        with mock.patch.object(
            app,
            "_spider_extract_legacy_doc_text_for_preview",
            return_value="verified oversized legacy document",
        ) as oversized_verifier:
            oversized_visual = app._spider_visual_preview_payload(
                oversized_fixture,
                "application/pdf",
                "misleading-oversized.pdf",
            )
            self.assertIsNone(oversized_visual)
            oversized_route = self.client.post(
                "/preview-file",
                data={
                    "file": (
                        io.BytesIO(oversized_fixture),
                        "misleading-oversized.pdf",
                    )
                },
                headers=headers,
                content_type="multipart/form-data",
            )
            self.assertEqual(oversized_route.status_code, 200)
            self.assertFalse(oversized_route.get_json()["ok"])
            self.assertIn(
                "larger than 12 MB",
                oversized_route.get_json()["error"],
            )
            oversized_route.request.environ["wsgi.input"].close()
            oversized_route.request.close()
            oversized_route.close()
            self.assertEqual(oversized_verifier.call_count, 2)

        self.assertFalse(
            app._spider_prefetch_should_defer_ocr(
                oversized_fixture,
                "application/pdf",
                "misleading-oversized.pdf",
            )
        )
        oversized_pdf = b"%PDF" + (b"\0" * (visual_limit - 3))
        oversized_image = b"\x89PNG\r\n\x1a\n" + (
            b"\0" * (visual_limit - 7)
        )
        self.assertIsNone(
            app._spider_visual_preview_payload(
                oversized_pdf,
                "application/msword",
                "misleading.doc",
            )
        )
        self.assertIsNone(
            app._spider_visual_preview_payload(
                oversized_image,
                "application/msword",
                "misleading.doc",
            )
        )
        self.assertTrue(
            app._spider_prefetch_should_defer_ocr(
                oversized_pdf,
                "application/msword",
                "misleading.doc",
            )
        )
        self.assertTrue(
            app._spider_prefetch_should_defer_ocr(
                oversized_image,
                "application/msword",
                "misleading.doc",
            )
        )

        with mock.patch.object(
            app,
            "_spider_extract_legacy_doc_text_for_preview",
            side_effect=AssertionError(
                "strong non-DOC magic must not reach Antiword"
            ),
        ):
            with mock.patch.object(
                app,
                "_spider_ocr_pdf_download",
                return_value=("verified PDF text", "PDF magic path"),
            ):
                pdf_text, pdf_source = (
                    app._spider_extract_text_from_download(
                        b"%PDF-1.4\ninvalid-test-payload",
                        "application/msword",
                        "stale-name.doc",
                    )
                )
            self.assertEqual(pdf_text, "verified PDF text")
            self.assertEqual(pdf_source, "PDF magic path")

            with mock.patch.object(
                app,
                "_extract_docx_text_preserve_tables",
                return_value="Verified DOCX resume experience and skills",
            ):
                docx_text, docx_source = (
                    app._spider_extract_text_from_download(
                        b"PK\x03\x04test-docx-payload",
                        "application/msword",
                        "stale-name.doc",
                    )
                )
            self.assertIn("Verified DOCX resume", docx_text)
            self.assertEqual(docx_source, "downloaded DOCX resume")

        malformed = self.client.post(
            "/extract-text",
            data={"file": (io.BytesIO(b"not-a-legacy-document"), "malformed.doc")},
            headers=headers,
            content_type="multipart/form-data",
        )
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(malformed.get_json()["code"], "INVALID_REQUEST")

        corrupt_ole = self.client.post(
            "/extract-text",
            data={
                "file": (
                    io.BytesIO(bytes.fromhex("d0cf11e0a1b11ae1") + (b"\0" * 2048)),
                    "corrupt.doc",
                )
            },
            headers=headers,
            content_type="multipart/form-data",
        )
        self.assertEqual(corrupt_ole.status_code, 424)
        self.assertEqual(
            corrupt_ole.get_json()["code"],
            "LEGACY_DOC_EXTRACTION_FAILED",
        )
        self.assertEqual(
            corrupt_ole.get_json()["action"],
            "convert_to_docx_or_pdf",
        )
        self.assertEqual(
            corrupt_ole.get_json()["details"]["reason"],
            "document-extraction-failed",
        )
        for route in ("/preview-file", "/ocr"):
            with self.subTest(route=route, failure="corrupt-doc"):
                corrupt_route = self.client.post(
                    route,
                    data={
                        "file": (
                            io.BytesIO(
                                bytes.fromhex("d0cf11e0a1b11ae1")
                                + (b"\0" * 2048)
                            ),
                            "corrupt.doc",
                        )
                    },
                    headers=headers,
                    content_type="multipart/form-data",
                )
                self.assertEqual(corrupt_route.status_code, 424)
                self.assertEqual(
                    corrupt_route.get_json()["code"],
                    "LEGACY_DOC_EXTRACTION_FAILED",
                )

        oversized = self.client.post(
            "/extract-text",
            headers=headers,
            environ_overrides={
                "CONTENT_LENGTH": str(app.app.config["MAX_CONTENT_LENGTH"] + 1)
            },
        )
        self.assertEqual(oversized.status_code, 413)
        self.assertEqual(oversized.get_json()["code"], "REQUEST_TOO_LARGE")

        with self.assertRaises(app.AntiwordDependencyError) as empty_error:
            app._spider_extract_legacy_doc_text_for_preview(b"")
        self.assertEqual(
            empty_error.exception.reason,
            "document-extraction-failed",
        )
        with self.assertRaises(app.AntiwordDependencyError):
            app._spider_extract_text_from_download(
                b"",
                "application/msword",
                "empty.doc",
            )

        unavailable = app.AntiwordDependencyError("runtime-missing")
        with mock.patch.object(
            app,
            "_require_verified_antiword_runtime",
            side_effect=unavailable,
        ):
            stale_resume_cache = mock.Mock(
                return_value={
                    "text": "stale cached candidate profile",
                    "source": "profile fallback",
                    "content_kind": "pdf",
                }
            )
            resume_download = mock.Mock(
                return_value=(
                    fixture,
                    "text/plain; charset=utf-8",
                    "unchanged-resume.txt",
                )
            )
            with (
                mock.patch.object(
                    app,
                    "_spider_resume_text_cache_get",
                    stale_resume_cache,
                ),
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=(
                        [
                            {
                                "attachmentId": "unchanged-resume",
                                "fileName": "unchanged-resume.txt",
                                "type": "Resume",
                            }
                        ],
                        True,
                    ),
                ),
                mock.patch.object(
                    app,
                    "_spider_get_ja_raw",
                    resume_download,
                ),
            ):
                with self.assertRaises(
                    app.AntiwordDependencyError
                ) as cached_resume:
                    app._spider_fetch_candidate_resume_text(
                        "<fixture-token>",
                        "candidate-with-stale-cache",
                    )
            self.assertIs(cached_resume.exception, unavailable)
            stale_resume_cache.assert_called_once_with(
                "<fixture-token>",
                "candidate-with-stale-cache",
                app._spider_download_content_identity(fixture),
            )
            resume_download.assert_called_once()

            with self.assertRaises(app.AntiwordDependencyError) as mislabeled:
                app._spider_extract_text_from_download(
                    fixture,
                    "text/plain; charset=utf-8",
                    "misleading-resume.txt",
                )
            self.assertIs(mislabeled.exception, unavailable)
            with self.assertRaises(
                app.AntiwordDependencyError
            ) as oversized_visual_error:
                app._spider_visual_preview_payload(
                    oversized_fixture,
                    "application/pdf",
                    "misleading-oversized.pdf",
                )
            self.assertIs(
                oversized_visual_error.exception,
                unavailable,
            )
            oversized_preview = self.client.post(
                "/preview-file",
                data={
                    "file": (
                        io.BytesIO(oversized_fixture),
                        "misleading-oversized.pdf",
                    )
                },
                headers=headers,
                content_type="multipart/form-data",
            )
            self.assertEqual(oversized_preview.status_code, 424)
            self.assertEqual(
                oversized_preview.get_json()["code"],
                "ANTIWORD_DEPENDENCY_UNAVAILABLE",
            )
            oversized_preview.request.environ["wsgi.input"].close()
            oversized_preview.request.close()
            oversized_preview.close()

            prefetch_store = mock.Mock()
            stale_preview_cache = mock.Mock(
                return_value={
                    "ok": True,
                    "mode": "profile",
                    "text": "stale profile fallback",
                }
            )
            preview_download = mock.Mock(
                return_value=(
                    oversized_fixture,
                    "application/pdf",
                    "misleading-oversized.pdf",
                )
            )
            with (
                mock.patch.object(
                    app,
                    "_ai_crawler_lock_allowed",
                    return_value=True,
                ),
                mock.patch.object(
                    app,
                    "_ja_refresh_access_token",
                    return_value="<fixture-token>",
                ),
                mock.patch.object(
                    app,
                    "_spider_resume_cache_key",
                    return_value="oversized-ole-prefetch",
                ),
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=[
                        {
                            "attachmentId": "oversized-ole",
                            "fileName": "misleading-oversized.pdf",
                            "type": "Resume",
                        }
                    ],
                ),
                mock.patch.object(
                    app,
                    "_spider_preview_payload_cache_get",
                    stale_preview_cache,
                ),
                mock.patch.object(
                    app,
                    "_spider_fetch_candidate_detail",
                    return_value={
                        "firstName": "Fixture",
                        "lastName": "Candidate",
                    },
                ),
                mock.patch.object(
                    app,
                    "_spider_get_ja_raw",
                    preview_download,
                ),
                mock.patch.object(
                    app,
                    "_CVSTUDIO_JOBS",
                    prefetch_store,
                ),
            ):
                prefetch_response = self.client.get(
                    "/jobadder/spider_candidate_preview"
                    "?candidate_id=oversized-ole&prefetch=1",
                    headers=headers,
                )
            self.assertEqual(prefetch_response.status_code, 424)
            self.assertEqual(
                prefetch_response.get_json()["code"],
                "ANTIWORD_DEPENDENCY_UNAVAILABLE",
            )
            stale_preview_cache.assert_called_once_with(
                "<fixture-token>",
                "oversized-ole",
                app._spider_download_content_identity(oversized_fixture),
                "full",
            )
            preview_download.assert_called_once()
            with self.assertRaises(app.AntiwordDependencyError) as office:
                app._office_bytes_to_pdf_preview(fixture, ".txt")
            self.assertIs(office.exception, unavailable)

            with mock.patch(
                "builtins.__import__",
                side_effect=reject_optional_ocr_imports,
            ):
                ocr_without_pytesseract = self.client.post(
                    "/ocr",
                    data={
                        "file": (
                            io.BytesIO(fixture),
                            "misleading-resume.png",
                        )
                    },
                    headers=headers,
                    content_type="multipart/form-data",
                )
            self.assertEqual(ocr_without_pytesseract.status_code, 424)
            self.assertEqual(
                ocr_without_pytesseract.get_json()["code"],
                "ANTIWORD_DEPENDENCY_UNAVAILABLE",
            )

            for content_type, name in (
                ("text/plain", "misleading-resume.txt"),
                ("application/pdf", "misleading-resume.pdf"),
                ("image/png", "misleading-resume.png"),
            ):
                with self.subTest(
                    helper="spider-visual",
                    content_type=content_type,
                ):
                    with self.assertRaises(
                        app.AntiwordDependencyError
                    ) as visual:
                        app._spider_visual_preview_payload(
                            fixture,
                            content_type,
                            name,
                        )
                    self.assertIs(visual.exception, unavailable)

            for route in ("/extract-text", "/preview-file", "/ocr"):
                for name in (
                    "verification.doc",
                    "misleading-resume.txt",
                    "misleading-resume.pdf",
                    "misleading-resume.png",
                ):
                    with self.subTest(route=route, name=name):
                        response = self.client.post(
                            route,
                            data={"file": (io.BytesIO(fixture), name)},
                            headers=headers,
                            content_type="multipart/form-data",
                        )
                        payload = response.get_json()
                        self.assertEqual(response.status_code, 424)
                        self.assertEqual(
                            payload["code"],
                            "ANTIWORD_DEPENDENCY_UNAVAILABLE",
                        )
                        self.assertEqual(payload["action"], "run_installer")
                        self.assertEqual(
                            payload["details"]["required_for"],
                            "legacy_doc",
                        )
            with self.assertRaises(app.AntiwordDependencyError):
                app._spider_extract_legacy_doc_text_for_preview(fixture)

    def test_jobadder_resume_caches_use_downloaded_content_identity(self):
        fixture = (
            Path(__file__).resolve().parents[1]
            / "vendor"
            / "antiword"
            / "fixtures"
            / "UDHR-english.doc"
        ).read_bytes()
        token = "<fixture-token>"
        candidate_id = "content-bound-candidate"
        record = {
            "attachmentId": "stable-attachment",
            "fileName": "resume.pdf",
            "type": "Resume",
        }
        old_pdf = b"%PDF-1.4\nold-content"
        new_pdf = b"%PDF-1.4\nreplacement-content"

        with mock.patch.object(
            app,
            "_spider_resume_cache_key",
            return_value="content-bound-cache-key",
        ):
            app._spider_resume_text_cache_clear()
            app._spider_resume_text_cache_put(
                token,
                candidate_id,
                "old cached PDF resume",
                "fixture PDF",
                content_sha256=app._spider_download_content_identity(old_pdf),
                content_kind="pdf",
            )

            for discovery_ok, expected_source in (
                (False, "resume attachment discovery failed"),
                (True, "resume attachment unavailable"),
            ):
                with self.subTest(discovery_ok=discovery_ok):
                    cache_get = mock.Mock(
                        wraps=app._spider_resume_text_cache_get
                    )
                    with (
                        mock.patch.object(
                            app,
                            "_spider_candidate_attachment_records",
                            return_value=([], discovery_ok),
                        ),
                        mock.patch.object(
                            app,
                            "_spider_resume_text_cache_get",
                            cache_get,
                        ),
                    ):
                        text, source = (
                            app._spider_fetch_candidate_resume_text(
                                token,
                                candidate_id,
                            )
                        )
                    self.assertEqual(text, "")
                    self.assertEqual(source, expected_source)
                    cache_get.assert_not_called()

            with mock.patch.object(
                app,
                "_spider_get_ja_raw",
                side_effect=OSError("fixture listing failure"),
            ):
                records, discovery_ok = (
                    app._spider_candidate_attachment_records(
                        token,
                        candidate_id,
                        include_status=True,
                    )
                )
            self.assertEqual(records, [])
            self.assertFalse(discovery_ok)

            with mock.patch.object(
                app,
                "_spider_get_ja_raw",
                return_value=(
                    b"{not-valid-json",
                    "application/json",
                    "",
                ),
            ):
                records, discovery_ok = (
                    app._spider_candidate_attachment_records(
                        token,
                        candidate_id,
                        include_status=True,
                    )
                )
            self.assertEqual(records, [])
            self.assertFalse(discovery_ok)

            unchanged_extractor = mock.Mock(
                side_effect=AssertionError(
                    "unchanged content should reuse extracted text"
                )
            )
            with (
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=([record], True),
                ),
                mock.patch.object(
                    app,
                    "_spider_get_ja_raw",
                    return_value=(old_pdf, "application/pdf", "resume.pdf"),
                ),
                mock.patch.object(
                    app,
                    "_spider_extract_text_from_download",
                    unchanged_extractor,
                ),
            ):
                text, source = app._spider_fetch_candidate_resume_text(
                    token,
                    candidate_id,
                )
            self.assertEqual(text, "old cached PDF resume")
            self.assertEqual(source, "fixture PDF")
            unchanged_extractor.assert_not_called()

            replacement_extractor = mock.Mock(
                return_value=("replacement PDF resume", "replacement PDF")
            )
            with (
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=([record], True),
                ),
                mock.patch.object(
                    app,
                    "_spider_get_ja_raw",
                    return_value=(
                        new_pdf,
                        "application/pdf",
                        "resume.pdf",
                    ),
                ),
                mock.patch.object(
                    app,
                    "_spider_extract_text_from_download",
                    replacement_extractor,
                ),
            ):
                text, source = app._spider_fetch_candidate_resume_text(
                    token,
                    candidate_id,
                )
            self.assertEqual(text, "replacement PDF resume")
            self.assertEqual(source, "replacement PDF")
            replacement_extractor.assert_called_once()
            cached_replacement = app._spider_resume_text_cache_get(
                token,
                candidate_id,
                app._spider_download_content_identity(new_pdf),
            )
            self.assertEqual(
                cached_replacement["text"],
                "replacement PDF resume",
            )

            unavailable = app.AntiwordDependencyError("runtime-missing")
            with (
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=([record], True),
                ),
                mock.patch.object(
                    app,
                    "_spider_get_ja_raw",
                    return_value=(
                        fixture,
                        "application/pdf",
                        "resume.pdf",
                    ),
                ),
                mock.patch.object(
                    app,
                    "_require_verified_antiword_runtime",
                    side_effect=unavailable,
                ),
            ):
                with self.assertRaises(
                    app.AntiwordDependencyError
                ) as changed_to_ole:
                    app._spider_fetch_candidate_resume_text(
                        token,
                        candidate_id,
                    )
            self.assertIs(changed_to_ole.exception, unavailable)

            app._spider_resume_text_cache_put(
                token,
                candidate_id,
                "verified legacy resume",
                "verified Antiword",
                content_sha256=app._spider_download_content_identity(fixture),
                content_kind="legacy_doc",
                antiword_verified=True,
            )
            healthy_gate = mock.Mock(return_value="verified-antiword")
            cached_extractor = mock.Mock(
                side_effect=AssertionError(
                    "healthy verified OLE cache hit must not re-extract"
                )
            )
            with (
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=([record], True),
                ),
                mock.patch.object(
                    app,
                    "_spider_get_ja_raw",
                    return_value=(
                        fixture,
                        "application/msword",
                        "resume.doc",
                    ),
                ),
                mock.patch.object(
                    app,
                    "_require_verified_antiword",
                    healthy_gate,
                ),
                mock.patch.object(
                    app,
                    "_spider_extract_text_from_download",
                    cached_extractor,
                ),
            ):
                text, source = app._spider_fetch_candidate_resume_text(
                    token,
                    candidate_id,
                )
            self.assertEqual(text, "verified legacy resume")
            self.assertEqual(source, "verified Antiword")
            healthy_gate.assert_called_once_with()
            cached_extractor.assert_not_called()

            with (
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=([record], True),
                ),
                mock.patch.object(
                    app,
                    "_spider_get_ja_raw",
                    return_value=(
                        fixture,
                        "application/msword",
                        "resume.doc",
                    ),
                ),
                mock.patch.object(
                    app,
                    "_require_verified_antiword",
                    side_effect=unavailable,
                ),
                mock.patch.object(
                    app,
                    "_spider_extract_text_from_download",
                    side_effect=AssertionError(
                        "verified OLE cache hit should gate before extraction"
                    ),
                ),
            ):
                with self.assertRaises(
                    app.AntiwordDependencyError
                ) as unchanged_ole:
                    app._spider_fetch_candidate_resume_text(
                        token,
                        candidate_id,
                    )
            self.assertIs(unchanged_ole.exception, unavailable)

            metadata_doc = (
                b"Name: Metadata Candidate\n"
                b"Experience: verified legacy resume fixture\n"
                b"Skills: regression coverage"
            )
            metadata_record = {
                "attachmentId": "metadata-doc",
                "fileName": "resume.doc",
                "type": "Resume",
            }
            app._spider_resume_text_cache_clear()
            metadata_extractor = mock.Mock(
                return_value=(
                    "verified metadata legacy resume",
                    "downloaded legacy DOC resume",
                )
            )
            with (
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=([metadata_record], True),
                ),
                mock.patch.object(
                    app,
                    "_spider_get_ja_raw",
                    return_value=(
                        metadata_doc,
                        "application/msword",
                        "resume.doc",
                    ),
                ),
                mock.patch.object(
                    app,
                    "_spider_extract_text_from_download",
                    metadata_extractor,
                ),
            ):
                metadata_text, metadata_source = (
                    app._spider_fetch_candidate_resume_text(
                        token,
                        candidate_id,
                    )
                )
            self.assertEqual(
                metadata_text,
                "verified metadata legacy resume",
            )
            self.assertEqual(
                metadata_source,
                "downloaded legacy DOC resume",
            )
            metadata_extractor.assert_called_once()
            metadata_cached = app._spider_resume_text_cache_get(
                token,
                candidate_id,
                app._spider_download_content_identity(metadata_doc),
            )
            self.assertEqual(
                metadata_cached["content_kind"],
                "legacy_doc",
            )
            self.assertTrue(metadata_cached["antiword_verified"])

            with (
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=([metadata_record], True),
                ),
                mock.patch.object(
                    app,
                    "_spider_get_ja_raw",
                    return_value=(
                        metadata_doc,
                        "application/msword",
                        "resume.doc",
                    ),
                ),
                mock.patch.object(
                    app,
                    "_require_verified_antiword",
                    side_effect=unavailable,
                ),
                mock.patch.object(
                    app,
                    "_spider_extract_text_from_download",
                    side_effect=AssertionError(
                        "metadata DOC cache hit must gate before extraction"
                    ),
                ),
            ):
                with self.assertRaises(
                    app.AntiwordDependencyError
                ) as metadata_text_unavailable:
                    app._spider_fetch_candidate_resume_text(
                        token,
                        candidate_id,
                    )
            self.assertIs(
                metadata_text_unavailable.exception,
                unavailable,
            )

            headers = self._headers("content-bound-preview-cache")
            visual_payload = {
                "visual_mode": "pages",
                "pages": [{"image": "data:image/webp;base64,fixture"}],
                "page_count": 1,
                "shown_pages": 1,
                "source": "fixture renderer",
            }

            app._spider_resume_text_cache_clear()
            metadata_render = mock.Mock(return_value=visual_payload)
            metadata_search = mock.Mock(
                return_value=(
                    "verified metadata legacy resume",
                    "downloaded legacy DOC resume",
                )
            )
            with (
                mock.patch.object(
                    app,
                    "_ai_crawler_lock_allowed",
                    return_value=True,
                ),
                mock.patch.object(
                    app,
                    "_ja_refresh_access_token",
                    return_value=token,
                ),
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=[metadata_record],
                ),
                mock.patch.object(
                    app,
                    "_spider_fetch_candidate_detail",
                    return_value={
                        "firstName": "Metadata",
                        "lastName": "Candidate",
                    },
                ),
                mock.patch.object(
                    app,
                    "_spider_get_ja_raw",
                    return_value=(
                        metadata_doc,
                        "application/msword",
                        "resume.doc",
                    ),
                ),
                mock.patch.object(
                    app,
                    "_spider_visual_preview_payload",
                    metadata_render,
                ),
                mock.patch.object(
                    app,
                    "_spider_extract_text_from_download",
                    metadata_search,
                ),
                mock.patch.object(
                    app,
                    "_spider_preview_cancel_persistent_work",
                    return_value=0,
                ),
            ):
                metadata_preview_first = self.client.get(
                    "/jobadder/spider_candidate_preview"
                    "?candidate_id=content-bound-candidate",
                    headers=headers,
                )
            self.assertEqual(metadata_preview_first.status_code, 200)
            self.assertFalse(
                metadata_preview_first.get_json()["preview_cache_hit"]
            )
            metadata_render.assert_called_once()
            metadata_search.assert_called_once()

            with (
                mock.patch.object(
                    app,
                    "_ai_crawler_lock_allowed",
                    return_value=True,
                ),
                mock.patch.object(
                    app,
                    "_ja_refresh_access_token",
                    return_value=token,
                ),
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=[metadata_record],
                ),
                mock.patch.object(
                    app,
                    "_spider_fetch_candidate_detail",
                    return_value={
                        "firstName": "Metadata",
                        "lastName": "Candidate",
                    },
                ),
                mock.patch.object(
                    app,
                    "_spider_get_ja_raw",
                    return_value=(
                        metadata_doc,
                        "application/msword",
                        "resume.doc",
                    ),
                ),
                mock.patch.object(
                    app,
                    "_require_verified_antiword",
                    side_effect=unavailable,
                ),
                mock.patch.object(
                    app,
                    "_spider_visual_preview_payload",
                    side_effect=AssertionError(
                        "metadata DOC preview cache hit must not re-render"
                    ),
                ),
                mock.patch.object(
                    app,
                    "_spider_extract_text_from_download",
                    side_effect=AssertionError(
                        "metadata DOC preview cache hit must not re-extract"
                    ),
                ),
                mock.patch.object(
                    app,
                    "_spider_preview_cancel_persistent_work",
                    return_value=0,
                ),
            ):
                metadata_preview_unavailable = self.client.get(
                    "/jobadder/spider_candidate_preview"
                    "?candidate_id=content-bound-candidate",
                    headers=headers,
                )
            self.assertEqual(
                metadata_preview_unavailable.status_code,
                424,
            )
            self.assertEqual(
                metadata_preview_unavailable.get_json()["code"],
                "ANTIWORD_DEPENDENCY_UNAVAILABLE",
            )

            app._spider_resume_text_cache_clear()
            fixture_identity = app._spider_download_content_identity(fixture)
            app._spider_preview_payload_cache_put(
                token,
                candidate_id,
                fixture_identity,
                {
                    "ok": True,
                    "candidate_id": candidate_id,
                    "mode": "resume_attachment_file",
                    "visual_mode": "pages",
                    "pages": [
                        {
                            "image": (
                                "data:image/webp;base64,cached-fixture"
                            )
                        }
                    ],
                    "page_count": 1,
                    "shown_pages": 1,
                    "preview_partial": False,
                    "preview_variant": "full",
                },
                "full",
                content_kind="legacy_doc",
                antiword_verified=True,
            )
            preview_render = mock.Mock(
                side_effect=AssertionError(
                    "healthy verified OLE preview hit must not re-render"
                )
            )
            healthy_preview_gate = mock.Mock(
                return_value="verified-antiword"
            )
            with (
                mock.patch.object(
                    app,
                    "_ai_crawler_lock_allowed",
                    return_value=True,
                ),
                mock.patch.object(
                    app,
                    "_ja_refresh_access_token",
                    return_value=token,
                ),
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=[record],
                ),
                mock.patch.object(
                    app,
                    "_spider_fetch_candidate_detail",
                    return_value={
                        "firstName": "Fixture",
                        "lastName": "Candidate",
                    },
                ),
                mock.patch.object(
                    app,
                    "_spider_get_ja_raw",
                    return_value=(
                        fixture,
                        "application/msword",
                        "resume.doc",
                    ),
                ),
                mock.patch.object(
                    app,
                    "_spider_visual_preview_payload",
                    preview_render,
                ),
                mock.patch.object(
                    app,
                    "_spider_preview_cancel_persistent_work",
                    return_value=0,
                ),
                mock.patch.object(
                    app,
                    "_require_verified_antiword",
                    healthy_preview_gate,
                ),
            ):
                healthy_preview = self.client.get(
                    "/jobadder/spider_candidate_preview"
                    "?candidate_id=content-bound-candidate",
                    headers=headers,
                )
            self.assertEqual(healthy_preview.status_code, 200)
            self.assertTrue(
                healthy_preview.get_json()["preview_cache_hit"]
            )
            healthy_preview_gate.assert_called_once_with()
            preview_render.assert_not_called()

            with (
                mock.patch.object(
                    app,
                    "_ai_crawler_lock_allowed",
                    return_value=True,
                ),
                mock.patch.object(
                    app,
                    "_ja_refresh_access_token",
                    return_value=token,
                ),
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=[record],
                ),
                mock.patch.object(
                    app,
                    "_spider_fetch_candidate_detail",
                    return_value={
                        "firstName": "Fixture",
                        "lastName": "Candidate",
                    },
                ),
                mock.patch.object(
                    app,
                    "_spider_get_ja_raw",
                    return_value=(
                        fixture,
                        "application/msword",
                        "resume.doc",
                    ),
                ),
                mock.patch.object(
                    app,
                    "_spider_visual_preview_payload",
                    preview_render,
                ),
                mock.patch.object(
                    app,
                    "_spider_preview_cancel_persistent_work",
                    return_value=0,
                ),
                mock.patch.object(
                    app,
                    "_require_verified_antiword",
                    side_effect=unavailable,
                ),
            ):
                unavailable_preview = self.client.get(
                    "/jobadder/spider_candidate_preview"
                    "?candidate_id=content-bound-candidate",
                    headers=headers,
                )
            self.assertEqual(unavailable_preview.status_code, 424)
            self.assertEqual(
                unavailable_preview.get_json()["code"],
                "ANTIWORD_DEPENDENCY_UNAVAILABLE",
            )
            preview_render.assert_not_called()

            for raw, content_type, filename in (
                (old_pdf, "application/pdf", "resume.pdf"),
                (b"PK\x03\x04fixture-docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "resume.docx"),
            ):
                with self.subTest(cache_format=filename):
                    app._spider_resume_text_cache_clear()
                    render = mock.Mock(return_value=visual_payload)
                    download = mock.Mock(
                        return_value=(raw, content_type, filename)
                    )
                    with (
                        mock.patch.object(
                            app,
                            "_ai_crawler_lock_allowed",
                            return_value=True,
                        ),
                        mock.patch.object(
                            app,
                            "_ja_refresh_access_token",
                            return_value=token,
                        ),
                        mock.patch.object(
                            app,
                            "_spider_candidate_attachment_records",
                            return_value=[record],
                        ),
                        mock.patch.object(
                            app,
                            "_spider_fetch_candidate_detail",
                            return_value={
                                "firstName": "Fixture",
                                "lastName": "Candidate",
                            },
                        ),
                        mock.patch.object(
                            app,
                            "_spider_get_ja_raw",
                            download,
                        ),
                        mock.patch.object(
                            app,
                            "_spider_visual_preview_payload",
                            render,
                        ),
                        mock.patch.object(
                            app,
                            "_spider_extract_text_from_download",
                            return_value=(
                                "fixture searchable resume",
                                "fixture extraction",
                            ),
                        ),
                        mock.patch.object(
                            app,
                            "_CVSTUDIO_JOBS",
                            mock.Mock(),
                        ),
                    ):
                        first = self.client.get(
                            "/jobadder/spider_candidate_preview"
                            "?candidate_id=content-bound-candidate&prefetch=1",
                            headers=headers,
                        )
                        second = self.client.get(
                            "/jobadder/spider_candidate_preview"
                            "?candidate_id=content-bound-candidate&prefetch=1",
                            headers=headers,
                        )
                    self.assertEqual(first.status_code, 200)
                    self.assertFalse(
                        first.get_json()["preview_cache_hit"]
                    )
                    self.assertEqual(second.status_code, 200)
                    self.assertTrue(
                        second.get_json()["preview_cache_hit"]
                    )
                    self.assertEqual(render.call_count, 1)
                    self.assertEqual(download.call_count, 2)

            app._spider_resume_text_cache_clear()
            changing_raw = {"value": old_pdf}

            def content_aware_render(raw, *_args, **_kwargs):
                if app._document_content_kind(raw) == "legacy_doc":
                    app._require_verified_antiword()
                return visual_payload

            render = mock.Mock(side_effect=content_aware_render)

            def changing_download(*_args, **_kwargs):
                raw = changing_raw["value"]
                return raw, "application/pdf", "resume.pdf"

            with (
                mock.patch.object(
                    app,
                    "_ai_crawler_lock_allowed",
                    return_value=True,
                ),
                mock.patch.object(
                    app,
                    "_ja_refresh_access_token",
                    return_value=token,
                ),
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=[record],
                ),
                mock.patch.object(
                    app,
                    "_spider_fetch_candidate_detail",
                    return_value={
                        "firstName": "Fixture",
                        "lastName": "Candidate",
                    },
                ),
                mock.patch.object(
                    app,
                    "_spider_get_ja_raw",
                    side_effect=changing_download,
                ),
                mock.patch.object(
                    app,
                    "_spider_visual_preview_payload",
                    render,
                ),
                mock.patch.object(
                    app,
                    "_CVSTUDIO_JOBS",
                    mock.Mock(),
                ),
            ):
                original = self.client.get(
                    "/jobadder/spider_candidate_preview"
                    "?candidate_id=content-bound-candidate&prefetch=1",
                    headers=headers,
                )
                changing_raw["value"] = new_pdf
                replacement = self.client.get(
                    "/jobadder/spider_candidate_preview"
                    "?candidate_id=content-bound-candidate&prefetch=1",
                    headers=headers,
                )
                changing_raw["value"] = fixture
                with mock.patch.object(
                    app,
                    "_require_verified_antiword",
                    side_effect=unavailable,
                ):
                    changed_to_ole = self.client.get(
                        "/jobadder/spider_candidate_preview"
                        "?candidate_id=content-bound-candidate&prefetch=1",
                        headers=headers,
                    )
            self.assertEqual(original.status_code, 200)
            self.assertEqual(replacement.status_code, 200)
            self.assertFalse(replacement.get_json()["preview_cache_hit"])
            self.assertEqual(render.call_count, 3)
            self.assertEqual(changed_to_ole.status_code, 424)
            self.assertEqual(
                changed_to_ole.get_json()["code"],
                "ANTIWORD_DEPENDENCY_UNAVAILABLE",
            )

            profile_cache_put = mock.Mock()
            with (
                mock.patch.object(
                    app,
                    "_ai_crawler_lock_allowed",
                    return_value=True,
                ),
                mock.patch.object(
                    app,
                    "_ja_refresh_access_token",
                    return_value=token,
                ),
                mock.patch.object(
                    app,
                    "_spider_candidate_attachment_records",
                    return_value=[record],
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
                    side_effect=OSError("fixture download unavailable"),
                ),
                mock.patch.object(
                    app,
                    "_spider_preview_payload_cache_put",
                    profile_cache_put,
                ),
            ):
                profile = self.client.get(
                    "/jobadder/spider_candidate_preview"
                    "?candidate_id=content-bound-candidate",
                    headers=headers,
                )
            self.assertEqual(profile.status_code, 200)
            self.assertEqual(profile.get_json()["mode"], "profile")
            profile_cache_put.assert_not_called()
            app._spider_resume_text_cache_clear()

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
