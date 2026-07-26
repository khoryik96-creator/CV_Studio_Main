# CV Studio v24.6.235 — Phase 5B AI Cost Guardrails QA Report

Date: 26 July 2026

Release type: private owner/source only

Authorized source baseline: CV Studio v24.6.234 at
`327858799f17d880e37c740f71dfe321ea7bde0a`

Implementation branch: `codex/phase-5b-ai-cost-guardrails`

Stable checkpoints:

- `c595f13` — owner authorization, entry verification and active plan;
- `d4546e6` — paid-provider inventory and pre-change characterization;
- `ba46674` — central accounting and request-guardrail foundation;
- `f29bfa2` — existing-call, failure, external-billing and frontend integration.

The final source commit is recorded in the adjacent release verification
sidecar.

## Authorization and scope

The owner explicitly authorized Phase 5B only: central AI cost guardrails and
provider-billing reconciliation.

The release does not add persistent-job families, workers, credential
migration, admin billing credentials, frontend modularisation/lazy loading,
unrelated workflows, Flask server replacement, Phase 6 work or backburner item
4, 7 or 8. No live credential or paid/provider request was used.

## Entry gate

Before production code changed:

- the worktree was clean;
- `master` and `HEAD` were exactly
  `327858799f17d880e37c740f71dfe321ea7bde0a`;
- all installed source surfaces identified v24.6.234;
- the v24.6.234 release directory contained the owner ZIP, checksum,
  verification sidecar, corrective QA report and Phase 5B handover;
- the ZIP independently recomputed to
  `eb44700e941deb079c55cbff1f200b3c97733f5171e24748088fe38490b5b8cd`;
- its sidecar `source_commit` exactly matched master;
- a fresh 117-file extraction matched approved Git with zero missing, extra or
  byte-mismatched files;
- unchanged-source entry regression passed 86 Python tests, 38 focused tests,
  both then-existing frontend fixtures and 24 live smoke assertions;
- tracked-language static validation, owner preflight, repository consistency
  and whitespace validation passed.

## Pre-change inventory

Characterization recorded:

- eight browser-session-gated AI `POST` routes;
- the separate owner-only DeepSeek probe and its exact paid confirmation;
- the optional Tavily/SerpAPI connectivity boundary;
- the Anthropic, DeepSeek, OpenAI, Tavily/SerpAPI and Apollo helper paths;
- canonical/native provider, model, input/output/cache/call and local estimate
  fields;
- every established success, post-response failure, timeout and salary
  processing field;
- protected AI-secret slots and permitted non-secret billing metadata;
- all retry, timeout and ambiguous charge boundaries;
- the v24.6.215 field-presence cutoff and preserved historical-cost behavior.

Standard inference responses were confirmed to provide provider-originated
usage rather than invoice-authoritative per-call USD cost. Anthropic and OpenAI
have separate admin cost-report APIs requiring distinct administration
credentials, while DeepSeek documents usage and a separate balance endpoint.
Those credentials and aggregate billing calls are outside this phase.

References inspected:

- OpenAI organization usage API:
  https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage
- Anthropic Usage and Cost Admin API:
  https://platform.claude.com/docs/en/manage-claude/usage-cost-api
- Anthropic cost report:
  https://platform.claude.com/docs/en/api/admin/cost_report
- DeepSeek chat-completion usage:
  https://api-docs.deepseek.com/api/create-chat-completion/
- DeepSeek balance:
  https://api-docs.deepseek.com/api/get-user-balance/

## Central foundation

`cvstudio_ai_costs.py` is app-independent and owns:

- established provider/model rate-table resolution;
- provider-neutral usage normalization and deliberate multi-call merging;
- unchanged DeepSeek cache-hit/cache-miss estimate behavior;
- explicit estimate, usage-authority and cost-authority provenance;
- strict optional provider-authoritative billing normalization;
- USD estimate-versus-authority difference calculation;
- explicit non-USD reconciliation without invented conversion;
- missing-billing and paid-failure descriptors;
- an opt-in conservative pre-transport request ceiling.

The legacy top-level `cost` and `cost_details.usd` remain local estimates with
their established numeric behavior. Additive fields expose:

- `estimated_cost_usd`;
- `cost_value_type=local_estimate`;
- `cost_authority=local_rate_table`;
- `usage_authority`;
- `provider_billing_status`;
- nullable `provider_authoritative_cost_usd`;
- provider billing currency/source;
- reconciliation status and nullable differences;
- explicit `billing_data_missing`;
- configured guardrail status and limit.

Authoritative billing requires an explicit one-request scope, an approved
provider response/cost-report/invoice source, finite bounded non-negative
amount and bounded record count. Invalid authority fails visibly. Optional
provider references are not propagated into application responses or durable
usage records.

## Guardrail behavior

