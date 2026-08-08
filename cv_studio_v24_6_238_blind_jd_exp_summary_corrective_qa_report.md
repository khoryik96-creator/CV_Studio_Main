> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.238 — Blind JD Experience-Summary Corrective QA Report

Date: 26 July 2026

Release type: private owner/source only

Authorized comparison baseline: CV Studio v24.6.237 at
`3894042b496896e9a4f358ac9b0e10270052571b`

Implementation branch: `codex/blind-jd-exp-summary-corrective`

The exact final source commit is recorded in the adjacent verification sidecar.

## Authorization and baseline

The owner authorized only a narrow corrective removal of the duplicated
standalone Experience/Exp summary from Blind JD browser preview, Word export
and PDF export. JobAdder sign-out/settings work and Phase 6 remained inactive.

At entry:

- the worktree was clean and detached at exact local master commit
  `3894042b496896e9a4f358ac9b0e10270052571b`;
- all active installed source surfaces identified v24.6.237;
- the v24.6.237 owner/source ZIP and its checksum/verification sidecars were
  present;
- the ZIP independently recomputed to SHA-256
  `5bc44d77cb34c0624dbab973a907ce2eba34dee33593c940af41d0e217bf8cd9`;
- the verification `source_commit` exactly matched approved master;
- a fresh extraction contained 128 tracked files and matched every approved
  Git blob with zero missing, extra or byte-mismatched files.

The immutable v24.6.237 release artifacts were hashed before work and remained
unchanged.

## Current-source inventory

Before production changes, the complete source was searched for `exp_range`,
`Experience:` and `Exp:` across every Blind JD preview, print and export
surface.

The inventory found:

1. the required `exp_range` field in the AI raw-JSON output schema;
2. one duplicated preview badge in `renderAnonJDCard()`;
3. one duplicated top `Experience:` line in `exportAnonJDDoc()`;
4. one duplicated `Exp:` tile in `exportAnonJDPDF()`.

No other Blind JD preview, print or export surface independently displayed
`exp_range`. Requirements, Nice to Have and the other recruiter-critical body
arrays are separate structured fields.

## Pre-change characterization

`tests/test_blind_jd_exp_summary_frontend.js` was added before production
changes. Against exact master it failed on:

- the preview experience badge;
- the Word top Experience summary;
- the PDF Exp tile;
- the three render/export source-scope checks.

Its prompt/schema, retained body requirements, metadata, escaping and unrelated
section checks already passed.

The unchanged-source entry gate also passed all 117 Python tests after
restoring the documented ignored exact `adm-zip` 0.5.17 runtime copy. All four
established frontend fixtures passed.

## Corrective change

The smallest safe production correction:

- removes `j.exp_range` only from the preview metadata array;
- removes only the `Experience:` entry from the Word About the Role summary;
- removes only the `Exp:` PDF tile;
- divides the complete 174 mm PDF content width evenly across the remaining
  present Location and Work tiles, retaining the established 4 mm gap.

The correction does not change:

- the source JD;
- prompt instructions;
- the raw JSON output schema or `exp_range` field;
- the structured `window._lastAnonJD` object;
- What You Need to Succeed, Nice to Have or any recruiter-critical body field;
- unrelated Blind JD content or export sections;
- the valid locally scoped `esc2` helper in `renderAnonJDCard()`.

## Focused regression coverage

The new four-case fixture proves:

- preview omits the standalone experience badge;
- Word export omits the top Experience summary;
- PDF export omits the Exp tile;
- body experience requirements remain in Requirements and Nice to Have;
- `exp_range` remains in the generated structured-data schema and is not
  mutated by rendering/export;
- Location, Work Arrangement and Industry remain in preview/Word output;
- Location and Work remain in PDF output and fill the metadata width;
- browser HTML and Word HTML remain escaped;
- PDF values remain text-only arguments;
- all unrelated Blind JD sections and representative content remain.

The retained v24.6.237 JobAdder fixture separately proves both legitimate local
`esc2` helpers and every JobAdder escaping correction remain.

## Final validation

- Complete Python discovery: 117 tests passed with `ResourceWarning` treated
  as an error.
- Focused Phase 3/4/5A/5B gate: 91 tests passed.
- Frontend fixtures: all five passed.
- Focused Blind JD fixture: all four cases passed.
- Live loopback source smoke: all 24 assertions passed.
- Python static validation: all 27 tracked files passed.
- JavaScript static validation: all 23 tracked files and both full inline
  scripts passed.
- Bash/command syntax: all five tracked files passed through Git Bash.
- PowerShell parser: all five tracked files passed with zero parser errors.
- Owner-source validation/preflight and vetted `adm-zip` 0.5.17 behavior
  passed.
- Repository consistency and Git whitespace validation passed.

## Preserved invariants and repeated review

Repeated exact-master review re-proved:

- all 107 Flask route URL/method/endpoint tuples;
- all five ordered global request/security guards;
- all authentication, CSRF, request-size and paid-call confirmation gates;
- all 18 compatibility signatures and Phase 4 initialization/rebinding order;
- SQLite schema version 10;
- Phase 5A journal metadata schema 1, lifecycle and non-replay semantics;
- Phase 3 provider endpoints, headers, retry and timeout behavior;
- every Phase 5B estimate, guardrail, billing and paid-operation non-replay
  contract;
- protected credential/redaction boundaries;
- the v24.6.215 DeepSeek detailed-history cutoff;
- the v24.6.237 JobAdder `esc2` scope correction.

After release-string normalization, only the three authorized Blind JD
render/export paths changed in production logic. The prompt and schema remain
exact baseline text. No further concrete finding remained after the repeated
review.

No live credential, JobAdder call, paid request, external mutation, protected
colleague build, native compilation, JobAdder sign-out/settings, Phase 6 work
or backburner item was used or introduced.

## Private archive

The authoritative archive is
`cv_studio_v24_6_238_blind_jd_exp_summary_corrective_owner_source.zip` under
`C:\CV-Studio-Codex\releases\v24.6.238`.

It is generated from the exact final clean branch commit with one
`cv_formatter/` root, freshly extracted and compared with every tracked Git
blob with zero missing, extra or byte-mismatched files. The adjacent
`.zip.sha256` and `.zip.verification.json` sidecars are authoritative for the
digest, bytes, `source_commit`, counts and verification time.

Stop before handoff or merge. Phase 6 remains inactive.
