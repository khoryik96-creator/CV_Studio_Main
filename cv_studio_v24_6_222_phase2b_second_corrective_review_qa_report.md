> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.222 — Phase 2B Second Corrective Review QA Report

Date: 22 July 2026

Phase 2B source baseline: private owner/source v24.6.219 at
`a43dbb84dcc44c773527f49d0332b2eb15a37cc1`

Previous corrective release under review: v24.6.221

Second corrective private owner/source release: v24.6.222

## Release intent

This owner-only corrective release closes the two remaining actionable review
findings against Phase 2B. It does not change schema version 10, add or rename a
route, begin Phase 3 or implement a backburner item.

## Corrected findings

1. Browser-setting import/upsert routes now pass each allowlisted value through
   the repository's canonical normalizer before reporting success. Oversized or
   suspicious scalar values return the structured request-ID
   `STORAGE_PAYLOAD_INVALID` response instead of being silently omitted while
   the route reports success. JSON settings retain recursive credential-field
   sanitization and canonical persistence.
2. Schema-1 local-data restore now requires confirmed durable success for every
   requested setting, PPC metadata document, transfer-record collection and
   saved-link collection. A false helper result or rejected write promise rejects
   restore, suppressing the success message and automatic reload. The returned
   count is the sum of confirmed writes only.

## Targeted QA

- 16 Python Phase 2A/2B repository and real-Flask integration tests passed.
- Rejected scalar and over-2-MiB setting values returned HTTP 400 with request
  IDs and left the prior authoritative setting unchanged.
- A JSON-valued setting containing a nested credential-like key was accepted in
  canonical sanitized form.
- The Phase 2B frontend fixture proved exact successful restore counts and
  rejection for failed setting, saved-link and PPC durable writes.

## Complete regression and release QA

- `python -m unittest discover -s tests -p test_*.py -v`: 26 tests passed.
- Both Phase 2A and Phase 2B Node frontend fixtures passed.
- `python tests/run_phase2a_source_smoke.py`: 24 live loopback assertions passed.
- Python syntax passed for all 12 tracked Python files.
- JavaScript syntax passed for all 20 tracked JavaScript files and both complete
  inline scripts in `index.html`.
- Git Bash syntax passed for all 5 tracked shell/command entry points.
- PowerShell parser validation passed for all 5 tracked `.ps1` files.
- Owner-source validation, dependency preflight, repository consistency and Git
  whitespace validation passed.

## Data-safety and compatibility result

- A route cannot claim a browser setting is durable when repository validation
  would omit it.
- A failed backup restore remains on the current page with an error; it does not
  falsely claim success or reload over an unpersisted browser mirror.
- Independent selected stores retain their existing per-store transactions. If
  a later store fails after an earlier store succeeds, restore reports failure
  and the external schema-1 backup remains available for a safe idempotent retry.
- Schema version remains 10; no migration or migration backup was required.
- All 107 Flask route URLs and existing response fields remain present.
- Legacy JSON, selected browser mirrors, tombstones and schema-1 compatibility
  remain unchanged.
- No credential migration, shared client, background job, modularisation, lazy
  loading, new workflow or roadmap item 4, 7 or 8 was implemented.

## Private owner/source archive

The authoritative archive is
`cv_studio_v24_6_222_phase2b_second_corrective_owner_source.zip`. It has one
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
