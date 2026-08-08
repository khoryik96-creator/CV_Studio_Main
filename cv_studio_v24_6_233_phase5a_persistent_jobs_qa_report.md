> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.233 — Phase 5A Persistent Jobs QA Report

Date: 26 July 2026

Release type: private owner/source only

Phase 5A source baseline: CV Studio v24.6.232 at
`4b366ddde1cf0a398706b52d55b0e82ed2dbc27c`

Implementation branch: `codex/phase-5a-persistent-jobs`

Stable implementation checkpoints:

- `4a1ad74079f13b729e220ef7753f37047460f298` — Phase 5A activation;
- `06aaa4ff9343fd5960d565d4d9ef196960e4650f` — inventory and
  characterization;
- `200115aca55d964b850a893a9eb42739fc788ef3` — bounded job-state
  foundation;
- `b71d1962c73a56d56b3ad85a8b4138345b4f9d02` — existing preview-prefetch
  integration;
- `4ef93f3d33e01e12e5903cd88ada1db8e507129c` — startup/recovery
  verification.

## Authorized scope and release identity

The owner explicitly authorized Phase 5A only: persistent background jobs and
resumable task state. Phase 5B AI cost guardrails/provider billing
reconciliation, credential migration, frontend modularisation/lazy loading,
Phase 6, Flask server replacement and backburner items 4, 7 and 8 remained out
of scope.

The next unused private owner/source identity was v24.6.233. No protected
colleague package was created.

## Entry verification

- The worktree was clean at entry.
- Both local `master` and `HEAD` resolved exactly to
  `4b366ddde1cf0a398706b52d55b0e82ed2dbc27c`.
- All installed source surfaces identified v24.6.232.
- The v24.6.232 release directory contained the owner/source ZIP, checksum,
  verification sidecar, corrective QA report and Phase 5 handover.
- The v24.6.232 owner/source ZIP independently recomputed to
  `99255d90a6dd6fa6ce73e1a6baa77e93413595e2b64fc4113003a458f2883c0d`.
- Its verification `source_commit` exactly matched the approved master commit.
- A fresh extraction contained 108 tracked files and matched approved Git with
  zero missing, extra or byte-mismatched files.
- Unchanged-source entry QA passed 55 Python tests, 29 focused Phase 3/4 tests,
  both frontend fixtures, 24 live source-smoke assertions, tracked-language
  static validation, owner-source preflight, repository consistency and Git
  whitespace validation.

## Inventory and selected boundary

Thirty-three existing background/long-running Flask routes were inventoried
with their methods, endpoint names, success/failure fields, retry boundaries,
locks, process-local stores, filesystem/SQLite interactions and startup/
shutdown behavior.

The only selected integration is the existing browser-background request:

`GET /jobadder/spider_candidate_preview?prefetch=1`

It is a safe, idempotent JobAdder read plus bounded local rendering/extraction,
already cooperatively cancellable and already requested explicitly by the
browser queue. Paid AI calls, Outlook/OneNote/JobAdder mutations, OAuth/device
sessions, uploaded-file batches, synchronous thread pools and process control
remain untracked and non-replaying.

## Persistent-job foundation

`cvstudio_jobs.py` is app-independent and owns a separate atomic JSON metadata
journal. It does not import `app`, open SQLite, access protected credential
stores, start threads/processes, register shutdown hooks or perform network
work.

The journal:

- uses metadata schema 1 while primary SQLite remains schema version 10;
- defaults to `cv_studio_jobs.json` in the private per-user state directory;
- is capped at 500 records and 2 MiB;
- writes through a same-directory temporary file, flush/fsync and atomic
  replace;
- changes in-memory state only after the durable replace succeeds;
- stores opaque SHA-256 job IDs and request-ID digests, bounded lifecycle/
  progress fields, timestamps, attempts, recoveries and sanitized error
  metadata;
- excludes candidate identifiers, emails, credentials, profile/document
  content, filenames, results and private paths.

Lifecycle states are `queued`, `running`, `succeeded`, `failed`,
`cancel_requested`, `cancelled`, `interrupted` and `needs_attention`.

## Integration and recovery semantics

- A prefetch claim durably enters `running`, records coarse bounded stages and
  closes as `succeeded`, `failed` or `cancelled`.
- A concurrent matching claim fails before preview work with structured
  `JOB_ALREADY_RUNNING`.
- Existing normal 200 responses, cooperative-cancellation
  `PREVIEW_PREFETCH_SUPERSEDED` 409 fields and empty cancellation 204 body
  remain exact.
