# CV Studio Backburner and Stability Roadmap

Last updated: 20 July 2026  
Current implementation base: v24.6.217

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

## Active stability direction

Continue the remaining improvements conservatively and in staged releases:

- SQLite/local-storage migration with schema upgrades and backups;
- shared JobAdder, Microsoft and provider clients;
- persistent background task management;
- modular backend/frontend extraction without a rewrite;
- AI cost guardrails and provider-billing reconciliation;
- frontend lazy loading and remaining explainable-fit/memory refinements.

## Safety rule

Prefer small additive changes with regression tests. Do not perform a broad rewrite or combine unrelated high-risk migrations in one release.
