# CV Studio Stability Roadmap

## Release state

- v24.6.217 was the approved Phase 2A starting point.
- v24.6.218 completed the Phase 2A implementation.
- v24.6.219 is the completed private owner/source Phase 2A corrective release.
- v24.6.220 completed Phase 2B browser-backed durable records and settings.
- v24.6.221 corrected all three Phase 2B post-release review findings.
- v24.6.222 corrected the two remaining Phase 2B durability-review findings.
- v24.6.223 completed the shared external-service client foundations in Phase 3.
- Phases 1, 2A, 2B and 3 are complete.
- No later phase is active. Phase 4 requires a new explicit owner instruction.

## Phase 1 — Completed

- additive structured error contract;
- request IDs;
- transactional update health checks;
- rollback foundation;
- owner-only integration-test foundation.

## Phase 2A — Completed in v24.6.218

SQLite foundation and lower-risk backend durable-data migration:

1. database location and connection lifecycle;
2. WAL, foreign keys, busy timeout and integrity checks;
3. schema version and migration history;
4. automatic timestamped migration backup;
5. repository interfaces;
6. usage history migration;
7. lead-title cache migration;
8. lead-contact cache migration;
9. salary-component cache migration;
10. PPC metadata migration;
11. diagnostic-state migration;
12. legacy JSON fallback/import;
13. idempotency, corruption and rollback tests;
14. QA, private package and Phase 2B handover.

### v24.6.219 corrective review closure

- preserve SQLite authority when legacy usage or PPC mirrors are stale;
- make usage-history clear failure-visible and recover its local mirror;
- distinguish transient SQLite contention from corruption;
- recursively remove credential-like usage fields before persistence;
- retain schema version 7, all legacy files and the Phase 2A stop boundary.

## Phase 2B — Completed in v24.6.220

- durable OneNote transfer records and saved desktop links;
- the existing non-secret local-data-backup setting allowlist, corrected to
  include its per-provider model selections;
- explicit SQLite-first import, mirror, delete/tombstone and export
  compatibility;
- temporary UI/session state, credential state and regenerable caches remain in
  their existing browser storage where appropriate;
- schema versions 8–10, each with a verified pre-change backup and transactional
  restart-safe migration;
- completed owner/source release, QA evidence and Phase 3 handover.

### v24.6.221 corrective review closure

- reject invalid or oversized OneNote record arrays atomically before any
  tombstoning replacement;
- rebuild AI-routing controls from SQLite-authoritative hydrated settings;
- reapply and schedule Auto diagnostics for the hydrated preview-memory mode;
- retain schema version 10, all Phase 2A/2B compatibility contracts and the
  Phase 3 stop boundary.

### v24.6.222 second corrective review closure

- validate allowlisted browser-setting values through the repository's
  canonical size, secret and JSON-sanitization contract before route success;
- reject schema-1 local-data restore when any requested setting, PPC metadata,
  transfer-record or saved-link durable write fails;
- return only counts from confirmed writes and avoid a false success reload;
- retain schema version 10, all Phase 2A/2B compatibility contracts and the
  Phase 3 stop boundary.

## Phase 3 — Completed in v24.6.223

Shared external-service clients:

- JobAdderClient;
- MicrosoftGraphClient;
- AIProviderClient;
- central retry, pagination, refresh, timeout, redaction and error handling.

The three clients remain behind the existing app helpers and all 107 route
URLs. Safe/idempotent reads have bounded retry, Graph continuation traversal is
capped, a rejected Microsoft token gets one refresh/retry, and chargeable or
other unsafe writes are not replayed after ambiguous transient failures. Credential stores, schema
version 10, paid-call gates and existing response fields remain unchanged.

## Phase 4 — Future

Gradual backend modularisation without changing behaviour or routes.

## Phase 5 — Future

Persistent background jobs and central AI cost guardrails.

## Phase 6 — Future

Frontend modularisation, lazy loading, remaining adaptive-memory work and final explainable-fit refinements.

## Phase 7 — Backburner

Do not implement until explicitly reactivated:

- item 4: replace Flask's local server;
- item 7: saved/versioned AI Crawler scoring profiles;
- item 8: candidate decision workflow.
