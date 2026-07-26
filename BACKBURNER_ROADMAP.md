# CV Studio Backburner and Stability Roadmap

Last updated: 26 July 2026
Current implementation base: v24.6.237

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

### v24.6.230 — Phase 3 content-negotiation corrective closure

- JobAdder JSON requests retain `Accept: application/json`;
- raw candidate-CV and attachment downloads no longer force JSON negotiation;
- caller-supplied Accept headers, download behavior and legacy diagnostic error
  fields remain intact;
- v24.6.225-v24.6.229 release identities remain immutable;
- Phase 4, schema version 10, all 107 routes and the backburner remain unchanged.

### v24.6.231 — Phase 4 gradual backend modularisation

- the 19 existing durable-storage routes delegate to an explicit, app-independent
  storage bridge while retaining route decorators, endpoint names, response
  fields and schema version 10;
- runtime diagnostics, redaction and in-memory support-bundle construction use
  an app-independent service with explicit callbacks/providers;
- shared document validation, PDF/image limits, rendering and serialized OCR
  primitives use an app-independent module behind compatibility names;
- all 107 routes, global security/request-size guards, Phase 1/2 storage
  guarantees and Phase 3 shared-client behavior remain unchanged;
- Phase 5/6 work and backburner items 4, 7 and 8 remain untouched.

### v24.6.232 — Phase 4 compatibility corrective closure

- storage and diagnostics services again resolve their established app-level
  compatibility dependencies at call time;
- document safety again resolves app limits, nested helpers and the shared OCR
  semaphore at call time, with the semaphore restored to its original startup
  position;
- seven Phase 4 characterization tests pass against both master and the
  corrected source;
- all 107 routes, schema version 10, prior storage/client guarantees, Phase 5/6
  scope and backburner items 4, 7 and 8 remain unchanged.

### v24.6.233 — Phase 5A persistent background jobs

- a bounded app-independent JSON lifecycle journal tracks only opaque metadata
  for the existing safe AI Crawler preview-prefetch boundary;
- startup marks interrupted safe work retryable for an explicit identical
  request, closes cancellation and never executes or silently replays work;
- paid and externally mutating ambiguity is classified `needs_attention` and
  remains non-replaying;
- journal corruption and write failures are visible without taking unrelated
  routes down;
- all 107 routes, schema version 10, security/compatibility boundaries,
  protected stores, Phase 1–4 guarantees and backburner items 4, 7 and 8 remain.

### v24.6.234 — Phase 5A corrective review closure

- strict schema-1 journal loading rejects unknown, duplicate, noncanonical,
  non-finite and out-of-bound metadata while preserving corrupt bytes;
- request correlations are always one-way digested and bounded summaries cover
  quoted/generic credentials, authorization values, cookies, private paths and
  candidate identifiers;
- lifecycle transitions and pruning retain interrupted/review evidence, and
  paid or externally mutating interrupted identities cannot be reclaimed;
- actual bytes read are independently size-bounded across file-replacement
  races, and every write/clock/encoding failure remains typed and visible;
- schema version 10, all 107 routes, five guards, 18 compatibility signatures
  and every Phase 1–4/Phase 5A scope boundary remain unchanged.

### v24.6.235 — Phase 5B AI cost guardrails and reconciliation

- centralizes provider usage, local estimate and billing-authority provenance;
- adds an opt-in request ceiling before paid inference transport;
- keeps unavailable provider billing nullable and failure-visible;
- preserves Phase 5A recovery, provider zero-retry behavior and every
  established paid confirmation gate.

### v24.6.236 — Phase 5B corrective review

- distinguishes absent/partial usage from explicit zero counters;
- preserves exact authoritative decimal text and distinct delayed/partial
  reconciliation states;
- rejects malformed, mismatched, over-precise and duplicate/excess billing
  authority without discarding successful paid output;
- separates Apollo/search-provider failures from AI paid-call ambiguity and
  strengthens credential-like metadata redaction;
- retains all Phase 5B scope exclusions and every Phase 1–5A contract.

### v24.6.237 — JobAdder esc2 corrective

- the candidate-not-found dialog and formatted-CV upload queue use the
  established global HTML escaper outside the two legitimate local `esc2`
  scopes;
- matched/unmatched queue filenames, status text and dialog email remain
  HTML-escaped;
- source-scope coverage prevents new out-of-scope `esc2` calls from being
  concealed by a global alias;
- JobAdder routes, request behavior, candidate creation, uploads and response
  contracts remain unchanged;
- all Phase 1–5B and backburner boundaries remain unchanged.

## Active stability direction

No later phase is active. If the owner explicitly starts Phase 6, continue
frontend modularisation, lazy loading and remaining explainable-fit/memory
refinements conservatively and without a rewrite.

## Safety rule

Prefer small additive changes with regression tests. Do not perform a broad rewrite or combine unrelated high-risk migrations in one release.
