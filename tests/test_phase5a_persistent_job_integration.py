import hashlib
from contextlib import ExitStack
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


_MODULE_TEMPORARY = tempfile.TemporaryDirectory(
    prefix="cvstudio-phase5a-integration-"
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

from cvstudio_jobs import PersistentJobStore, deterministic_job_id


class Phase5APersistentJobIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="cvstudio-phase5a-integration-case-"
        )
        self.path = Path(self.temporary.name) / "jobs.json"
        self.store = PersistentJobStore(self.path)
        self.store.initialize()
        self.cache_key = hashlib.sha256(
            b"phase5a-fixture-cache-key"
        ).hexdigest()
        self.job_id = deterministic_job_id(
            app._SPIDER_PREVIEW_PREFETCH_JOB_KIND,
            self.cache_key,
        )

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _headers(request_id):
        return {
            "X-AI-Crawler-Code": "fixture-unlocked",
            "X-CV-Studio-Request": "1",
            "X-CV-Studio-Request-ID": request_id,
        }

    def _route_patches(self, *, attachment_side_effect=None):
        attachment_patch = {
            "return_value": [],
        }
        if attachment_side_effect is not None:
            attachment_patch = {"side_effect": attachment_side_effect}
        return (
            mock.patch.object(
                app, "_ai_crawler_lock_allowed", return_value=True
            ),
            mock.patch.object(
                app,
                "_ja_refresh_access_token",
                return_value="<fixture-token>",
            ),
            mock.patch.object(
                app,
                "_spider_resume_cache_key",
                return_value=self.cache_key,
            ),
            mock.patch.object(
                app,
                "_spider_candidate_attachment_records",
                **attachment_patch,
            ),
            mock.patch.object(
                app,
                "_spider_preview_payload_cache_get",
                return_value=None,
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
        )

    def _prefetch(self, store, request_id, *, attachment_side_effect=None):
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(app, "_CVSTUDIO_JOBS", store)
            )
            for patcher in self._route_patches(
                attachment_side_effect=attachment_side_effect
            ):
                stack.enter_context(patcher)
            return app.app.test_client().get(
                "/jobadder/spider_candidate_preview"
                "?candidate_id=fixture-candidate&prefetch=1",
                headers=self._headers(request_id),
            )

    def test_prefetch_lifecycle_is_durable_without_private_payload_data(self):
        response = self._prefetch(
            self.store,
            "phase5a-integration-success",
        )
        self.assertEqual(response.status_code, 200)
        record = self.store.get(self.job_id)
        self.assertEqual(record["state"], "succeeded")
        self.assertEqual(record["stage"], "complete")
        self.assertEqual(record["progress_current"], 100)
        self.assertEqual(record["attempts"], 1)
        self.assertEqual(
            record["request_id"],
            hashlib.sha256(
                b"phase5a-integration-success"
            ).hexdigest(),
        )

        raw = self.path.read_text(encoding="utf-8")
        for private_value in (
            "fixture-candidate",
            "<fixture-token>",
            "Fixture",
            "Candidate",
            "Analyst",
            "preview_text",
            "search_text",
            "phase5a-integration-success",
        ):
            self.assertNotIn(private_value, raw)

    def test_interrupted_safe_prefetch_resumes_only_on_explicit_same_request(self):
        self.store.begin(
            self.job_id,
            kind=app._SPIDER_PREVIEW_PREFETCH_JOB_KIND,
            safety="safe_idempotent_read",
            request_id="phase5a-before-restart",
            stage="candidate_profile",
        )
        restarted = PersistentJobStore(self.path)
        recovery = restarted.initialize()
        self.assertEqual(recovery["interrupted"], 1)
        interrupted = restarted.get(self.job_id)
        self.assertEqual(interrupted["state"], "interrupted")
        self.assertEqual(interrupted["attempts"], 1)

        response = self._prefetch(
            restarted,
            "phase5a-explicit-resume",
        )
        self.assertEqual(response.status_code, 200)
        resumed = restarted.get(self.job_id)
        self.assertEqual(resumed["state"], "succeeded")
        self.assertEqual(resumed["attempts"], 2)
        self.assertEqual(resumed["recoveries"], 1)
        self.assertEqual(
            resumed["request_id"],
            hashlib.sha256(b"phase5a-explicit-resume").hexdigest(),
        )

    def test_active_claim_returns_structured_conflict_before_preview_work(self):
        self.store.begin(
            self.job_id,
            kind=app._SPIDER_PREVIEW_PREFETCH_JOB_KIND,
            safety="safe_idempotent_read",
        )
        attachment_call = mock.Mock(return_value=[])
        patches = self._route_patches()
        with (
            mock.patch.object(app, "_CVSTUDIO_JOBS", self.store),
            patches[0],
            patches[1],
            patches[2],
            mock.patch.object(
                app,
                "_spider_candidate_attachment_records",
                attachment_call,
            ),
        ):
            response = app.app.test_client().get(
                "/jobadder/spider_candidate_preview"
                "?candidate_id=fixture-candidate&prefetch=1",
                headers=self._headers("phase5a-active-conflict"),
            )
        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertEqual(payload["code"], "JOB_ALREADY_RUNNING")
        self.assertTrue(payload["retryable"])
        self.assertEqual(payload["request_id"], "phase5a-active-conflict")
        attachment_call.assert_not_called()

    def test_prefetch_begin_write_failure_is_visible_and_prevents_work(self):
        def reject_replace(_source, _destination):
            raise OSError("fixture durable replace denied")

        failed_store = PersistentJobStore(
            self.path,
            replace=reject_replace,
        )
        failed_store.initialize()
        attachment_call = mock.Mock(return_value=[])
        patches = self._route_patches()
        with (
            mock.patch.object(app, "_CVSTUDIO_JOBS", failed_store),
            patches[0],
            patches[1],
            patches[2],
            mock.patch.object(
                app,
                "_spider_candidate_attachment_records",
                attachment_call,
            ),
        ):
            response = app.app.test_client().get(
                "/jobadder/spider_candidate_preview"
                "?candidate_id=fixture-candidate&prefetch=1",
                headers=self._headers("phase5a-write-failure"),
            )
        self.assertEqual(response.status_code, 503)
        payload = response.get_json()
        self.assertEqual(payload["code"], "JOB_STATE_UNAVAILABLE")
        self.assertTrue(payload["retryable"])
        self.assertEqual(payload["request_id"], "phase5a-write-failure")
        attachment_call.assert_not_called()
        self.assertIsNone(failed_store.get(self.job_id))

    def test_progress_write_failure_replaces_partial_success_with_error(self):
        replace_calls = 0

        def fail_after_begin(source, destination):
            nonlocal replace_calls
            replace_calls += 1
            if replace_calls > 1:
                raise OSError("fixture progress replace denied")
            os.replace(source, destination)

        failed_store = PersistentJobStore(
            self.path,
            replace=fail_after_begin,
        )
        failed_store.initialize()
        response = self._prefetch(
            failed_store,
            "phase5a-progress-failure",
        )
        self.assertEqual(response.status_code, 503)
        payload = response.get_json()
        self.assertEqual(payload["code"], "JOB_STATE_UNAVAILABLE")
        self.assertEqual(payload["request_id"], "phase5a-progress-failure")
        record = failed_store.get(self.job_id)
        self.assertEqual(record["state"], "running")
        self.assertEqual(record["stage"], "attachment_metadata")
        self.assertEqual(record["progress_current"], 0)

    def test_cancel_is_durable_and_cancel_write_failure_is_visible(self):
        self.store.begin(
            self.job_id,
            kind=app._SPIDER_PREVIEW_PREFETCH_JOB_KIND,
            safety="safe_idempotent_read",
        )
        with mock.patch.object(app, "_CVSTUDIO_JOBS", self.store):
            response = app.app.test_client().post(
                "/jobadder/spider_preview_cancel_prefetch",
                json={},
                headers=self._headers("phase5a-cancel-success"),
            )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.get_data(), b"")
        self.assertEqual(
            self.store.get(self.job_id)["state"], "cancel_requested"
        )

        second_id = deterministic_job_id(
            app._SPIDER_PREVIEW_PREFETCH_JOB_KIND,
            "second-cancel-fixture",
        )
        self.store.mark_cancelled(self.job_id)
        self.store.begin(
            second_id,
            kind=app._SPIDER_PREVIEW_PREFETCH_JOB_KIND,
            safety="safe_idempotent_read",
        )

        def reject_replace(_source, _destination):
            raise OSError("fixture cancellation replace denied")

        self.store._replace = reject_replace
        with mock.patch.object(app, "_CVSTUDIO_JOBS", self.store):
            response = app.app.test_client().post(
                "/jobadder/spider_preview_cancel_prefetch",
                json={},
                headers=self._headers("phase5a-cancel-failure"),
            )
        self.assertEqual(response.status_code, 503)
        payload = response.get_json()
        self.assertEqual(payload["code"], "JOB_STATE_UNAVAILABLE")
        self.assertEqual(payload["request_id"], "phase5a-cancel-failure")
        self.assertEqual(self.store.get(second_id)["state"], "running")

    def test_cooperative_prefetch_cancellation_finishes_cancelled(self):
        response = self._prefetch(
            self.store,
            "phase5a-cooperative-cancel",
            attachment_side_effect=app._SpiderPreviewCancelled(
                "fixture cancellation"
            ),
        )
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.get_json()["prefetch_cancelled"])
        self.assertEqual(self.store.get(self.job_id)["state"], "cancelled")


def tearDownModule():
    _MODULE_TEMPORARY.cleanup()


if __name__ == "__main__":
    unittest.main()
