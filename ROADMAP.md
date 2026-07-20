# CV Studio Stability Roadmap

## Baseline

- v24.6.217 is the approved starting point.
- Phase 1 is complete.

## Phase 1 — Completed

- additive structured error contract;
- request IDs;
- transactional update health checks;
- rollback foundation;
- owner-only integration-test foundation.

## Phase 2A — Active

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

## Phase 2B — Future

- durable browser-backed records such as notes and saved links;
- selected persistent settings;
- explicit migration/export compatibility;
- temporary UI state remains in localStorage where appropriate.

## Phase 3 — Future

Shared external-service clients:

- JobAdderClient;
- MicrosoftGraphClient;
- AIProviderClient;
- central retry, pagination, refresh, timeout, redaction and error handling.

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
