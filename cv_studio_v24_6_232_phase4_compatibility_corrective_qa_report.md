> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.232 — Phase 4 Compatibility Corrective QA Report

Date: 26 July 2026

Release type: private owner/source only

Phase 4 source baseline: CV Studio v24.6.230 at
`7a0efcf0bce10b07e034592fb22a6021141d4146`

Original Phase 4 release: CV Studio v24.6.231 at
`0d2b02ec924a7531d96f236396a0620674fcb994`

Authorized corrective implementation checkpoint:
`83e029c0c48126d43586991a8088e405ddff94bb`

## Release identity

The owner authorized a corrective Phase 4 release after the second full review
confirmed three compatibility regressions. The immutable v24.6.231 release
directory and artifacts were independently rechecked before corrective release
work:

- owner/source ZIP SHA-256:
  `8b77d18a07fb2164ec3cfb516fb5bcb03bb03f332004068950de422b86cec361`;
- verification `source_commit`:
  `0d2b02ec924a7531d96f236396a0620674fcb994`.

Those artifacts were not overwritten, modified or reinterpreted. v24.6.232 was
the next available release identity.

## Corrected findings

### 1. Durable-storage compatibility dependencies were captured

`StorageBridge` received several function objects and setting rules once during
app initialization. The v24.6.230 route bodies instead resolved their
established app-level compatibility globals on each call.

Differential testing proved the behavior change: rebinding
`_phase2a_usage_records` to reject a payload produced HTTP 400 on master but
HTTP 200 in v24.6.231. Similar capture affected structured error and response
adapters, current request IDs, browser-setting allowlists/normalization and
other storage validators.

The bridge now receives forwarding callbacks. Validators, structured errors,
request IDs, setting rules and repository providers resolve at request time.
App compatibility helper signatures and their original storage-constant
initialization position remain.

### 2. Diagnostics dependencies were captured or bypassed

`DiagnosticsService` captured the request-ID function, Flask response
functions and version at construction. Support-bundle browser sanitization also
called the extracted implementation directly instead of the established app
compatibility helper.

Differential testing proved empty/stale request IDs and a frozen v24.6.231
bundle filename after app-level rebinding, while master returned the rebound
request ID and version.

Diagnostics now resolves request/response, runtime/cache, redaction,
sanitization, version, archive clock, root and runtime-log dependencies through
explicit forwarding callbacks on each call.

### 3. Document safety bypassed app compatibility state

Direct function aliases caused document validation and OCR helpers to resolve
limits, the semaphore and nested PDF helpers inside
`cvstudio_document_safety.py`. Master resolved the established app-level names
at call time. The shared OCR semaphore was also constructed during early module
import rather than at its original app initialization position.

Differential testing proved that a rebound ZIP entry limit was ignored and a
rebound PDF page-count/render pair was bypassed in v24.6.231.

Thin app adapters now pass the current limits, semaphore, nested helpers and
monotonic clock explicitly. The shared semaphore is again constructed at its
original app-level startup position. The extracted document module has no
application import or persistent state.

## Characterization evidence

Three focused tests were added for call-time compatibility rebinding:

- storage validators, request IDs, errors, setting allowlists and canonical
  normalization;
- diagnostics request IDs, version, browser sanitizer and `send_file`;
- document limits, nested PDF helpers and the shared OCR semaphore.

The complete seven-test Phase 4 characterization module passes unchanged
against both:

- exact master baseline
  `7a0efcf0bce10b07e034592fb22a6021141d4146`;
- corrected v24.6.232 source.

This separately proves the new tests describe established master behavior
rather than a newly invented contract.

## Complete regression and static validation

- Complete Python discovery: 55 tests passed with `ResourceWarning` treated as
  an error.
- Phase 2A frontend fixture: passed.
- Phase 2B frontend fixture: passed.
- Both complete inline `index.html` scripts compile in Node.
- Live source smoke: all 24 assertions passed on an ephemeral loopback port
  with temporary receipt, database and log state.
- Python compilation: all 19 tracked files passed.
- JavaScript syntax: all 20 tracked files plus both inline scripts passed.
- Bash/command syntax: all five tracked files passed through Git Bash.
- PowerShell parsing: all five tracked files passed with zero parser errors.
- Owner-source validation/preflight: passed.
- Repository consistency: passed.
- Git whitespace validation: passed.

## Repeated final review

The final review was repeated against exact master after the corrective changes
and version/document updates.

- The release review found one additional app definition-order drift:
  `_phase2b_record_array` appeared before the Phase 2A route declarations
  instead of immediately after them as on master. The side-effect-free wrapper
  was moved to its exact master-relative position and the complete gates were
  repeated.
- The exact ordered 107 Flask route URL/method/endpoint tuples match master.
- All five global `before_request` guards remain in their original order.
- Error-handler registration is unchanged.
- All 18 established app compatibility helper signatures match master.
- The global request limit remains 80 MiB.
- SQLite remains at schema version 10.
- The app-level storage constants and OCR semaphore occupy their established
  initialization positions.
- `cvstudio_storage_bridge.py`, `cvstudio_diagnostics.py` and
  `cvstudio_document_safety.py` do not import `app`.
- No circular import or new module startup I/O was introduced.
- No concrete response-contract, authentication, CSRF, request-size,
  request-ID, redaction, persistence, startup, update, receipt, backup,
  restore, rollback, external-client or paid-call regression remains.

## Scope result

- All 107 routes, methods, endpoint names and established response fields
  remain.
- Schema version 10 and every Phase 1/2 storage, migration, backup, recovery,
  tombstone and compatibility-mirror guarantee remain.
- All Phase 3 retry, pagination, token-refresh, timeout, redirect,
  case-insensitive-header, content-negotiation, redaction and unsafe-write
  non-replay behavior remains.
- No credential/protected-secret migration, persistent background job,
  resumable task state, central AI cost guardrail, provider billing
  reconciliation, frontend modularisation, lazy loading, unrelated workflow,
  Flask server replacement, scoring profile, candidate decision workflow or
  Phase 5/6 implementation was added.

No live credentialed external request or paid call was made. No protected
colleague ZIP was created. Genuine native Windows/macOS compilation, protected
binary smoke and physical installer/rollback testing are not claimed.

## Private owner/source archive

The authoritative archive is
`cv_studio_v24_6_232_phase4_compatibility_corrective_owner_source.zip` under
`C:\CV-Studio-Codex\releases\v24.6.232`.

It is generated from the exact final clean corrective commit with one
`cv_formatter/` root. A fresh extraction is compared against every tracked Git
blob using `git hash-object --no-filters`. The adjacent `.sha256` and
`.verification.json` sidecars are authoritative for the archive digest, byte
size, final `source_commit` and extraction counts.

Phase 4 is complete. Stop before merge and do not begin Phase 5 without a new
explicit owner instruction.
