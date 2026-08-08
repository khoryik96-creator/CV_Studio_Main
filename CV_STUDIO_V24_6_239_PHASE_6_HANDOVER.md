> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.239 — Phase 6 Handover

Date: 28 July 2026

Handover source: completed private owner/source Blind JD PDF
metadata-overflow corrective

Phase 6 status: inactive; explicit owner authorization is required

## Completed baseline

CV Studio v24.6.239 completes Phases 1, 2A, 2B, 3, 4, 5A and 5B and includes
the v24.6.237 JobAdder `esc2`, v24.6.238 Blind JD experience-summary and
v24.6.239 Blind JD PDF metadata-overflow correctives.

The v24.6.239 correction is limited to `exportAnonJDPDF()`. Long first-page
Location/Work/Industry header metadata now wraps within its available width.
Long Location and Work values wrap within their padded tiles, and all present
tiles share the calculated maximum height while preserving the complete 174 mm
content width and established 4 mm gap.

## Immutable v24.6.239 contracts

Later work must preserve unless separately authorized:

- Blind JD PDF header metadata remains within the 18–192 mm content bounds;
- Location and Work tile text remains within each tile's padded width;
- present metadata tiles retain equal calculated height, complete metadata
  width and the established gap;
- no metadata value is truncated or silently omitted;
- the v24.6.238 Experience/Exp omission remains unchanged;
- structured `exp_range`, AI prompt/output schema, experience requirements and
  recruiter-critical body content remain unchanged;
- preview and Word export behavior remain unchanged.

## Earlier immutable contracts

Phase 6 work must also preserve:

- all 107 route URL/method/endpoint tuples and legacy response fields;
- all five ordered global security guards;
- authentication, CSRF, request-size and paid confirmation boundaries;
- all 18 compatibility signatures and Phase 4 call-time rebinding/
  initialization order;
- SQLite schema version 10 and every Phase 1/2 backup, migration, fallback,
  mirror and data-authority guarantee;
- Phase 3 provider endpoints, headers, retries, token refresh, pagination,
  redaction, content negotiation and zero-retry unsafe/paid writes;
- Phase 5A journal metadata schema 1, lifecycle states, bounded recovery and
  no-replay guarantees;
- Phase 5B estimate/authority separation, guardrail/reconciliation semantics
  and all paid-operation non-replay boundaries;
- protected credential stores, redaction and existing recovery semantics;
- the v24.6.215 DeepSeek detailed-history cutoff;
- the v24.6.237 locally scoped `esc2` correction.

## Phase 6 activation gate

Do not start Phase 6 from this handover alone. The owner must explicitly
authorize the exact Phase 6 milestone and compatibility boundary.

Before a Phase 6 production change:

1. verify the v24.6.239 owner ZIP, checksum, verification sidecar and exact
   `source_commit`;
2. freshly extract it and compare every tracked Git blob;
3. read this handover, the v24.6.239 corrective QA report, the v24.6.238
   handover/report and all earlier phase evidence;
4. run all 117 Python tests with `ResourceWarning` as an error;
5. run the focused Phase 3/4/5A/5B gate;
6. run all five frontend fixtures and 24 live smoke assertions;
7. run tracked Python/JavaScript/inline/Bash/PowerShell validation, owner
   preflight, repository consistency and whitespace validation;
8. inventory the exact frontend state/dependency/loading boundary selected for
   the authorized milestone;
9. add characterization before changing behavior;
10. stop for separate owner authorization if a route, response, schema, data
    authority, credential boundary, paid gate, provider retry/non-replay rule,
    journal semantic or recovery contract would change.

## Candidate Phase 6 direction

The roadmap lists frontend modularisation, lazy loading, remaining
adaptive-memory work and final explainable-fit refinements. This is planning
context only, not authorization.

Any authorized Phase 6 should select one bounded frontend area at a time,
preserve established globals/browser compatibility adapters, characterize load
order and state ownership before movement, avoid a broad rewrite, and run
targeted plus full acceptance gates.

## Explicit exclusions

Without separate owner authorization, do not:

- change SQLite schema 10 or Phase 5A journal schema 1;
- add billing/admin credentials, background billing workers or a durable
  billing ledger;
- change paid confirmation gates or replay ambiguous paid work;
- migrate protected secrets;
- perform JobAdder sign-out/settings work;
- replace Flask's built-in local server;
- implement saved/versioned AI Crawler scoring profiles;
- implement AI Crawler Shortlist / Maybe / Reject / Reviewed workflow;
- combine unrelated workflow changes with frontend modularisation.

## Release evidence

The authoritative corrective artifacts are under
`C:\CV-Studio-Codex\releases\v24.6.239`:

- `cv_studio_v24_6_239_blind_jd_pdf_metadata_overflow_corrective_owner_source.zip`;
- its `.zip.sha256` sidecar;
- its `.zip.verification.json` sidecar;
- `cv_studio_v24_6_239_blind_jd_pdf_metadata_overflow_corrective_qa_report.md`;
- this Phase 6 handover.

No protected colleague build or native platform certification is implied.

Stop before handoff or merge. Phase 6 remains inactive.
