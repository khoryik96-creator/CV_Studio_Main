# CV Studio v24.6.235 — Phase 6 Handover

Date: 26 July 2026

Handover source: completed private owner/source Phase 5B release

Phase 6 status: inactive; explicit owner authorization is required

## Completed baseline

CV Studio v24.6.235 completes Phases 1, 2A, 2B, 3, 4, 5A and 5B.

Phase 5B adds one bounded app-independent module:

- `cvstudio_ai_costs.py` — canonical provider usage, established local
  estimates, opt-in pre-transport request ceilings, explicit billing authority
  and failure-visible reconciliation.

Standard Anthropic, DeepSeek and OpenAI inference responses do not provide
invoice-authoritative per-call cost. Existing numeric `cost` remains a local
rate-table estimate. Provider-returned usage, local cost authority, nullable
provider-authoritative cost and reconciliation status are distinct.

Tavily/SerpAPI and Apollo remain separate third-party billing domains. Their
unknown fees are not folded into the AI estimate and are explicitly marked
unavailable when their responses return no billing amount.

## Immutable Phase 5B contracts

Any later work must preserve unless separately authorized:

- `CVSTUDIO_AI_MAX_ESTIMATED_REQUEST_USD` is disabled when unset;
- a configured guardrail blocks before provider transport;
- unknown models use a conservative known-provider rate ceiling;
- invalid, negative, non-finite or unbounded request ceilings fail visibly;
- legacy `cost` and `cost_details.usd` remain local estimates;
- missing provider billing remains nullable and never becomes zero or
  authoritative;
- authoritative billing requires explicit one-request scope, approved source
  and finite bounded amount;
- non-USD authority is not converted without an authorized exchange-rate
  source;
- ambiguous paid operations are never automatically replayed;
- the owner DeepSeek probe retains owner authorization and exact paid
  confirmation;
- protected credentials/account identifiers do not enter billing metadata,
  usage history, logs, diagnostics, journals or release evidence;
- the v24.6.215 DeepSeek field-presence history cutoff remains unchanged.

## Earlier immutable contracts

Phase 6 work must also preserve:

- all 107 route URL/method/endpoint tuples and legacy response fields;
- all five ordered global security guards;
- authentication, CSRF, request-size and paid-call confirmation boundaries;
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

Before any Phase 6 production change:

1. verify the v24.6.235 owner ZIP, checksum, verification sidecar and exact
   `source_commit`;
2. freshly extract it and compare every tracked Git blob;
3. read this handover, the Phase 5B QA report and all earlier phase evidence;
4. run all 104 Python tests with `ResourceWarning` as an error;
5. run the 51-test Phase 5B/3/4/5A focused gate;
6. run all three frontend fixtures and 24 live smoke assertions;
7. run tracked Python/JavaScript/inline/Bash/PowerShell static validation,
   owner preflight, repository consistency and whitespace validation;
8. inventory the exact frontend state, dependency and loading boundary selected
   for the authorized milestone;
9. add characterization before changing behavior;
10. stop for separate owner authorization if a route, response, schema, data
    authority, credential boundary, paid gate, provider retry/non-replay rule,
    journal semantic or recovery contract would change.

## Candidate Phase 6 direction

The roadmap currently lists frontend modularisation, lazy loading, remaining
adaptive-memory work and final explainable-fit refinements. This is planning
context only, not authorization.

Any authorized Phase 6 should:

- select one bounded frontend area at a time;
- preserve established globals and browser/storage compatibility adapters;
- avoid a broad rewrite;
- characterize load order, state ownership and error behavior before movement;
- run targeted tests after each move and full acceptance before release.

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

The authoritative Phase 5B artifacts are under
`C:\CV-Studio-Codex\releases\v24.6.235`:

- `cv_studio_v24_6_235_phase5b_ai_cost_guardrails_owner_source.zip`;
- its `.zip.sha256` sidecar;
- its `.zip.verification.json` sidecar;
- `cv_studio_v24_6_235_phase5b_ai_cost_guardrails_qa_report.md`;
- this Phase 6 handover.

No protected colleague build or native platform certification is implied.

Phase 5B is complete. Stop before handoff, merge or Phase 6.
