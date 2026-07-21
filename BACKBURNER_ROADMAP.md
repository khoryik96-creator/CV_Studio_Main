# CV Studio Backburner and Stability Roadmap

Last updated: 21 July 2026
Current implementation base: v24.6.220

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

## Active stability direction

No later phase is active. If the owner explicitly starts further work, continue
the remaining improvements conservatively and in staged releases:

- shared JobAdder, Microsoft and provider clients;
- persistent background task management;
- modular backend/frontend extraction without a rewrite;
- AI cost guardrails and provider-billing reconciliation;
- frontend lazy loading and remaining explainable-fit/memory refinements.

## Safety rule

Prefer small additive changes with regression tests. Do not perform a broad rewrite or combine unrelated high-risk migrations in one release.
