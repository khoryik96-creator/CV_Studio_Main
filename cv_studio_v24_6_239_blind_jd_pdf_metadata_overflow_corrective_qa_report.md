# CV Studio v24.6.239 — Blind JD PDF Metadata-Overflow Corrective QA Report

Date: 28 July 2026

Release type: private owner/source only

Corrective source baseline: CV Studio v24.6.238 at
`8dd2c1ba0d0e0fc9640997b50d82ce41c7dd129d`

Exact master comparison baseline:
`3894042b496896e9a4f358ac9b0e10270052571b`

Implementation branch: `codex/blind-jd-pdf-overflow-corrective`

The exact final source commit is recorded in the adjacent verification sidecar.

## Authorization and verified entry state

The owner supplied a generated Blind JD PDF with an output defect and
authorized correction followed by repeated exact-master review. Phase 6,
JobAdder sign-out/settings work and unrelated product changes remained
inactive.

At entry:

- the worktree was clean on completed v24.6.238 commit
  `8dd2c1ba0d0e0fc9640997b50d82ce41c7dd129d`;
- local `master` remained exactly
  `3894042b496896e9a4f358ac9b0e10270052571b`;
- all active installed source surfaces identified v24.6.238;
- the v24.6.238 owner/source ZIP and both sidecars were present;
- that ZIP independently recomputed to SHA-256
  `ca63ded2c7beef0d1e6853792c7e0c671708acb6cb3d571765bbe0cc9f9c0de8`;
- its verification `source_commit` exactly matched the v24.6.238 source
  baseline;
- the owner-supplied reproduction PDF recomputed to SHA-256
  `7aca950544f5068f89877d0ca2a7052047e732d1430f5fbbfea19d6594e94d1e`.

The immutable v24.6.238 release artifacts remained unchanged.

## Confirmed diagnosis

The supplied two-page PDF was rendered at 150 DPI and inspected visually, with
text extraction used only as a supporting content check.

Page 1 had two concrete horizontal-overflow defects:

1. the unwrapped Location/Work/Industry header summary continued beyond the
   right page edge;
2. the long Work value continued beyond the right edge of its equal-width
   metadata tile and page.

Page 2 and all Blind JD body sections were intact.

Current-source review traced both defects to `exportAnonJDPDF()`. The header
called `doc.text()` with an unsplit string, and each metadata tile rendered one
unsplit line inside a fixed 7.2 mm height. Preview and Word export did not share
this PDF layout path.

## Regression-first correction

The existing Blind JD corrective fixture was extended before production code.
It uses the exact long Work Arrangement from the supplied PDF and initially
failed because the header metadata did not wrap.

The smallest production correction:

- splits the header metadata to the measured width between its established
  x-position and the 18 mm right margin;
- moves the header rule and following metadata row only when extra wrapped
  lines require it;
- splits each Location/Work label and value to the tile width minus its
  established horizontal padding;
- gives all present tiles the same calculated height based on the largest line
  count;
- retains the complete 174 mm metadata width and established 4 mm gap.

No Blind JD value is truncated, omitted or replaced.

## Preserved Blind JD contracts

- The v24.6.238 standalone Experience/Exp removal remains in preview, Word and
  PDF output.
- `exp_range` remains in the generated structured data and AI output schema.
- Existing AI prompts and schema text remain unchanged.
- Experience requirements remain eligible in What You Need to Succeed, Nice
  to Have and other recruiter-critical body content.
- Location and Work remain present in the PDF; Location, Work and Industry
  remain present in preview, Word and the PDF header.
- HTML and Word values retain their established escaping. PDF values remain
  safe text arguments.
- No unrelated Blind JD section or representative content changed.

## Visual verification

A real PDF was exported through the repository's bundled jsPDF using local
headless Chrome and the supplied long metadata values. Both pages were rendered
with Poppler and inspected.

The final first page shows:

- a two-line header summary fully inside the right margin;
- equal-width and equal-height Location/Work tiles;
- a two-line Work value fully inside its padded tile;
- unchanged section alignment, typography and body legibility.

The final second page has no clipping, overlap or footer defect.

## Final validation

- Focused Blind JD frontend fixture: all five cases passed.
- Complete Python discovery: 117 tests passed with `ResourceWarning` treated
  as an error.
- Focused Phase 3/4/5A/5B and invariant gates passed.
- Frontend fixtures: all five passed.
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

Repeated review against exact master and the completed v24.6.238 source
re-proved:

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
- the v24.6.237 JobAdder `esc2` correction;
- the complete v24.6.238 Blind JD experience-summary correction.

After release-string normalization, only `exportAnonJDPDF()` changed in
production logic relative to completed v24.6.238. No further concrete finding
remained after the repeated review.

No live credential, paid request, external mutation, protected colleague
build, native compilation, JobAdder sign-out/settings work, Phase 6 work or
backburner item was used or introduced.

## Private archive

The authoritative archive is
`cv_studio_v24_6_239_blind_jd_pdf_metadata_overflow_corrective_owner_source.zip`
under `C:\CV-Studio-Codex\releases\v24.6.239`.

It is generated from the exact final clean branch commit with one
`cv_formatter/` root, freshly extracted and compared with every tracked Git
blob. The adjacent `.zip.sha256` and `.zip.verification.json` sidecars are
authoritative for the digest, bytes, `source_commit`, counts and verification
time.

Stop before handoff or merge. Phase 6 remains inactive.
