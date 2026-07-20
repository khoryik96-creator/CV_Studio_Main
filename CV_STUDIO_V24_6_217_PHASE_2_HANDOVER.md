# CV Studio v24.6.217 → Phase 2 Handover

**Current private patch base:** v24.6.217  
**Owner ZIP SHA-256:** `c499ea8043f274bf47a4981c84794759f38fc7c761b98ba3939626114a898a59`  
**Phase completed:** Phase 1 — release safety, additive JSON error contract, transactional rollback and owner integration-test foundation

## Preserve these rules

Do not implement until explicitly reactivated:

- **4:** Replace Flask's local server.
- **7:** Saved/versioned AI Crawler scoring profiles.
- **8:** Candidate Shortlist/Maybe/Reject workflow.

Do not combine the next storage migration with shared API-client refactoring, background jobs, modularisation or new user-facing workflow features.

## Phase 1 foundations now available

- all requests have request IDs;
- legacy JSON failures gain the additive structured contract;
- browser API failures are captured in bounded redacted diagnostics;
- Windows/macOS installers health-test a new extracted folder before changing the stable launcher;
- previous signed receipts and launcher targets can be restored transactionally;
- owner source builds have a hidden downloadable integration-test report panel.

Rollback state:

- Windows: `%LOCALAPPDATA%\TheGuoLab\CVStudio\update_state.json`
- macOS: `~/.guo_lab_cv_studio/update_state.json`

## Next phase recommendation: Phase 2A only

Implement the SQLite foundation and migrate lower-risk backend durable data first:

1. add a local SQLite database with WAL, foreign keys, busy timeout and integrity checks;
2. add a schema-version/migration table;
3. create an automatic timestamped backup before every migration;
4. add repositories for usage history and non-sensitive caches;
5. migrate usage history, lead-title cache, lead-contact cache, salary-component cache, PPC metadata and diagnostic state one store at a time;
6. read SQLite first, fall back to legacy JSON, import safely and preserve one-release backward readability;
7. leave credentials in the current protected storage mechanism;
8. leave browser notes/settings migration for Phase 2B;
9. run migration twice to prove idempotency;
10. test failed/corrupt migrations against the v24.6.217 rollback flow.

## Phase 2A acceptance criteria

- no user-data loss from a v24.6.217 fixture;
- migration is transactional and idempotent;
- a backup is created before schema changes;
- database corruption produces a structured request-ID error and recovery guidance;
- old JSON is not deleted during the transition release;
- existing features continue to read/write correctly;
- items 4, 7 and 8 remain untouched;
- a new private ZIP, SHA-256, QA report and next-phase handover are produced.

## Native-test caveat

v24.6.217 passed live Linux source tests, controlled Windows/macOS package assembly, PowerShell syntax parsing and macOS rollback fixtures. Genuine Windows and physical macOS installation/restore tests remain required before distributing a colleague package.