- Begin, progress, completion, failure and cancellation write errors return the
  established structured request-ID error shape. The route never reports
  lifecycle success after a failed write.
- Startup reconciliation performs no work. Safe active state becomes retryable
  `interrupted`; cancellation becomes `cancelled`; paid or externally mutating
  ambiguity becomes non-retryable `needs_attention`.
- Safe resumption occurs only when the browser explicitly issues the identical
  request. It restarts at the established idempotent request boundary.
- Reconciliation is idempotent and safe interruption recovery is capped at
  three process lifetimes before visible `JOB_RECOVERY_LIMIT_REACHED`.
- Corrupt/unsupported/oversized journals are preserved and fail visibly while
  unrelated routes remain available.
- No paid or externally mutating operation is integrated or automatically
  replayed.

## Characterization and integration coverage

- Six pre-change characterization tests fix the 33-route inventory, 107-route
  count, five ordered global guards, 80 MiB request limit, schema 10, all 18
  compatibility signatures/initialization markers, preview response fields,
  cancellation and existing process/browser-local state.
- Seven foundation tests cover atomic lifecycle, bounded pruning, opaque
  metadata, duplicate claims, safe/unsafe/cancel restart classification,
  bounded recovery, failed-write rollback, corruption preservation, bulk
  cancellation and redaction.
- Eight integration tests cover durable success, explicit resume, structured
  duplicate rejection, begin/progress/cancel write failure, corruption
  recovery and cooperative cancellation.
- Three fresh-process startup tests prove one-time reconciliation, idempotent
  second startup, corruption isolation and absence of worker/network/shutdown
  hooks.
- The seven Phase 4 characterization tests continue to prove call-time
  dependency rebinding and compatibility behavior.

## Complete regression and static validation

- Focused Phase 5A/Phase 4 gate: 31 tests passed.
- Complete Python discovery: 79 tests passed with `ResourceWarning` treated as
  an error.
- Phase 2A frontend fixture: passed.
- Phase 2B frontend fixture: passed.
- Live source smoke: all 24 assertions passed on an ephemeral loopback port
  with temporary receipt/database/log state.
- Python compilation: all 24 tracked Python files passed.
- JavaScript syntax: all 20 tracked files plus both complete inline
  `index.html` scripts passed.
- Bash/command syntax: all five tracked files passed through Git Bash.
- PowerShell parsing: all five tracked files passed with zero parser errors.
- Owner-source validation/preflight: passed.
- Repository consistency: passed.
- Git whitespace validation: passed.

The first warnings-as-errors smoke pass exposed one existing harness cleanup
finding: the expected HTTP 404 response was read but not closed. The harness now
closes that response deterministically, and the complete smoke and regression
gates pass without the warning.

## Repeated baseline review

The implementation and release changes were repeatedly reviewed against exact
master baseline `4b366ddde1cf0a398706b52d55b0e82ed2dbc27c`.

- The ordered 107 Flask route URL/method/endpoint tuples remain exact.
- The only changed existing route functions are preview-prefetch and its
  cancellation endpoint; the only new app functions are the job error adapter
  and persistent cancellation adapter.
- All five global `before_request` guards retain their exact order and code.
- All 18 compatibility helper signatures remain exact.
- Request size remains 80 MiB and SQLite remains schema version 10.
- Existing storage/client/diagnostics/document modules and external-client
  URLs, headers, retry/refresh/pagination/content-negotiation behavior remain
  byte-identical to the baseline apart from release version surfaces.
- Phase 4 app-level call-time dependency rebinding and relative initialization
  markers remain covered and passing.
- No credential authority, schema/data authority, paid-call confirmation,
  update/receipt/backup/restore/rollback or unsafe-write non-replay contract
  changed.

No live credentialed external request or paid call was made. Genuine native
Windows/macOS compilation, protected binary smoke and physical installer/
rollback testing are not claimed.

## Private owner/source archive

The authoritative archive is
`cv_studio_v24_6_233_phase5a_persistent_jobs_owner_source.zip` under
`C:\CV-Studio-Codex\releases\v24.6.233`.

It is generated from the exact final clean branch commit with one
`cv_formatter/` root. A fresh extraction is compared against every tracked Git
blob with zero missing, extra or mismatched files. The adjacent `.sha256` and
`.verification.json` sidecars are authoritative for the final archive digest,
byte size, `source_commit` and extraction counts.

Phase 5A is complete. Stop before handoff or merge and do not begin Phase 5B or
Phase 6 without a new explicit owner instruction.
