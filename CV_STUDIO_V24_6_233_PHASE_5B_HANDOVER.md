> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.233 — Phase 5B Handover

Date: 26 July 2026

Handover source: completed private owner/source Phase 5A release

Phase 5B status: inactive; explicit owner authorization is required

## Completed baseline

CV Studio v24.6.233 is the completed Phase 5A persistent-jobs release. Phases
1, 2A, 2B, 3, 4 and 5A are complete.

Phase 5A adds one bounded app-independent lifecycle module:

- `cvstudio_jobs.py` — atomic metadata state for existing authorized background
  work, with no app import, worker, network activity, protected-store access or
  SQLite migration.

Only the existing safe AI Crawler preview-prefetch request is integrated. The
browser still calls the same synchronous GET and receives the same normal
success/cancellation responses. No new route, polling API, frontend workflow or
result store exists.

## Immutable Phase 5A contracts

Any later work must preserve:

- journal metadata schema 1 and its 500-record/2 MiB bounds unless the owner
  explicitly authorizes an exact compatibility change;
- primary SQLite schema version 10 and existing Phase 1/2 data authority;
- opaque job identities and request-ID digests, with no credentials, candidate
  identifiers, emails, private paths, profile/document content or results in
  the journal;
- explicit `queued`, `running`, `succeeded`, `failed`, `cancel_requested`,
  `cancelled`, `interrupted` and `needs_attention` states;
- atomic failure-visible writes and in-memory commit only after durable replace;
- startup reconciliation without execution or hidden worker creation;
- explicit-identical-request restart only for proven safe/idempotent work;
- bounded interruption recovery and visible manual recovery after the limit;
- non-retryable owner review for ambiguous paid or externally mutating work;
- no automatic replay of paid or unsafe operations.

## Other immutable entry contracts

Any authorized Phase 5B work must also preserve:

- all 107 Flask route URLs, methods, endpoint names and established response
  fields;
- all five ordered global request/security guards, authentication, CSRF,
  request-size and paid-call confirmation boundaries;
- all 18 app compatibility helper signatures, Phase 4 call-time dependency
  rebinding and established initialization order;
- request-ID propagation, structured error normalization and redaction;
- every Phase 1/2 migration, verified-backup, corruption/recovery, tombstone
  and compatibility-mirror guarantee;
- protected credential stores and the rule that secrets never enter plain
  SQLite, logs, fixtures, diagnostics, support bundles or release evidence;
- Phase 3 redirect, header, content-negotiation, retry, pagination, timeout,
  Microsoft token-refresh and unsafe-write non-replay policies;
- Phase 4 app-independent module and explicit-dependency boundaries;
- startup, update, receipt, backup, restore and rollback behavior;
- external-service URLs, headers and retry rules;
- the v24.6.215 DeepSeek detailed-cost history cutoff.

## Required entry verification

1. Start from the latest clean master branch and verify the owner-specified
   commit.
2. Verify every active source surface identifies v24.6.233.
3. Verify `C:\CV-Studio-Codex\releases\v24.6.233` contains the owner/source ZIP,
   checksum, verification sidecar, Phase 5A QA report and this handover.
4. Independently recompute the ZIP SHA-256 and confirm the verification
   `source_commit` exactly matches approved master.
5. Freshly extract and compare every file with approved Git; require zero
   missing, extra or byte-mismatched files.
6. Read `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md`, `IMPLEMENT.md`, this
   handover, the Phase 5A QA report, v24.6.232 Phase 5 handover and corrective
   QA, v24.6.231 Phase 4 QA, all Phase 3 QA, Phase 2B QA, historical Phase 2A QA
   and `BACKBURNER_ROADMAP.md` completely.
7. Restore only documented ignored vetted owner-source dependencies.
8. Re-run all 79 Python tests, the 31-test focused Phase 5A/Phase 4 gate, both
   frontend fixtures, 24-assertion live smoke, tracked-language static
   validation, owner-source preflight, repository consistency and whitespace
   validation.
9. Re-prove the exact route/security/signature/schema/initialization invariants
   and all Phase 5A recovery/non-replay contracts before production changes.

## Phase 5B activation gate

Do not start Phase 5B from this handover alone. The owner must explicitly
authorize the exact AI cost-guardrail/provider-billing-reconciliation milestone.

Before code changes, inventory:

- every paid provider route/helper and confirmation gate;
- existing normalized usage/model/provider/cost fields;
- DeepSeek cutoff behavior and history calculations;
- client-side cost estimates versus provider-authoritative billing data;
- retry, timeout and ambiguous paid-call boundaries;
- protected credentials and any proposed non-secret authority;
- failure, reconciliation and recovery response semantics.

Add characterization before implementation. If Phase 5B would change SQLite
schema 10, data authority, Phase 5A journal semantics, a paid confirmation gate,
provider retry/non-replay behavior, response compatibility or recovery
semantics, stop and present the exact change for separate owner authorization.

## Scope exclusions

Unless separately and explicitly activated, do not implement:

- additional persistent-job families or automatic background workers;
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

For a separately authorized Phase 5B milestone:

1. make the smallest additive change;
2. run targeted tests and fix every failure;
3. record decisions, limitations and recovery semantics;
4. create stable Git checkpoints;
5. run the complete regression and static-validation suites;
6. review against the exact approved master baseline and correct every concrete
   finding;
7. create only authorized release artifacts from the exact final clean commit;
8. freshly extract and byte-verify the owner/source archive;
9. confirm sidecar `source_commit` equals final branch HEAD;
10. stop before merge and before Phase 6.

Phase 5B is not active. This document is a handover, not authorization.
