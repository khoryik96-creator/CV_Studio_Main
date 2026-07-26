import json
from pathlib import Path
import tempfile
import unittest

from cvstudio_jobs import (
    PersistentJobConflictError,
    PersistentJobNeedsAttentionError,
    PersistentJobStateCorruptError,
    PersistentJobStateUnavailableError,
    PersistentJobStore,
    deterministic_job_id,
    sanitize_job_text,
)


class _Clock:
    def __init__(self, value=1000.0):
        self.value = float(value)

    def __call__(self):
        self.value += 1.0
        return self.value


class Phase5APersistentJobFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="cvstudio-phase5a-jobs-"
        )
        self.path = Path(self.temporary.name) / "state" / "jobs.json"
        self.clock = _Clock()

    def tearDown(self):
        self.temporary.cleanup()

    def _store(self, **kwargs):
        return PersistentJobStore(
            self.path,
            clock=self.clock,
            **kwargs,
        )

    def test_lifecycle_is_atomic_bounded_and_contains_only_opaque_metadata(self):
        store = self._store(max_jobs=3)
        self.assertEqual(
            store.initialize(),
            {
                "interrupted": 0,
                "cancelled": 0,
                "needs_attention": 0,
                "recovery_limited": 0,
            },
        )
        self.assertFalse(self.path.exists())

        private_identity = "fixture-candidate-123"
        job_id = deterministic_job_id(
            "ai_crawler_preview_prefetch", private_identity
        )
        started = store.begin(
            job_id,
            kind="ai_crawler_preview_prefetch",
            safety="safe_idempotent_read",
            request_id="phase5a-foundation",
            stage="attachment_metadata",
        )
        self.assertEqual(started["state"], "running")
        self.assertEqual(started["attempts"], 1)
        with self.assertRaises(PersistentJobConflictError):
            store.begin(
                job_id,
                kind="ai_crawler_preview_prefetch",
                safety="safe_idempotent_read",
            )

        progressed = store.progress(
            job_id, stage="candidate_profile", current=40
        )
        self.assertEqual(
            (
                progressed["state"],
                progressed["stage"],
                progressed["progress_current"],
                progressed["progress_total"],
            ),
            ("running", "candidate_profile", 40, 100),
        )
        completed = store.complete(job_id)
        self.assertEqual(completed["state"], "succeeded")
        self.assertEqual(completed["progress_current"], 100)

        raw = self.path.read_text(encoding="utf-8")
        self.assertNotIn(private_identity, raw)
        self.assertNotIn("candidate_id", raw)
        payload = json.loads(raw)
        self.assertEqual(payload["schema"], 1)
        self.assertEqual(len(payload["jobs"]), 1)
        self.assertEqual(payload["jobs"][0]["id"], job_id)

        for index in range(3):
            another = deterministic_job_id("local_fixture", str(index))
            store.begin(
                another,
                kind="local_fixture",
                safety="local_idempotent",
            )
            store.complete(another)
        self.assertEqual(store.summary()["jobs"], 3)
        self.assertIsNone(store.get(job_id))

    def test_restart_recovery_is_idempotent_and_never_replays_unsafe_work(self):
        safe_id = deterministic_job_id("safe_fixture", "one")
        unsafe_id = deterministic_job_id("unsafe_fixture", "two")
        cancel_id = deterministic_job_id("cancel_fixture", "three")

        first = self._store()
        first.initialize()
        first.begin(
            safe_id,
            kind="safe_fixture",
            safety="safe_idempotent_read",
        )
        first.begin(
            unsafe_id,
            kind="unsafe_fixture",
            safety="external_mutation",
        )
        first.begin(
            cancel_id,
            kind="cancel_fixture",
            safety="safe_idempotent_read",
        )
        first.request_cancel(cancel_id)

        restarted = self._store()
        recovery = restarted.initialize()
        self.assertEqual(
            recovery,
            {
                "interrupted": 1,
                "cancelled": 1,
                "needs_attention": 1,
                "recovery_limited": 0,
            },
        )
        self.assertEqual(restarted.get(safe_id)["state"], "interrupted")
        self.assertTrue(restarted.get(safe_id)["retryable"])
        self.assertEqual(
            restarted.get(safe_id)["recovery_action"],
            "retry_same_request",
        )
        self.assertEqual(
            restarted.get(unsafe_id)["state"], "needs_attention"
        )
        self.assertFalse(restarted.get(unsafe_id)["retryable"])
        self.assertEqual(restarted.get(cancel_id)["state"], "cancelled")
        self.assertEqual(restarted.initialize(), recovery)

        restarted.begin(
            safe_id,
            kind="safe_fixture",
            safety="safe_idempotent_read",
            stage="resumed",
        )
        self.assertEqual(restarted.get(safe_id)["attempts"], 2)
        with self.assertRaises(PersistentJobNeedsAttentionError):
            restarted.begin(
                unsafe_id,
                kind="unsafe_fixture",
                safety="external_mutation",
            )

    def test_repeated_safe_interruptions_have_a_bounded_recovery_limit(self):
        job_id = deterministic_job_id("safe_fixture", "bounded")
        current = self._store(max_recoveries=2)
        current.initialize()
        current.begin(
            job_id,
            kind="safe_fixture",
            safety="safe_idempotent_read",
        )

        for expected_recoveries in (1, 2):
            current = self._store(max_recoveries=2)
            current.initialize()
            record = current.get(job_id)
            self.assertEqual(record["state"], "interrupted")
            self.assertEqual(record["recoveries"], expected_recoveries)
            current.begin(
                job_id,
                kind="safe_fixture",
                safety="safe_idempotent_read",
            )

        limited = self._store(max_recoveries=2)
        recovery = limited.initialize()
        self.assertEqual(recovery["recovery_limited"], 1)
        record = limited.get(job_id)
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["error_code"], "JOB_RECOVERY_LIMIT_REACHED")
        self.assertEqual(record["recovery_action"], "retry_manually")

    def test_write_failures_are_visible_and_do_not_change_committed_memory(self):
        def rejected_replace(_source, _destination):
            raise OSError("fixture atomic replace denied")

        store = self._store(replace=rejected_replace)
        store.initialize()
        job_id = deterministic_job_id("safe_fixture", "write-failure")
        with self.assertRaises(PersistentJobStateUnavailableError):
            store.begin(
                job_id,
                kind="safe_fixture",
                safety="safe_idempotent_read",
            )
        self.assertIsNone(store.get(job_id))
        self.assertFalse(self.path.exists())
        temp_files = list(self.path.parent.glob(self.path.name + ".*.tmp"))
        self.assertEqual(temp_files, [])

    def test_corruption_is_failure_visible_and_never_overwritten(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        original = b"{not valid persistent job JSON"
        self.path.write_bytes(original)
        store = self._store()
        with self.assertRaises(PersistentJobStateCorruptError) as raised:
            store.initialize()
        self.assertEqual(raised.exception.code, "JOB_STATE_CORRUPT")
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(self.path.read_bytes(), original)

    def test_cancel_kind_updates_all_matching_active_records_once(self):
        store = self._store()
        store.initialize()
        ids = [
            deterministic_job_id("preview", "one"),
            deterministic_job_id("preview", "two"),
        ]
        for job_id in ids:
            store.begin(
                job_id,
                kind="preview",
                safety="safe_idempotent_read",
            )
        other = deterministic_job_id("other", "three")
        store.begin(
            other,
            kind="other",
            safety="safe_idempotent_read",
        )
        self.assertEqual(store.request_cancel_kind("preview"), 2)
        self.assertEqual(
            [store.get(job_id)["state"] for job_id in ids],
            ["cancel_requested", "cancel_requested"],
        )
        self.assertEqual(store.request_cancel_kind("preview"), 0)
        self.assertEqual(store.get(other)["state"], "running")

    def test_error_sanitization_removes_private_and_credential_values(self):
        raw = (
            "candidate_id=12345 email fixture@example.test "
            "access_token=fixture-secret C:\\Private\\candidate.docx "
            "/home/private/candidate.pdf"
        )
        sanitized = sanitize_job_text(raw)
        self.assertNotIn("12345", sanitized)
        self.assertNotIn("fixture@example.test", sanitized)
        self.assertNotIn("fixture-secret", sanitized)
        self.assertNotIn("C:\\Private", sanitized)
        self.assertNotIn("/home/private", sanitized)
        self.assertIn("[redacted]", sanitized)


if __name__ == "__main__":
    unittest.main()
