# CV Studio v24.6.237 — JobAdder esc2 Corrective QA Report

Date: 26 July 2026

Release type: private owner/source only

Authorized comparison baseline: CV Studio v24.6.236 at
`e22b05f139a743dc5e690f8ccb7b61a703fffc63`

Implementation branch: `codex/jobadder-esc2-corrective`

The exact final source commit is recorded in the adjacent verification sidecar.

## Authorization and baseline

The owner authorized only a narrow post-Phase-5B investigation and correction
for the JobAdder `esc2 is not defined` browser failure. Phase 6 remained
inactive.

At entry:

- the worktree was clean and both `HEAD` and local `master` resolved exactly to
  `e22b05f139a743dc5e690f8ccb7b61a703fffc63`;
- all active installed source surfaces identified v24.6.236;
- the v24.6.236 owner/source ZIP and both sidecars were present;
- the ZIP independently recomputed to SHA-256
  `c60dd25e79616d580449450c943a40760baa7c8aeaaceff21637c88e51a09146`;
- the verification `source_commit` exactly matched approved master;
- a fresh extraction contained 125 tracked files and matched every approved
  Git blob with zero missing, extra or byte-mismatched files.

The v24.6.235 and v24.6.236 release artifacts were hashed before work and
remained immutable.

## Independently confirmed diagnosis

Complete inspection of `showJADialog()`, `renderJAUploadList()`,
`renderAnonJDCard()`, `renderCompanyCard()`, every `esc2` occurrence and the
global `esc()` helper confirmed:

- `renderAnonJDCard()` and `renderCompanyCard()` each own one valid,
  function-local `esc2` helper;
- `showJADialog()` called `esc2(email)` outside either local scope;
- `renderJAUploadList()` called `esc2()` for filename and status text outside
  either local scope;
- there was no global `esc2`;
- the established global `esc()` is safe for the three affected text values;
- `renderJAUploadList()` also declared a local string variable named `esc`.
  A mechanical `esc2()` to `esc()` replacement without renaming that variable
  would have changed the failure to `TypeError: esc is not a function`.

Pre-change characterization failed on both affected runtime paths with
`ReferenceError: esc2 is not defined` and separately identified the three
out-of-scope source occurrences. The two local card-renderer escaping cases
already passed.

## Corrective change

The smallest safe production correction:

- replaces the invalid dialog `esc2(email)` call with global `esc(email)`;
- replaces the invalid upload filename and status calls with global `esc()`;
- renames only the upload renderer's shadowing local ID variable from `esc` to
  `escapedId`, preserving its value and both existing uses;
- leaves both local `esc2` definitions and all of their internal calls
  unchanged.

No global `esc2` alias was added. The new source-scope regression requires
every `esc2` definition and call to remain inside the two established local
renderers, so a future scope error fails visibly instead of being concealed by
an alias.

## Regression coverage

`tests/test_jobadder_esc2_frontend.js` proves:

- the candidate-not-found JobAdder dialog renders without `ReferenceError`;
- the dialog retains both Skip and Create actions;
- email text is HTML-escaped;
- matched and unmatched upload-queue entries render without `ReferenceError`;
- both queue filenames and unmatched status text are HTML-escaped;
- the matched entry retains its JobAdder profile link;
- `renderAnonJDCard()` and `renderCompanyCard()` retain their established local
  escaping behavior;
- every `esc2` call and definition is source-scoped to one of those two local
  renderers, with exactly two local definitions.

## Final validation

- Complete Python discovery: 117 tests passed with `ResourceWarning` treated
  as an error.
- Focused Phase 3/4/5A/5B gate: 91 tests passed.
- Frontend fixtures: all four passed, including the new JobAdder corrective
  fixture and all three established fixtures.
- Live loopback source smoke: all 24 assertions passed.
- Python static validation: all 27 tracked files passed.
- JavaScript static validation: all 22 tracked files and both full inline
  scripts passed.
- Bash/command syntax: all five tracked files passed through Git Bash.
- PowerShell parser: all five tracked files passed with zero parser errors.
- Owner-source validation/preflight and vetted `adm-zip` 0.5.17 behavior
  passed.
- Repository consistency and Git whitespace validation passed.
- Exact-master review confirmed that only `showJADialog()` and
  `renderJAUploadList()` changed in production logic; the two local card
  renderer function bodies remained exact master bytes.

## Preserved invariants

Final characterization re-proved:

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
- the v24.6.215 DeepSeek detailed-history cutoff.

No JobAdder route, request, candidate creation, upload, response field,
credential boundary or external-call policy changed. No live credential,
JobAdder call, paid request, external mutation, protected colleague build,
native compilation, Phase 6 work or backburner item was used or introduced.

## Private archive

The authoritative archive is
`cv_studio_v24_6_237_jobadder_esc2_corrective_owner_source.zip` under
`C:\CV-Studio-Codex\releases\v24.6.237`.

It is generated from the exact final clean branch commit with one
`cv_formatter/` root, freshly extracted and compared with every tracked Git
blob with zero missing, extra or byte-mismatched files. The adjacent
`.zip.sha256` and `.zip.verification.json` sidecars are authoritative for the
digest, bytes, `source_commit`, counts and verification time.

Stop before handoff or merge. Phase 6 remains inactive.
