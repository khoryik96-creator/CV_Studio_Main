> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.231 — Phase 5 Handover

Date: 23 July 2026

Handover source: completed private owner/source Phase 4 release

Phase 5 status: inactive; explicit owner authorization is required

## Completed baseline

CV Studio v24.6.231 completes Phase 4 gradual backend modularisation. Phases 1,
2A, 2B, 3 and 4 are complete.

Phase 4 added three bounded app-independent modules:

- `cvstudio_storage_bridge.py` — orchestration for the 19 existing
  `/storage/*` handlers using explicit request/response/repository providers;
- `cvstudio_diagnostics.py` — redacted diagnostics and in-memory support-bundle
  construction using explicit callbacks and path/state providers;
- `cvstudio_document_safety.py` — bounded ZIP/image/PDF validation, rendering
  and serialized OCR primitives.

`app.py` still owns all route decorators and endpoint names, security/request
guards, startup and integration initialization, protected-store access and
compatibility adapters. No extracted module imports `app`.

## Immutable entry contracts

Any authorized Phase 5 work must preserve:

- all 107 Flask route URLs, methods, endpoint names and established response
  fields;
- every authentication, CSRF, request-size and paid-call confirmation boundary;
- request-ID propagation, normalized errors and redaction;
- SQLite schema version 10 and all Phase 1/2 migration, verified-backup,
  rollback/restart, corruption-recovery, tombstone and compatibility-mirror
  guarantees;
- existing protected credential stores and the rule that secrets never enter
  plain SQLite, logs, fixtures, diagnostics, support bundles or release
  evidence;
- all Phase 3 client behavior, including redirects, case-insensitive response
  headers, content negotiation, bounded retries/pagination/timeouts, Microsoft
  token refresh and no replay of unsafe ambiguous writes;
- the Phase 4 explicit dependency boundaries, route registration,
  initialization order and runtime/test rebinding behavior;
- existing startup, update, receipt, backup, restore and rollback behavior;
- external-service URLs, headers and retry rules.

## Phase 5 activation gate

Do not start Phase 5 from this handover alone. The owner must explicitly
authorize it and identify the precise Phase 5 milestone to implement.

The roadmap lists two distinct future areas:

1. persistent background jobs and resumable task state;
2. central AI cost guardrails and provider billing reconciliation.

These areas have materially different persistence, recovery, compatibility and
paid-call consequences. They must not be silently combined. Before code
changes, inventory affected routes, in-memory task state, locks, filesystem and
SQLite state, startup/shutdown behavior, retry/idempotency rules, billing
fields, paid confirmation gates and recovery semantics. Add characterization
coverage before moving or persisting behavior.

## Required entry verification

1. Start from the latest clean master branch and verify the owner-specified
   commit.
2. Verify all active source surfaces identify v24.6.231.
3. Verify the v24.6.231 release directory contains the owner/source ZIP,
   checksum, verification sidecar, Phase 4 QA report and this handover.
4. Independently recompute the ZIP SHA-256 and confirm that the verification
   sidecar `source_commit` exactly matches the approved master commit.
5. Freshly extract the archive and byte-compare every file with the approved
   Git blobs; require zero missing, extra or mismatched files.
6. Read `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md`, `IMPLEMENT.md`, this
   handover, the Phase 4 QA report, all Phase 3 QA reports, the Phase 2B QA
   reports, the historical Phase 2A QA reports and `BACKBURNER_ROADMAP.md`
   completely.
7. Restore only the documented ignored vetted owner-source dependencies.
8. Re-run the complete Phase 1/2/3/4 regression, both frontend fixtures, live
   source smoke, tracked-language static validation, owner-source preflight,
   repository consistency and whitespace validation before implementation.

## Scope exclusions

Unless separately and explicitly activated, do not implement:

- credential or protected-secret migration;
- frontend modularisation or lazy loading;
- unrelated user-facing workflows;
- Flask server replacement;
- saved/versioned AI Crawler scoring profiles;
- AI Crawler Shortlist / Maybe / Reject / Reviewed workflow;
- Phase 6 work.

Do not use live credentials or make paid external calls. Do not claim genuine
Windows/macOS native testing unless it was actually performed. Do not create a
protected colleague ZIP without matching native compilation and smoke testing.

## Release discipline

For an authorized Phase 5 milestone:

1. make the smallest additive change;
2. run targeted tests and fix every failure;
3. record decisions, limitations and recovery semantics in `PHASE_STATUS.md`;
4. create stable Git checkpoints;
5. run the complete regression and static-validation suites;
6. review against the exact approved master baseline and correct all concrete
   findings;
7. create only the authorized release artifacts from the final clean commit;
8. freshly extract and byte-verify the owner/source archive;
9. confirm the sidecar `source_commit` exactly matches final branch HEAD;
10. stop before merge and before Phase 6.

Phase 5 is not active. This document is a handover, not authorization.
