> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.230 — Phase 3 Content-Negotiation Corrective QA Report

Date: 23 July 2026

Phase 3 source baseline: private owner/source v24.6.222 at
`1be9da48d8307c418d82807cbdaedc9f876a1b15`

Previous completed private owner/source release: v24.6.224 at
`0892dcc1fbec2fb68b4668014792230249c73cae`

Corrective private owner/source release: v24.6.230

## Release identity

The immutable release directories v24.6.225 through v24.6.229 already exist.
They were not overwritten or reinterpreted. v24.6.230 is therefore the next
available repository-compliant corrective release identity. The v24.6.224
archive and sidecars remain unchanged.

## Release intent

This owner-only corrective release fixes the confirmed JobAdder
content-negotiation regression introduced by the Phase 3 shared-client
extraction. It does not change schema version 10, add or rename a route,
change an authentication boundary or retry rule, migrate credentials, begin
Phase 4 or implement roadmap item 4, 7 or 8.

## Corrected behavior

1. `JobAdderClient.request_raw` no longer adds
   `Accept: application/json` to every request.
2. Candidate-CV and attachment downloads remain representation-neutral unless
   their caller explicitly requests a representation.
3. `JobAdderClient.request_json` supplies `Accept: application/json` when the
   caller did not supply an Accept header.
4. Caller-supplied Accept headers are honored case-insensitively by both raw
   and JSON request paths.
5. The one rejected-token refresh/retry retains the selected request headers.
6. Exact download bytes, content type, content disposition and established
   JobAdder diagnostic success/error fields remain unchanged.

## Regression coverage

- JSON JobAdder requests assert the JSON Accept default on the original call
  and the one rejected-token retry.
- Raw JobAdder requests assert that no implicit Accept header is present.
- A raw `Accept: application/pdf` fixture proves the caller header is retained
  while exact binary bytes are returned.
- A lower-case caller `accept` header proves case-insensitive override behavior
  for the JSON path.
- Candidate-CV/attachment characterization preserves exact bytes and response
  metadata without a live JobAdder call.
- Diagnostic GET retry and POST non-replay fixtures preserve caller Accept
  headers and every legacy network-error field.

## Complete regression and release QA

- Focused shared-client and external-service characterization:
  22 no-network tests passed with `ResourceWarning` treated as an error.
- Cache integration subset: 7 tests passed.
- Complete Python discovery: 48 tests passed with `ResourceWarning` treated as
  an error.
- Both Phase 2A and Phase 2B Node frontend fixtures passed.
- Live source smoke: all 24 loopback assertions passed with temporary local
  state.
- Python syntax passed for all 15 tracked Python files.
- JavaScript syntax passed for all 20 tracked JavaScript files and both complete
  inline scripts in `index.html`.
- Git Bash syntax passed for all 5 tracked shell/command entry points.
- PowerShell parser validation passed for all 5 tracked `.ps1` files.
- Owner-source validation and dependency preflight passed, including exact
  vetted/local `adm-zip` 0.5.17 behavior.
- Repository consistency and Git whitespace validation passed.

## Compatibility and scope result

- All 107 Flask route URLs and their established success/failure fields remain.
- `cvstudio_storage.py` remains at schema version 10; no migration, repository,
  credential store, legacy mirror, tombstone or schema-1 backup contract
  changed.
- JobAdder authentication and reconnect behavior, safe-read retry, bounded
  pagination and unsafe-write non-replay remain unchanged.
- Microsoft Graph and AI-provider behavior is unchanged.
- No live JobAdder, Microsoft Graph, Outlook, OneNote or paid AI call was made.
- No persistent background job, backend/frontend modularisation, lazy loading,
  new workflow, Flask-server replacement, scoring profile or candidate
  decision workflow was added.

## Private owner/source archive

The authoritative archive is
`cv_studio_v24_6_230_phase3_content_negotiation_corrective_owner_source.zip`.
It has one `cv_formatter/` root and is generated from the exact final clean Git
commit. A fresh extraction is compared against all 100 tracked files with zero
missing files, zero extra files and zero byte mismatches. Its authoritative
SHA-256, byte size, source commit and extraction result are recorded in the
adjacent `.sha256` and `.verification.json` sidecars under
`C:\CV-Studio-Codex\releases\v24.6.230\`.

## Not genuinely tested

- Native protected Windows/macOS compilation or protected-binary smoke launch;
- physical Windows or macOS installer/restore execution;
- live JobAdder, Microsoft/Outlook/OneNote or paid AI calls.

No protected colleague package was created or claimed.

## Stop boundary

Phases 1, 2A, 2B and 3 are complete. Phase 4 remains inactive and must not
begin without a new explicit owner instruction.
