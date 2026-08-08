> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.220 — Phase 2B Browser Storage QA Report

Date: 21 July 2026

Source baseline: private owner/source v24.6.219 at
`a43dbb84dcc44c773527f49d0332b2eb15a37cc1`

Completed private owner/source release: v24.6.220

## Release intent

This release completes Phase 2B only. It migrates the selected durable
browser-backed records and non-secret settings to the existing local SQLite
foundation while preserving the selected browser keys as transition mirrors.
It does not start Phase 3 or implement a backburner item.

## Implemented scope

- schema version 8: OneNote transfer record history;
- schema version 9: saved OneNote desktop links;
- schema version 10: the exact allowlist of non-secret browser settings used by
  local-data backup/restore;
- insert-only legacy import and SQLite-authoritative reads;
- serialized live replacement/upsert/delete/clear operations;
- tombstones that prevent stale mirrors from resurrecting deleted records or
  settings;
- bounded record counts, payload sizes and nesting;
- recursive credential-field filtering in both browser and backend paths;
- additive schema-1 export/import record collections while preserving the
  legacy `settings` object for v24.6.219 readability.

The settings allowlist now includes the known Anthropic, DeepSeek and OpenAI
per-provider model selections and the existing named AI-route selections. It
does not admit arbitrary provider prefixes, API keys, OAuth tokens, passwords,
device sessions or other protected credentials.

## Migration and data-safety result

- A schema-7 fixture upgraded through migrations 8, 9 and 10 with one unique,
  independently integrity-verified pre-change backup for each migration.
- A second initialization created no duplicate migration/history row or backup.
- A deterministic interruption during migration 9 rolled back its schema and
  history atomically; restart completed migrations 9–10 after fault removal.
- Phase 2A schema objects, migration checksums and fixture data remained intact.
- Record/link replacement and setting deletion leave tombstones, so changed
  stale browser imports cannot restore intentionally deleted values.
- Legacy browser keys and Phase 2A JSON files remain present and readable.
- No API key, OAuth token or credential-like nested field is written to the new
  SQLite stores or emitted by the local-data export.
- No user data was deleted or irreversibly reinterpreted.

## Targeted QA

- 9 repository/schema tests passed across the selected Phase 2B stores, schema-7
  upgrade, idempotency, verified backups and interrupted migration recovery.
- 11 combined real-Flask integration tests passed across the Phase 2A and Phase
  2B routes, including bounded payloads, allowlist rejection, request IDs,
  credential filtering, tombstones and corrupt-database recovery.
- Both Phase 2A and Phase 2B frontend fixtures passed hydration, mutation race,
  stale mirror, clear/delete rollback and export/import persistence cases.

## Complete regression and release QA

- `python -m unittest discover -s tests -p test_*.py`: 26 tests passed.
- `node tests/test_phase2a_frontend_storage.js`: passed.
- `node tests/test_phase2b_frontend_storage.js`: passed.
- `python tests/run_phase2a_source_smoke.py`: 24 live loopback assertions
  passed, including durable rows for all three Phase 2B stores.
- Python syntax passed for 12 tracked files.
- JavaScript syntax passed for 20 tracked files and both complete inline HTML
  scripts.
- Git Bash syntax passed for all 5 tracked `.sh`/`.command` entry points.
- PowerShell parser validation passed for all 5 tracked `.ps1` files.
- Owner-source validation, pinned dependency preflight, repository consistency
  and Git whitespace validation passed.

## Final review against master

- All 96 baseline Flask route URLs remain. Exactly 11 additive Phase 2B storage
  routes bring the current total to 107; no existing route was renamed.
- Active product, installer, launcher and owner protected-build source surfaces
  agree on v24.6.220 and contain no stale v24.6.219 production identifier.
- The Phase 2B application diff contains no shared JobAdder/Microsoft/provider
  client, background job, backend/frontend modularisation, lazy loading, new
  workflow, Flask-server replacement, scoring-profile or candidate-decision
  implementation.
- Roadmap items 4, 7 and 8 remain backburnered.

## Private owner/source archive

The authoritative archive is
`cv_studio_v24_6_220_phase2b_browser_storage_owner_source.zip`. It has one
`cv_formatter/` root and is generated from the final clean Git commit. A fresh
extraction is compared byte-for-byte with every tracked source file. The final
SHA-256, source commit, archive size and exact extraction counts are recorded in
the adjacent `.sha256` and `.verification.json` sidecars, because a ZIP cannot
reliably contain its own authoritative digest.

## Not genuinely tested

- native Nuitka protected builds or protected-binary smoke launches;
- physical Windows or macOS installer/restore execution;
- live JobAdder, Microsoft/Outlook/OneNote or paid AI calls.

No protected colleague package was created or claimed.

## Stop boundary

Phases 1, 2A and 2B are complete. Phase 3 is not active and must not begin
without a new explicit owner instruction.