`CVSTUDIO_AI_MAX_ESTIMATED_REQUEST_USD` is read at call time:

- unset: disabled, preserving v24.6.234 behavior;
- valid and within bounds: a conservative request ceiling is evaluated before
  provider transport;
- estimate over limit: typed visible block before transport;
- invalid/non-finite/out-of-range configuration: typed visible configuration
  failure before transport.

The estimate uses one input token per UTF-8 payload byte plus the requested
maximum output tokens. Unknown models use the highest known rate for the
resolved provider. Invalid, negative and arbitrarily large output ceilings
cannot be silently replaced by a cheaper fallback or lower cap.

This is an in-request ceiling, not a persisted budget, billing ledger or
background reconciliation worker.

## Existing-call integration

- `call_anthropic`, `_call_deepseek` and `_call_openai` keep their signatures,
  endpoints, headers, timeout behavior and Phase 3 zero-retry paid boundary.
- `call_llm`, usage merge and cost helper signatures remain unchanged.
- Success responses retain every legacy field and add authority provenance.
- Paid failures add `paid_call_status` and `billing_reconciliation` while
  retaining legacy error fields and status behavior.
- Guardrail blocks, definite provider errors, returned usage, no-call paths and
  ambiguous no-usage failures are distinguished.
- OneNote salary processing retains legacy camel-case fields and adds matching
  provenance; cache/local paths are explicitly no-call.
- The owner DeepSeek probe retains owner authorization and exact confirmation.
  Its legacy `metadata.cost_usd` now reads the correct estimate key instead of
  the nonexistent key that previously yielded zero.
- Tavily/SerpAPI and Apollo expose separate `external_billing` status with
  nullable authoritative amount. Their unknown fees do not enter AI token
  estimates.
- New usage-history records persist non-secret authority metadata inside the
  existing schema-10 JSON payload. No schema or data authority changed.
- Tracker labels and CSV columns now identify estimates and reconciliation.
  Pre-v24.6.215 history remains untouched and keeps its exact legacy message.

## Repeated review findings corrected

The exact-v24.6.234-master review found and corrected:

1. provider-authoritative billing needed an explicit per-request scope before
   comparison with a per-request estimate;
2. billing amount and record totals needed finite bounds;
3. optional provider billing references should not propagate across the
   protected account-identifier boundary;
4. invalid, negative or extremely large output ceilings could otherwise be
   replaced or capped below the requested value during guard evaluation.

The repository formatter also restored required CRLF/no-BOM discipline in the
three Windows launcher/build files touched by version advancement.

The repeated clean review confirmed no remaining concrete finding.

## Final validation

- Complete Python discovery: 104 tests passed with `ResourceWarning` treated
  as an error.
- Focused Phase 5B/3/4/5A gate: 51 tests passed.
- Frontend fixtures: all three passed.
- Live loopback source smoke: all 24 assertions passed.
- Python static validation: 27 tracked files passed.
- JavaScript static validation: 21 tracked files and both full inline scripts
  passed.
- Bash/command syntax: five tracked files passed through Git Bash.
- PowerShell parser: five tracked files passed with zero parser errors.
- Owner-source validation/preflight and vetted `adm-zip` 0.5.17 behavior
  passed.
- Repository consistency and Git whitespace validation passed.

No live credentials, paid external call, external mutation, protected
colleague build, native compilation or genuine macOS test was performed or
claimed.

## Preserved invariants

Final characterization re-proved:

- 107 Flask route URL/method/endpoint tuples;
- five ordered global request/security guards;
- 18 compatibility signatures;
- 80 MiB request limit;
- SQLite schema version 10;
- Phase 5A journal metadata schema 1 and non-replay recovery semantics;
- Phase 4 call-time rebinding and initialization markers;
- Phase 3 provider endpoints, headers, bounded timeouts and zero retries for
  chargeable posts;
- protected credential slots and redaction;
- v24.6.215 DeepSeek detailed-history cutoff.

`cvstudio_clients.py`, `cvstudio_storage.py`, `cvstudio_jobs.py`,
`cvstudio_storage_bridge.py`, `cvstudio_diagnostics.py` and
`cvstudio_document_safety.py` remain exact v24.6.234 master bytes.

## Private archive

The authoritative archive is
`cv_studio_v24_6_235_phase5b_ai_cost_guardrails_owner_source.zip` under
`C:\CV-Studio-Codex\releases\v24.6.235`.

It is generated from the exact final clean branch commit with one
`cv_formatter/` root, freshly extracted and compared against every tracked Git
blob with zero missing, extra or byte-mismatched files. The adjacent
`.zip.sha256` and `.zip.verification.json` sidecars are authoritative for
digest, size, `source_commit`, counts and verification time.

Phase 5B is complete. Stop before handoff, merge or Phase 6.
