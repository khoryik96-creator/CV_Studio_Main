> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.236 — Phase 5B Corrective QA Report

Date: 26 July 2026

Release type: private owner/source only

Authorized comparison baseline: CV Studio v24.6.234 at
`327858799f17d880e37c740f71dfe321ea7bde0a`

Reviewed Phase 5B release: v24.6.235 at
`fc64f21168990bc58512dc34aa685b08c0d28a5f`

Implementation branch: `codex/phase-5b-ai-cost-guardrails`

Corrective checkpoints:

- `935ddac` — initial reconciliation/guardrail edge corrections;
- `923ea1c` — precision, redaction and paid-boundary hardening;
- `af65b24` — missing-usage and multi-call accounting checkpoint.

The exact final source commit is recorded in the adjacent verification sidecar.

## Authorization and method

The owner authorized review and correction of Phase 5B only. Every Phase 5B
change was reviewed against exact master, fixed when a concrete defect was
found, characterized with no-network tests and reviewed again. Three review
cycles completed with no remaining concrete finding.

No live credential, paid request, external mutation, protected colleague build,
native compilation, schema migration, background worker, Phase 6 work or
backburner item 4, 7 or 8 was used or introduced.

## Concrete findings corrected

The repeated review corrected these bounded defect classes:

1. zero, boolean, fractional and string output ceilings could be defaulted or
   truncated rather than rejected before transport;
2. float comparison could lose a real estimate-versus-limit difference;
3. underflowing, excessively precise or unbounded guard configuration could
   produce misleading numeric metadata;
4. malformed/partial merged billing could retain unallowlisted fields or
   reconcile only a valid subset;
5. provider mismatch, missing/malformed currency and unsafe billing sources
   were not rejected consistently;
6. delayed billing was collapsed into pending, and missing/partial/unavailable/
   invalid states were not fully distinct;
7. non-USD authority and exact high-precision decimal text could be lost;
8. missing billing/no-call states could be reported as zero or missing when
   billing was not applicable;
9. absent or partial input/output usage could appear as an available zero
   estimate after `api_calls=1` was synthesized;
10. invalid token/call/cache counters could become a valid-looking estimate;
11. one billing record could be reconciled against several calls, while
    excess/duplicate records could be summed;
12. a cross-record currency/provider defect could discard otherwise successful
    paid output;
13. malformed billing on a successful response could discard content/usage and
    encourage an unsafe duplicate retry;
14. Tavily/SerpAPI or pre-Apollo failures could be mislabeled as ambiguous paid
    AI calls;
15. Apollo auth/rate-limit attempts were not included in the observed operation
    count;
16. credential-like fragments could survive inside new model/provider/reason
    metadata;
17. browser persistence/export could coerce malformed authority to `NaN`, lose
    exact native authority or display an unavailable estimate as zero.

## Corrected contracts

- Guardrails remain opt-in through
  `CVSTUDIO_AI_MAX_ESTIMATED_REQUEST_USD` and enforce an exact, conservative,
  bounded Decimal comparison before provider transport.
- Explicit zero token counters are valid. Absent or partial counters retain
  compatible legacy numeric fields but add
  `estimated_cost_usd=null`,
  `cost_value_type=local_estimate_unavailable`,
  `usage_validation_status=missing` and
  `estimate_status=usage_unavailable`.
- Provider authority requires explicit request scope, approved source,
  matching provider, strict three-letter currency and a bounded non-negative
  Decimal with at most 30 significant digits and 18 decimal places.
- Exact authoritative text is retained beside compatible numeric fields.
  Non-USD authority remains native and no conversion is invented.
- Pending, delayed, partial, unavailable, invalid, authoritative USD and
  authoritative non-USD states remain distinct and failure-visible.
- Multi-call reconciliation requires one valid request-scoped authority record
  per paid call. Partial coverage is not summed; excess records are invalid.
- Malformed embedded billing never discards successful provider content/usage.
  Raw billing is stripped and only normalized allowlisted data or a safe status
  marker survives.
- External search/enrichment billing remains separate from AI token estimates.
  AI ambiguity fields are added only after an AI request boundary starts.
- Browser history retains exact authority text/native currency and exports
  unavailable estimates as blank/`n/a`, not zero.
- Credential-like model/provider identifiers and external billing reasons are
  bounded and redacted.

## Final validation

- Complete Python discovery: 117 tests passed with `ResourceWarning` treated
  as an error.
- Focused Phase 3/4/5A/5B gate: 91 tests passed.
- Phase 5B targeted gate: 31 tests passed.
- Frontend fixtures: all three passed.
- Live loopback source smoke: all 24 assertions passed.
- Concurrent guardrail/reconciliation/JSON probe: 96 parallel cases passed.
- Python static validation: 27 tracked files passed.
- JavaScript static validation: 21 tracked files and both full inline scripts
  passed.
- Bash/command syntax: five tracked files passed through Git Bash.
- PowerShell parser: five tracked files passed with zero parser errors.
- Owner-source validation/preflight and vetted `adm-zip` 0.5.17 behavior
  passed.
- Repository consistency and Git whitespace validation passed.
- Exact-master route decorator audit confirmed all 107 routes unchanged.
- Protected Phase 1–5A modules remained byte-identical to master.

## Preserved invariants

Final characterization re-proved:

- 107 Flask route URL/method/endpoint tuples;
- five ordered global request/security guards;
- all authentication, CSRF, request-size and paid-call confirmation gates;
- 18 compatibility signatures and Phase 4 initialization/rebinding order;
- SQLite schema version 10;
- Phase 5A journal metadata schema 1, lifecycle and non-replay semantics;
- Phase 3 provider endpoints, headers, retry and timeout behavior;
- no automatic replay of ambiguous paid operations;
- protected credential/redaction boundaries;
- the v24.6.215 DeepSeek detailed-history cutoff.

`cvstudio_clients.py`, `cvstudio_storage.py`, `cvstudio_jobs.py`,
`cvstudio_storage_bridge.py`, `cvstudio_diagnostics.py` and
`cvstudio_document_safety.py` remain exact master bytes.

## Private archive

The authoritative archive is
`cv_studio_v24_6_236_phase5b_ai_cost_guardrails_corrective_owner_source.zip`
under `C:\CV-Studio-Codex\releases\v24.6.236`.

It is generated from the exact final branch commit with one `cv_formatter/`
root, freshly extracted and compared against every tracked Git blob with zero
missing, extra or byte-mismatched files. The adjacent `.zip.sha256` and
`.zip.verification.json` sidecars are authoritative for digest, bytes,
`source_commit`, counts and verification time.

Phase 5B is complete. Stop before handoff, merge or Phase 6.
