> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.221 — Phase 2B Corrective Review QA Report

Date: 21 July 2026

Phase 2B source baseline: private owner/source v24.6.219 at
`a43dbb84dcc44c773527f49d0332b2eb15a37cc1`

Phase 2B release under review: v24.6.220

Corrective private owner/source release: v24.6.221

## Release intent

This owner-only corrective release closes the three actionable code-review
findings against Phase 2B. It does not change schema version 10, add a route,
begin Phase 3 or implement a backburner item.

## Corrected findings

1. OneNote transfer and saved-link arrays are fully normalized before import or
   replacement. Invalid or oversized records return the existing structured
   `STORAGE_PAYLOAD_INVALID` response before a tombstoning transaction begins.
   Both repositories also reject invalid arrays defensively for internal callers.
2. Browser-setting hydration rebuilds the AI-routing rows from the
   SQLite-authoritative mirror. Controls rendered from a stale startup mirror
   can no longer be saved back over current SQLite route selections.
3. Browser-setting hydration reapplies the selected AI Crawler preview-memory
   profile. Auto mode schedules a single diagnostics load when system-memory
   data is not yet available.

## Targeted QA

- 16 Python repository and real-Flask integration tests passed in the focused
  correction run.
- Oversized transfer and saved-link replacements returned HTTP 400 with request
  IDs and left the previously authoritative rows unchanged.
- Direct repository replacement raised before opening a destructive replacement
  transaction and preserved the prior rows.
- The Phase 2B frontend fixture proved that hydrated route controls are rebuilt,
  the hydrated memory profile is applied and Auto diagnostics scheduling is
  requested only for Auto mode.

## Complete regression and release QA

- `python -m unittest discover -s tests -p test_*.py -v`: 26 tests passed.
- Both Phase 2A and Phase 2B Node frontend fixtures passed.
- `python tests/run_phase2a_source_smoke.py`: 24 live loopback assertions passed.
- Python syntax passed for every tracked Python file.
- JavaScript syntax passed for every tracked JavaScript file and both complete
  inline scripts in `index.html`.
- Git Bash syntax passed for all tracked shell/command entry points.
- PowerShell parser validation passed for all tracked `.ps1` files.
- Owner-source validation, dependency preflight, repository consistency and Git
  whitespace validation passed.

## Data-safety and compatibility result

- Invalid input is rejected atomically rather than partially persisted.
- Existing OneNote rows remain intact after rejected replacement attempts.
- SQLite remains authoritative over stale browser mirrors.
- Schema version remains 10; no migration or migration backup was required.
- All 107 existing Flask route URLs and response fields remain present.
- Legacy JSON, selected browser mirrors, tombstones and schema-1 export/import
  compatibility remain unchanged.
- No credential migration, shared client, background job, modularisation, lazy
  loading, new workflow or roadmap item 4, 7 or 8 was implemented.

## Private owner/source archive

The authoritative archive is
`cv_studio_v24_6_221_phase2b_corrective_owner_source.zip`. It has one
`cv_formatter/` root and is generated from the final clean Git commit. A fresh
extraction is compared byte-for-byte with every tracked source file. Its final
SHA-256, source commit, byte size and extraction counts are recorded in the
adjacent `.sha256` and `.verification.json` sidecars under the private release
directory.

## Not genuinely tested

- Native protected Windows/macOS compilation or protected-binary smoke launch;
- physical Windows or macOS installer/restore execution;
- live JobAdder, Microsoft/Outlook/OneNote or paid AI calls.

No protected colleague package was created or claimed.

## Stop boundary

Phases 1, 2A and 2B are complete. Phase 3 remains inactive and must not begin
without a new explicit owner instruction.
