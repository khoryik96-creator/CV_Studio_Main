> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.219 — Phase 2A Corrective Review QA Report

Date: 21 July 2026

Source baseline: v24.6.217 at `c8eeb34c275d374170a5931d69ed95ea213c791a`

Phase 2A release under review: v24.6.218

Corrective private owner/source release: v24.6.219

## Release intent

This owner-only patch closes the five actionable review findings against the
completed Phase 2A SQLite migration. It does not change schema version 7, begin
Phase 2B, delete a legacy store or add a user-facing workflow.

## Corrected findings

1. Usage-history legacy import is insert-only on record-ID conflict. Live
   upsert remains the only path that may update an existing authoritative row.
   Browser hydration prefers SQLite, with a narrow exception for the exact
   records mutated on the current page while hydration was in flight.
2. PPC legacy import/upsert replaces an existing row only when the incoming
   non-empty `updatedAt` is at least as new. Missing timestamps no longer gain a
   synthetic current time that could overwrite authoritative data.
3. Usage-history clear waits for hydration, reports durable-clear failure,
   restores the local compatibility mirror on failure, and re-upserts records
   genuinely created after a successful clear began.
4. SQLite busy/locked conditions return retryable `STORAGE_BUSY` with a retry
   action. Only recognized corrupt/not-a-database conditions return
   `STORAGE_CORRUPT`; other operational failures return storage-unavailable
   recovery guidance.
5. Usage payload filtering recursively drops credential-like keys, including
   camel-case and hyphenated variants, before SQLite or backup persistence.
   Safe accounting fields such as `input_tokens` and `output_tokens` remain.

## Targeted QA

- 16 Python tests passed across the repository, foundation and Flask-integration
  suites used while implementing the corrections.
- The Node frontend fixture passed stale usage, per-record hydration race, stale
  PPC, successful clear and failed-clear restoration cases.
- A real second SQLite writer proved that contention returns `STORAGE_BUSY` and
  that initialization succeeds once the lock is released.
- Nested, camel-case and hyphenated credential-key fixtures were excluded while
  safe usage audit fields survived.

## Complete regression and release QA

- `python -m unittest discover -s tests -p test_*.py -v`: 17 tests passed.
- `node tests/test_phase2a_frontend_storage.js`: passed; both inline scripts
  also compiled.
- `python tests/run_phase2a_source_smoke.py`: 18 loopback assertions passed
  using temporary receipt, database and log state.
- The full v24.6.217 fixture migrated twice without duplicates or destructive
  effects; a restart created no extra migration or backup.
- Interrupted migration rolled back without a partial upgrade and completed on
  restart after fault removal.
- A corrupt database returned the structured request-ID recovery contract.
- Every legacy JSON fixture remained byte-identical and readable.
- Python syntax passed for 10 tracked modules/test modules.
- JavaScript syntax passed for 19 tracked files/inline blocks.
- Bash syntax passed for all 5 `.sh`/`.command` entry points through Git Bash.
- PowerShell parser validation passed for all 5 tracked `.ps1` files.
- Owner-source validation, dependency preflight and repository consistency
  passed.
- All 88 baseline Flask route URLs remain; only the existing 8 Phase 2A storage
  routes are additional.
- Eight primary version surfaces agree on v24.6.219.
- The corrective diff contains no Phase 2B, credential migration, shared-client,
  background-job, modularisation, lazy-loading or roadmap 4/7/8 implementation.

## Data-safety result

- SQLite is authoritative over stale compatibility mirrors.
- Migration/import remains transactional, restart-safe and idempotent.
- Schema version remains 7; no schema-changing migration was needed.
- Legacy JSON/localStorage formats remain intact for transition readability.
- Credentials remain outside plain SQLite, and credential-like usage payload
  fields are filtered before durable writes and migration backups.
- No user data was deleted or irreversibly reinterpreted.

## Private owner/source archive

The authoritative archive is
`cv_studio_v24_6_219_phase2a_corrective_owner_source.zip`. It has one
`cv_formatter/` root and is generated from the final clean Git commit. A fresh
extraction is compared byte-for-byte with every tracked source file. The final
SHA-256, source commit, archive size and extraction counts are recorded in the
adjacent `.sha256` and `.verification.json` sidecars, because a ZIP cannot
reliably contain its own authoritative digest.

## Not genuinely tested

- Native Nuitka protected builds or protected-binary smoke launches;
- physical Windows or macOS installer/restore execution;
- live JobAdder, Microsoft/Outlook/OneNote or paid AI calls.

No protected colleague package was created or claimed.

## Stop boundary

Phase 2A and this corrective patch are complete. Do not start Phase 2B or a
later phase without a new explicit owner instruction.
