# CV Studio Backburner and Stability Roadmap

Last updated: 23 July 2026
Current implementation base: v24.6.224

## Explicit backburner — do not implement until the owner reactivates them

### 4. Replace Flask's built-in local server

Consider a bundled local WSGI server such as Waitress only after genuine Windows and macOS protected-build testing is available. The current Flask server remains unchanged for now.

### 7. Saved and versioned AI Crawler scoring profiles

Deferred scope includes saved role-family rubrics, Boolean rules, exclusions, nice-to-have terms, experience ranges, weighting choices, sort order, version history, and reproducible reruns.

### 8. AI Crawler candidate decision workflow

Deferred scope includes Shortlist / Maybe / Reject / Reviewed states, recruiter notes, multi-candidate comparison, bulk export, optional JobAdder tagging, and sourcing-session history.

## Completed stability stages

### v24.6.216

- explainable AI Crawler Job Fit scoring;
- adaptive and visible preview-cache controls;
- request identifiers and selected structured errors;
- redacted runtime diagnostics and support bundles.

### v24.6.217 — Phase 1 release safety

- additive structured error normalisation for legacy JSON failures;
- browser request-ID propagation and bounded recent API-error diagnostics;
- pre-launch update health checks on a temporary loopback port;
- previous signed-receipt preservation and transactional Windows/macOS rollback;
- owner-source-only integration-test panel and downloadable reports.

### v24.6.218 — Phase 2A SQLite foundation

- per-user SQLite database with WAL, foreign keys, busy timeout and integrity checks;
- transactional schema migrations with verified timestamped backups and durable history;
- SQLite-first usage history, lead caches, salary-component cache, PPC metadata and non-sensitive diagnostic state;
- idempotent legacy import plus one-release JSON/localStorage backward readability;
- structured request-ID recovery for corruption and migration failure.

### v24.6.219 — Phase 2A corrective review closure

- stale legacy usage and PPC mirrors no longer overwrite authoritative SQLite rows;
- usage clear reports durable failures and restores its compatibility mirror;
- transient SQLite contention is retryable and is not reported as corruption;
- credential-like fields are removed recursively before usage persistence;
- schema version 7 and all Phase 2A compatibility boundaries remain unchanged.

### v24.6.220 — Phase 2B browser-backed durable records and settings

- schema versions 8–10 add OneNote transfer records, saved OneNote links and an
  exact allowlist of non-secret browser settings;
- insert-only legacy import, SQLite authority, tombstones and serialized
  frontend writes prevent stale browser mirrors from resurrecting deleted data;
- schema-1 local-data backup remains backward readable and adds optional record
  collections without credential export;
- every Phase 2A migration, backup, recovery and compatibility contract remains;
- shared clients, background jobs, modularisation, lazy loading, new workflows
  and backburner items 4, 7 and 8 remain untouched.

### v24.6.221 — Phase 2B corrective review closure

- invalid or oversized OneNote record arrays are rejected before replacement,
  preserving the existing authoritative rows;
- hydrated AI-routing controls and preview-memory behavior now reflect the
  SQLite-authoritative settings;
- schema version 10 and every existing scope boundary remain unchanged.

### v24.6.222 — Phase 2B second corrective review closure

- browser-setting routes reject values that repository normalization cannot
  persist while retaining recursive sanitization for JSON settings;
- local-data restore reports failure and avoids reload when any requested
  durable write fails, and counts only confirmed writes;
- schema version 10, all routes, mirrors and scope boundaries remain unchanged.

### v24.6.223 — Phase 3 shared external-service clients

- shared JobAdder, Microsoft Graph and AI-provider client foundations sit
  behind the existing route/helper contracts;
- safe retry, bounded pagination, one-time Microsoft token refresh, timeout,
  redaction and structured upstream errors are centralized;
- chargeable AI calls, JobAdder writes/uploads and Graph draft writes are not
  replayed after ambiguous transient failures; device-code operations are not
  replayed;
- schema version 10, all 107 routes, credential stores and paid-call gates
  remain unchanged.

### v24.6.224 — Phase 3 corrective review closure

- redirects are constrained on every hop and sensitive headers are removed
  across allowed origin changes;
- rejected redirects close their upstream response deterministically;
- response-header lookups remain case-insensitive and JobAdder diagnostic
  network failures preserve their established fields;
- the corrected source has a distinct verified owner/source release identity;
- Phase 4, schema version 10, all 107 routes and the backburner remain unchanged.

## Active stability direction

No later phase is active. If the owner explicitly starts further work, continue
the remaining improvements conservatively and in staged releases:

- gradual behavior-preserving backend modularisation;
- persistent background task management, central AI cost guardrails and
  provider-billing reconciliation;
- later frontend modularisation, lazy loading and remaining explainable-fit/
  memory refinements without a rewrite.

## Safety rule

Prefer small additive changes with regression tests. Do not perform a broad rewrite or combine unrelated high-risk migrations in one release.
