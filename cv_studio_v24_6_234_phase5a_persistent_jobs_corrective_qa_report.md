# CV Studio v24.6.234 — Phase 5A Corrective QA Report

Date: 26 July 2026

Release type: private owner/source only

Phase 5A source baseline: CV Studio v24.6.232 at
`4b366ddde1cf0a398706b52d55b0e82ed2dbc27c`

Reviewed release: CV Studio v24.6.233 at
`c12158bbf42f78550d5f6295ed365964ec76cd9a`

Implementation branch: `codex/phase-5a-persistent-jobs`

Corrective checkpoints:

- `d5358db26a52e51a72a9c2d2354f1e0791ffa35c` — strict metadata,
  lifecycle and pruning boundaries;
- `32598bd296d424b3459fec340325953fb4ae7b3c` — canonical JSON and
  failure-visible encoding;
- `273fd946c878b604eafd6850fd1a523233bb0226` — actual-read size bound;
- `9a3e64d` — expanded credential redaction and unsafe interrupted
  no-replay enforcement.

## Authorization and scope

The owner requested a complete review of Phase 5A against exact master, repair
of every concrete finding and repetition of the same review until clean.
Corrections remain limited to persistent background jobs and resumable task
state. No Phase 5B cost guardrail/provider reconciliation, credential
migration, frontend modularisation/lazy loading, Phase 6 work, Flask server
replacement, unrelated workflow or backburner item 4, 7 or 8 is included.

The v24.6.233 release artifacts remain immutable. v24.6.234 is the next unused
private owner/source corrective identity. No protected colleague package was
created.

## Findings corrected

Repeated source, state-machine and adversarial journal reviews confirmed ten
issues:

1. Quoted or escaped secret and candidate-ID values could evade bounded
   error-summary redaction.
2. A caller request ID already shaped as 64 lowercase hexadecimal characters
   could be persisted without an additional one-way digest.
3. Schema-1 loading normalized unknown fields, invalid types/ranges,
   non-finite timestamps, raw request IDs and unsanitized summaries instead of
   preserving the file as corrupt.
4. Completion/failure helpers accepted invalid lifecycle transitions.
5. Capacity pruning could discard `interrupted` and `needs_attention`
   evidence.
6. Duplicate JSON object keys could hide unsupported top-level or record data.
7. An escaped lone Unicode surrogate could escape the typed atomic-write
   boundary.
8. The loader trusted a pre-read `stat` size without bounding the actual byte
   buffer after a concurrent replacement.
9. Quoted authorization values and generic token/cookie/credential fields
   remained outside the error-summary sanitizer.
10. A syntactically valid legacy or altered paid/external-mutation
    `interrupted` identity could be reclaimed despite an ambiguous outcome.

## Corrections and recovery semantics

- Every non-empty inbound request ID is SHA-256 digested before persistence.
- Schema-1 loading requires exact top-level and record field sets, canonical
  names/IDs, strict bounded integer and finite timestamp values, opaque request
  digests, booleans and already-sanitized summaries.
- Duplicate keys, unsupported fields, noncanonical Unicode, oversized actual
  reads and all other invalid journals fail visibly as `JOB_STATE_CORRUPT`.
  Original bytes are never rewritten.
- Serialization and UTF-8 encoding remain inside the typed, failure-visible
  atomic-write boundary; non-finite clocks fail as `JOB_STATE_UNAVAILABLE`.
- Finish transitions are explicit and idempotent only for an already matching
  terminal state. Incompatible transitions return `JOB_STATE_CONFLICT`.
- Pruning removes only old `succeeded`, `failed` or `cancelled` entries.
  Active, interrupted and review-required evidence is protected.
- Quoted/generic OAuth tokens, authorization values, cookies, credentials,
  secrets, candidate identifiers, emails and private paths are redacted from
  bounded persisted summaries.
- Both `interrupted` and `needs_attention` identities in a paid or externally
  mutating safety class are independently blocked from being claimed.
- Startup still executes no work. Safe/idempotent interrupted work resumes only
  at the explicit identical request boundary. Ambiguous unsafe work is never
  replayed.

The journal remains metadata schema 1 and primary SQLite remains schema version
10. No data-authority, migration, compatibility, paid-call or recovery contract
was broadened.

## Regression coverage

The foundation suite now contains 14 tests. Added cases cover:

- quoted/generic credential redaction;
- mandatory request-ID digests;
- strict schema/type/range/canonical validation;
- duplicate keys and invalid Unicode;
- non-finite clock failures;
- actual-read bounds after stale `stat`;
- invalid finish transitions;
- protected evidence under capacity pressure;
- paid/unsafe interrupted identity rejection.

The complete focused gate contains 38 tests:

- 14 persistent-job foundation tests;
- 8 selected-route integration tests;
- 3 fresh-process startup/recovery tests;
- 6 Phase 5A characterization tests;
- 7 Phase 4 compatibility tests.

All tests use temporary state and controlled fakes. No live credentials,
credentialed external calls, external mutations or paid calls are used.

## Final validation

The corrective source is required to pass:

- all 38 focused Phase 5A/Phase 4 tests;
- all 86 complete Python-discovery tests with `ResourceWarning` treated as an
  error;
- both frontend fixtures;
- all 24 live loopback source-smoke assertions;
- tracked Python, JavaScript/inline-script, Bash/command and PowerShell static
  validation;
- owner-source preflight, repository consistency and Git whitespace checks.

The final recorded counts and archive verification are authoritative in
`PHASE_STATUS.md` and the adjacent release verification sidecar.

## Clean repeated review

After the last correction, a new review from exact master passed:

- all 107 ordered Flask route URL/method/endpoint tuples are exact;
- all five ordered global request/security guard bodies are exact;
- all 18 compatibility signatures and Phase 4 initialization markers pass;
- after release-string normalization, the only changed existing app functions
  are the authorized preview-prefetch and cancellation endpoints;
- the only new app functions are the structured job-error adapter and
  persistent cancellation adapter;
- schema version 10 and the 80 MiB request boundary are unchanged;
- Phase 1–4 storage, external-client, storage-bridge, diagnostics and
  document-safety modules remain exact master bytes;
- external URLs, headers, retry/content-negotiation behavior, protected stores,
  paid-call gates and unsafe-write non-replay behavior remain unchanged.

No further concrete finding remained in the clean review pass.

## Private archive

The authoritative archive is
`cv_studio_v24_6_234_phase5a_persistent_jobs_corrective_owner_source.zip`
under `C:\CV-Studio-Codex\releases\v24.6.234`.

It must be generated from the exact final clean branch commit with one
`cv_formatter/` root, freshly extracted and compared against every tracked Git
blob with zero missing, extra or byte-mismatched files. Its adjacent SHA-256
and verification sidecars are authoritative for digest, byte size,
`source_commit` and extraction counts.

Phase 5A is complete. Stop before handoff or merge. Phase 5B and Phase 6 remain
inactive without a new explicit owner instruction.
