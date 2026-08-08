> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.236 — Phase 6 Handover

Date: 26 July 2026

Handover source: completed private owner/source Phase 5B corrective release

Phase 6 status: inactive; explicit owner authorization is required

## Completed baseline

CV Studio v24.6.236 completes Phases 1, 2A, 2B, 3, 4, 5A and 5B. It preserves
the v24.6.235 Phase 5B foundation and corrects its bounded post-release
guardrail, usage, reconciliation, precision, redaction and paid-boundary
findings.

Standard Anthropic, DeepSeek and OpenAI inference responses provide usage, not
invoice-authoritative per-call cost. Legacy numeric `cost` remains a local
rate-table estimate. Missing/partial usage makes the additive estimate
unavailable; it is not treated as an authoritative or meaningful zero.

Tavily/SerpAPI and Apollo remain separate third-party billing domains. Their
unknown fees are not folded into AI token estimates.

## Immutable Phase 5B contracts

Any later work must preserve unless separately authorized:

- `CVSTUDIO_AI_MAX_ESTIMATED_REQUEST_USD` is disabled when unset;
- configured guardrails use exact bounded comparison and block before provider
  transport;
- invalid limits and invalid output-token ceilings fail visibly;
- unknown models use a conservative known-provider rate ceiling;
- legacy `cost` and `cost_details.usd` remain compatible local estimates;
- estimate, usage authority and provider billing authority remain distinct;
- absent/partial usage is explicitly unavailable, while returned zero counters
  remain valid zero usage;
- missing billing is nullable and never becomes zero or authoritative;
- authoritative billing requires explicit request scope, approved source,
  matching provider, strict currency and bounded exact Decimal amount;
- exact authoritative decimal text/native currency is retained;
- pending, delayed, partial, unavailable and invalid reconciliation states are
  distinct;
- multi-call billing must cover every paid call exactly once;
- malformed embedded billing cannot discard successful paid output;
- non-USD authority is not converted without an authorized rate source;
- ambiguous paid operations are never automatically replayed;
- search/enrichment billing remains separate from AI token estimates;
- credential-like metadata is redacted;
- the owner DeepSeek probe retains owner authorization and exact confirmation;
- the v24.6.215 DeepSeek history cutoff remains unchanged.

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
- protected credential stores and existing recovery semantics.

## Phase 6 activation gate

Do not start Phase 6 from this handover alone. The owner must explicitly
authorize the exact Phase 6 milestone and compatibility boundary.

Before a Phase 6 production change:

1. verify the v24.6.236 owner ZIP, checksum, verification sidecar and exact
   `source_commit`;
2. freshly extract it and compare every tracked Git blob;
3. read this handover, the v24.6.236 corrective QA report, the v24.6.235 Phase
   5B evidence and all earlier phase evidence;
4. run all 117 Python tests with `ResourceWarning` as an error;
5. run the 91-test focused Phase 3/4/5A/5B gate;
6. run all three frontend fixtures and 24 live smoke assertions;
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
- replace Flask's built-in local server;
- implement saved/versioned AI Crawler scoring profiles;
- implement AI Crawler Shortlist / Maybe / Reject / Reviewed workflow;
- combine unrelated workflow changes with frontend modularisation.

## Release evidence

The authoritative Phase 5B corrective artifacts are under
`C:\CV-Studio-Codex\releases\v24.6.236`:

- `cv_studio_v24_6_236_phase5b_ai_cost_guardrails_corrective_owner_source.zip`;
- its `.zip.sha256` sidecar;
- its `.zip.verification.json` sidecar;
- `cv_studio_v24_6_236_phase5b_ai_cost_guardrails_corrective_qa_report.md`;
- this Phase 6 handover.

No protected colleague build or native platform certification is implied.

Phase 5B is complete. Stop before handoff, merge or Phase 6.
