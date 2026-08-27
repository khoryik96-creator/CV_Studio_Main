> **Version source of truth.** The current release is whatever the repository-root [`VERSION`](VERSION) file says — it is generated into every code surface by `bump_version.py` and enforced by `tests/test_version_single_source.py`. Any version number written *below* is historical context from when this document was authored; do **not** treat it as the current baseline. See `HANDOFF.md` for live project state.

# Current Phase Status

## Release state

- Approved baseline: v24.6.217
- Current source baseline: see the repository-root `VERSION` file (single source
  of truth). The specific numbers that used to be pinned here — e.g. "v24.6.252",
  "v24.6.253", "completed release v24.6.243" — went stale and have been removed
  so nothing contradicts `VERSION`.
- Phase 2B source baseline: v24.6.219
- Phase 2B baseline Git commit: `a43dbb84dcc44c773527f49d0332b2eb15a37cc1`
- Phase 3 source baseline: v24.6.222
- Phase 3 baseline Git commit: `1be9da48d8307c418d82807cbdaedc9f876a1b15`
- Phase 4 source baseline: v24.6.230
- Phase 4 baseline Git commit: `7a0efcf0bce10b07e034592fb22a6021141d4146`
- Phase 5A source baseline: v24.6.232
- Phase 5A baseline Git commit: `4b366ddde1cf0a398706b52d55b0e82ed2dbc27c`
- Phase 5B source baseline: v24.6.234
- Phase 5B baseline Git commit: `327858799f17d880e37c740f71dfe321ea7bde0a`
- Phase 7A source baseline Git commit:
  `a6b35d2e0cad977e737622ed7d10e451ed5f7de3`
- Phase 7B-1 source baseline Git commit (merged Phase 7A):
  `54298b9b6a822e1f36c9c101f1ff4edc9c7e835f`
- Phase 7B-4 source baseline Git commit (merged Phase 7B-3):
  `1e75737cb83e32d4f70d100c0f77a3de720cca9c`
- Current merged source: v24.6.360 through PR #181
  (`541cbf3`).
- Active work: v24.6.361 CV download folders on
  `chatgpt/pr182-v24.6.361-cv-download-folders` (planned PR #182, unmerged).
- Completed private owner/source release: v24.6.243 (Windows x64 only)
- Status: PR #155 merged the v24.6.340 HTML-highlight corrective as `a25bf5b`.
  The owner separately authorized the v24.6.341 OCR partial-failure corrective
  and its merge through PR #156. PR #162 merged the v24.6.347 LHDN source
  reliability corrective as `61a001d`. PR #164 merged the v24.6.348 KWSP
  source-access corrective. PR #165 merged the v24.6.349 salary
  contribution-profile repair. PR #166 merged the v24.6.350 salary
  profile-migration safety corrective. PR #167 merged the v24.6.351 JobAdder
  original-CV, candidate-contact and blank-PDF corrective as `85dc896`. PR #171
  merged the v24.6.353 Windows source-updater hardening as `af322db`. PR #173
  merged the v24.6.354 updater/CI reliability corrective as `0f2c6f5`; its
  final protected retry was cancelled at the owner's request to conserve CI
  minutes, with the retained local builder designated as the final package
  check. PR #174 merged the manual-only protected-build configuration as
  `ab96824`. PR #175 merged the updater preflight-path fix. PR #176 merged the
  audit hardening as `d94554c`. PR #177 merged the updater runtime-consistency
  corrective as `2c06bc5`. PR #179 merged the updater preflight-output
  corrective as `a20b7f9`. PR #181 merged the v24.6.360 Blind CV
  candidate-gender neutralization feature as `541cbf3`; current master is
  v24.6.360.
- Current stop: v24.6.360 is merged on `master` through PR #181. The v24.6.361
  CV download-folder branch is active and unmerged.

## v24.6.361 CV download folders (active, unmerged)

- Settings → Downloads provides separate Formatted CV and Blind CV destination
  folders. Each destination covers both single and batch downloads, and users
  may deliberately select the same folder for both.
- Supported Chromium browsers store only the browser-authorized directory
  handle in local IndexedDB; the full private path is neither exposed nor sent
  to the backend. Restarted browsers may require permission confirmation on the
  next download.
- Direct saves sanitize generated names and choose a numbered filename rather
  than overwriting an existing file. Unsupported, denied or failed folder
  access falls back to the established browser Downloads mechanism, including
  its existing spaced batch-download behavior.
- The post-review corrective preserves the complete numbered suffix when a
  near-limit filename must be shortened and fails safe rather than overwriting
  after the bounded collision search. Batch results retain their processing
  mode, so changing the visible Format All / Blind All selection after a run
  cannot redirect completed files to the other destination.
- Only formatted/blinded CV DOCX downloads change. Reports, CSVs, diagnostics
  and every other export remain unchanged. No route, schema, dependency,
  credential, paid/AI/external call, CV content/formatting or protected-build
  trigger changes.
- Validation: 984 tests passed, 4 skipped and 96 subtests; all 20 frontend
  fixtures; 24 live source-smoke assertions; 142 Python, 70 JavaScript, 9
  PowerShell and 3 POSIX-shell syntax checks; exact dependency and repository
  consistency; Windows Antiword/Tesseract/adm-zip protected-source preflight;
  and a clean real-browser render with no console warnings/errors.

## v24.6.360 Blind CV candidate-gender neutralization (merged through PR #181)

- General Settings has an off-by-default toggle used only by single and batch
  Blind CV. Enabled runs rewrite candidate-only pronouns to `the candidate` /
  `the candidate's`, expand candidate contractions grammatically and avoid
  candidate-referent they/them.
- The instruction explicitly preserves gendered references to managers,
  colleagues, clients, referees, family members and every other party. It is
  part of the existing paid blinding request and does not add another AI call.
- Single runs snapshot the toggle before parsing; batch runs snapshot it once
  for the whole run. The setting is included in established non-secret durable
  browser/SQLite backup and restore.
- Default Blind CV behavior and all normal Format CV paths remain unchanged.
  No route, schema, dependency, credential, paid-call-count, candidate-data or
  protected-build trigger change.

## v24.6.359 updater preflight-output corrective

- `Invoke-Preflight` displays the downloaded PowerShell preflight's output but
  returns only its numeric exit code. Visible success/error text can no longer
  turn the function result into `System.Object[]` and crash `Stop-Update` with a
  brief red parameter-conversion error.
- The Windows updater fixture now always prints a realistic child-preflight
  diagnostic. Its failure regression verifies exit code 8, the actionable
  message, no conversion crash and that the current server remains untouched.
- No route, schema, dependency, CV-formatting, credential, paid/external call,
  candidate-data, storage or protected-build trigger changes. PR #179 merged to
  `master` as `a20b7f9` after 982 tests, 4 skips and 96 subtests passed locally;
  hosted runners did not start because the Actions spending limit was
  exhausted.

## v24.6.358 updater runtime-consistency corrective

- One shared PowerShell resolver owns Windows source-mode Python selection for
  both update preflight and `START_HIDDEN.vbs`. It verifies every exact
  `requirements.txt` distribution version and imports the complete runtime set,
  then startup launches the exact executable returned by that probe.
- A stale PATH Python can no longer pass control to a different interpreter or
  take the working server down after a later candidate passed preflight. A
  manual GitHub Desktop pull and the one-time transition from an older updater
  cannot restart CV Studio with merely importable but stale dependency
  versions; `INSTALL.bat` remains the explicit repair path.
- The downloaded candidate preflight remains self-contained while the old
  v24.6.357 checkout does not yet contain `PYTHON_RUNTIME.ps1`; subsequent
  updater runs also verify that the candidate contains that helper before
  changing source files.
- Focused Windows regressions cover exact-version acceptance/rejection and seal
  the shared resolver into source preflight, startup and protected Windows
  package validation. No route, schema, CV-formatting, credential, paid or
  external-call, candidate-data or storage behavior changes. PR #177 merged to
  `master` as `2c06bc5` after 982 tests, 4 skips and 96 subtests passed locally;
  hosted runners did not start because the Actions spending limit was
  exhausted.

## v24.6.357 audit hardening

- Source update execution moves into a preloaded PowerShell transaction so a
  real fast-forward may replace `UPDATE.bat` without corrupting the running
  updater. Automatic updates require a clean exact `master`, validate the
  current installation before fetch, validate the downloaded preflight before
  changing source and retain the established no-reset/no-auto-install safety.
- Python source preflight tries every compatible PATH/fixed candidate and adds
  Python 3.13/3.14 fixed locations, so one stale executable cannot hide a
  healthy installation. The source launcher mirrors those fixed locations.
- Browser responses retain same-origin Salary framing and all existing inline
  scripts/styles while adding compatible default/base/object/form/connect/
  image/font/frame/worker CSP restrictions.
- Protected builds write a standard SHA-256 sidecar beside the colleague ZIP.
  Copied owner-only Nuitka diagnostics replace source/build/user roots with
  placeholders before leaving the temporary build folder.
- Exact pins update pdfplumber 0.11.10, pypdfium2 5.13.0, certifi 2026.7.22 and
  ReportLab 5.0.1. A clean isolated Python 3.14 environment passes 979 tests,
  4 skips and 96 subtests with these versions.
- No route, schema, credential, CV-formatting, candidate-data, paid/external
  call or automatic protected-build boundary changes. PR #176 merged to
  `master` as `d94554c`.

## v24.6.355 manual-only protected-build configuration

- The expensive `Build protected CV Studio packages` workflow has no automatic
  pull-request or push trigger. It retains only `workflow_dispatch`, so an
  owner must deliberately choose **Run workflow** in GitHub Actions.
- The workflow stays disabled in GitHub while this PR is open, preventing the
  configuration PR itself from consuming protected-build minutes. Re-enable it
  only after merge; the committed manual-only trigger then remains in force.
- Local Windows protected builds continue through
  `owner_build_tools/BUILD_PROTECTED_WINDOWS.bat`. The owner will report any
  local failure for correction.
- Ordinary regression CI and Dependabot remain enabled. No application route,
  schema, runtime, dependency, credential, external-call, user-data or
  protected-package-content boundary changed.
- Validation: 973 passed, 4 skipped, 96 subtests; all 19 frontend fixtures;
  24 source-smoke assertions; tracked Python, JavaScript and PowerShell syntax;
  repository/version consistency; and Windows protected-source
  Antiword/Tesseract/adm-zip preflight.

## v24.6.354 Windows source updater and CI reliability corrective

- `UPDATE.bat` validates authorization and the installed Node, Python and
  Tesseract runtime before stopping the current server. Missing dependencies
  leave the running app untouched and give a clear `INSTALL.bat` instruction;
  the updater does not install anything automatically.
- The updater waits for `START_HIDDEN.vbs`'s existing bounded health/identity
  result instead of reporting success immediately. Failures preserve the real
  error code and show the previous/current Git commits plus non-destructive
  GitHub Desktop recovery guidance.
- A bounded, rotating `source_update.log` records update, preflight, stop and
  restart outcomes without credentials or candidate data. Tests use an
  isolated state directory and prove preflight failures do not stop or restart
  CV Studio. A real local Git pull also proves that Windows can replace the
  running `UPDATE.bat` and still complete its stop/restart sequence.
- Source preflight now tries the PATH Python first, matching the real launcher
  and installer. A stale broken fixed-location Python can no longer block an
  otherwise healthy update.
- Regression CI now runs for pull requests and the exact merged `master`
  commit. GitHub actions use maintained runtime versions pinned to immutable
  commit SHAs. Protected-packaging boundary changes trigger a real Windows
  protected build, older runs for the same PR are canceled, and artifact names
  use the repository `VERSION` instead of a stale hard-coded release. The
  current low-memory, single-worker Nuitka build exceeded the former internal
  90-minute ceiling; its compile is now bounded at 120 minutes inside a
  150-minute workflow budget, leaving time for setup, smoke and uploads.
- Repository consistency and protected build validation share one authoritative
  Windows batch-file inventory. The new updater preflight participates in the
  protected source checks while `UPDATE.bat` remains excluded from colleague
  packages.
- Dependabot checks Python packages and GitHub Actions weekly, grouping routine
  minor/patch proposals while leaving major upgrades visible individually.
  All 15 direct Python requirements are exact-pinned so installs are
  reproducible and Dependabot proposals show a precise version change. GitHub
  Dependabot alerts, malware alerts, automatic security updates and grouped
  security updates are enabled; version-update PRs activate when this branch is
  merged.
  npm version updates are intentionally excluded: the only npm dependency,
  `adm-zip`, requires deliberate vetted-tree and aggregate-hash replacement.
- No route, schema, dependency-set, credential, external-call, user-data or
  protected colleague-package-content boundary changed. Five existing tested
  Python dependency ranges were tightened to their installed exact versions.
- Validation: 973 passed, 4 skipped, 96 subtests; all 19 frontend fixtures;
  24-assertion source smoke; tracked Python, JavaScript and PowerShell syntax;
  repository/version consistency; Windows protected-source Antiword/Tesseract/
  adm-zip preflight; and 28 focused updater, workflow, dependency and version
  tests.

## v24.6.353 Windows source updater hardening corrective

- `UPDATE.bat` displays Git's branch output directly instead of expanding a
  branch name into a `cmd.exe` command line. Branch metacharacters such as `&`
  therefore remain data and cannot start another command.
- A missing or unsuccessful `FORCE_STOP.ps1` now stops the update/restart flow
  with a visible error. The updater no longer launches a second instance while
  the previous server may still own port 5000.
- The updater returns the real `CV Studio.bat` startup result, preserving the
  existing authorization and startup failure codes instead of always exiting
  successfully.
- The source-only updater is registered in both repository-consistency and
  protected-source batch-byte validation. Focused tests execute the launcher
  in isolated temporary Git repositories on Windows and cover branch-name
  safety, stop failure and startup failure.
- `UPDATE.bat` remains excluded from protected colleague package contents. No
  route, schema, dependency, credential, external call or user-data boundary
  changes.
- Validation: 964 passed, 4 skipped, 96 subtests; all 19 frontend fixtures;
  24-assertion source smoke; tracked-language syntax; repository/version
  consistency; Windows protected-source Antiword/Tesseract/adm-zip preflight;
  and successful Windows x64, macOS Intel and macOS Apple Silicon CI jobs.

## v24.6.352 Windows watchdog recovery corrective

- A long-standing Windows recovery dead-end was reproduced from the launch
  scripts. When port 5000 still belonged to the exact package but its server
  stopped answering, `WATCHDOG.vbs` called `INSTANCE_PORT.ps1 -Mode Stop`.
  That helper stopped the package watchdog first, then stopped the listener;
  the now-terminated watchdog could never execute its following `LaunchServer`.
- Watchdog-initiated recovery now passes `-PreserveWatchdog`. The helper keeps
  that supervisor alive through the bounded verified-listener stop and restart
  race, so it can launch the replacement. `START_HIDDEN.vbs`, `STOP_CORE.ps1`,
  upgrades and package replacement do not pass the flag and therefore preserve
  the established old-watchdog-first shutdown behavior.
- Focused regressions require both sides of this contract. Windows protected
  source and packaged-tree validation reject a package that loses the
  recovery-only preserve flag.
- No route, schema, dependency, credential, external-call, user-data or
  protected-package boundary changed.
- Validation: 959 passed, 4 skipped, 96 subtests; all 20 JavaScript
  source/fixture scripts; 24-assertion source smoke; repository byte
  consistency; PowerShell parsing; Windows protected-source/Antiword/
  Tesseract/adm-zip/launcher preflight.

## v24.6.351 JobAdder original-CV, candidate-contact and blank-PDF corrective

- Create Profile preserves the browser's original File object, and the backend
  sends deterministic PDF/DOCX/DOC MIME metadata instead of labelling every
  JobAdder Resume upload as generic `application/octet-stream`.
- Multipart boundaries are unique and checked against the uploaded bytes. An
  empty CV is rejected locally before any JobAdder write.
- A candidate that was already found or successfully created is no longer
  reported as wholly missing when only its résumé attachment fails. The row
  keeps the JobAdder profile link, shows JobAdder's readable validation detail,
  and offers a résumé-only retry that does not repeat extraction, paid parsing
  or candidate creation.
- New-candidate original-CV failures are no longer silently swallowed. Remote
  error text is escaped before rendering.
- AI-produced email labels/placeholders and concatenated phone prose are
  normalized before candidate create/update. An invalid email stops locally
  with a clear manual-entry message, while an invalid optional phone is omitted
  instead of producing JobAdder's 422/50-character rejection. Any remaining
  JobAdder validation response exposes its readable field-level reason.
- Near-uniform rendered PDF pages are recorded as intentionally blank. Blank
  trailing pages therefore do not become false partial-extraction warnings,
  while faint, blurry, rotated and otherwise unreadable scans retain the
  existing safety stop. The two owner PDFs reproduce 5,733 and 15,621 recovered
  characters respectively with no partial warning after the correction.
- The owner-supplied DOCX/PDFs and diagnostic were used read-only to verify the
  reported scenarios and are not stored in Git. No live JobAdder write or paid
  AI call was made during implementation or QA.
- No route, schema, dependency or protected-package boundary changed.
- Validation: 956 passed, 4 skipped, 96 subtests; all 19 JavaScript fixtures;
  24-assertion source smoke; real extraction of both supplied PDFs; Windows
  protected-source/Antiword/Tesseract/adm-zip preflight; route, architecture
  and version gates.

## v24.6.350 salary profile-migration safety corrective

- Narrows the startup profile repair to the exact matching packaged-default
  and empty-list pair created by the earlier migration. Rules that genuinely
  predate both profile fields still receive the established additive upgrade.
- A valid explicit empty contribution-profile list with no default is
  preserved, so it continues using the rule's legacy contribution settings.
- Malformed profile values remain unchanged and reach the repository's normal
  handled validation error rather than failing bootstrap with `TypeError` and
  producing HTTP 500.
- No route, schema, dependency or protected-package boundary changed.

## v24.6.349 salary contribution-profile repair

- Startup repairs the specific incomplete stored-rule shape created when the
  packaged Malaysia Resident default contribution profile was added without
  its matching profile list. Only the matching packaged contribution profiles
  are restored; user-approved tax brackets, rates, sources, notes and other
  custom values are preserved.
- Same-year one-click AI tax previews now retain the stored contribution/pass
  profiles when the provider omits them, so publishing an updated tax rule
  cannot recreate the invalid pair.
- Custom rules with a different default profile are not silently rewritten.
- No route, schema, dependency or protected-package boundary changed.

## v24.6.348 KWSP source-access corrective

- The one-click Malaysia updater now uses KWSP's current Mandatory
  Contribution page rather than the obsolete Third Schedule page alias.
- Public KWSP fetches include the browser-compatible request metadata required
  by KWSP's Cloudflare gate. CV Studio does not solve a challenge, retain a
  cookie, authenticate or use a private endpoint.
- Registered fallbacks are residency-appropriate: the October-2025 Third
  Schedule for Resident rules and the official non-Malaysian contribution
  flyer for Non-Resident rules. The successful source URL is recorded.
- No route, schema, dependency or protected-package boundary changed.
- Validation: 943 passed, 4 skipped, 93 subtests; live extraction from all four
  registered KWSP primary/fallback sources; Windows protected-source preflight;
  and 24-assertion source smoke.

## v24.6.347 LHDN source reliability corrective

- Replaces the removed English Malaysia individual tax-rate page with LHDN's
  live `Navigasi HASiL 2026` PDF, which explicitly contains the resident
  individual schedule for YA2025.
- The one-click updater tries only registered official fallback URLs and stores
  the URL that actually supplied the text. It still stops with a clear error
  when every approved tax source is unavailable.
- The existing rule metadata now points to the reachable official LHDN source.
- No route, schema, dependency or protected-package boundary changed.
- Validation: 939 passed, 4 skipped, 93 subtests; live extraction from both
  registered LHDN PDFs; Windows protected-source preflight; and 24-assertion
  source smoke.

## v24.6.344 crawler, JobAdder, Malaysia tax and installer corrective

- AI Crawler has a 330-second internal processing deadline, smaller bounded
  detail/resume budgets and partial-result metadata. It returns useful ranked
  candidates with a visible warning instead of letting optional enrichment run
  into the browser's 420-second timeout.
- JobAdder refreshes shortly before the protected token expiry. Multiple tabs
  reuse the backend refresh lock, transient 429/5xx/network failures preserve
  the connection and retry, and only permanent 400/401/403 refresh failures
  require reconnecting.
- Malaysia YA2025 now includes the official 30% non-resident rule with personal
  reliefs disabled. Tax residence stays separate from EPF/pass profiles:
  Malaysian citizen, PR, EP, RP-T and spousal/long-term-visit pass. EP/RP-T/
  spousal profiles apply the mandatory 2% + 2% rate from October 2025 as a
  clearly labelled annual comparison assumption.
- The tax updater has a one-click next-year draft action using registered
  official LHDN/KWSP or IRAS/CPF sources. It refuses to draft when the sources
  do not explicitly support the requested year, never auto-publishes and keeps
  the existing human review/approval gate.
- Windows receipt verification now uses the same `LOCALAPPDATA` path as the
  Python verifier. Antiword hash and signature checks no longer depend on
  user-controlled `HOME` module auto-loading.
- No route was added or removed; the sealed 116-route contract and SHA remain
  unchanged. No dependency or protected-package boundary changed.
- Validation: 922 passed, 4 skipped, 93 subtests; all JavaScript fixtures;
  Windows protected source/dependency preflight; Python/JavaScript syntax;
  version gates; and diff whitespace review (only expected CRLF version-stamp
  notices remain).

## v24.6.341 OCR partial-failure corrective

- When OCR is unavailable for selected pages in a mixed PDF, `/extract-text`
  keeps independently readable pages and marks the HTTP 200 response as a
  partial extraction with a visible warning and the affected page numbers.
- A name/contact fragment on an OCR-routed cover page cannot make an otherwise
  scanned CV look successful. At least one independently readable page must
  survive, otherwise the established OCR failure remains visible.
- Every interactive `/extract-text` browser workflow shows a persistent partial
  warning. Batch formatting and JobAdder profile creation stop before generating
  or uploading from incomplete text.
- The focused PDF test uses an isolated temporary installation receipt and is
  verified not to change the user's real authorization file.
- No route, schema, dependency, document-trust or package boundary changes.
- Validation: 903 passed, 4 skipped, 2 known unrelated Windows tests
  deselected, 93 subtests; all 16 JavaScript fixtures; protected Windows
  source/dependency preflight; repository consistency; and the 24-assertion
  live source smoke.

## v24.6.340 HTML Boolean-highlight review corrective

- Converted-DOC/DOCX HTML preview phrases are matched per visual paragraph or
  table cell, so bold, italic and other Word run boundaries no longer hide a
  multi-word Boolean phrase.
- The browser maps each logical match back to its contributing DOM text nodes
  and highlights every visual fragment without changing the source wording.
- The 60,000-character / 8,000-node scan boundary is enforced before accepting
  each node; one oversized Word run can no longer bypass the total character
  budget and multiply browser work across up to 150 Boolean terms.
- Focused coverage uses a phrase split across three DOM text nodes and a single
  70,000-character run. No route, schema, backend document-trust boundary,
  dependency or package boundary changes.
- Validation: 899 passed, 4 skipped, 1 known unrelated Windows
  receipt-isolation test deselected, 93 subtests; all 15 JavaScript fixtures;
  protected Windows source/dependency preflight; repository consistency; and
  the 24-assertion live source smoke.

## v24.6.339 legacy-DOC preview and highlight corrective

- PR #154 was merged to `master` as `5e4da48` at v24.6.339.

- Verified Antiword remains mandatory and always runs first. Only a completed
  rejection of the exact document can use the existing Microsoft Word or
  LibreOffice conversion exception; dependency and execution-time trust
  failures remain fatal.
- AI Crawler and `/preview-file` reuse the validated converted DOCX for visual
  HTML fallback when LibreOffice PDF rendering is unavailable, rather than
  dropping the recruiter into unverified text-only recovery.
- Converted Office HTML previews receive direct Boolean highlights. Literal
  matching also tolerates NBSP spacing, Unicode ligatures, soft hyphens and
  line-wrap hyphenation while preserving original-text highlight offsets.
- Foreground scanned/coordinate-less PDF pages can reuse the mandatory
  Tesseract installation for a bounded three-page, 28-second visual word-box
  layer. Background prefetch remains OCR-free.
- No route, schema, security gate, dependency requirement or protected-build
  package boundary changes.
- Validation: 899 passed, 4 skipped, 1 unrelated Windows receipt-isolation
  test deselected, 93 subtests; all 15 JavaScript fixtures; route/version and
  protected Windows source gates; repository consistency; 24-assertion live
  smoke; genuine Yan Yen Fen and Kwong legacy-DOC preview checks.

## v24.6.279 legacy-DOC and CV-formatting corrective

- PR #98 was squash-merged to `master` as `a18cda4` at v24.6.279.
- `/extract-text` still requires and runs the exact verified Antiword runtime
  first for every genuine legacy Word OLE payload. A missing, untrusted or
  non-functional runtime retains the structured 424/install-repair contract,
  including when execution-time verification fails after preflight.
- When verified Antiword rejects only the supplied document, CV Studio can now
  convert that document to a temporary macro-free DOCX through locally
  installed Microsoft Word on Windows, or LibreOffice where available. The
  resulting OOXML package is safety-validated and parsed through the existing
  DOCX table/list path before it can satisfy extraction. Word disables automatic
  link updates before opening the untrusted input. Failed and timed-out
  converters terminate the wrapper process tree and separately recorded Word
  process.
- Genuine Windows testing used the owner-supplied Antiword-incompatible DOC:
  Microsoft Word conversion produced a valid DOCX and the real `/extract-text`
  route returned 19,247 characters with status 200. The private
  source document and converted output are not committed.
- Education placeholders such as `No Degree`, `Not specified` and `N/A` are
  omitted deterministically, including after stripping a `No Degree:` prefix.
  Real qualification wording, including
  `Non-Degree Certificate`, remains unchanged.
- The owner-marked Isaac comparison is now deterministic rather than
  provider-dependent: adjacent continuous Dec 2015-Mar 2021 Unilever roles and
  May 2008-Oct 2011 DKSH roles share one employer block, while the separate
  Johor/earlier Unilever entries remain separate. Employer blocks and their
  dated roles are sorted newest-first, so Jun 2014-Nov 2015 Nestle precedes
  Sep 2013-May 2014 Unilever even if provider order is inconsistent.
- Education month precision is restored from nearby source evidence only when
  both endpoint years match the parsed entry; a single graduation year is not
  expanded (`06/2004-05/2008` becomes
  `Jun 2004 to May 2008`). A provider-leading `to` before a lone graduation
  year is removed (`to 2001` becomes `2001`), while a missing date remains empty
  so the institution renders without a date separator. Core Expertise arrays,
  newline lists and comma-separated strings normalize to real Word bullets.
- The owner-supplied Faizal outputs exposed literal bare enumerators beside
  Word's own list marker. Lower-case `a.`/`i.`/`ii.`/`a-` and numeric `1-`
  markers are now stripped while `3.5`, `5-star`, `-5%`, `i.e.`, capitalised
  initials and real year ranges remain protected. Source-derived nesting levels
  still render at their intended Word indents.
- No route, guard, schema, JobAdder or Lead Finder contract changes. CV wording
  remains source-preserving; only grouping, ordering, date precision and visible
  source-marker structure are normalized.
- The owner-supplied Kwong legacy DOC contains no GitHub text or URL, but the
  provider emitted `https://github.com/unknown`; source-aware normalization now
  removes any ungrounded GitHub path. The JobStreet/SiVA `Retrieved Resumes` /
  `Date Applied` routing line is removed recursively wherever it is mapped.
- The same source contains 13 Project Involvement History items and 16
  Participated Training Programme items. Both bracketed lists are recovered
  deterministically in exact source order, and training entries already placed
  in certifications are de-duplicated before output.
- The v24.6.279 review corrective rejects the known `github.com/unknown`
  placeholder even when `/generate-docx` has no source text, while retaining
  other source-free links and accepting terminal sentence punctuation when a
  real source GitHub path is available. Inline JobStreet/SiVA metadata after a
  `|` item separator is removed, and recovered multi-item skill sections render
  as bullets in the browser preview as well as the Word document.
- The v24.6.280 post-merge corrective stops allowlisted Project/Training source
  recovery at recognized ordinary CV headings, preventing later Education,
  References or similar sections from being absorbed. It also aligns
  `AGENTS.md` with the owner-authorized, Antiword-rejection-only Word/LibreOffice
  fallback. The separate Summary-format experiment remains local and is not
  included.
- The v24.6.281 follow-up adds common combined section-heading boundaries,
  including Education & Certification, Professional Qualifications, Courses &
  Training, and Professional Affiliations, so their later content cannot be
  absorbed into a recovered Project/Training list.
- The v24.6.283 review corrective treats literal `AND` and `&` the same in
  combined source headings while preserving explicitly marked project/training
  items whose wording resembles a heading. Undated current employers and roles
  keep their source positions; only month-precise touching stints with exact or
  known broad-location employer names can merge, so year-only dates and short
  business-unit suffixes stay separate. Core Expertise remains bulleted without
  splitting commas inside an already-structured item.

## Phase 7B-8 JobAdder typo-correction extraction

- `cvstudio_ja_typos.py` is a new pure-helper module holding seven JobAdder
  recruitment/salary typo-correction functions and their four data tables, moved
  verbatim from `app.py`: bounded edit distance (`_ja_edit_distance_limited`),
  casing preservation (`_ja_case_like`), alias/fuzzy typo targeting
  (`_ja_recruitment_typo_target`), and the field-level corrections for screening
  notes, notice-period text and salary strings (`_ja_correct_recruitment_typos`,
  `_ja_correct_screening_field_typos`, `_ja_correct_notice_typos`,
  `_ja_salary_normalize_recruiter_typos`), plus `_JA_RECRUITMENT_TYPO_ALIASES`,
  `_JA_RECRUITMENT_FUZZY_TERMS`, `_JA_RECRUITMENT_PROTECTED_WORDS` and
  `_JA_SALARY_TYPO_RULES`.
- The cluster is a clean pure closure: the only import is the standard library
  `re`, there are no app-function dependencies, and the four data tables are used
  only inside the cluster. `app.py` re-exports all eleven names, so no caller
  changes and the sealed route SHA is unchanged.
- The `ja_typos` module joins the acyclic graph as a `domain`-layer dependency of
  the legacy web shell. Registered in `cvstudio_architecture.py`,
  `owner_build_tools/build_protected.py`, and the Phase 7A foundation names tuple.
- Behaviour preservation is proven by a new characterization net (edit distance,
  casing, alias targeting, multi-typo text correction, screening-field and
  notice/salary corrections) plus a re-export identity assertion.
- Validation passed the full local Python suite (542 passed, 9 platform-gated
  Antiword skips; the single pre-existing Antiword extraction failure is
  Linux-only and reproduces byte-identically on master).

## Phase 7B-7 Spider JD-scoring and candidate-fit extraction

- `cvstudio_spider_score.py` is a new pure-helper module holding twelve Spider
  JD-scoring and candidate-fit functions moved verbatim from `app.py`, plus the
  `_SPIDER_JD_HEADING_PREFIX_RE` heading regex they use: JD heading/section
  parsing and relevance-term extraction (`_spider_strip_jd_heading_prefix`,
  `_spider_jd_heading_section`, `_spider_jd_scoring_lines`,
  `_spider_jd_relevance_terms`), fit-term handling (`_spider_ignored_fit_term`,
  `_spider_strip_context_fit_term`, `_spider_context_only_fit_term`), weighted
  term coverage (`_spider_weighted_coverage`), the candidate fit-percentage and
  overall item score (`_spider_match_fit_percent`, `_spider_item_score`), and
  JobAdder option-payload flattening (`_spider_option_fallbacks`,
  `_spider_extract_option_values`).
- The cluster is a clean pure closure: it depends only on the standard library
  (`re`) and the already-extracted `cvstudio_spider_boolean` — no Flask, app
  globals, network, provider, or Antiword/OCR access. The interleaved `.doc`/OCR
  functions and the `_spider_preview_name`/`jobadder_spider_options` route stay
  in the shell. `app.py` re-exports the twelve names (and the heading regex), so
  no caller changes and the sealed route SHA is unchanged.
- The `spider_score` module joins the acyclic graph as a `domain`-layer
  dependency of `spider_boolean` and the legacy web shell. Registered in
  `cvstudio_architecture.py`, `owner_build_tools/build_protected.py`, and the
  Phase 7A foundation names tuple.
- Behaviour preservation is proven by a new characterization net (JD parsing,
  weighted coverage, `match_fit_percent`/`item_score` on a representative
  candidate, option flattening) plus a re-export identity assertion.
- Validation passed the full local Python suite (529 passed, 9 platform-gated
  Antiword skips; the single pre-existing Antiword extraction failure is
  Linux-only and reproduces byte-identically on master), including the module
  graph and route-contract tests.

## Phase 7B-6 Spider candidate data-shaping extraction

- `cvstudio_spider_summary.py` is a new pure-helper module holding ten Spider
  candidate data-shaping functions moved verbatim from `app.py`: numeric
  coercion (`_spider_number`), salary/notice/card snapshots
  (`_spider_salary_snapshot`, `_spider_notice_snapshot`, `_spider_card_fields`,
  `_spider_custom_field_value`), record-identity keys
  (`_spider_custom_record_key`, `_spider_work_record_key`), and the summary/detail
  deep-merge (`_spider_merge_record_lists`, `_spider_merge_missing_json`,
  `_spider_merge_candidate_summary_and_detail`).
- The cluster is a clean pure closure: it depends only on the standard library
  and the already-extracted `cvstudio_spider_boolean` (`_spider_flatten`,
  `_spider_normalized_record_label`) — no Flask, app globals, network, or
  provider access. `app.py` re-exports the ten names, so no caller changes and
  the sealed route URL/method/endpoint SHA-256 is unchanged (pure-helper move,
  no route touched).
- The `spider_summary` module joins the acyclic module graph as a `domain`-layer
  dependency of `spider_boolean` and of the legacy web shell. Registered in
  `cvstudio_architecture.py`, `owner_build_tools/build_protected.py`, and the
  Phase 7A foundation names tuple.
- Behaviour preservation is proven by a new characterization net written before
  the move (expected values captured from the original `app._spider_*`
  functions) and green after it, plus a re-export identity assertion.
- No new feature, route, schema, credential handling or release is included.
  The remaining pure Spider cluster (JD-scoring / fit-term matching,
  ~10,160–11,100) is a self-contained follow-up slice; the `.doc`/OCR cluster
  stays in the shell.
- Validation passed the full local Python suite (519 passed, 9 platform-gated
  Antiword skips; the single pre-existing Antiword extraction failure is
  Linux-only and reproduces byte-identically on master), including the module
  graph and route-contract tests.

## v24.6.253 Phase 7B-5c JobAdder candidate JSON write extraction

- Exact source baseline is merged Phase 7B-5b commit
  `e93be4d7fc542cde7f8a3099f7ee5d0e457965fb`.
- `cvstudio_jobadder_write.py` is a new composed `JobAdderWriteService` behind
  the `/jobadder/create_candidate` and `/jobadder/update_candidate` endpoints.
  The payload construction (email flattening, empty-value stripping, candidateId
  handling) and the non-retryable POST/PUT transport calls are a verbatim move
  from `app.py`.
- The `_ja_critical_write_route` decorator stays on the delegating routes in
  `app.py`, so the critical-write concurrency guard and non-retry semantics
  (`safe_to_retry=False`) are unchanged. The application keeps ownership of the
  OAuth token lifecycle and the `JobAdderClient` transport; the service reaches
  the token refresh, request body and transport only through injected callbacks.
- The two routes become thin delegators, so the sealed route
  URL/method/endpoint SHA-256 stays byte-identical to the Phase 7A baseline
  (`f8378b6f3424476eb0683af8e0bbb06ed430675abfe11b74ebed5ab361a20bc9`) and the
  route count stays at 108. The `jobadder_write` module joins the acyclic module
  graph (now sixteen modules) as a `domain`-layer dependency of `external_clients`.
- Behaviour preservation is proven by a new Phase 7B-5c write characterization
  net (POST/PUT endpoint, non-retryable flags, payload construction) written
  before the move and green after it, plus the Phase 7B-5a unauthenticated
  coverage. The uploads and the OAuth token lifecycle are deferred to later
  slices; the token lifecycle also retains its existing Phase 3 sign-out and
  account-state regression coverage.
- No new feature, route, schema, credential handling or release is included.
- Validation passed 207 Python tests (the one pre-existing Antiword extraction
  failure and nine platform-gated Antiword skips are Linux-only and match
  master), all ten frontend fixtures, 24 source-smoke assertions, tracked
  Python/JavaScript/POSIX syntax, and repository consistency and whitespace
  checks.

## v24.6.252 Phase 7B-5b read-only JobAdder proxy extraction

- Exact source baseline is merged Phase 7B-5a commit
  `88ced4a1655148bd5653376826b4a5f6bb3b21b8`.
- `cvstudio_jobadder_read.py` is a new composed `JobAdderReadService` behind the
  read-only `/jobadder/api_info`, `/jobadder/search_candidate`,
  `/jobadder/lists`, `/jobadder/get_candidate` and `/jobadder/debug_endpoints`
  endpoints. The logic is a verbatim move from `app.py`.
- The application keeps ownership of the JobAdder OAuth token lifecycle, the
  shared credentials store and the `JobAdderClient` transport; the service
  reaches the token refresh, transport, public-info projection, credentials
  store and API-path helper only through injected callbacks resolved at call
  time, and performs no writes.
- The five routes become thin delegators, so the sealed route
  URL/method/endpoint SHA-256 stays byte-identical to the Phase 7A baseline
  (`f8378b6f3424476eb0683af8e0bbb06ed430675abfe11b74ebed5ab361a20bc9`) and the
  route count stays at 108. The `jobadder_read` module joins the acyclic module
  graph (now fifteen modules) as a `domain`-layer dependency of `external_clients`
  and of the legacy web shell.
- Behaviour preservation is proven by the Phase 7B-5a JobAdder coverage net,
  which was written before this extraction and stays green after it.
- No new feature, route, schema, credential handling, release or backburner item
  is included; this is the first (lowest-risk, read-only) slice of the JobAdder
  extraction. Token lifecycle and candidate writes follow in later slices.
- Validation passed 203 Python tests (the one pre-existing Antiword extraction
  failure and nine platform-gated Antiword skips are Linux-only and match
  master), all ten frontend fixtures, 24 source-smoke assertions, tracked
  Python/JavaScript/POSIX syntax, and repository consistency and whitespace
  checks.

## v24.6.251 Phase 7B-4 AI secret-store domain extraction

- Exact source baseline is merged Phase 7B-3 commit
  `1e75737cb83e32d4f70d100c0f77a3de720cca9c`.
- `cvstudio_secrets.py` is a new composed `SecretsService` behind the
  `/secure-secrets/info`, `/secure-secrets/save` and `/secure-secrets/clear`
  endpoints. The slot validation, in-place mutation and storage bookkeeping are
  a verbatim move from `app.py`.
- Unlike the earlier fully-isolated extractions, this domain operates on the
  shared, machine-bound AI secret store and the `_cv_secure_save`/
  `_cv_secure_delete` primitives (also used by the JobAdder and OneNote
  credential stores). Those stay in `app.py`; the service reaches them only
  through injected callbacks resolved at call time, so no credential handling is
  duplicated and the shared store keeps a single owner.
- The three routes become thin delegators, so the sealed route
  URL/method/endpoint SHA-256 stays byte-identical to the Phase 7A baseline
  (`f8378b6f3424476eb0683af8e0bbb06ed430675abfe11b74ebed5ab361a20bc9`) and the
  route count stays at 108. The `secrets` module joins the acyclic module graph
  (now fourteen modules) as a `domain`-layer dependency of the legacy web shell.
- Characterization tests were written before the move and swap the shared store
  and secure save/delete primitives for in-memory fakes, so they exercise the
  info/save/clear behaviour (including unknown-slot rejection, blank clearing
  and backend deletion when empty) without writing real credentials.
- No new feature, route, schema, credential handling, release, protected
  package or backburner item is included.
- Validation passed 196 Python tests (seven new Phase 7B-4 cases; the one
  pre-existing Antiword extraction failure and nine platform-gated Antiword
  skips are Linux-only and match master), all ten frontend fixtures, 24
  source-smoke assertions, tracked Python/JavaScript/POSIX syntax, and
  repository consistency and whitespace checks.

## v24.6.250 Phase 7B-3 static web-asset domain extraction

- Stacked on the unmerged Phase 7B-2 branch `claude/phase-7b2-runtime-service`;
  rebase onto `master` once Phase 7B-1 and 7B-2 merge.
- `cvstudio_web_assets.py` is a new composed `WebAssetsService` behind the
  `/vendor/<path>`, `/cv_studio_logo.png`, `/cv_studio.ico` and `/favicon.ico`
  endpoints. The static-file serving, the vendor path-traversal rejection and
  the favicon fallback are a verbatim move from `app.py`; the module receives
  the source directory through an injected callback and never imports the
  application or shared mutable state.
- The four routes become thin delegators, so the sealed route
  URL/method/endpoint SHA-256 stays byte-identical to the Phase 7A baseline
  (`f8378b6f3424476eb0683af8e0bbb06ed430675abfe11b74ebed5ab361a20bc9`) and the
  route count stays at 108. The `web_assets` module joins the acyclic module
  graph (now thirteen modules) as a `domain`-layer dependency of the legacy web
  shell.
- Characterization tests were written before the move and capture the served
  bytes for the vendor asset, logo, icon and favicon-fallback, plus the
  security-sensitive path rejection (invalid characters and missing assets both
  return the shared NOT_FOUND envelope).
- No new feature, route, schema, credential handling, release, protected
  package or backburner item is included.
- Validation passed 189 Python tests (six new Phase 7B-3 cases; the one
  pre-existing Antiword extraction failure and nine platform-gated Antiword
  skips are Linux-only and match master), all ten frontend fixtures, 24
  source-smoke assertions, tracked Python/JavaScript/POSIX syntax, and
  repository consistency and whitespace checks.

## v24.6.249 Phase 7B-2 runtime liveness domain extraction

- Stacked on the unmerged Phase 7B-1 branch `claude/phase-7b1-startup-service`;
  rebase onto `master` once Phase 7B-1 merges.
- `cvstudio_runtime.py` is a new composed `RuntimeService` behind the read-only
  `/status`, `/instance`, `/instance-id` and `/ping` endpoints. The liveness and
  process-identity logic is a verbatim move from `app.py`; the module receives
  the version, install root, root hash, instance id and port through injected
  callbacks and never imports the application or shared mutable state.
- The four routes become thin delegators, so the sealed route
  URL/method/endpoint SHA-256 stays byte-identical to the Phase 7A baseline
  (`f8378b6f3424476eb0683af8e0bbb06ed430675abfe11b74ebed5ab361a20bc9`) and the
  route count stays at 108. The `runtime` module joins the acyclic module graph
  (now twelve modules) as a `domain`-layer dependency of the legacy web shell.
- Characterization tests were written before the move and capture the exact
  status/instance/instance-id/ping payloads, status codes and launcher headers.
- No new feature, route, schema, credential handling, release, protected
  package or backburner item is included.
- Validation passed 183 Python tests (five new Phase 7B-2 cases; the one
  pre-existing Antiword extraction failure and nine platform-gated Antiword
  skips are Linux-only and match master), all ten frontend fixtures, 24
  source-smoke assertions, tracked Python/JavaScript/POSIX syntax, and
  repository consistency and whitespace checks.

## v24.6.248 Phase 7B-1 startup domain extraction

- Exact source baseline is merged Phase 7A commit
  `54298b9b6a822e1f36c9c101f1ff4edc9c7e835f`.
- `cvstudio_startup.py` is a new composed `StartupService` behind the existing
  `/startup/status`, `/startup/enable` and `/startup/disable` endpoints. The
  cross-platform login-item logic is a verbatim move from `app.py`; the module
  receives the install root and instance id through injected callbacks and never
  imports the application or shared mutable state.
- The three routes become thin delegators, so the sealed route
  URL/method/endpoint SHA-256 is byte-identical to the Phase 7A baseline
  (`f8378b6f3424476eb0683af8e0bbb06ed430675abfe11b74ebed5ab361a20bc9`) and the
  route count stays at 108. The `startup` module is registered in the acyclic
  module graph (now eleven modules) as a `domain`-layer dependency of the
  legacy web shell.
- Characterization tests were written before the move and capture the exact
  status/enable/disable contracts, including the shared error-envelope
  enrichment on the graceful "unsupported platform" path.
- No new feature, route, schema, credential handling, release, protected
  package or backburner item is included.
- Validation passed 178 Python tests (five new Phase 7B-1 cases; one pre-existing
  Antiword extraction test fails only where no Linux Antiword binary is vendored,
  identically to master, and nine platform-gated Antiword tests skip on Linux),
  all ten frontend fixtures, 24 source-smoke assertions, tracked Python,
  JavaScript and POSIX syntax, and repository consistency and whitespace checks.
- Native Windows/macOS startup mutation is covered by the platform CI gates; the
  graceful non-native path is exercised directly.

## v24.6.247 Phase 7A modular-monolith foundation

- Exact source baseline is clean `origin/master` commit
  `a6b35d2e0cad977e737622ed7d10e451ed5f7de3`.
- The owner explicitly authorized modular-monolith work while retaining the
  Python/Flask backend and JavaScript frontend; no language rewrite is included.
- `cvstudio_architecture.py` is the app-independent composition root. It owns a
  validated, acyclic inventory of the existing platform, storage, job, AI-cost,
  external-client, document, diagnostic, storage-HTTP and legacy-web modules.
- `app.py` remains the temporary compatibility web shell. It registers every
  established route and callback, then seals the application against the exact
  route URL/method/endpoint digest, five ordered request guards and 80 MiB
  request boundary.
- Existing extracted modules remain unable to import the legacy `app` shell.
  Future milestones can move one domain at a time behind this composition seam.
- Preserve exactly 108 routes, five request guards, 18 compatibility
  signatures, SQLite schema 10, journal schema 1, external-service behavior,
  mandatory Antiword/Tesseract boundaries and native packaging behavior.
- No new feature, route, schema, credential handling, server replacement,
  release, protected package or backburner item 4/7/8 is included.
- Focused review corrected the route canonicalizer so Flask's implicit
  `HEAD`/automatic `OPTIONS` methods are ignored while the two explicitly
  supported OCR `OPTIONS` methods remain part of the sealed contract.
- Validation passed 21 focused Phase 7A/4/5A tests across the implementation
  and final correction, 173 complete Python tests with one expected skip, all
  ten frontend fixtures, 24 source-smoke assertions, tracked Python,
  JavaScript, PowerShell and POSIX syntax, Windows x64 owner preflight with
  trusted functional Antiword and Tesseract, repository consistency and
  whitespace checks.
- Native macOS execution and protected packaging were not rerun because this
  milestone changes neither native dependency nor packaging behavior.

## v24.6.246 mandatory macOS Antiword and Tesseract

- Exact base is corrected v24.6.245 PR head
  `4710236e08775609462e8b04ca2213c13a61938b`.
- Official R-universe Antiword 1.3.5 Intel and arm64 artifacts are pinned to
  upstream commit `51441d45283512081c08010835b8002af79fe5e6`, bundled separately,
  complete-manifest verified and executed from a private immutable snapshot.
- Windows and macOS installers now fail closed unless Tesseract executes and
  reports English language data. macOS installs it through Homebrew when
  available; otherwise setup stops with explicit repair instructions.
- GitHub CI and protected builds cover native Windows x64, macOS Intel and
  macOS Apple Silicon. No release or macOS support claim exists until both Mac
  jobs pass functional fixture and protected smoke validation.

## v24.6.245 long-CV output and access corrective

- Exact base: merged Phase 6C source v24.6.244 at
  `c75aa20c5a99ea5e9af84204a19703c90e0c2d36`.
- Long or role-dense CV parsing now uses one shared policy: backend provider
  timeout 180/300 seconds and browser timeout 210/330 seconds, with long mode
  selected at 18,000 characters or eight standalone responsibility/achievement
  markers. Single format, batch format and JobAdder Create Profile all use it.
- The parser prompt forbids invented titles and serialized structured groups.
  Backend, preview and DOCX-generator normalizers decode valid JSON-looking
  bullet groups, canonicalize responsibility/achievement headings, remove only
  bounded inference annotations, filter empty sections and remain idempotent.
- The single independent review found two bounded normalization gaps. Plain
  top-level responsibility/achievement labels now become section objects in
  backend, preview and DOCX paths without promoting content inside an existing
  group. Parenthetical `assumed`, `guessed` and `likely` annotations tied to
  duties, responsibilities, content or context are also suppressed, while
  ordinary explicit titles remain unchanged.
- DOCX headings use keep-next behavior, structured groups always render as
  headings plus real bullets, empty role titles and empty sections are omitted,
  and the company name is never used as a missing position fallback.
- CV Scoring is the final feature tab and is protected by version-scoped casual
  access code `1996`. AI Crawler is unlocked and no longer prompts for or sends
  a feature password; the backend compatibility hook permits local requests.
- Validation completed without live/paid AI: 162 Python tests, all ten frontend
  fixtures, 24 source-smoke assertions, Python/JavaScript/PowerShell syntax,
  owner preflight, repository consistency, whitespace and a rendered real-DOCX
  visual inspection of the supplied corruption pattern.
- The pre-review v24.6.245 owner/source archive remains immutable at commit
  `956eb4d8faf96980a7c4c12739f00a985b6ca2ef` and is superseded by the corrected
  PR head. It must not be used as the final source artifact or overwritten.
- Windows Antiword preflight passed. No protected colleague package or macOS
  artifact/support claim is produced; macOS remains deferred.

## Phase 6C authorization, inventory and bounded implementation

- The owner authorized Phase 6C only from exact clean Cloud HEAD
  `fee134792f179de9d75d0de24afe08c27fb526c4`; the candidate controller branch
  identity is `agent/v24.6.244-phase-6c-adaptive-memory`. Installed identity
  remains v24.6.243 and no release, tag or protected package is created.
- End-to-end inventory confirmed preview mode is a schema-10 allowlisted browser
  setting hydrated through the Phase 2B bridge; Auto reads redacted same-origin
  runtime memory diagnostics, applies Low/Standard/High cache and prefetch limits,
  trims insertion-ordered Map caches, releases evicted DOM URLs, and shares the
  existing backend clear, prefetch concurrency, persistent-job, reload and
  JobAdder account-transition invalidation boundaries. Manual profiles remain
  authoritative and offline operation remains local-Flask-only.
- The concrete gap was that Auto treated memory globals as indefinitely trusted
  and the status omitted diagnostic freshness/reason and exact active limits.
  Auto now accepts only positive, internally consistent memory data received in
  the last five minutes, otherwise resolves to Standard with an explicit
  stale/unavailable reason. Lower resolutions trim immediately; reapplying an
  unchanged selected/resolved profile retains caches rather than repeatedly
  clearing them. The Settings status states selected mode, resolved profile,
  reason, freshness/age, current browser/backend limits and usage.
- Job Fit inventory confirmed the numeric score remains normalized weighted
  coverage of JD, Boolean/must-have, role and nice-to-have terms, with existing
  native-Boolean and discovery floors. Location, work arrangement, language,
  education, salary, industry and target companies remain excluded; hard
  eligibility, resume-budget selection, profile/detail/resume source labels,
  response aliases, sorting and rendering boundaries are unchanged.
- The concrete explanation gaps were hidden pre-floor coverage and ambiguous
  unavailable evidence. Additive breakdown metadata and escaped rendering now
  state the points/coverage before a native-Boolean floor, flag components with
  no visible evidence, retain discovery-floor disclosure, and explicitly say
  when no resume text contributed. No score, ranking, filter or response alias
  changed. Focused Python and browser characterization fixes these contracts.
- Exactly 108 routes, five guards, 18 compatibility signatures, SQLite schema
  10, journal schema 1, Phase 6A eager order and Phase 6B jsPDF loading/retry
  remain preserved. GitHub Windows-x64 CI remains the native platform gate.
- Independent review found that freshness was recalculated only on another
  interaction. Auto now owns one cancellable deadline for its trusted sample;
  expiry reapplies Standard limits, trims payload/DOM caches, updates the active
  prefetch budget and rerenders the decision/statistics. Selecting a manual
  profile cancels the deadline, and unchanged resolutions still avoid clearing.

## Phase 6B authorization, inventory and bounded implementation

### Entry and immutable boundaries

- The owner authorized Phase 6B lazy loading only from exact Codex Cloud HEAD
  `00235a6923082195b15224febb279c5a9a30f040`. The platform-selected `master`
  provenance, internal `work` branch and clean worktree satisfy the corrected
  cloud entry gate; absent remote and tag refs are explicitly non-blocking.
- Installed source identity remains v24.6.243. No backend, route, schema,
  installer, release, tag, macOS claim or protected artifact changed.
- Exactly 108 routes, five ordered guards, 18 compatibility signatures,
  SQLite schema 10 and Phase 5A journal schema 1 remain mandatory. Phase 6C,
  Phase 7 and backburner items 4/7/8 remain excluded.

### Frontend and packaging inventory

- `index.html` retains the Phase 6A eager classic-script boundaries for local
  API transport, pinned navigation and heartbeat/reconnect startup. Those
  scripts, their globals, DOM/listener order and startup timing remain eager.
- The tracked `vendor/cvstudio` tree contained those three Phase 6A modules;
  the only other browser JavaScript asset was the local, tracked
  `vendor/jspdf.umd.min.js`. It was eagerly parsed before application startup
  but is referenced only by the four explicit PDF-export actions: Blind JD,
  Company Profile, CV Scoring and The Owl.
- The four entry points already owned their source-data readiness checks,
  established global names and visible jsPDF-unavailable errors. jsPDF has no
  localStorage/IndexedDB, DOM listener, API transport or startup dependency.
  Word/DOCX generation, all browser stores and every non-PDF feature remain
  unchanged.
- Flask's existing offline vendor route serves both files. Owner protection
  already validates, transforms, hashes, replaces and smoke-fetches every file
  named by `FRONTEND_MODULES`, while the complete vendor tree includes jsPDF.
  Phase 6B extends that list only for the small loader and retains the existing
  jsPDF packaged URL. No remote runtime or CDN is introduced.

### Selected lazy boundary and behavior

- Only local jsPDF is lazy-loaded. A small eager classic-script loader keeps
  the existing global model, creates the jsPDF script on the first valid PDF
  export action and resumes that same global export function after readiness.
- Concurrent first entries share one network request and each action resumes
  once. Ready subsequent entries execute synchronously. A failed or incomplete
  load removes its script, clears in-flight state, preserves each established
  visible error and permits the next entry to retry without stale promises,
  duplicate listeners or partially initialized loader state.
- The loader itself is deterministic and idempotent and has no listeners,
  storage access, backend request or feature initialization. No startup-
  critical Phase 6A module or non-PDF asset was deferred.
- Pre-change characterization recorded the eager dependency and all four
  global PDF/error entry contracts. The Phase 6B fixture covers source
  discovery, on-demand timing, concurrent entry, synchronous ready behavior,
  visible failure cleanup and retry. Existing Blind JD export coverage and
  Phase 6A protected-asset coverage remain in force.

### Cloud validation and focused review

- The single complete Python discovery ran all 153 tests (eight skipped). One
  Windows-only Antiword functional-route assertion returned the expected
  dependency-not-ready HTTP 424 instead of 200 because Linux cannot execute
  the pinned Windows binary; the other 152 tests completed without a Phase
  6B failure. The same platform boundary prevented full owner Windows-x64
  Antiword preflight after Python and all five frontend-module syntax checks
  passed. No native Windows or PowerShell result is claimed.
- All eight frontend fixtures passed, including Phase 6A and the new Phase 6B
  fixture. Live source smoke passed all 24 assertions. Tracked Python,
  JavaScript and POSIX syntax, repository consistency and whitespace checks
  passed in Linux.
- The one focused self-review compared the complete change against exact base
  `00235a6923082195b15224febb279c5a9a30f040`. It found that one throwing
  resumed export could prevent another concurrent queued export from running;
  isolated callback draining and a focused regression corrected that finding.
  Only the affected Phase 6B fixture, loader syntax and whitespace check were
  rerun, and all passed. GitHub Windows-x64 CI remains the platform gate after
  the controller creates the draft pull request.
- The single independent review of draft PR #5 then found one concrete retry
  mismatch: all four export guards accepted a partial `window.jspdf` namespace
  even though the loader requires `window.jspdf.jsPDF`. The guards now use the
  loader's exact readiness predicate. Focused coverage retains a partial
  namespace after an incomplete load and proves that the next attempt reloads
  and succeeds. The Phase 6B fixture, affected JavaScript syntax and whitespace
  checks passed after this bounded correction; no broader review loop ran.

## Phase 6A authorization, entry verification and bounded plan

### Authorization and immutable boundary

- The owner explicitly authorized Phase 6A frontend modularisation only from
  exact clean GitHub-backed master commit
  `1fbcb19bdebf5cb99a975b5b732278be242ff086` on branch
  `agent/phase-6a-frontend-modularisation`.
- Local `HEAD`, fetched `origin/master` and the merge base all resolved to the
  exact authorized commit before tracked files changed. The private remote is
  `khoryik96-creator/CV_Studio_Main`.
- The annotated immutable `v24.6.243` tag remains object
  `128bfc429d292c0ecfca34d1b2b474f7c80ee08e` and peels to the required release
  commit `2507c096eb11c2e7d1361e0c1f7f2609abf625b8` locally and on the remote.
- Installed source identity remains v24.6.243. This milestone cannot create or
  mutate a tag, release ZIP, handover, immutable release artifact, protected
  package or macOS artifact and cannot claim a protected/native build.
- Exactly 108 routes, five ordered guards, 18 compatibility signatures,
  SQLite schema 10, Phase 5A journal schema 1, security/credential/paid-call
  boundaries, provider retry/non-replay behavior and the v24.6.239 macOS
  boundary remain immutable.
- Phase 6B lazy loading, Phase 6C adaptive-memory/explainable-fit behavior,
  Phase 7/backburner items 4/7/8, backend behavior and all unrelated workflow
  changes remain excluded.

### Read and unchanged-source entry gate

- `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md`, `IMPLEMENT.md`,
  `BACKBURNER_ROADMAP.md`, the v24.6.243 Phase 6 handover/corrective QA and all
  directly required v24.6.242 through Phase 2A handover/QA records were read
  before implementation.
- The first unchanged Python discovery exposed only the documented ignored
  working dependency: owner-local DOCX generation could not resolve
  `adm-zip`. The exact pinned 0.5.17 dependency was restored with the normal
  no-script/no-lockfile install; no tracked byte changed.
- The qualifying unchanged-source gate then passed 151 Python tests with
  `ResourceWarning` treated as an error, all six established frontend fixture
  files, 24 live source-smoke assertions, tracked Python/JavaScript/Bash/
  PowerShell syntax, both complete inline scripts, owner Windows-x64 source
  validation/preflight including genuine bundled Antiword extraction and
  vetted `adm-zip`, repository consistency and Git whitespace validation.
- No live credential, provider request, paid call, remote mutation or private
  customer/candidate data was used.

### Complete frontend inventory relevant to Phase 6A

- `index.html` is 19,588 lines with one bundled jsPDF dependency and two
  classic inline scripts. The first inline block is the 16,000-line application
  surface; the second owns reconnect heartbeat plus final startup listeners.
  Classic script semantics make top-level declarations browser globals and
  make parser order part of the compatibility contract.
- The first block begins with the local API transport bootstrap. It captures
  the native `window.fetch`, adds same-origin request IDs and the established
  unsafe-request header, normalizes structured JSON failures, keeps a bounded
  30-entry diagnostic history, dispatches `cvstudio-api-error` and exposes
  `window.cvStudioNormaliseApiFailure`. Its dependencies are `window`,
  `Headers`, `URL`, `CustomEvent`, crypto/randomness and the same-origin
  location; it owns no DOM ID, browser storage or startup listener.
- The optional pinned-navigation domain owns global
  `PAGE_NAV_PIN_STORE`, its seven process-local layout/scroll state values and
  the established `pageNav*`, `clearPageNavFloating`, `refreshPageNavPin`,
  `queuePageNavPinRefresh`, `setPageNavPin`, `togglePageNavPin` and
  `initPageNavPin` entry points. It depends on `#pageTabs`,
  `#pageTabsSpacer`, `#pageNavPinToggle`, `#pageNavPinLabel`,
  `.page-view.active`, document/body portal layout, scroll/resize/
  `requestAnimationFrame`, `showToast`, and the existing
  `cvStudioDurableSettingSet` adapter. Its only storage key is
  `cvstudio_page_nav_pinned_v1`. Its `DOMContentLoaded` registration must stay
  before the following Settings/application initialization listener.
- The second-block reconnect domain has no public global. Its closure owns
  missed-ping, banner and reload state; immediately posts `/heartbeat`, polls
  every 20 seconds, displays `#reconnect-banner`/`#reconnect-msg` after four
  consecutive failures, posts `/restart` with the established restart header,
  probes `/ping`, and reloads after recovery. It owns no localStorage or
  IndexedDB state. The immediate ping and listener/timer registration position
  must remain before the trailing lock/status and PPC token-restore startup.
- Existing event surfaces outside these seams include document click/keydown,
  `DOMContentLoaded`, window load/focus/scroll/resize and visibility listeners.
  Their registration order is preserved. Inline HTML handlers continue to
  resolve the same classic-script globals.
- Durable browser data remains in the existing Phase 2A/2B bridges: usage
  history, PPC metadata, OneNote transfer records, saved OneNote links and the
  exact non-secret setting allowlist. JobAdder compatibility keys, temporary
  UI/result snapshots and the connection-scoped PPC IndexedDB/query-cache plus
  localStorage fallback retain their established ownership. The selected
  modules do not move or reinterpret any of these stores.
- All existing fetch URLs and response fields stay in their current feature
  orchestration. The selected transport bootstrap only preserves the existing
  wrapper; the reconnect module retains only `/heartbeat`, `/restart` and
  `/ping`. No Flask route or method changes.
- CV/Blind JD/Company/The Owl/Lead Finder exports, jsPDF paths, DOCX generation
  through `generate.js`, Blob/object-URL downloads and Batch/JobAdder upload
  paths remain inline and unchanged. Their escaping and recent corrective
  contracts are not extraction candidates in Phase 6A.
- The six established Node fixtures source-extract named inline functions for
  Phase 2A/2B storage, Phase 5B costs, JobAdder escaping/account settings and
  Blind JD export. None of the three selected domains intersects those named
  extraction seams. Phase 6A adds dedicated behavioral and source-order
  characterization rather than rewriting the historical fixtures.
- Flask already serves safe offline assets through the existing
  `/vendor/<path:filename>` route, and protected packaging already copies the
  complete `vendor` tree. Tracked CV Studio modules will use a bounded
  `vendor/cvstudio/` namespace so the 108-route contract remains exact.
  Owner preflight, conservative JavaScript protection and protected smoke must
  explicitly validate and package those files rather than leaving a hidden
  source/protected-asset gap.

### Bounded extraction sequence

1. Add passing pre-move Node/Python characterization for API request/error
   semantics, page-nav globals/DOM/storage/listener behavior, heartbeat timing
   and recovery behavior, script order, the exact 108-route contract and the
   existing protected asset seam.
2. Extract the API transport bootstrap to one synchronous classic module in
   `vendor/cvstudio/`, loaded immediately before the application inline block.
3. Extract the complete optional pinned-navigation definitions to one
   synchronous classic module while retaining every global name, whole-script
   hoisting availability and the exact relative `DOMContentLoaded` order through
   a one-line compatibility registration at its former source position.
4. Extract only the reconnect heartbeat closure to one synchronous classic
   module at the beginning of the second-script position, retaining immediate
   ping/timer behavior and leaving trailing startup calls in place.
5. Extend owner validation/protection/package smoke for the tracked modules,
   run affected Phase 6A and historical frontend fixtures after each bounded
   extraction, then run the one complete final acceptance gate and one exact-
   baseline self-review required by the owner.

### Implemented extraction boundaries

- `vendor/cvstudio/api-transport.js` contains only the established local API
  transport bootstrap. It remains a synchronous classic script immediately
  before the main application script, so `window.fetch`,
  `window.cvStudioNormaliseApiFailure`, `_cvStudioRecentApiErrors`, request-ID
  generation, unsafe-request headers, structured failure normalization and the
  diagnostic event remain available before every existing application caller.
- `vendor/cvstudio/page-nav.js` contains the optional pinned-navigation state
  and definitions. It loads synchronously before the main application script,
  preserving the original whole-script function-hoisting availability for the
  earlier Phase 2B hydration seam. A one-line compatibility registration stays
  at the exact former inline position after `downloadBatchZip()` and before the
  Settings startup listener. All listed `PAGE_NAV_PIN_STORE`, `_pageNav*` state
  and `pageNav*`/pin globals retain classic-script names and behavior; the DOM
  IDs, durable key, passive listeners, animation-frame scheduling and
  `DOMContentLoaded` order are unchanged.
- `vendor/cvstudio/server-heartbeat.js` contains only the existing reconnect
  closure. It remains at the beginning of the former second-script position,
  performs the same immediate `/heartbeat` POST, registers the same 20-second
  timer and retains the four-miss banner, `/restart` header, `/ping` recovery
  polling and reload timings before the trailing lock/PPC startup calls.
- `index.html` uses three deterministic local classic-script tags with the
  existing v24.6.243 cache key. There is no module mode, dynamic import,
  bundler, framework, CDN, remote runtime, lazy loading or startup deferral.
- `owner_build_tools/build_protected.py` now requires and syntax-checks the
  three tracked files, applies the existing conservative non-global-renaming
  JavaScript protection (or the explicit copy path), records source/protected
  hashes, replaces the packaged `vendor/cvstudio` tree with those staged files
  and smoke-fetches each packaged URL. The existing vendor route and complete
  offline vendor tree remain authoritative; no protected package was built.
- `.github/workflows/ci.yml` runs the new Phase 6A browser fixture beside the
  six established fixture files. Python discovery automatically includes the
  new Flask route/protected-asset characterization.

### Characterization and bounded regression evidence

- `tests/test_phase6a_frontend_modularisation.js` was added before extraction
  and passed against the original inline seams. It executes the real inline or
  extracted sources in isolated browser fixtures and fixes API error/request
  behavior, page-nav globals/storage/listeners, heartbeat loss/recovery timing
  and deterministic source order.
- `tests/test_phase6a_frontend_modularization.py` was added before extraction
  and passed against the original route/protection surface. As each module
  appeared it proved the unchanged 108-route inventory, safe existing vendor
  route, module responses, traversal rejection, owner validation, staged
  source/protected hash inventory and package/smoke integration.
- The API extraction passed both new focused fixtures. The navigation
  extraction additionally passed the existing Phase 2B frontend-storage
  fixture. The heartbeat/protected-asset extraction passed both complete new
  fixtures, tracked builder syntax and whitespace validation before its stable
  checkpoint.
- JobAdder, PPC/IndexedDB, durable storage hydration, export/generation/jsPDF,
  CV/Blind JD/Company/Lead Finder/The Owl orchestration and all other inline
  application domains remain in place and unchanged.

### Exact-baseline review and final acceptance

- The single thorough review compared the complete branch against exact
  authorized baseline `1fbcb19bdebf5cb99a975b5b732278be242ff086`. It found
  one concrete timing risk: placing page-nav definitions only at their former
  textual location removed their original whole-inline-script function
  hoisting while Phase 2B hydration starts earlier. The focused correction
  loads those definitions before the main application script and retains only
  the original registration line at its former position. A regression now
  proves definition availability before hydration and unchanged listener order.
- Read-only source equivalence proved that the API and heartbeat modules are
  exact normalized baseline blocks and that `page-nav.js` plus its one-line
  compatibility registration exactly reconstructs the baseline navigation
  block. No extracted block remains duplicated inline, and all three local
  script references occur exactly once in deterministic order.
- After the review correction, the affected Phase 6A Python/Node and existing
  Phase 2B frontend fixtures passed. The required final complete gate then
  passed 153 Python tests with `ResourceWarning` treated as an error; all six
  established frontend fixture files plus the Phase 6A fixture; and the live
  source smoke with all 24 assertions.
- Tracked syntax passed for 31 Python, 28 JavaScript, five PowerShell and five
  POSIX shell files. Owner Windows-x64 source validation/preflight passed for
  all inline/module JavaScript, exact vetted `adm-zip` 0.5.17 and the genuine
  bundled Antiword 1.3.5 fixture with trusted/functional status. Repository
  consistency and Git whitespace validation passed.
- Production changes are limited to `index.html`, the three tracked
  `vendor/cvstudio` modules and the owner protected-build asset integration.
  Test/status/CI changes add only characterization, regression execution and
  this evidence. `app.py`, backend modules, route registration, storage and
  schemas are untouched; the complete regression retains 108 routes, five
  guards, 18 compatibility signatures, SQLite schema 10 and Phase 5A journal
  schema 1.
- No live credential, network provider request, paid call, external data
  mutation, customer/candidate data, protected-package build, release ZIP,
  tag, handover, native/macOS artifact, merge, Phase 6B, Phase 6C, Phase 7 or
  backburner work occurred.

## v24.6.243 JobAdder account-isolation corrective

### Review boundary and corrections

- The one independent review compared exact master
  `21408d0457c9e4c5db5018c39333c32420d54339` with exact v24.6.242 head
  `e7c86bc0020302723ea845cd046d6592f67263d2` and reported four findings.
  No second reviewer or repeated review-and-fix loop was started.
- OAuth token exchange can finish only while the session claimed before
  transport is still live and `exchanging`; a sign-out that clears the session
  wins over a late callback response.
- Backend PPC detail entries include the protected account cache namespace.
  Browser PPC memory, fallback localStorage and IndexedDB cache entries are
  connection-scoped, cleared on transition and protected from in-flight
  read/write repopulation.
- Sign-out and direct account replacement invalidate AI Crawler search results,
  preview/prefetch state and active run sequence; OneNote candidate matches and
  in-flight lookups are invalidated; PPC rows, previews, filters and caches are
  cleared.
- Protected Client ID/Secret retention, changed-Client-ID rejection,
  same-Client-ID secret reuse, durable failure visibility, six critical write
  routes, unsafe non-replay and the exact `/jobadder/disconnect` response
  remain.

### Recorded lookup disclosure

- The prior diagnostic was one read-only
  `GET /jobadder/lists?name=worktype`; it was not a write, upload, OAuth login
  or paid action and did not alter protected credentials.
- No live response payload, account identifier, tenant information, token,
  secret, private URL or candidate data was retained in Git history, QA
  evidence, logs or release artifacts. Temporary diagnostic output was absent
  from the reviewed tree and release evidence.
- The retained evidence cannot establish that the existing browser handler did
  not set or refresh localStorage key `ja_perm_work_type_id`. The v24.6.242
  QA/handover claim is corrected to this narrower, supportable statement.

### Preserved contracts

- Exactly 108 Flask routes remain; subtracting `/jobadder/sign_out` produces
  the unchanged 107-route v24.6.241 contract.
- Five ordered guards, 18 compatibility signatures, SQLite schema 10 and Phase
  5A journal schema 1 remain.
- Antiword, Blind JD, AI-cost, Phase 1–5B and unsafe-provider non-replay
  contracts remain unchanged. This repository has no separately defined Phase
  5C contract.
- v24.6.243 remains Windows-x64-only. No Intel or Apple Silicon macOS artifact
  or claim is produced; macOS users remain on v24.6.239.

### Corrective validation

- Selected Python contract set: 30 passed; all six frontend fixture files
  passed; local source smoke passed 24 assertions.
- Tracked syntax passed for 30 Python, 24 JavaScript, five Bash/command and five
  PowerShell files. Owner Windows-x64 preflight, genuine Antiword extraction,
  vetted `adm-zip`, repository consistency and whitespace checks passed.
- The complete regression suite was not rerun, following the owner's explicit
  post-review restriction.
- Native Windows-x64 protected build and package-only smoke passed. The
  colleague archive SHA-256 is
  `d876c604e8f9121a1314a84f0940d981e5fc910714f5d1fa63098d6280406b6c`.
- All five v24.6.242 protected-output files rehashed unchanged after the new
  build.

## Completed pre-Phase-6 JobAdder account-management and settings milestone

### Authorization and preserved boundary

- Entry verification passed from a clean exact-master v24.6.241 baseline. The
  owner/source ZIP recomputed to
  `f4c27b897d478b4629ccfe8011d6e9019d8f5c5a7f7b0309941afd4fc8b10e76`;
  both v24.6.241 verification sidecars name the exact master commit; fresh
  owner/source and protected Windows-x64 extractions verified; and all
  v24.6.240/v24.6.241 release artifacts were hash-snapshotted before work.
- The only authorized route addition is authenticated, CSRF-protected
  `POST /jobadder/sign_out`. The final inventory contains exactly 108
  routes while preserving every prior route, method, endpoint name and response
  field.
- Normal sign-out preserves the protected JobAdder Client ID and Client Secret,
  removes all connection/account state, invalidates tenant-bound AI Crawler
  state and remains failure-visible. Critical writes/uploads cannot be silently
  cancelled or replayed. Existing `POST /jobadder/disconnect` retains its
  disconnect-and-forget compatibility meaning.
- Complete JobAdder application setup moves to Settings → Integrations & Data.
  Format CV keeps connect/status/upload only. No secret or OAuth token may enter
  HTML, localStorage, SQLite, diagnostics, fixtures, logs or release evidence.
- Five guards, 18 compatibility signatures, SQLite schema 10, journal schema 1,
  Phase 1–5B contracts, mandatory Windows Antiword behavior, cost controls and
  the v24.6.239 macOS baseline remain unchanged. Controlled automated tests
  made no live JobAdder calls. The local visual check triggered one read-only
  work-type lookup from pre-existing protected credentials; no remote write,
  upload, OAuth login, paid call or credential exposure occurred. The retained
  evidence cannot prove the browser's local work-type key was unchanged; the
  v24.6.243 corrective record supplies that disclosure. Phase 6 and all
  unrelated work remain inactive.

### Final validation and review

- Focused JobAdder/backend/cache compatibility: 54 passed.
- One focused self-review found and corrected exactly two concrete issues: a
  late OAuth/legacy-restore race and loss of a newly typed Client ID before
  missing-secret rejection. No repeated review loop or independent reviewer
  was started.
- Qualifying complete Python discovery: 149 passed. All six frontend fixture
  files passed. Source smoke passed 24 assertions.
- Static validation passed for 29 Python, 23 JavaScript, five Bash/command and
  five PowerShell files. Owner Windows-x64 preflight, repository consistency,
  byte-stability and whitespace checks passed.
- Final contracts: 108 routes, five ordered guards, 18 compatibility
  signatures, SQLite schema 10 and Phase 5A journal schema 1.
- All 24 snapshotted v24.6.240/v24.6.241 release files rehashed unchanged.

## v24.6.241 Windows Antiword TOCTOU corrective

### Authorization and boundary

- The owner authorized only the single confirmed v24.6.240 independent-review
  finding: the user-writable Windows runtime could be replaced after hash and
  functional verification released its handles but before process creation.
- v24.6.240 release artifacts remain immutable. The correction uses the next
  valid version, v24.6.241, and remains Windows-x64-only.
- macOS installer/runtime production files remain at the exact v24.6.239
  baseline. No v24.6.241 Intel or Apple Silicon claim or artifact is authorized.
- JobAdder, Phase 6, AI Crawler, schemas, routes and all unrelated work remain
  outside scope.

### Correction

- `cvstudio_antiword.py` opens the runtime root, pinned manifest, controlled
  fixture, every parent directory and all 37 manifest-listed runtime files with
  Windows handles that allow only read sharing. These handles deny write,
  delete and rename replacement before hashes are computed and remain held
  through functional and document process completion.
- One exported `run_verified_antiword()` primitive performs candidate locking,
  complete existing path/reparse/manifest/file-set/hash validation, genuine
  fixture extraction and the requested legacy-`.doc` execution without a gap.
  Both application process-launch paths use this primitive.
- The child environment removes `ANTIWORDHOME` and binds `HOME` to the locked
  executable file. Upstream `$HOME/.antiword` lookup therefore cannot be
  populated to shadow the pinned, locked global mapping resources.
- Process timeout, start failure and cancellation paths kill/reap the process
  where applicable and release every handle in deterministic cleanup.
- `INSTALL_CORE.ps1` applies the equivalent `CreateFileW` read-only,
  read-share-only protected interval around its mandatory functional process.
  Its existing hash, unsigned-binary, reparse, repair, idempotency, timeout and
  false-success gates remain.

### Regression coverage

- Adversarial Windows coverage attempts in-place write, delete, rename and
  atomic replacement of both `antiword.exe` and a critical UTF-8 mapping
  resource immediately before process creation. Every attempt is denied during
  both functional verification and actual extraction.
- A corrupt executable cannot become trusted/functional even when the mocked
  process output contains both public fixture markers; process creation is
  never reached.
- Success, functional timeout, actual extraction timeout, process-start failure,
  cancellation and integrity-failure paths prove their locks are released.
- The real installer self-test proves protected execution, blocked executable
  and mapping replacement, timeout/failure cleanup, genuine extraction,
  install, repeated-install idempotency, corruption repair, nested reparse
  rejection and missing-bundle failure.
- Static application coverage requires both legacy-`.doc` process-launch paths
  to use the secured primitive and forbids the old direct launches.

### Final validation and review

- Final focused Antiword/installer plus full Phase 4 document/route
  characterization: 30 passed.
- Complete Python discovery ran exactly once after the final application and
  installer correction: 140 executed, 138 passed. Strict warning handling
  promoted two unrelated existing `datetime.utcnow()` deprecation warnings in
  salary-cache and JobAdder diagnostic code to errors. Those paths were not
  changed or fixed, and the suite was not rerun.
- All five frontend fixtures passed. Live source smoke passed 24 assertions.
- Tracked syntax passed for 29 Python, 23 JavaScript, five Bash/command and five
  PowerShell files. Owner Windows-x64 preflight, both inline scripts, repository
  consistency and whitespace checks passed.
- One focused self-review found no remaining concrete actionable issue in the
  TOCTOU correction. It also reconfirmed the v24.6.239 Mac file hashes,
  immutable v24.6.240 release hashes, and absence of route/guard/schema or
  JobAdder/Phase-6 scope drift.
- No repeated self-review loop or independent reviewer was started.

## Pre-Phase-6 mandatory Antiword dependency and packaging milestone

### Final owner platform scope

- The owner narrowed v24.6.240 to Windows x64 only. Antiword 1.3.5 remains
  mandatory, bundled, hash-pinned and functionally verified for every Windows
  x64 legacy `.doc` boundary.
- No v24.6.240 Intel or Apple Silicon macOS support claim or artifact was
  produced. macOS users remain on the last verified release, v24.6.239.
- The v24.6.239 `install.sh`, `start.sh`, `restore_previous.sh` and historical
  Mac owner-builder command are byte-identical to exact master
  `a5762488f7d90fe58f00870b2c0b2944be084e71`. The v24.6.240 builder and private
  CI matrix reject/omit Mac targets, so those baseline files cannot produce a
  v24.6.240 artifact.
- The unvalidated Intel and Apple Silicon archive URLs, hashes and inspection
  notes remain in provenance as future-work evidence. Their archives,
  extracted runtimes and mandatory installer/runtime changes are absent from
  the final production and packaging tree.
- A separately authorized native-validation milestone must validate each Mac
  architecture before changing the v24.6.239 Mac production baseline or making
  any newer macOS claim.

### Authorization and entry verification

- The owner separately authorized only this dependency/packaging milestone on
  branch `codex/antiword-mandatory-dependency`; JobAdder settings/sign-out,
  Phase 6, AI Crawler behavior, cost tracking, frontend modularisation,
  credential migration and backburner work remain inactive.
- Entry was a clean worktree at master commit
  `a5762488f7d90fe58f00870b2c0b2944be084e71`, with v24.6.239 on every active
  source surface.
- The immutable v24.6.239 release directory and all adjacent artifacts were
  re-hashed. Its owner/source ZIP remained exactly
  `295df2ff6775058af248f2f4b66b0fcf74e00aad01084f9f8e1d47c7d075de2a`,
  and the verification sidecar `source_commit` exactly matched master.
- A fresh extraction contained 133 tracked files and compared with master with
  zero missing, extra or byte-mismatched files. No existing release artifact
  was changed.
- All required roadmap, status, implementation, private-patch, installer,
  protected-build, historical handover and QA sources were read completely
  before production changes.
- The unchanged Python baseline ran 117 tests: 116 passed and the existing
  owner-integration health test failed because the machine receipt belonged to
  another extracted folder. All five unchanged frontend fixtures passed. The
  failure is environmental and was recorded before implementation.

### Complete legacy `.doc` and packaging inventory

- The shared `/extract-text` route supplies legacy `.doc` text to CV formatting,
  Blind CV/JD, Summary, CV Scoring, The Owl, Company, Lead Finder, OneNote
  upload/profile and related browser workflows.
- JobAdder AI Crawler preview, prefetch, searchable preview text and bounded
  resume-scoring enrichment use the separate Spider download/extraction path.
- `/preview-file` and the Spider visual preview can ask LibreOffice to decode a
  `.doc` to PDF. `/ocr` formerly treated unknown `.doc` bytes as a plain-text
  fallback. All of these legacy `.doc` entry points are now in the mandatory
  dependency boundary.
- The old runtime searched package folders, Program Files, `C:\antiword`,
  `ANTIWORDHOME`, POSIX system paths and sometimes PATH, accepted existence
  without hash/function checks and silently allowed LibreOffice/native/raw
  fallback success.
- The old Windows installer reported success when Antiword was missing and
  advertised the native parser as sufficient. The macOS installer had no
  Antiword step. Diagnostics exposed only a boolean. Protected builds copied
  `vendor` under `runtime/native/vendor`; source packages use root `vendor`.
- The only supported v24.6.240 deliverables are the Windows-x64 owner/source
  package and Windows-x64 protected colleague package.

### Provenance, security and redistribution decision

- rOpenSci R-universe records package 1.3.5, GPL-2, upstream commit
  `51441d45283512081c08010835b8002af79fe5e6`, corresponding-source SHA-256
  `72e84b33b54c11101cb70d63304ca0283f57a6d0ef518ca6329ff5e6490ad630`
  and successful Windows/macOS native checks.
- Exact content-addressed package SHA-256 values are:
  Windows x64 `9a99f67680475605de009cb85ba94c7dc546eb261a4256d743597fbb24b0ddf8`,
  macOS Intel `501f2cf83b050fd4a56ab1ecff6fe21295c168eb4a9876d46c259e7ca21cb923`
  and macOS ARM
  `17cd193eb8ed3b27d092c60fec181e6a7b6d82eda9741dbec03578396d659e25`.
- The owner-provided Program Files installation was independently confirmed as
  package 1.3.5/GPL-2 with unsigned executable SHA-256
  `5f46d20310baf9e647b658a5a8be70fcc8da940a4c068a34b17e8676bce8ba84`.
  It is an older rebuild: all official resources matched, but its executable
  did not match the current content-addressed build, so none of its bytes were
  copied or trusted for packaging.
- Windows x64, Mach-O x86_64 and Mach-O arm64 architecture were independently
  inspected. The macOS binaries link only to system `libSystem`; Intel is
  unsigned and ARM contains a code-signature load command. Trust is based on
  exact official archive, complete runtime manifest, executable hash and
  platform-native architecture/signature checks, not an unsupported publisher
  signature claim.
- Microsoft Defender platform `4.18.26060.3008-0`, signature `1.455.390.0`,
  reported no threats in the official archives/extractions or the comparison
  installation on 2026-07-28.
- Full GPL-2 text, attribution/provenance, the original Windows archive and
  exact corresponding-source archive are bundled. Deferred Mac archives and
  extracted runtimes are not shipped.

### Implementation plan and recovery behavior

- `cvstudio_antiword.py` is the bounded app-independent trust/function
  foundation. It accepts explicit package/runtime roots, never searches PATH,
  verifies the compiled-in SHA256SUMS hash, exact 37-file `bin`/`share` set,
  every file hash, executable hash and controlled fixture hash, then performs
  a bounded native extraction before returning a binary.
- The installer validates the bundled platform runtime, copies/repairs it
  without administrator elevation in the CV Studio local state directory,
  validates the staged and installed copies, and fails setup rather than
  issuing a receipt when any trust/function check fails. An invalid prior
  managed copy is retained with a collision-resistant
  `.invalid.<timestamp>.<unique-suffix>` name.
- At runtime CV Studio checks only the managed or exact bundled platform
  runtime. Diagnostics preserve the legacy `dependencies.antiword` boolean and
  add version, engine version, platform, source class, trust method,
  availability, trust, manifest and functional status without a private path.
- The application remains startable when health fails. `/extract-text`,
  `/preview-file`, `/ocr`, JobAdder visual/text preview, prefetch and resume
  scoring return the explicit structured
  `ANTIWORD_DEPENDENCY_UNAVAILABLE`/`run_installer` contract when the verified
  runtime is unavailable. A verified runtime that cannot decode a corrupt or
  incompatible document returns
  `LEGACY_DOC_EXTRACTION_FAILED`/`convert_to_docx_or_pdf`. PDF, DOCX, image,
  OCR and other formats retain their established paths.
- Existing 20-second document execution, 45-second LibreOffice conversion,
  12 MiB visual and 80 MiB request limits remain. Extraction performs no
  network request and temporary directories retain automatic cleanup.
- LibreOffice, native OLE piece-table parsing, raw scanning and renamed-DOCX
  parsing remain in source as defense-in-depth probes but cannot satisfy a
  verified legacy `.doc` success.

### Exact-master self-review corrections (including unshipped Mac prototype history)

The macOS-specific entries below record the unvalidated prototype work that
preceded the final owner scope reduction. They are preserved as future-work
evidence only; the affected Mac production files and runtime payloads are not
part of v24.6.240.

- The first complete review against exact master
  `a5762488f7d90fe58f00870b2c0b2944be084e71` found that the new Windows and
  macOS installer functional checks invoked the controlled `.doc` fixture
  without their own execution deadline. Runtime extraction was bounded, but a
  hung approved executable could therefore block installation indefinitely.
  Windows now uses redirected asynchronous output plus
  `WaitForExit(12000)`/forced termination, and macOS uses a 12-second watchdog
  with termination, forced-kill fallback and isolated output cleanup. Python
  health now distinguishes `functional-execution-timeout` from other launch
  failures. Regression coverage asserts all three timeout contracts; the
  focused verifier/document suite and genuine Windows installer self-test pass.
- The same review found that an interrupted/failed repair could retain a stage
  directory and that timestamp-only invalid-runtime backup names could collide
  during rapid repeated repairs. Windows now cleans its GUID-named stage in a
  `finally` block and adds a GUID to every retained invalid copy. macOS now
  uses `mktemp` stage names, cleans every pre-install failure path and combines
  timestamp, process ID and Bash randomness for invalid-copy names. Static
  installer regression assertions cover unique staging, cleanup and backup
  naming; the isolated Windows install/idempotency/corruption/repair test
  exercises the corrected path.
- A second trust-boundary pass found that the app-independent verifier rejected
  ordinary links but did not explicitly recognize Windows directory junctions,
  while the two native installer verifiers did not reject every equivalent
  Windows reparse point or macOS symlink. The shared verifier now rejects
  symlinks, junctions and other Windows reparse points. The Windows installer
  rejects reparse points at the runtime root, manifest, controlled fixture,
  `bin` and `share` boundaries; macOS applies matching symlink exclusions to
  the root, directories, manifest, fixture and executable. Focused junction
  recognition plus static installer assertions cover every boundary, and
  normal bundled/install/repair verification still passes.
- The macOS installer prepends Homebrew locations for ordinary dependency
  discovery, but its Antiword trust gate originally invoked hash,
  architecture and file-tree utilities through that mutable `PATH`. A
  shadowing utility could therefore influence the pre-execution installer
  decision before the later app-level verifier rejected the runtime. Every
  Antiword hash, manifest, architecture/signature, staging and functional-test
  primitive is now bound to its macOS system path; only the already hash-
  verified Antiword executable is launched from the managed/bundled tree.
  Static regression coverage requires all security-critical absolute tool
  paths, while Bash syntax and the platform-independent artifact verifier cover
  the resulting script and exact bytes.
- Unexpected PowerShell filesystem/process exceptions could also have placed a
  private package or state path into the new Windows Antiword installer log.
  Expected verification and staged/installed failure codes remain precise,
  while unexpected verifier and repair exceptions are now reduced to
  `verification-failed` or `install-or-repair-failed`. Static regression
  assertions fix both redaction fallbacks and the Windows installer self-test
  confirms that actionable known failures remain visible.
- The isolated Windows QA switch already constrained its state to an explicitly
  named operating-system temporary directory and could not issue a receipt, but
  it accepted a pre-created tree whose descendants could be junctions. It now
  requires a fresh, non-existent state leaf and rejects a reparse point
  immediately after creating it. Static coverage fixes both restrictions and
  the genuine isolated self-test continues to pass with a new temporary
  directory.
- Diagnostics originally called the full verified finder and the new detailed
  health callback separately, so one request could execute the controlled
  fixture twice. Both installer HTTP deadlines were also shorter than a single
  allowed 12-second functional timeout. When a process hung, polling could
  abandon the request and overlap another check. Detailed diagnostics now run
  one authoritative health check, derive the preserved legacy boolean from it,
  and retain the original two-argument finder behavior for compatibility
  callers. Windows and macOS installer diagnostics use 15-second request
  deadlines. Regression coverage proves single-call behavior, the legacy
  fallback contract and both installer deadlines.

### Independent-review corrections

- The first independent exact-master review found that the JobAdder
  resume-download extractor processed JSON and generic `text/*` metadata before
  checking the actual payload for legacy Word OLE bytes. A genuine `.doc`
  mislabeled as `text/plain` could therefore bypass verified Antiword and be
  returned as decoded binary gibberish. Legacy OLE bytes, `msword` metadata and
  `.doc` filenames are now classified before metadata-driven JSON/text paths.
  Characterization coverage uses the genuine pinned fixture mislabeled as
  `text/plain`, proves readable Antiword output without replacement characters,
  and proves an unavailable verified runtime propagates
  `AntiwordDependencyError`.
- The same review found that the macOS installer's corrected 15-second
  diagnostics allowance could be multiplied by all 180 startup-poll
  iterations. All three health requests now share a 75-second process-relative
  budget, and each request's maximum is reduced to the remaining
  budget while diagnostics retain their 15-second per-request allowance.
  Static regression coverage fixes the shared deadline, remaining-budget
  calculation and deadline-aware diagnostics call; Bash syntax validation
  covers the resulting installer.
- A fresh independent review found that JobAdder visual preview still checked
  JSON/PDF/image metadata before genuine OLE identity, while its Office helper
  gated Antiword only for a supplied `.doc` extension. An OLE `.doc` mislabeled
  as text, PDF or image could therefore reach an alternate renderer. Strong
  byte identity now precedes visual metadata, and the Office helper forces
  every genuine legacy Word payload through the exact-document Antiword check
  regardless of its supplied extension. Characterization coverage exercises
  the genuine fixture under text/PDF/image metadata, proves no alternative
  preview succeeds when Antiword is unavailable and proves the structured
  dependency error propagates.
- The same review found equivalent extension-first dispatch in the shared
  `/preview-file` and `/extract-text` upload paths. Genuine OLE `.doc` bytes
  uploaded with `.txt`, `.pdf` or `.png` names could avoid the legacy branch;
  plain-text decoding could even return binary gibberish successfully.
  Central strong-byte classification now canonicalizes genuine OLE content
  before those routes and the `/ocr` route. Regression coverage proves the
  mislabeled fixture extracts verified Antiword text when healthy and returns
  the preserved structured 424 dependency contract from every route when the
  runtime is unavailable.
- Finally, the first JobAdder correction had allowed weak `.doc`/`msword`
  metadata to override genuine PDF or ZIP/DOCX bytes. The shared classification
  order is now OLE, PDF, ZIP/DOCX and image by bytes, with filename and
  content type consulted only when no strong identity exists. Focused tests
  prove PDF and DOCX magic retain their established paths even when both the
  filename and content type falsely identify a legacy `.doc`.
- A third independent review found that both visual-preview helpers returned
  their 12 MiB size-only fallback before the new OLE classification and that
  background prefetch still deferred OCR from weak PDF/image metadata. A
  genuine oversized `.doc` could therefore skip the exact-document Antiword
  gate or be cached through profile fallback. Both size-only exits now perform
  the legacy-document Antiword check first, and prefetch defers OCR only for a
  strong PDF/image byte identity or for metadata when no strong identity
  exists. Regression coverage pads the genuine fixture beyond 12 MiB, proves
  unavailable Antiword propagates the structured dependency failure, proves
  the healthy visual size fallback remains, and confirms genuine oversized
  PDF/image identities retain OCR deferral.
- A fourth independent review found that candidate-only text cache entries were
  read before attachment discovery and that attachment-fingerprint preview
  caches could retain a profile fallback even when JobAdder later exposed
  genuine OLE bytes without changing that metadata. Because the fingerprint is
  not a content identity, candidate resume text is no longer reused while
  attachment metadata exists, and preview payloads are neither reused nor
  written at that boundary. Every such attachment is downloaded on the current
  request so exact OLE bytes reach Antiword. Focused regressions seed stale
  candidate/profile cache results, expose known attachments (including the
  oversized genuine fixture) and prove the downloads occur and return the
  structured 424 when Antiword is unavailable.
- The same review found that `/ocr` initialized optional `pytesseract` before
  classifying the upload. A missing OCR stack could therefore mask both healthy
  legacy-DOC extraction and Antiword's structured dependency failure.
  Tesseract discovery now occurs only inside PDF/image handling after strong
  byte classification. Route coverage forces the `pytesseract` import to fail
  and proves genuine OLE input still returns verified text when Antiword is
  healthy and the preserved 424 response when it is unavailable.
- A fifth independent review found that an attachment-listing failure was still
  indistinguishable from a confirmed empty result and could therefore admit an
  unbound candidate-only text cache entry. Attachment discovery now exposes its
  success state to the text fetcher, and neither a failed listing nor a
  confirmed deletion reuses resume text without current bytes. Resume text
  entries carry the downloaded-content SHA-256, strong content kind and
  Antiword-verification provenance. Reuse requires the same freshly downloaded
  bytes; a legacy-DOC hit also rechecks the current verified Antiword runtime.
  Coverage proves transport and malformed-response listing failures, confirmed
  deletion, unchanged PDF reuse, replacement-byte invalidation, changed-to-OLE
  failure and unavailable Antiword on an unchanged verified OLE entry.
- The same review confirmed that the conservative metadata-cache correction had
  made the bounded preview cache unreachable. Preview lookup now follows the
  current download and uses account/candidate plus downloaded-content SHA-256
  and full/prefetch variant. The established expensive-render reuse remains
  available for unchanged PDF and DOCX bytes; same metadata with changed bytes
  misses, changed-to-OLE bytes reach the 424 gate, and profile fallback never
  receives a reusable content key.
- The review also found an unused top-level `PIL.Image` import inside `/ocr`
  that could mask legacy-DOC dispatch in the same way as the earlier Tesseract
  import. It is removed; image decoding continues through the existing
  branch-local safe image helper. Healthy and unavailable-Antiword OLE route
  coverage forces both Pillow and Tesseract imports to fail.
- A sixth independent review found that the two new legacy-DOC cache-hit gates
  called the imported low-level resolver without its required package/runtime
  roots. Both now call the established app-level `_require_verified_antiword()`
  wrapper. Candidate-text and preview-cache regressions prove a healthy
  unchanged OLE hit rechecks the wrapper without re-extraction/re-rendering and
  that an unavailable runtime propagates the preserved Antiword dependency
  failure instead of falling through to missing evidence or profile fallback.
- A seventh independent review found that protected-build smoke inherited the
  host's normal managed Antiword candidate and could therefore certify a
  damaged package by borrowing a previous installation. Smoke now uses an
  isolated local state/home and matching temporary receipt, enables a
  package-only resolver mode, requires diagnostics to report `source: bundled`,
  and records that the package runtime root was verified. Packaging
  independently revalidates the copied `runtime/native/vendor/antiword` tree
  and executes that exact target runtime before the manifest/archive is
  created. Regression coverage seeds a valid ambient managed runtime, proves an
  intact copied bundle resolves as bundled, corrupts the copied mapping file
  and proves both package-only resolution and packaged-tree validation fail,
  then proves the ambient runtime would otherwise have masked the corruption.
- An eighth independent review found that the isolated protected smoke still
  inherited explicit `CVSTUDIO_STATE_DIR`, `CVSTUDIO_DB_PATH` and
  `CVSTUDIO_JOB_STATE_PATH` values from the owner environment. The smoke
  environment now redirects all three overrides, `HOME` and `LOCALAPPDATA`
  beneath its temporary root before the receipt or compiled process starts.
  Regression coverage seeds every prior path with sentinel bytes, initializes
  the real SQLite store and persistent-job resolver through the constructed
  smoke environment, proves every resolved path stays below the temporary
  root and proves every owner sentinel remains byte-identical. The fresh
  protected build then exercises that same environment helper end to end.
- The same review found that the Windows installer rejected reparse points at
  the runtime, `bin` and `share` roots and on files, but could still enumerate
  through a nested directory junction such as `share\antiword`. Runtime
  traversal is now explicit and checks each child for a reparse point before
  descending. The genuine Windows installer self-test moves the complete
  valid mapping directory outside the runtime, replaces it with a junction,
  requires `runtime-link-rejected`, safely restores the directory and
  re-verifies the runtime. Focused Python coverage executes that isolated
  installer self-test.

### Final validation and platform boundary

- The exact bundled Windows runtime and genuine upstream OLE `.doc` fixture
  pass hash, complete-resource and functional checks. Corruption, extra files
  and arbitrary PATH/`ANTIWORDHOME` candidates fail closed in focused tests.
- The Windows installer contains mandatory fail-closed, idempotent managed-copy
  validation and includes Antiword health in its post-install runtime smoke.
  The macOS production installer remains exactly v24.6.239.
- The Windows installer self-test passes bundled verification, initial managed
  install, repeat/idempotency, deliberate corruption rejection, automatic
  repair and missing-bundle failure in isolated local state. This test mode
  cannot issue a receipt or reach the installer main block.
- Owner protected-build preflight verifies the Windows distribution artifact,
  complete Windows runtime manifest, corresponding source, license and fixture,
  then executes the Windows runtime and fixture. Compiled-package smoke requires
  trusted/functional diagnostics and performs actual multipart
  `/extract-text` extraction of the pinned OLE fixture.
- The v24.6.240 protected CLI and workflow expose only Windows x64. Mac targets
  are rejected and deferred Mac payload paths fail repository consistency.
- Focused Windows Antiword/installer and exact-v24.6.239 macOS-baseline
  regressions pass. The complete regression suite was run once after the scope
  adjustment and passed. Python, JavaScript, PowerShell and Bash syntax,
  protected source preflight, exact `adm-zip` behavior, repository consistency
  and Git whitespace validation also pass on Windows.
- Genuine Windows x64 protected compilation and runtime smoke pass from the
  final implementation state. The compiled app reports Antiword 1.3.5 as
  bundled, package-root verified and trusted/functional under isolated
  package-only smoke state, performs real multipart `/extract-text` extraction
  of fixture SHA-256
  `f430cdfe9446c4b943074d4bf804232761c284f2caa3d4125006b158d8b14af8`
  with no Unicode replacement character, and preserves DOCX generation. The
  temporary non-release QA ZIP is
  `a9ddf77714d353adc0b6323dda31bb168396475c0ed8b578fe346b72c5f68f09`;
  its smoke JSON is
  `4156016f31a755bac094f5a83160e21dde05da8320e153c1eb1d56e98609d47d`.
  Neither artifact is copied to the immutable release directory.
- **Platform boundary:** v24.6.240 is Windows-x64-only. Intel and Apple Silicon
  validation is deferred; no macOS support claim or artifact was produced.
  macOS users remain on v24.6.239 until a separately authorized native-
  validation milestone.

## Post-Phase-5B Blind JD PDF metadata-overflow corrective

### Authorization and entry verification

- The owner supplied a generated Blind JD PDF with an output defect and
  authorized correction plus repeated exact-master review. JobAdder
  sign-out/settings work, Phase 6, unrelated frontend refactoring, AI Crawler
  work and cost work remained inactive.
- The worktree was clean on completed v24.6.238 commit
  `8dd2c1ba0d0e0fc9640997b50d82ce41c7dd129d`; local `master` remained exactly
  `3894042b496896e9a4f358ac9b0e10270052571b`.
- Active installed source surfaces identified v24.6.238.
- `C:\CV-Studio-Codex\releases\v24.6.238` contained the owner/source ZIP,
  checksum, verification sidecar, corrective QA report and Phase 6 handover.
- The v24.6.238 owner/source ZIP independently recomputed to SHA-256
  `ca63ded2c7beef0d1e6853792c7e0c671708acb6cb3d571765bbe0cc9f9c0de8`;
  its verification `source_commit` exactly matched completed v24.6.238 HEAD.
- The owner-supplied reproduction PDF recomputed to SHA-256
  `7aca950544f5068f89877d0ca2a7052047e732d1430f5fbbfea19d6594e94d1e`.
  Poppler and text inspection confirmed two first-page horizontal overflows:
  the header metadata summary and the long Work tile.
- The immutable v24.6.238 release artifacts remained unchanged.

### Corrective implementation

- `exportAnonJDPDF()` splits the first-page Location/Work/Industry summary to
  the exact width between its established x-position and the right margin.
- The header rule and following metadata row move down only when the wrapped
  title/summary requires additional vertical space.
- Location and Work values split to each tile's padded width. All present tiles
  share the maximum required calculated height, retain the complete 174 mm
  metadata width and retain the established 4 mm gap.
- Preview, Word export, the AI prompt/output schema, structured `exp_range`,
  requirements, nice-to-have items, recruiter-critical body content and every
  unrelated Blind JD section remain unchanged.
- The existing Blind JD fixture now uses the exact long Work Arrangement from
  the supplied PDF and asserts that header and tile lines stay within their
  right content edges while both tiles remain equal-height.

### Acceptance and release result

- The focused Blind JD fixture passes five cases covering the v24.6.238
  experience-summary contracts plus long PDF header/tile wrapping.
- Real bundled jsPDF export through local Chrome and Poppler rendering visually
  confirms both pages are unclipped, aligned and legible.
- Complete Python discovery passes all 117 tests with `ResourceWarning`
  treated as an error.
- The focused Phase 3/4/5A/5B and invariant gates pass.
- All five frontend fixtures and all 24 live loopback smoke assertions pass.
- Static validation passes for 27 tracked Python files, 23 tracked JavaScript
  files plus both complete inline scripts, five Bash/command files and five
  PowerShell files.
- Owner-source validation/preflight, vetted `adm-zip` 0.5.17 behavior,
  repository consistency and Git whitespace validation pass.
- Repeated exact-master review re-proves all 107 routes, five ordered guards,
  18 compatibility signatures, SQLite schema 10, journal schema 1, the
  v24.6.237 `esc2` correction, the v24.6.238 experience-summary correction and
  every Phase 1–5B compatibility/non-replay boundary.
- Active source identity advanced to the next unused private owner/source
  version, v24.6.239. Historical v24.6.238 evidence remains immutable.
- The authoritative archive is
  `cv_studio_v24_6_239_blind_jd_pdf_metadata_overflow_corrective_owner_source.zip`
  under `C:\CV-Studio-Codex\releases\v24.6.239`, with adjacent SHA-256 and
  verification sidecars. It is generated from final branch HEAD and freshly
  compared against every tracked Git blob with zero missing, extra or
  byte-mismatched files.
- `cv_studio_v24_6_239_blind_jd_pdf_metadata_overflow_corrective_qa_report.md`
  and `CV_STUDIO_V24_6_239_PHASE_6_HANDOVER.md` record the release evidence.
- No live credential, paid request, external mutation, protected colleague
  build, native compilation, handoff, merge, JobAdder sign-out/settings or
  Phase 6 work was performed.

## Post-Phase-5B Blind JD display/export corrective

### Authorization and entry verification

- The owner authorized only a narrow removal of the duplicated standalone
  Experience/Exp summary from Blind JD preview, Word export and PDF export.
  JobAdder sign-out/settings work, Phase 6, unrelated frontend refactoring, AI
  Crawler work and cost work remained inactive.
- The worktree was clean and detached at entry. `HEAD` and local `master`
  resolved exactly to
  `3894042b496896e9a4f358ac9b0e10270052571b`.
- Active installed source surfaces identified v24.6.237.
- `C:\CV-Studio-Codex\releases\v24.6.237` contained the owner/source ZIP,
  checksum, verification sidecar, corrective QA report and Phase 6 handover.
- The owner/source ZIP independently recomputed to SHA-256
  `5bc44d77cb34c0624dbab973a907ce2eba34dee33593c940af41d0e217bf8cd9`;
  its verification `source_commit` exactly matched approved master.
- A fresh extraction contained 128 tracked files and matched every approved
  Git blob with zero missing, extra or byte-mismatched files.
- The immutable v24.6.237 release artifacts were hashed before work and
  remained unchanged.

### Current-source inventory and pre-change characterization

- Complete current-source search for `exp_range`, `Experience:` and `Exp:`
  found exactly one structured Blind JD output-schema field and three
  duplicated standalone display/export sites:
  - the metadata badge array in `renderAnonJDCard()`;
  - the `Experience:` line in `exportAnonJDDoc()`;
  - the `Exp:` tile in `exportAnonJDPDF()`.
- `exp_range` was not independently rendered by any other Blind JD preview,
  print or export surface. Requirements, Nice to Have and other body sections
  are separate arrays and remain eligible to contain experience requirements.
- `tests/test_blind_jd_exp_summary_frontend.js` was added before production
  changes. It failed on all three intended baseline summaries while its prompt/
  schema and unrelated-content preservation assertions passed.
- Unchanged-source entry validation passed all 117 Python tests after restoring
  the documented ignored exact `adm-zip` 0.5.17 runtime copy. All four existing
  frontend fixtures passed.

### Corrective implementation

- `renderAnonJDCard()` metadata now includes only Location, Work Arrangement
  and Industry; it no longer reads `j.exp_range`.
- `exportAnonJDDoc()` retains About the Role, Work Arrangement, Location and
  Industry but no longer adds a top `Experience:` line.
- `exportAnonJDPDF()` retains Location and Work tiles, removes the `Exp:` tile
  and divides the complete 174 mm content width evenly between the present
  metadata tiles with the established 4 mm gap.
- The source JD, prompt instructions, raw JSON output schema,
  `window._lastAnonJD` structured object, requirements, nice-to-have items,
  recruiter-critical body content and all unrelated Blind JD sections remain
  unchanged.
- HTML/Word escaping and PDF text-only rendering remain in their established
  helper boundaries. The valid local `esc2` helper inside
  `renderAnonJDCard()` remains unchanged, preserving the v24.6.237 correction.

### Acceptance and release result

- The focused Blind JD fixture passes four cases covering preview, Word, PDF,
  structured-schema/body preservation, metadata width, escaping and unrelated
  content.
- Complete Python discovery passes all 117 tests with `ResourceWarning`
  treated as an error.
- The focused Phase 3/4/5A/5B gate passes all 91 tests.
- All five frontend fixtures pass: the new Blind JD corrective fixture plus
  the established JobAdder, Phase 2A, Phase 2B and Phase 5B fixtures.
- Live loopback source smoke passes all 24 assertions.
- Static validation passes for 27 tracked Python files, 23 tracked JavaScript
  files plus both complete inline scripts, five Bash/command files and five
  PowerShell files.
- Owner-source validation/preflight, vetted `adm-zip` 0.5.17 behavior,
  repository consistency and Git whitespace validation pass.
- Repeated exact-master review re-proves all 107 routes, five ordered guards,
  18 compatibility signatures, SQLite schema 10, journal schema 1, the
  v24.6.237 `esc2` correction and every Phase 1–5B compatibility/non-replay
  boundary. Only the three authorized Blind JD render/export paths changed in
  production logic.
- Active source identity advanced to the next unused private owner/source
  version, v24.6.238. Historical v24.6.237 evidence remains immutable.
- The authoritative archive is
  `cv_studio_v24_6_238_blind_jd_exp_summary_corrective_owner_source.zip` under
  `C:\CV-Studio-Codex\releases\v24.6.238`, with adjacent SHA-256 and
  verification sidecars. It is generated from final branch HEAD and freshly
  compared against every tracked Git blob with zero missing, extra or
  byte-mismatched files.
- `cv_studio_v24_6_238_blind_jd_exp_summary_corrective_qa_report.md` and
  `CV_STUDIO_V24_6_238_PHASE_6_HANDOVER.md` record the release evidence.
- No live credential, JobAdder call, paid request, protected colleague build,
  native compilation, handoff, merge, JobAdder sign-out/settings or Phase 6
  work was performed.

## Post-Phase-5B JobAdder esc2 corrective

### Authorization and entry verification

- The owner authorized a narrow investigation and correction of the JobAdder
  `esc2 is not defined` browser failure. Phase 6, unrelated frontend
  refactoring, AI Crawler work and cost-tracking changes remained inactive.
- The worktree was clean and detached at entry. `HEAD` and local `master`
  resolved exactly to
  `e22b05f139a743dc5e690f8ccb7b61a703fffc63`.
- Active source surfaces identified v24.6.236.
- `C:\CV-Studio-Codex\releases\v24.6.236` contained the owner/source ZIP,
  checksum, verification sidecar, corrective QA report and Phase 6 handover.
- The owner/source ZIP independently recomputed to SHA-256
  `c60dd25e79616d580449450c943a40760baa7c8aeaaceff21637c88e51a09146`;
  its verification `source_commit` exactly matched approved master.
- A fresh extraction contained 125 tracked files and matched every approved
  Git blob with zero missing, extra or byte-mismatched files.
- The immutable v24.6.235 and v24.6.236 release artifacts were hashed before
  work and remained unchanged.

### Diagnosis and pre-change characterization

- Complete source inspection found exactly two legitimate local `esc2`
  definitions, inside `renderAnonJDCard()` and `renderCompanyCard()`.
- `showJADialog()` had one invalid out-of-scope `esc2(email)` call.
  `renderJAUploadList()` had two invalid out-of-scope `esc2()` calls for the
  filename and status text.
- The established global `esc()` safely covers all three displayed values.
- Independent inspection found one additional compatibility hazard:
  `renderJAUploadList()` declared a local string variable named `esc`. A
  mechanical call replacement without renaming it would throw
  `TypeError: esc is not a function`.
- `tests/test_jobadder_esc2_frontend.js` was added before production changes.
  It failed on both affected runtime paths with
  `ReferenceError: esc2 is not defined`, while the two local card-renderer
  escaping cases passed. Its source inventory identified exactly the three
  out-of-scope occurrences.

### Corrective implementation

- The dialog email and upload filename/status calls now use global `esc()`.
- The upload renderer's local ID variable is named `escapedId`; its value and
  both existing handler uses are unchanged.
- The two valid local `esc2` helpers and every internal call remain exact
  baseline code.
- No global `esc2` alias was added. The source-scope regression now requires
  every `esc2` definition and call to stay within the two legitimate local
  renderers, preventing a future scope mistake from being concealed.
- No JobAdder route, request, candidate-creation path, upload path, response
  field, credential boundary or external-client policy changed.

### Acceptance and release result

- Complete Python discovery passed all 117 tests with `ResourceWarning`
  treated as an error.
- The focused Phase 3/4/5A/5B gate passed all 91 tests.
- All four frontend fixtures passed: the new JobAdder corrective fixture and
  the three established Phase 2A, Phase 2B and Phase 5B fixtures.
- Live loopback source smoke passed all 24 assertions.
- Static validation passed for 27 tracked Python files, 22 tracked JavaScript
  files plus both complete inline scripts, five Bash/command files and five
  PowerShell files.
- Owner-source validation/preflight, vetted `adm-zip` 0.5.17 behavior,
  repository consistency and Git whitespace validation passed.
- Final exact-master review re-proved all 107 routes, five ordered guards,
  18 compatibility signatures, SQLite schema 10, journal schema 1 and every
  Phase 1–5B compatibility/non-replay boundary. Only `showJADialog()` and
  `renderJAUploadList()` changed in production logic.
- Active source identity advanced to the next unused private owner/source
  version, v24.6.237. Historical v24.6.235 and v24.6.236 evidence remains
  immutable.
- The authoritative archive is
  `cv_studio_v24_6_237_jobadder_esc2_corrective_owner_source.zip` under
  `C:\CV-Studio-Codex\releases\v24.6.237`, with adjacent SHA-256 and
  verification sidecars. It is generated from final branch HEAD and freshly
  compared against every tracked Git blob with zero missing, extra or
  byte-mismatched files.
- `cv_studio_v24_6_237_jobadder_esc2_corrective_qa_report.md` and
  `CV_STUDIO_V24_6_237_PHASE_6_HANDOVER.md` record the release evidence.
- No live credential, JobAdder call, paid request, protected colleague build,
  native compilation, handoff, merge or Phase 6 work was performed.

## Phase 5B authorization and constraints

- Owner authorization received on 26 July 2026.
- Work only from clean master commit
  `327858799f17d880e37c740f71dfe321ea7bde0a` and preserve v24.6.234 as the
  source baseline.
- Phase 5B is limited to central AI cost guardrails and provider-billing
  reconciliation.
- Before production behavior changes, inventory every paid-provider route,
  helper and confirmation gate; normalized provider/model/usage/cost fields;
  the v24.6.215 DeepSeek detailed-cost cutoff and historical calculations;
  client-side estimates and available provider-authoritative billing fields;
  retry/timeout/failure/ambiguous-call boundaries; protected credentials and
  permitted non-secret billing data; and established success, failure and
  reconciliation response fields. Add characterization coverage first.
- Reconciliation must distinguish estimates from provider-authoritative
  values, remain failure-visible and never treat missing billing data as zero
  or authoritative.
- Preserve all 107 Flask routes/methods/endpoints/response fields, all five
  ordered global request/security guards, every authentication/CSRF/request-
  size/paid-call boundary, all 18 compatibility helper signatures, Phase 4
  call-time dependency rebinding and established initialization order.
- Preserve SQLite schema version 10, Phase 5A journal metadata schema 1 and its
  lifecycle/recovery/non-replay guarantees, Phase 3 endpoints/headers/retries/
  timeouts, the DeepSeek history cutoff, redaction and protected credential
  boundaries, and unsafe/paid ambiguous-call non-replay behavior.
- If Phase 5B would change a preserved schema, data authority, Phase 5A
  journal semantic, paid confirmation gate, provider retry/non-replay policy,
  response contract or recovery semantic, stop and present the exact proposed
  change for separate owner authorization.
- Do not use live credentials or make paid external calls.
- Do not add persistent-job families or workers, migrate credentials, perform
  frontend modularisation/lazy loading, begin Phase 6, add unrelated workflows,
  replace Flask's server or implement backburner items 4, 7 or 8.
- Stop after the Phase 5B owner/source release. Do not hand off, merge or begin
  Phase 6 automatically.

## Phase 5B entry verification

- The worktree was clean and detached at entry; both `HEAD` and local `master`
  resolved exactly to
  `327858799f17d880e37c740f71dfe321ea7bde0a`.
- Active source surfaces identify v24.6.234.
- `C:\CV-Studio-Codex\releases\v24.6.234` contains the owner/source ZIP,
  checksum, verification sidecar, Phase 5A corrective QA report and Phase 5B
  handover.
- The owner/source ZIP independently recomputed to SHA-256
  `eb44700e941deb079c55cbff1f200b3c97733f5171e24748088fe38490b5b8cd`;
  its verification `source_commit` exactly matches approved master.
- A fresh extraction contained 117 tracked files and matched every Git blob
  with zero missing, extra or byte-mismatched files.
- The documented ignored vetted `adm-zip` 0.5.17 dependency was restored
  without changing tracked Git state.
- Unchanged-source entry validation passed all 86 Python tests with
  `ResourceWarning` treated as an error, the 38-test focused Phase 5A/Phase 4
  gate, both frontend fixtures and all 24 live loopback smoke assertions.
- Static validation passed for 24 tracked Python files, 20 tracked JavaScript
  files plus both inline scripts, five Bash/command files and five PowerShell
  files. Owner-source validation/preflight, repository consistency and Git
  whitespace validation passed.
- Existing characterization re-proved the exact 107 routes, five ordered
  guards, 18 compatibility signatures, schema version 10, initialization
  markers and Phase 5A recovery/non-replay contracts.

## Phase 5B bounded milestone plan

### Milestone 1 — inventory and characterization

- Record every paid-provider route/helper/confirmation gate and its normalized
  provider, model, usage, estimate and cost response fields.
- Record the DeepSeek cutoff/historical calculation contract, provider-
  authoritative fields, non-secret billing-data boundary, retry/timeout/
  ambiguity behavior and every success/failure/reconciliation shape.
- Add no-network pre-change characterization before modifying production
  behavior.

### Milestone 2 — central accounting and guardrail foundation

- Add the smallest app-independent provider-aware accounting foundation with
  explicit dependencies and no circular import.
- Normalize bounded estimate/authority provenance, require explicit missing
  authority and make invalid or unavailable reconciliation failure-visible.
- Add configurable in-request guardrail evaluation without changing paid-call
  confirmation or retry/non-replay boundaries.

### Milestone 3 — existing-call integration

- Integrate only inventoried paid AI compatibility adapters while preserving
  their route decorators, fields, endpoints, headers, timeouts and zero-retry
  paid-call policy.
- Reconcile provider-returned authoritative billing fields when present and
  keep estimates explicitly labeled when authority is absent.
- Do not add a route, persistent job, billing worker, credential authority or
  schema migration.

### Milestone 4 — acceptance and release evidence

- Run complete regression, both frontend fixtures, live source smoke, tracked-
  language static validation, owner-source preflight, repository consistency
  and repeated exact-master compatibility review.
- Advance source version surfaces only after implementation/review are clean.
- Commit the exact final source; create, freshly extract and byte-verify the
  next private owner/source ZIP; generate SHA-256/verification sidecars, QA
  report and Phase 6 handover under the new release directory.
- Confirm sidecar `source_commit` equals final branch HEAD, confirm a clean
  worktree and stop before handoff, merge or Phase 6.

## Phase 5B milestones

- [x] Verify the v24.6.234 master/source/package baseline and all entry gates.
- [x] Record owner authorization, scope boundaries and bounded milestone plan.
- [x] Complete paid-provider, billing, credential and ambiguity inventory.
- [x] Add pre-change characterization for all in-scope field contracts.
- [x] Implement and verify the central accounting/guardrail foundation.
- [x] Integrate only compatible existing paid-provider call boundaries.
- [x] Run complete acceptance and repeated exact-master review.
- [x] Create and byte-verify the Phase 5B private owner/source release.
- [x] Produce QA report, sidecars and Phase 6 handover; stop before Phase 6.

## Phase 5B decisions and limitations

- SQLite remains schema version 10 and the separate Phase 5A journal remains
  metadata schema 1. No migration or durable billing authority is authorized.
- Provider billing authority, when available in an existing response, must be
  recorded distinctly from local estimates. Absence of authority remains
  explicit and is not converted to a zero value.
- Tests use temporary local state and controlled fakes only. No live
  credentialed external request, paid call, native protected build or physical
  installer test is authorized or claimed.

## Phase 5B Milestone 1 inventory and characterization result

### Paid-provider routes, helpers and confirmation gates

- The existing browser-session AI spend set contains exactly eight `POST`
  routes: `/test`, `/parse`, `/generate-ai`, `/blind`,
  `/jobadder/onenote_log_screening`, `/lead-finder/search`,
  `/lead-finder/find-people` and `/lead-finder/find-emails`. The fourth ordered
  global guard, `_require_ai_spend_browser_session`, protects this exact set.
  Host/origin/request-size guards and the Lead Finder's existing `1571` local
  feature lock remain separate and unchanged.
- `call_llm(provider, api_key, payload_dict)` is the central compatibility
  dispatcher used by the paid browser routes. It delegates through the existing
  signatures `call_anthropic(api_key, payload_dict)`,
  `_call_deepseek(api_key, payload_dict, timeout_seconds=180)` and
  `_call_openai(api_key, payload_dict, timeout_seconds=180)` to the shared
  Phase 3 `AIProviderClient`.
- `/jobadder/onenote_log_screening` optionally invokes
  `_ja_salary_ai_extract(fields, config=None)` before its established
  externally mutating JobAdder write. Only the two salary fields enter the AI
  payload. The later JobAdder mutation and every existing error/fallback field
  remain outside Phase 5B.
- The owner-only `/owner/integration/run` route can call one small DeepSeek
  probe through `_owner_integration_deepseek_probe`. It is outside the browser
  spend set and retains both owner-integration authorization and the exact
  `RUN ONE PAID DEEPSEEK PROBE` confirmation. Phase 5B must not weaken or move
  that confirmation.
- `/lead-finder/test-search-provider` may consume optional Tavily or SerpAPI
  third-party quota. It is outside the browser AI spend set and retains its
  established provider-configuration flow. Tavily/SerpAPI query helpers and
  Apollo person enrichment can consume separately billed credits, but are not
  AI token-provider calls and are explicitly excluded from the existing
  `cost`/`cost_details.usd` value. Changing those gates or folding unknown
  third-party fees into the legacy token-cost number is not authorized.

### Provider, model, usage and estimate fields

- Provider normalization recognizes `anthropic`/`claude`,
  `deepseek` and `openai`/`gpt`; model inference uses DeepSeek and GPT prefixes
  and otherwise defaults to Anthropic. Every existing paid success shape
  exposes the selected `model` and `provider`.
- `_normalize_llm_usage` preserves provider-native top-level counters while
  adding the canonical non-negative fields `input_tokens`, `output_tokens`,
  `prompt_cache_hit_tokens`, `prompt_cache_miss_tokens` and `api_calls`.
  Aliases include `prompt_tokens`/`completion_tokens`,
  `cache_read_input_tokens`/`cache_creation_input_tokens` and DeepSeek's
  returned hit/miss counters. `_merge_llm_usage` sums only those five canonical
  fields across deliberate multi-call workflows.
- `_llm_cost_details` currently produces a local USD estimate with the legacy
  audit fields `input_tokens`, `output_tokens`, `total_tokens`,
  `prompt_cache_hit_tokens`, `prompt_cache_miss_tokens`, `api_calls`, `usd`,
  `model`, `provider`, `pricing_model_key`, `pricing_known`, `cost_method`,
  `rates_per_million_usd` and `note`. DeepSeek additionally exposes
  `unclassified_input_tokens` and `billed_cache_miss_tokens`.
  `_llm_response_cost_fields` maps the same estimate to legacy top-level
  `cost` and nested `cost_details`.
- The local rate table covers the established Claude 5/Sonnet 4/Opus 4/Haiku
  4.5, DeepSeek v4 Flash/Pro and GPT 5.4/5.5 variants. An unrecognized model
  uses the established provider fallback rate with `pricing_known=false`.
  That flag describes recognition by the local table; it has never meant that
  the resulting dollar value is provider-authoritative.
- DeepSeek uses returned cache-hit/cache-miss counters when present. Any
  unclassified input is conservatively charged at the local cache-miss rate;
  if no split is returned, all input is treated as cache miss. This is a local
  estimate even though the underlying token counters came from the provider.

### DeepSeek history cutoff and browser calculation contract

- The v24.6.215 detailed-history cutoff is field-presence based. Usage rows
  containing `input_tokens`, `output_tokens` or `api_calls` retain their token,
  call and cache audit detail. Earlier rows preserve the stored historical
  numeric cost but display: `Created before v24.6.215; historical cost is
  preserved but token/call/cache details cannot be reconstructed.`
- The browser accepts backend `cost_details.usd` when supplied and otherwise
  repeats the established local calculation. It stores the numeric legacy
  `cost` with provider/model/token/rate/method audit metadata. Phase 5B may add
  provenance but must not reinterpret pre-v24.6.215 rows or rewrite historical
  values.
- The existing UI accurately excludes Tavily, SerpAPI, Apollo and other
  third-party fees, but it currently labels the locally calculated amount as
  `cost` without a machine-readable estimate-versus-authority distinction.

### Provider-authoritative fields and reconciliation boundary

- Anthropic Messages, OpenAI Responses and DeepSeek chat/message responses
  provide provider-originated usage counters, not an invoice-authoritative
  per-request USD amount. Anthropic and OpenAI expose separate organization
  administration cost-report APIs; those need distinct admin credentials and
  return aggregated cost records. DeepSeek documents returned token/cache
  usage and a separate account balance endpoint, not a per-call billed amount.
- Therefore Phase 5B can truthfully classify provider-returned usage as
  authoritative for the returned response and the current dollar value as a
  local estimate. Missing invoice authority must be represented explicitly as
  unavailable, never as `$0`, reconciled or authoritative.
- Adding admin billing credentials, background polling, organization-level
  billing routes or a durable billing ledger would cross the protected-secret,
  worker, schema and data-authority boundaries and is not authorized.
- Reference contracts inspected on 26 July 2026:
  [OpenAI organization usage API](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage),
  [Anthropic Usage and Cost Admin API](https://platform.claude.com/docs/en/manage-claude/usage-cost-api),
  [Anthropic cost report](https://platform.claude.com/docs/en/api/admin/cost_report),
  [DeepSeek chat completion usage](https://api-docs.deepseek.com/api/create-chat-completion/)
  and [DeepSeek balance](https://api-docs.deepseek.com/api/get-user-balance/).

### Retry, timeout, failure and ambiguity inventory

- Phase 3 sends every AI-provider request as one `POST` with
  `safe_to_retry=false` and `retries=0`. Provider timeouts remain bounded to
  15–300 seconds; compatibility adapters retain their established defaults and
  the salary helper retains its 90-second request.
- `/parse` deliberately makes up to three paid calls only after definite
  provider responses when repairing malformed/truncated output.
  `/generate-ai` can make one explicit no-tools follow-up only after a definite
  HTTP response says web search is unavailable. These are application
  continuations, not transport replay. A timeout or ambiguous transport
  failure is never automatically replayed.
- `/test`, `/parse`, `/generate-ai`, `/blind`, Lead Finder and salary assist
  retain their established uneven error shapes. Some post-response parsing
  failures include returned usage and cost; a transport failure can have no
  usage even though provider charging is ambiguous. Existing zero numeric
  fields in these legacy shapes mean “no billable usage was returned,” not a
  proven zero provider charge. Phase 5B must add an explicit ambiguity/status
  signal without deleting or reinterpreting those legacy values.
- Tavily/SerpAPI reads retain their bounded safe-read retry behavior. Apollo
  enrichment remains an externally charged/mutating-ambiguity boundary and is
  not automatically replayed by Phase 5B.

### Protected credentials and permitted non-secret billing data

- The protected AI store remains `_cv_secure_load("ai")`, backed by the
  established OS-protected/machine-bound mechanisms. Its only slots are
  `main_anthropic`, `main_deepseek`, `main_openai`, `lead_anthropic`,
  `lead_deepseek`, `lead_openai`, `search_tavily`, `search_serpapi` and
  `enrichment_apollo`. Existing request-key compatibility remains unchanged.
- API keys, admin keys, OAuth tokens and protected provider/account identifiers
  remain forbidden from SQLite, the Phase 5A journal, logs, fixtures,
  diagnostics, support bundles and release evidence.
- Permitted non-secret values are provider/model identifiers, returned token
  and cache counters, local rate keys/values, calculation method, estimate and
  authority status, bounded differences when both values exist, and existing
  third-party call/result counts. No new persistence authority is introduced.

### Established response fields characterized before production change

- `/test`: success `ok`, `usage`, `model`, `provider`, `cost`,
  `cost_details`; failure `ok`, `error` plus existing global error additions.
- `/parse`: success `ok`, `data`, `usage`, `model`, `provider`, `cost`,
  `cost_details`; post-response failures additionally use `error`,
  `paid_ai_failure` and the same usage/cost fields. Provider HTTP failures
  retain their smaller established error shape.
- `/generate-ai`: success `ok`, `content`, `usage`, `model`, `provider`,
  `cost`, `cost_details` and optional `warning`; established provider and
  generic failures remain unchanged.
- `/blind`: success `ok`, `data`, `usage`, `model`, `provider`, `cost`,
  `cost_details`; post-response failures retain `error`, `paid_ai_failure` and
  usage/cost audit fields.
- OneNote salary processing retains `fieldExtraction`, `salaryCalculation`,
  `aiAttempted`, `aiUsed`, `aiApiCalled`, `cacheHit`, `provider`, `model`,
  token/call/cache counters, `costUsd`, `pricingKnown`, `pricingModelKey`,
  `costMethod`, `costReason` and its existing fallback/cache fields.
- Lead search success retains `ok`, `summary`, `companies`, `people`, `usage`,
  `model`, `provider`, `cost`, `cost_details`, `phase` and optional `warning`.
  People search retains `ok`, `people`, `title_search_angles`, the same AI
  usage/cost fields, `phase` and optional `warning`. Email enrichment retains
  `ok`, `people`, usage/model/provider/cost fields and existing cache/Apollo
  counters and warning where applicable.
- The owner paid-probe result retains its integration-test envelope and
  metadata `model`, `usage`, `cost_usd`. Search-provider test success retains
  `ok`, `provider`, `count`, `sample`; failures retain `ok`, `error`.
- Eight no-network Phase 5B characterization tests pass. They cover the
  exact routes/gates/guard order, canonical/native usage, DeepSeek and standard
  calculation behavior, established provider translation, representative
  success/failure/salary fields, single-attempt ambiguous timeout behavior,
  central app integration, the v24.6.215 history cutoff and protected
  credential slots.

## Phase 5B Milestone 2 central accounting and guardrail foundation result

- Added app-independent `cvstudio_ai_costs.py`. It owns the existing backend
  rate table, canonical usage normalization/merging, estimate calculation,
  strict optional provider-authority normalization, reconciliation, request
  ceiling evaluation and non-secret missing-billing/failure descriptors.
- Existing app helper signatures remain unchanged and delegate to the central
  module. Legacy `cost`, `cost_details.usd`, rates and calculation methods keep
  their established numeric behavior. Additive cost detail now distinguishes:
  `estimated_cost_usd`, `cost_value_type=local_estimate`,
  `cost_authority=local_rate_table`, `usage_authority`,
  `provider_billing_status`, nullable `provider_authoritative_cost_usd`,
  billing currency/source, reconciliation status/difference and
  `billing_data_missing`.
- Provider billing is accepted only through an explicit authoritative envelope
  from a provider response, cost report or invoice. Invalid, negative,
  non-finite, unmarked or unapproved authority fails visibly. Authoritative USD
  is compared with the local estimate without replacing the legacy estimate.
  Non-USD authority remains visible but is not converted without an authorized
  exchange-rate authority.
- The standard provider responses currently have no such cost envelope, so
  their billing status is explicitly unavailable and authoritative cost stays
  `null`. Returned usage remains provider-response authoritative. OpenAI native
  usage details are retained and its returned cached-token counter is now
  normalized without changing the established input/output estimate.
- Added an opt-in call-time request guardrail using
  `CVSTUDIO_AI_MAX_ESTIMATED_REQUEST_USD`. It is disabled when unset, preserving
  v24.6.234 behavior. When configured, it estimates a conservative input
  ceiling at one token per UTF-8 payload byte plus the requested output maximum
  and blocks before provider transport if the estimate exceeds the limit.
  Unknown models use the highest known provider rate rather than a cheaper
  fallback. Invalid limits and blocked calls are failure-visible and contain no
  prompt or credential content.
- The guardrail is enforced inside all three established provider compatibility
  adapters, so browser routes and the separately confirmed owner DeepSeek probe
  share it without changing route gates, provider endpoints, headers, timeouts
  or the Phase 3 zero-retry policy.
- Owner-source validation now requires and compiles the new module. Nine pure
  foundation tests and eight integration/characterization tests pass with no
  live request. Tests prove missing authority is not zero, authoritative and
  non-USD reconciliation, invalid-data failure, disabled/allowed/blocked
  guardrails, conservative unknown-model pricing, no transport after a block,
  and propagation of a controlled authoritative fixture.
- This is an in-request ceiling, not a persistent budget or aggregate billing
  ledger. No schema, credential, worker, route or data-authority change was
  introduced.

## Phase 5B Milestone 3 existing-call integration result

- All existing browser AI paths now return the same legacy top-level
  `cost` estimate and `cost_details` fields plus the central provenance and
  reconciliation fields. Standard provider success responses explicitly say
  that usage came from the provider, cost came from the local rate table and
  provider-authoritative cost is unavailable rather than zero.
- Paid-call failure paths add `paid_call_status` and
  `billing_reconciliation` without removing or renaming any established error
  field. The status distinguishes a guardrail block before transport, a
  definite provider error response, a provider response with returned usage,
  no call, and an ambiguous failure with no returned usage. Ambiguous failures
  retain nullable authoritative cost and are never replayed.
- OneNote salary processing retains every legacy camel-case field and adds
  estimate/authority/reconciliation/guardrail status. Local and cache paths are
  explicitly `not_called`; a transport failure is explicit even though the
  legacy `aiApiCalled` field remains unchanged for compatibility.
- The owner-only paid DeepSeek probe retains its exact authorization and
  confirmation. Its legacy `metadata.cost_usd` now reads the established
  estimate from the correct `cost` field instead of the nonexistent
  `cost_usd` key that always yielded zero. Additive `cost_details` carries the
  authority distinction. The helper still makes no call in tests.
- Tavily/SerpAPI connectivity and configured Lead Finder search responses now
  expose a separate `external_billing` object with nullable authoritative
  amount. Apollo enrichment reports its observed lookup count and the same
  explicit missing-billing status. Their unknown fees remain excluded from the
  legacy AI token estimate.
- The usage tracker now labels current totals as estimates, persists the
  non-secret cost/usage/billing/reconciliation provenance on new schema-10
  usage-history payloads and exports those columns. It does not migrate or
  rewrite records. The exact v24.6.215 field-presence cutoff and historical
  stored values remain unchanged.
- Added a no-network Node fixture for client-side estimate fallback,
  backend-provenance propagation, usage-history persistence and the DeepSeek
  historical cutoff. The three frontend fixtures pass.
- Fifty-one focused Python tests pass across Phase 5B, the Phase 3 client
  boundary, Phase 4 modules and Phase 5A journal/recovery integration. They
  reconfirm 107 routes, five ordered guards, 18 compatibility signatures,
  schema 10, journal schema 1, initialization order and paid-call zero-retry
  behavior.
- No new route, worker, credential slot, schema, journal field, provider
  endpoint, header, timeout, retry or confirmation gate was introduced.

## Phase 5B Milestone 4 acceptance and release result

- Advanced every active backend, frontend, installer/receipt/launcher,
  owner-build and test version surface to the next unused private identity,
  v24.6.235. Historical release evidence remains immutable.
- Complete Python discovery passed all 104 tests with `ResourceWarning`
  promoted to an error. The focused Phase 5B/Phase 3/Phase 4/Phase 5A gate
  passed 51 tests. All three frontend fixtures passed and live loopback source
  smoke passed all 24 assertions.
- Static validation passed for 27 tracked Python files, 21 tracked JavaScript
  files plus both complete inline scripts, five Bash/command files through
  Git Bash and five PowerShell files. Owner-source validation/preflight,
  vetted `adm-zip` 0.5.17 behavior, repository consistency and Git whitespace
  validation passed.
- Repeated exact-v24.6.234-master review corrected four concrete final
  hardening findings: authoritative billing now requires explicit per-request
  scope; billing amount/record totals are bounded and finite; optional billing
  references are not propagated; invalid, negative or extremely large output
  ceilings can no longer fall back or clamp below the actual requested value.
  Repository-owned CRLF repair also restored the three Windows files touched by
  version advancement.
- The clean repeated review re-proved all 107 Flask route URL/method/endpoint
  tuples, the five ordered security guards, 18 compatibility signatures,
  SQLite schema version 10, journal metadata schema 1, initialization markers,
  the 80 MiB request limit, protected credential slots, Phase 5A recovery and
  non-replay behavior, and Phase 3 provider endpoints/headers/timeouts/zero
  retries for chargeable posts.
- Existing storage, client, journal, storage-bridge, diagnostics and
  document-safety modules remain exact v24.6.234 master bytes. The only
  production scope changes are the new central cost module, bounded app
  adapters/failure status and estimate-provenance UI described above. No
  further concrete finding remained.
- The authoritative private archive is
  `cv_studio_v24_6_235_phase5b_ai_cost_guardrails_owner_source.zip` under
  `C:\CV-Studio-Codex\releases\v24.6.235`. It has one `cv_formatter/` root and
  is freshly extracted against every tracked Git blob with zero missing, extra
  or byte-mismatched files.
- The adjacent `.zip.sha256` and `.zip.verification.json` sidecars are
  authoritative for the final SHA-256, bytes, tracked/extracted file counts,
  verification time and exact final `source_commit`. The QA report and
  `CV_STUDIO_V24_6_235_PHASE_6_HANDOVER.md` are copied beside them.
- No live credentials, paid/provider call, protected colleague build, native
  compilation or genuine macOS test was performed or claimed. Work stops
  before handoff, merge and Phase 6.

## Phase 5B post-release corrective review

- The owner authorized a complete review of the Phase 5B branch against exact
  master `327858799f17d880e37c740f71dfe321ea7bde0a` on 26 July 2026. The
  worktree and branch were clean at review entry; the merge base remains that
  exact master commit.
- Added failing regression characterization before production correction for
  each concrete first-pass finding:
  - explicit zero, boolean, fractional and string output-token ceilings could
    be defaulted or truncated during guard evaluation;
  - float conversion could erase a small but real estimate-versus-limit
    difference at the enforcement boundary;
  - merged partial/malformed billing records could silently discard invalid
    entries and retain unallowlisted provider/account fields;
  - missing currency and mismatched provider identity could still be accepted
    as authority;
  - delayed/partial authority lacked a distinct safe reconciliation state;
  - non-USD authoritative amounts were discarded even though their currency
    remained visible;
  - a no-call result incorrectly claimed provider billing was missing;
  - malformed usage counters could become a valid-looking zero estimate;
  - malformed billing could convert a successful paid inference into a route
    failure, discard returned usage/output and encourage a duplicate retry;
  - a search-provider failure before any AI request could be mislabeled as an
    ambiguous AI charge;
  - authoritative decimals could lose exact precision during float conversion
    and excessively precise/unbounded values were not rejected centrally;
  - model/provider identifiers in new guardrail and reconciliation metadata
    could retain embedded credential-like fragments;
  - delayed provider billing was collapsed into the generic pending state;
  - a pre-Apollo local failure could be mislabeled as an attempted AI call, and
    Apollo operation counts did not include an auth/rate-limit response;
  - a successful provider response with no token counters was synthesized with
    `api_calls=1` and could therefore appear to have an available zero-dollar
    estimate instead of missing estimate data;
  - merged workflows could reconcile one authoritative record against several
    calls or sum excess/duplicate records, and a cross-record reconciliation
    defect could still discard an otherwise successful paid output.
- The bounded correction now validates output ceilings as positive bounded
  integers and compares the exact decimal estimate to the configured limit
  before transport. Guardrail limits are bounded to 30 significant digits and
  18 decimal places, and underflowing/unbounded configuration fails visibly.
  It does not clamp or substitute invalid requested values.
- Billing normalization now requires an explicit three-letter currency,
  rejects provider mismatch, preserves a bounded authoritative native-currency
  amount and exact decimal text without inventing conversion, and represents
  pending, delayed, partial, unavailable and invalid data separately. Values
  are bounded to 30 significant digits and 18 decimal places. Raw or malformed
  billing envelopes are stripped from returned usage; only allowlisted
  normalized fields or a non-secret status marker survive.
- A malformed reconciliation envelope no longer discards a successful
  inference response. Returned content and usage remain available, while
  `provider_billing_status=invalid` and
  `reconciliation_status=reconciliation_failed` make the accounting defect
  visible. No automatic retry or replay is introduced.
- No-call and pre-transport guardrail failures now use
  `provider_billing_status=not_applicable`,
  `reconciliation_status=not_called` and `billing_data_missing=false`.
  Malformed provider token/call counters retain legacy numeric compatibility
  fields but set the additive estimate to unavailable with invalid-usage
  provenance.
- Lead Finder now tracks whether an AI request actually started before adding
  paid-call ambiguity fields, so a Tavily/SerpAPI failure before AI transport
  cannot be attributed to an AI charge. The same explicit boundary separates
  Apollo enrichment attempts from later AI fallback, and Apollo observed
  operations count the request even when it returns auth/rate-limit failure.
  Existing search/enrichment-provider billing status remains separate.
  Non-secret observed-operation counts require bounded non-negative integers;
  boolean, fractional, non-finite and oversized values remain unavailable.
- New model/provider metadata uses bounded safe identifiers and rejects
  embedded credential-like fragments; external billing reasons also redact
  authorization, key, token, secret and password forms.
- Provider responses with absent or partial input/output token counters now
  retain the legacy numeric `usd` field for response compatibility but set
  `estimated_cost_usd=null`, `cost_value_type=local_estimate_unavailable`,
  `usage_validation_status=missing` and
  `estimate_status=usage_unavailable`. Explicit provider-returned zero token
  counters remain a valid zero estimate. Mixed multi-call usage is unavailable
  if any constituent call omitted its counters, and browser display/export
  uses `n/a`/blank rather than presenting missing estimates as zero.
- Multi-call billing reconciliation is all-or-nothing: fewer normalized
  request-scoped billing records than paid calls is `partial`; more records
  than calls is `invalid`; and mixed-currency/provider defects remain invalid.
  Embedded reconciliation failures produce safe status fields without
  throwing away successful content or encouraging a duplicate paid retry.
- Browser history retains native authoritative amount/currency/source,
  invalid-data and estimate/usage-validation provenance inside the existing
  schema-10 JSON payload. Malformed persisted billing numbers are converted to
  an explicit invalid reconciliation rather than `NaN`, zero or authority.
- Repeated corrective targeted validation passes 31 Phase 5B Python tests, the
  Phase 5B frontend fixture and 91 Phase 3/4/5A/5B focused tests with
  `ResourceWarning` treated as an error.
- Complete v24.6.236 acceptance passes all 117 Python tests, all three frontend
  fixtures, 24 live source-smoke assertions, 27 Python files, 21 JavaScript
  files plus two full inline scripts, five Bash/command files and five
  PowerShell files. Owner-source validation/preflight, repository consistency,
  Git whitespace, exact-master 107-route and protected-module scope audits
  pass.
- The final private owner/source archive is
  `cv_studio_v24_6_236_phase5b_ai_cost_guardrails_corrective_owner_source.zip`
  under `C:\CV-Studio-Codex\releases\v24.6.236`. Its adjacent checksum and
  verification sidecars record the authoritative digest and exact final
  `source_commit`; a fresh extraction matches every tracked Git blob with zero
  missing, extra or byte-mismatched files.
- The corrective QA report and
  `CV_STUDIO_V24_6_236_PHASE_6_HANDOVER.md` are copied beside the archive.
  Phase 6 remains inactive and work stops before handoff or merge.
- No route, security guard, confirmation gate, provider endpoint/header/
  timeout/retry rule, SQLite schema, journal schema/semantic, credential slot,
  worker or Phase 6 scope changed.

## Phase 5A authorization and constraints

- Owner authorization received on 26 July 2026.
- Work only from clean master commit
  `4b366ddde1cf0a398706b52d55b0e82ed2dbc27c` and preserve v24.6.232 as the
  source baseline.
- Phase 5A is limited to persistent background jobs and resumable task state
  for existing authorized background work.
- Before production implementation, inventory all background/long-running
  routes and helpers; every in-memory state object, lock and queue; related
  filesystem and SQLite state; startup/shutdown behavior; existing lifecycle
  response fields; and retry/idempotency boundaries. Add characterization
  coverage for established success, progress, cancellation, failure and
  recovery behavior.
- Persistent jobs require explicit lifecycle states, bounded recovery,
  idempotent restart handling and failure-visible writes.
- Paid or externally mutating operations must never resume silently after an
  ambiguous failure.
- Preserve all 107 Flask routes/methods/endpoints/response fields, all five
  ordered global request/security guards, every authentication/CSRF/request-
  size/paid-call boundary, all 18 compatibility helper signatures, Phase 4
  call-time dependency rebinding and initialization order.
- Preserve request-ID propagation, structured errors/redaction, schema version
  10, every Phase 1–4 storage/client/modularisation contract, protected
  credential stores, external-service URLs/headers/retries and unsafe-write
  non-replay behavior.
- If Phase 5A would require changing schema version 10, existing data authority,
  compatibility contracts, paid-call behavior or established recovery
  semantics, stop and present the exact proposed change before implementation.
- Do not use live credentials or make paid external calls.
- Do not implement Phase 5B cost guardrails/provider billing reconciliation,
  credential migration, frontend modularisation/lazy loading, Phase 6,
  unrelated workflows, Flask server replacement or backburner items 4, 7 or 8.
- Stop after the Phase 5A owner/source release. Do not hand off, merge or begin
  Phase 5B/6 automatically.

## Phase 5A entry verification

- The worktree was clean and detached at entry; both `HEAD` and local `master`
  resolved exactly to
  `4b366ddde1cf0a398706b52d55b0e82ed2dbc27c`.
- All active installed source surfaces identify v24.6.232.
- The authoritative v24.6.232 release directory contains the owner/source ZIP,
  checksum, verification sidecar, corrective QA report and Phase 5 handover.
- The independently recomputed owner/source ZIP SHA-256 is
  `99255d90a6dd6fa6ce73e1a6baa77e93413595e2b64fc4113003a458f2883c0d`.
  The verification sidecar `source_commit` exactly matches the Phase 5A
  baseline/master commit.
- A fresh extraction contained 108 tracked files and matched every approved
  Git blob with zero missing, extra or byte-mismatched files.
- The ignored owner-source `adm-zip` 0.5.17 dependency was restored from the
  tracked vetted owner payload without changing Git state.
- Unchanged-source entry regression passed 55 Python tests with
  `ResourceWarning` treated as an error, 29 focused Phase 3/4 tests, both
  frontend fixtures and 24 live loopback source-smoke assertions.
- Static validation passed for 19 tracked Python files, 20 tracked JavaScript
  files plus both inline scripts, five Bash/command files and five PowerShell
  files. Owner-source validation/preflight, repository consistency and Git
  whitespace validation passed.

## Phase 5A bounded milestone plan

### Milestone 1 — inventory and characterization

- Record every existing background/long-running route and helper, lifecycle
  response field, process-local state object, lock/queue, filesystem/SQLite
  interaction and startup/shutdown behavior.
- Classify each operation as read-only/idempotent, paid, externally mutating or
  ambiguous after interruption; identify exact retry and recovery boundaries.
- Add no-network characterization tests for success, progress, cancellation,
  failure, restart/recovery and preserved global compatibility invariants before
  production behavior changes.

### Milestone 2 — bounded persistent-job foundation

- Add the smallest app-independent durable job-state foundation required by the
  selected existing work, with explicit dependencies and no circular import.
- Keep the primary SQLite schema at version 10. Use explicit lifecycle states,
  failure-visible atomic writes, bounded payloads/redaction and deterministic
  job identities.
- Prove write failure visibility, restart idempotency, bounded recovery and
  conservative classification of interrupted unsafe/paid work.

### Milestone 3 — existing-work integration

- Integrate only the inventoried existing background work that can preserve its
  route, response, security and non-replay contracts.
- Retain established app-level entry points, call-time dependency rebinding,
  initialization order, locks and paid confirmation boundaries.
- Resume only work proven safe and idempotent. Mark ambiguous paid/external
  mutations for visible owner action rather than replaying them.

### Milestone 4 — startup, shutdown and recovery

- Reconcile persisted non-terminal state once at the established startup
  boundary with bounded work and idempotent repeated initialization.
- Preserve current shutdown behavior and prevent duplicate workers or replay
  after restart.
- Characterize clean completion, cancellation, durable-write failure, crash/
  restart recovery and ambiguous unsafe operation handling.

### Milestone 5 — acceptance and release evidence

- Run complete regression, both frontend fixtures, live source smoke,
  tracked-language static validation, owner-source preflight, repository
  consistency and repeated compatibility review against exact Phase 5A master.
- Advance source version surfaces only after the implementation is clean.
- Commit the exact final source; create, freshly extract and byte-verify the
  next private owner/source ZIP; generate SHA-256/verification sidecars, QA
  report and next owner-gated handover under the new release directory.
- Confirm sidecar `source_commit` equals final branch HEAD, confirm the worktree
  is clean and stop before handoff/merge or Phase 5B/6.

## Phase 5A milestones

- [x] Verify the v24.6.232 master/source/package baseline and all entry gates.
- [x] Record owner authorization, scope boundaries and bounded milestone plan.
- [x] Complete background-work/state/recovery inventory.
- [x] Add pre-change characterization for lifecycle and failure paths.
- [x] Implement and verify the bounded persistent-job foundation.
- [x] Integrate only compatible existing background work.
- [x] Implement and verify bounded startup/shutdown recovery.
- [x] Run complete acceptance and repeated compatibility review.
- [x] Create and byte-verify the Phase 5A private owner/source release.
- [x] Produce QA report, sidecars and next handover; stop before Phase 5B/6.

## Phase 5A decisions and limitations

- The primary SQLite schema remains version 10. A migration or reinterpretation
  of existing durable data is not authorized.
- Phase 5A may create durable state only for new persistent-job identities and
  lifecycle metadata; it must not absorb credentials or reinterpret existing
  Phase 1/2 stores.
- No operation is resumable merely because it ran in a thread. Safe resumption
  requires an inventoried idempotency boundary and characterization evidence.
- Paid and externally mutating operations remain non-replaying after ambiguous
  interruption. Recovery must expose the state and required owner action.
- Tests use temporary local state and controlled fakes only. No live
  credentialed external request, paid call, native protected build or physical
  installer test is authorized or claimed.

## Phase 5A Milestone 1 inventory and characterization result

### Runtime threads, executors and shutdown behavior

- One daemon `_watchdog` thread starts at module import before Flask route
  registration. It sleeps in two-second intervals, leaves heartbeat shutdown
  disabled while `_HEARTBEAT_TIMEOUT == 0`, and performs one safe loopback
  `/ping` every 120 seconds. It has no task identifier, progress response,
  cancellation endpoint or durable state.
- `/restart` returns an empty HTTP 204 after spawning one daemon restart thread.
  The thread waits 0.4 seconds, then uses a detached replacement process on
  Windows or `os.execv` elsewhere. Unauthorized requests retain the legacy
  `error` field plus global normalized error fields. Restart itself is process
  control, not resumable user work, and remains outside the job foundation.
- `jobadder_spider_search` creates bounded per-request thread pools of at most
  five resume reads and six candidate-detail reads.
  `jobadder_ppc_placements` creates a bounded per-request pool of at most eight
  read-only placement-detail reads. The executors are joined before their
  synchronous route returns; there is no surviving server queue or worker.
- App startup initializes schema-10 storage before runtime PID/log setup,
  writes the exact-instance Windows PID file, registers only PID cleanup with
  `atexit`, starts the watchdog and then registers Flask routes. Normal Flask
  shutdown has no user-task drain/requeue step. Abrupt exit loses every
  process-local task/cache object.

### Backend process-local task and coordination state

- JobAdder OAuth uses `_ja_oauth_sessions` under `_ja_oauth_lock`. Entries
  contain pending/exchanging/complete/error state, expiry and protected login
  material until the initiating tab polls. `/jobadder/poll_token` returns
  `status=pending` with HTTP 202, `status/error/detail` on failure, or
  `status=complete`, `connected` and the established redacted public connection
  fields. These credential-bearing sessions are explicitly excluded from
  Phase 5A persistence.
- OneNote and Outlook device login use `_ms_graph_device_store` and
  `_ms_outlook_device_store` under their existing locks. `_polling` prevents a
  concurrent poll; pending/error responses retain route-specific `error`,
  `status`, `detail`, `action`, `technical_details`, `pending` and
  `retry_after` fields, while completion returns `ok`, `connected` and the
  existing public connection/account fields. Device codes and login sessions
  remain ephemeral and are not persistent jobs.
- Outlook draft creation uses `_ms_outlook_draft_request_cache`,
  `_MS_OUTLOOK_DRAFT_LOCK` and a `threading.Event`. A duplicate in-flight
  request returns HTTP 409 with `error`, `action` and
  `retry_same_request=True`; a completed duplicate returns the established
  draft result plus `reused=True`. Successful draft results retain
  `ok`, `draft_id`, `webLink`, `isDraft`, `mayRequireEditClick` and
  `created_at`. The cache expires completed entries after 30 minutes and
  in-progress entries after two minutes, but is lost on restart. Because Graph
  draft creation is an unsafe external mutation, Phase 5A must not replay it
  after an ambiguous interruption.
- Owner integration uses `_OWNER_INTEGRATION_LAST_REPORT` under an `RLock`.
  `/owner/integration/run` is synchronous and returns `ok`, `product`,
  `version`, `generated_at`, `request_id`, `summary` and `results`; each result
  retains `name`, `ok`, `status`, `duration_ms`, `detail` and optional
  `metadata`. It has no progress or cancellation response. Connected tests need
  credentials and the DeepSeek probe is paid and separately confirmed, so the
  route remains outside automatic persistence/resumption.
- AI Crawler preview data uses `_SPIDER_RESUME_TEXT_CACHE`,
  `_SPIDER_PREVIEW_PAYLOAD_CACHE`, byte/count/TTL limits and their two locks.
  Cooperative cancellation is a process-local generation counter protected by
  `_SPIDER_PREVIEW_CANCEL_LOCK`; expensive rendering is serialized by
  `_SPIDER_PREVIEW_RENDER_LOCK`. Salary AI and PPC details have their own
  process-local cache locks. These caches remain regenerable and are not made
  authoritative job storage.
- The shared OCR semaphore, protected credential-store locks and Phase 1/2
  repository locks are coordination primitives, not job queues, and remain in
  their exact initialization positions.

### Existing background preview lifecycle and response contract

- The only explicit user-work background queue is the AI Crawler preview
  prefetch queue in `index.html`. It holds candidate work, attempted/failed/
  target sets, byte budget, current promise, abort controller, generation,
  paused/running booleans, consecutive failures and stop reason entirely in the
  browser page process.
- Each queue item calls the existing synchronous GET
  `/jobadder/spider_candidate_preview?prefetch=1`. The server performs safe
  JobAdder reads plus bounded local rendering/extraction and returns only a
  terminal response. It exposes no job ID or server progress/status route.
- Successful profile-fallback prefetch retains the exact field set:
  `ok`, `candidate_id`, `name`, `mode`, `source`, `note`, `preview_text`,
  `search_text`, `tried`, `attachment_fingerprint`, `preview_cache_hit`,
  `preview_partial` and `preview_variant`. File-preview variants retain their
  established additional visual fields.
- `/jobadder/spider_preview_cancel_prefetch` increments the process-local
  generation and returns an empty HTTP 204. The interrupted request returns
  HTTP 409 with `ok`, `error`, `message`, `code`, `retryable`, `request_id`,
  `severity` and `prefetch_cancelled`; its code remains
  `PREVIEW_PREFETCH_SUPERSEDED`.
- Browser progress is queue-derived only: attempted/failed counts, cache bytes,
  current-running state and stop reasons `memory`, `locked`, `auth` or
  `failures`. Aborting the request or reloading the page loses queue state. A
  foreground preview deliberately supersedes background rendering.
- The operation is safe to restart from its request boundary: JobAdder calls
  are reads using the Phase 3 bounded safe-read retry policy, local rendering
  has no external mutation, and completed payloads are cacheable. It is the
  only existing background-work boundary selected for Phase 5A integration.

### Other long-running synchronous work

- Read-only/idempotent families are OneNote page/desktop imports, AI Crawler
  search, PPC placement retrieval, document preview/extraction/OCR and local
  DOCX generation. They return route-specific terminal success fields such as
  `pages`/`combined_text`, `query`/`items`/`filter_summary`,
  `items`/`returned`/`complete`/`details_complete`/diagnostics,
  or file/text payload fields. Failure retains each route's legacy `error`,
  `detail`, `status`, `needs_reconnect`, `query`, completeness or fallback
  fields plus global normalization where applicable. None exposes durable
  progress or cancellation state.
- Paid AI families are `/parse`, `/generate-ai`, `/blind`, Lead Finder search/
  people/email paths and the optional owner DeepSeek probe. Their established
  successes retain `ok`, result data/content, `usage`, `model`, `provider` and
  cost fields; established failures retain `error` and, where already present,
  `paid_ai_failure`, usage/model/provider/cost fields. A provider POST is never
  replayed after an ambiguous failure.
- Unsafe externally mutating families are Outlook draft creation, JobAdder
  candidate create/update, original/formatted CV upload and OneNote-to-JobAdder
  activity creation. Existing success/error shapes and confirmation/session
  boundaries remain. Phase 3 gives them zero ambiguous-failure retries.
- The frontend batch formatter, per-tab run indicators and OneNote profile
  creation keep their file/blob/result rows, running counters and cosmetic
  progress timers only in page memory. Uploaded `File`/`Blob` objects cannot be
  reconstructed after restart, and the workflow can cross paid AI and
  JobAdder-mutation boundaries. They are not safe automatic-resume candidates.

### Filesystem, SQLite and recovery inventory

- Primary authoritative durable data remains `cv_studio.sqlite3` at schema
  version 10 with its verified migration backups. Phase 5A will not add a table,
  migration or reinterpret an existing repository.
- Protected JobAdder, OneNote, Outlook and AI stores retain their current
  OS-backed mechanisms. No token, key, device code or protected session enters
  job state.
- Existing runtime filesystem state comprises bounded runtime/startup logs,
  exact-instance PID JSON, installer/update/receipt files, transition cache
  JSON and temporary document/subprocess files. None currently records a
  resumable user-task lifecycle.
- Existing recovery is terminal-request based: browsers retry safe reads,
  credential sessions reconnect, storage errors return request-ID recovery
  guidance, and ambiguous paid/unsafe writes require explicit user action.
  There is no startup reconciliation of interrupted user work.

### Retry/idempotency selection and bounded Phase 5A design

- Selected integration: AI Crawler preview prefetch only. It is already
  explicitly background, cooperatively cancellable and safe/idempotent at the
  request boundary. Foreground preview remains untracked as a job.
- The foundation will use a separate bounded atomic JSON job journal in the
  existing private per-user state directory. This is new lifecycle metadata,
  not a replacement data authority; the primary SQLite schema remains 10.
- Records will contain only an opaque deterministic job ID, kind, safety class,
  lifecycle state, bounded stage/progress, attempt/recovery counts, timestamps,
  request ID and bounded sanitized error code/summary. Candidate IDs, emails,
  credentials, document content, results and private paths will not be stored.
- Lifecycle states are `queued`, `running`, `succeeded`, `failed`,
  `cancel_requested`, `cancelled`, `interrupted` and `needs_attention`.
  Startup reconciliation is bounded and idempotent: interrupted safe reads are
  marked retryable for the next identical explicit request; cancelled work is
  closed; paid/unsafe non-terminal work is marked `needs_attention` and is
  never run.
- No background work will silently start at process import. The next identical
  prefetch request reclaims an interrupted safe job and restarts it from its
  established idempotent request boundary. Concurrent duplicate claims are
  rejected rather than duplicated.
- Existing 200/409/204 preview response fields remain exact. A journal write
  failure is a new failure-only structured request-ID response and stops the
  tracked prefetch rather than falsely claiming lifecycle persistence.
- No new Flask URL is required. All 107 baseline routes, five global guards,
  18 compatibility signatures and Phase 4 initialization order remain exact.

### Milestone 1 characterization evidence

- Added `tests/test_phase5a_persistent_jobs_characterization.py` before
  production changes.
- Six no-network tests pass with `ResourceWarning` treated as an error.
- Coverage fixes the 33 inventoried long-running/background route method and
  endpoint pairs, exact 107-route baseline, absence of a pre-existing job API,
  five ordered global guards, 80 MiB limit, schema version 10 and all 18
  compatibility signatures/initialization-order markers.
- Coverage fixes preview-prefetch success/cancellation field sets, empty-204
  cancellation behavior, process-local generation state, Outlook in-memory
  idempotency completion/failure behavior and the browser-only crawler/batch/
  tab/OneNote task-state markers.
- All external behavior is controlled by fixtures. No live credential,
  protected secret, external mutation or paid call is used.

## Phase 5A Milestone 2 bounded persistent-job foundation result

- Added app-independent `cvstudio_jobs.py`. It does not import `app`, open the
  primary SQLite database, access a protected store, start a thread or perform
  a network request.
- The separate atomic JSON journal defaults to
  `cv_studio_jobs.json` in the existing private per-user state directory.
  Tests may use `CVSTUDIO_JOB_STATE_PATH`; an existing `CVSTUDIO_DB_PATH`
  override places the journal beside the temporary test database.
- The journal schema is independent metadata format 1. Primary
  `cvstudio_storage.py` remains exactly at schema version 10 with no migration,
  table, backup, repository or authority change.
- Records are capped at 500 and the journal at 2 MiB. Atomic writes use a
  same-directory temporary file, flush/fsync and `os.replace`; in-memory state
  changes only after the durable replace succeeds. Terminal records are pruned
  oldest-first, while active work is never silently evicted.
- Records admit only opaque SHA-256 IDs, bounded kind/safety/stage names,
  lifecycle/progress values, attempt/recovery counts, timestamps, opaque
  request-ID digests and bounded sanitized error/recovery metadata. No input
  payload, candidate identifier, email, credential, document content, result or
  private path is accepted.
- Explicit states are `queued`, `running`, `succeeded`, `failed`,
  `cancel_requested`, `cancelled`, `interrupted` and `needs_attention`.
  Conflicting concurrent claims fail with `JOB_ALREADY_RUNNING`.
- Startup recovery converts active safe/idempotent work to explicit retryable
  `interrupted`, closes cancellation requests, and converts active paid/
  externally mutating work to non-retryable `needs_attention`. It never
  executes a job. Reconciliation is idempotent and safe recovery is capped at
  three interrupted process lifetimes before `JOB_RECOVERY_LIMIT_REACHED`
  requires an explicit manual retry.
- Corrupt/unsupported/oversized journals are never overwritten. Atomic write
  and corruption failures raise typed failure-visible errors with bounded
  recovery guidance.
- Added seven foundation tests covering atomic lifecycle, opaque persisted
  metadata, pruning, concurrent-claim conflict, safe/unsafe/cancel restart
  classification, idempotent and bounded recovery, write-failure rollback,
  corrupt-byte preservation, kind cancellation and sensitive-text redaction.
- All seven tests pass with `ResourceWarning` treated as an error. Python
  compilation and Git whitespace validation pass.
- Owner-source validation/preflight now requires and compiles
  `cvstudio_jobs.py`; no protected package or native build is created.

## Phase 5A Milestone 3 existing-work integration result

- `app.py` now initializes one `PersistentJobStore` immediately after the
  established schema-10 storage initialization. Existing storage, runtime,
  watchdog, Flask, OCR semaphore and extracted-module relative initialization
  markers remain in their established order.
- Only the existing AI Crawler
  `GET /jobadder/spider_candidate_preview?prefetch=1` boundary is tracked. No
  new route, worker, queue, polling API, frontend state or result store was
  added. The route remains a synchronous safe JobAdder read plus bounded local
  rendering.
- Each tracked request claims a deterministic double-hashed account/candidate
  cache identity, writes `running`, records only bounded coarse stages, then
  durably closes as `succeeded`, `failed` or `cancelled`. Candidate identifiers,
  access tokens, profile fields, preview content, filenames, results and
  external response bodies never enter the journal.
- Request correlation is stored only as a one-way SHA-256 digest, while HTTP
  responses retain the established original request-ID propagation contract.
- A matching active claim returns the structured request-ID
  `JOB_ALREADY_RUNNING` 409 before attachment/profile work begins. An
  `interrupted` safe record is reclaimed only when the browser explicitly
  issues the same prefetch request; its attempt counter advances and the route
  restarts at the established idempotent request boundary.
- Cooperative prefetch cancellation still uses the established generation
  counter and 409 `PREVIEW_PREFETCH_SUPERSEDED` response. The existing empty
  204 cancellation endpoint, foreground supersession and diagnostics cache
  clear now also durably request cancellation for active preview-prefetch
  records.
- Existing successful 200, cooperative-cancellation 409 and cancellation 204
  response fields/bodies remain exact. A failed begin, progress, completion,
  failure or cancellation journal write returns a structured request-ID job
  error rather than claiming persistence succeeded.
- `PersistentJobError` uses the existing normalized error payload helper and
  exposes only bounded public recovery guidance. It does not disclose the
  journal path, private identifiers, credentials or stored detail.
- Added eight no-network integration tests covering opaque success lifecycle,
  explicit restart/resume, concurrent-claim rejection, begin/progress write
  failures, corruption recovery, durable cancellation and cooperative
  cancellation closure.
- Route count remains 107, the five global guards and 80 MiB boundary are
  unchanged, all 18 compatibility signatures remain exact, primary storage
  schema remains 10 and Phase 4 call-time service rebinding remains covered.
  No paid call, external mutation, protected credential access or automatic
  replay was introduced.

## Phase 5A Milestone 4 startup, shutdown and recovery result

- Real fresh-process app imports now prove startup reconciliation executes once
  at the new journal boundary after schema-10 storage initialization. A running
  safe read becomes retryable `interrupted`, a pending cancellation becomes
  terminal `cancelled`, and an active externally mutating fixture becomes
  non-retryable `needs_attention`.
- A second fresh-process import over the reconciled journal reports zero new
  recovery actions and preserves every record byte-for-byte semantically. No
  attempt count advances and no job function executes until an explicit request
  claims safe interrupted work.
- Recovery is bounded by the foundation's three-interruption limit. The existing
  tests prove a fourth reconciliation becomes visible
  `JOB_RECOVERY_LIMIT_REACHED`/`retry_manually`; ambiguous paid/external
  mutation fixtures never execute and remain owner-review-only.
- A corrupt journal is preserved exactly. Fresh app import records
  `JOB_STATE_CORRUPT` but leaves all 107 routes registered and unrelated
  `/ping` available with its existing empty 204 response. A tracked prefetch
  claim returns the structured non-retryable request-ID recovery response before
  attachment/profile work begins.
- `cvstudio_jobs.py` contains no worker thread, executor, subprocess, network
  client, app import, `.start()` call or `atexit` registration. Startup never
  launches or replays work. Existing shutdown behavior remains the single
  runtime-PID cleanup registration; no task drain, hidden replay or new shutdown
  hook was added.
- Added three isolated fresh-process startup tests for one-time reconciliation,
  idempotent second startup, corrupt-state isolation and absence of execution/
  shutdown hooks. Together with eight integration, seven foundation, six
  characterization and seven Phase 4 tests, all 31 focused tests pass.
- Primary SQLite remains schema 10; no existing authority, compatibility
  signature, route, global guard, credential store, external-client policy,
  paid-call gate or Phase 4 dependency-rebinding contract changed.

## Phase 5A Milestone 5 acceptance and release result

- Source identity advanced to the next unused version, v24.6.233, across the
  backend, frontend, installer/receipt/launcher, protected-build and private
  starter-pack surfaces. Historical release evidence remains immutable.
- Focused acceptance passed all 31 Phase 5A/Phase 4 tests. Complete Python
  discovery passed all 79 tests with `ResourceWarning` treated as an error.
- Both frontend storage fixtures passed. Live loopback source smoke passed all
  24 assertions with temporary receipt, schema-10 database and runtime state.
- Static validation passed for all 24 tracked Python files, all 20 tracked
  JavaScript files plus both complete inline scripts, all five Bash/command
  files and all five PowerShell files.
- Owner-source validation/preflight, repository consistency and Git whitespace
  validation passed after the versioned Windows launch/build files were restored
  to their required BOM-free CRLF representation.
- Warnings-as-errors smoke found one concrete cleanup issue in the historical
  harness: an expected HTTP 404 response was read but not closed. The response
  now closes deterministically, and smoke/regression/static gates were repeated
  cleanly.
- AST comparison against exact master
  `4b366ddde1cf0a398706b52d55b0e82ed2dbc27c` confirms all 107 ordered route
  URL/method/endpoint tuples remain exact. Only the two selected preview route
  functions changed; the only new app functions are the job error and durable
  cancellation adapters.
- The five ordered global guards, 80 MiB request boundary, 18 compatibility
  signatures, schema version 10 and established initialization markers remain
  exact. Phase 1–4 storage/client/module implementations remain unchanged
  outside version surfaces and the documented bounded integration.
- Produced
  `cv_studio_v24_6_233_phase5a_persistent_jobs_qa_report.md` and
  `CV_STUDIO_V24_6_233_PHASE_5B_HANDOVER.md`. The handover is not Phase 5B
  authorization.
- The private owner/source ZIP is generated from the exact final clean commit
  with one `cv_formatter/` root and copied with SHA-256/verification sidecars
  to `C:\CV-Studio-Codex\releases\v24.6.233`. A fresh extraction is required to
  have zero missing, extra or byte-mismatched files; the external verification
  sidecar records the exact final `source_commit`, byte size and counts.
- No live credentialed request or paid call was made. No protected colleague
  ZIP or native-build claim was made. Stop before handoff/merge and before Phase
  5B or Phase 6.

## Phase 5A post-release repeated-review findings

The owner requested another complete review against exact master after the
v24.6.233 release, with every finding corrected and the review repeated until
clean. Five persistence-boundary findings were confirmed:

1. Quoted JSON secret and candidate-ID values could evade the journal error-
   summary sanitizer, especially when a quoted value contained whitespace or
   escaped quotes.
2. A caller-supplied request ID already shaped as 64 lowercase hexadecimal
   characters was treated as opaque and persisted without a one-way digest.
3. Schema-1 load validation silently normalized unknown fields, non-finite
   timestamps, out-of-range progress, non-boolean flags, raw request IDs and
   unsanitized summaries instead of treating the unchanged journal as corrupt.
4. Completion/failure helpers accepted invalid transitions from interrupted or
   incompatible terminal states.
5. Capacity pruning treated `interrupted` and `needs_attention` as removable.
   Losing `needs_attention` evidence could permit a later identical unsafe
   identity to be claimed despite ambiguous prior execution.

Corrections now:

- redact quoted/escaped credential and candidate values plus control
  characters before any error metadata is accepted;
- digest every non-empty inbound request ID, including 64-hex-shaped input;
- require the exact schema-1 top-level/record field sets and canonical bounded
  types/ranges, finite timestamps, opaque request digests, booleans and already
  sanitized summaries; corrupt bytes remain unchanged;
- enforce explicit valid finish transitions with `JOB_STATE_CONFLICT`;
- prune only completed `succeeded`, `failed` or `cancelled` records and fail
  visibly when the bound contains only protected active/interrupted/review
  evidence.

Four additional foundation tests cover these exact findings. All 11 foundation
tests and the 35-test focused Phase 5A/Phase 4 gate pass without network,
credentials, external mutations or paid calls.

The first repeated review after those corrections found two additional strict-
boundary cases:

- duplicate JSON object keys could hide unsupported top-level or record data
  because the standard decoder retained only the last value;
- an escaped lone Unicode surrogate could pass record parsing and fail before
  the atomic-write exception wrapper with an untyped encoding error.

The loader now rejects duplicate object keys and noncanonical Unicode while
preserving the source bytes. Serialization and encoding occur inside the typed
failure-visible write boundary. A twelfth foundation test proves a non-finite
clock fails with `JOB_STATE_UNAVAILABLE` without creating state; strict-
corruption subcases cover duplicate keys and escaped surrogates.

The next repeated review preserved the exact master app diff and released
schema-1 compatibility but found one bounded-read TOCTOU gap: the loader checked
`stat().st_size` before `read_bytes()` without checking the actual bytes read.
A concurrent atomic replacement could therefore substitute an oversized file
between those operations. The loader now enforces the same non-empty/maximum
bound on the actual byte buffer before JSON parsing. A thirteenth foundation
test simulates a stale small `stat` result over an oversized actual read and
proves corrupt-byte preservation.

The fourth repeated review reproduced two remaining safety-boundary gaps:

- quoted `Authorization` and generic token/cookie/credential fields were not
  covered by the bounded error-summary sanitizer;
- a syntactically valid legacy or externally altered `interrupted` record with
  a paid/external-mutation safety class could be reclaimed even though its
  execution outcome remained ambiguous.

The sanitizer now covers generic OAuth tokens, authorization values, cookies,
credentials and secrets in addition to the existing specific fields. Job
claiming independently refuses both `interrupted` and `needs_attention`
identities for every unsafe class, so malformed or legacy lifecycle metadata
cannot cross the no-replay boundary. A fourteenth foundation test proves the
unsafe interrupted case and the sanitizer characterization covers the expanded
credential forms.

The fifth review started again from exact master and is clean:

- after normalizing only the v24.6.234 release string, all 107 ordered route
  URL/method/endpoint tuples and all five guard bodies remain exact;
- the only changed existing app functions are the two authorized preview
  endpoints and the only new functions are their two bounded job adapters;
- all 18 compatibility signatures and Phase 4 initialization markers pass;
- Phase 1–4 storage, client, storage-bridge, diagnostics and document-safety
  implementation modules remain exact master bytes;
- adversarial journal, lifecycle, redaction, startup/recovery and released
  schema-1 compatibility checks have no remaining concrete finding.

### v24.6.234 corrective acceptance and release result

- Source identity advanced from immutable v24.6.233 to the next unused
  private owner/source version, v24.6.234, across backend, frontend,
  installer/receipt/launcher, protected-build and starter-pack surfaces.
- The focused Phase 5A/Phase 4 gate passes all 38 tests: 14 foundation, eight
  integration, three fresh-process startup, six Phase 5A characterization and
  seven Phase 4 compatibility tests.
- Complete Python discovery passes all 86 tests with `ResourceWarning` treated
  as an error. Both frontend fixtures and all 24 live loopback source-smoke
  assertions pass.
- Static validation passes for 24 tracked Python files, 20 tracked JavaScript
  files and both complete inline scripts, five Bash/command files and five
  PowerShell files.
- Owner-source validation/preflight, vetted `adm-zip` 0.5.17 behavior,
  repository consistency and Git whitespace validation pass.
- The ten corrective findings and unchanged recovery/non-replay semantics are
  recorded in
  `cv_studio_v24_6_234_phase5a_persistent_jobs_corrective_qa_report.md`.
  `CV_STUDIO_V24_6_234_PHASE_5B_HANDOVER.md` is owner-gated evidence only and
  does not authorize Phase 5B.
- The authoritative private archive is
  `cv_studio_v24_6_234_phase5a_persistent_jobs_corrective_owner_source.zip`
  under `C:\CV-Studio-Codex\releases\v24.6.234`, with adjacent SHA-256 and
  verification sidecars. It is generated from final branch HEAD and must
  freshly extract with zero missing, extra or byte-mismatched files.
- No live credentialed or paid call, protected colleague build, native-build
  claim, handoff or merge was made. Phase 5B and Phase 6 remain inactive.

## Phase 4 authorization and constraints

- Owner authorization received on 23 July 2026.
- Work only from clean master commit
  `7a0efcf0bce10b07e034592fb22a6021141d4146` and preserve v24.6.230 as the
  source baseline.
- Phase 4 is limited to gradual backend modularisation without changing
  behavior, routes or response contracts.
- Before each bounded extraction, inventory routes, helpers/globals, response
  fields, locks, protected stores, filesystem state and startup side effects;
  add success/error characterization; then extract with explicit dependencies
  and no circular imports.
- Preserve route registration and initialization order, all required app-level
  compatibility adapters, all 107 routes/methods/response fields, every
  authentication/CSRF/request-size boundary, schema version 10, Phase 1/2
  storage guarantees and all Phase 3 shared-client behavior.
- Preserve request-ID propagation, error normalization/redaction, startup,
  update, receipt, backup, restore and rollback behavior, paid-call gates and
  existing external-service URLs, headers and retry rules.
- Do not make live credentialed or paid external calls.
- Do not implement credential migration, persistent background jobs/resumable
  state, central AI cost guardrails/billing reconciliation, frontend
  modularisation/lazy loading, unrelated workflows, Flask server replacement,
  roadmap item 7/8 or any Phase 5/6 work.
- Stop after the Phase 4 private owner/source release, QA report and Phase 5
  handover. Do not begin Phase 5 automatically.

## Phase 4 entry verification

- The owner `master` worktree and this worktree were clean at entry and both
  resolved to owner-specified commit
  `7a0efcf0bce10b07e034592fb22a6021141d4146`.
- All active source version surfaces identify v24.6.230.
- The authoritative v24.6.230 release directory contains the owner/source ZIP,
  SHA-256, verification JSON, QA report and Phase 4 handover.
- The independently computed owner-ZIP SHA-256 is
  `b6004e7577e4c1cb5f9543ec526b8c1b7d46c09ce9aea4bf9cb9cc6d7dc6faf3`;
  the verification sidecar `source_commit` exactly matches the Phase 4 baseline
  commit.
- A fresh extraction contained 100 tracked files with zero missing, extra or
  byte-mismatched files against the baseline Git blobs.
- The ignored owner/source runtime dependency was restored from the immutable
  vetted `adm-zip` 0.5.17 tree. Entry QA then passed 48 Python tests with
  `ResourceWarning` treated as an error, both frontend fixtures, 24 live-source
  smoke assertions, 22 focused Phase 3 no-network tests, all tracked Python/
  JavaScript/Bash/PowerShell syntax checks, owner-source validation/preflight,
  repository consistency and Git whitespace validation.
- The entry suites re-proved schema version 10 migrations, idempotency,
  rollback/restart, corruption recovery, tombstones, rejected-replacement
  preservation, strict setting validation, restore failure visibility, legacy
  bytes, the exact 107-route inventory and Phase 3 redirect/header/content-
  negotiation contracts.

## Phase 4 implementation plan

### Milestone 1 — inventory and compatibility fixtures

- Map the monolithic backend into cohesive candidate areas and record each
  area's routes, helper/global dependencies, response fields, locks, protected
  stores, filesystem state and startup side effects.
- Select the smallest low-coupling module boundaries and add characterization
  fixtures for success and error behavior before production movement.
- Record the final bounded extraction sequence and explicit dependency design.

### Milestones 2–4 — bounded backend extractions

- Extract one selected cohesive backend area per milestone.
- Keep Flask route registration and compatibility entry points in their
  established order unless characterization proves an equivalent explicit
  registration adapter.
- Run focused characterization and integration tests, update this record and
  create a stable Git checkpoint before starting the next extraction.

### Milestone 5 — acceptance and release evidence

- Run complete regression, live source smoke, tracked-language static
  validation, owner-source preflight, repository consistency and iterative
  final review against the exact Phase 4 master baseline.
- Advance completed owner/source version surfaces only after the implementation
  is clean, create and freshly byte-verify the private owner/source ZIP, and
  produce the QA report, SHA-256 and Phase 5 handover.
- Confirm the verification sidecar `source_commit` exactly matches final branch
  HEAD, copy all artifacts to the new release directory and stop before merge.

## Phase 4 milestones

- [x] Verify the v24.6.230 master/source/package baseline and all entry gates.
- [x] Record owner authorization, scope boundaries and milestone plan.
- [x] Inventory candidate backend areas and select bounded module sequence.
- [x] Add pre-move success/error characterization for the selected areas.
- [x] Extract and verify the first bounded backend module.
- [x] Extract and verify the second bounded backend module.
- [x] Extract and verify the third bounded backend module.
- [x] Run complete regression, static validation and iterative final review.
- [x] Create and byte-verify the Phase 4 private owner/source release.
- [x] Produce QA report, SHA-256 and Phase 5 handover; stop before Phase 5.

## Phase 4 decisions and limitations

- Phase 4 is an incremental structural change, not a rewrite. Candidate areas
  are not selected merely because code is long; coupling, initialization order
  and compatibility risk determine the sequence.
- Characterization and integration tests use local fixtures and controlled
  fakes only. No live credentialed external-service or paid request is
  authorized or claimed.
- Schema version 10 and every existing durable-storage, protected-credential,
  browser-mirror, update/receipt and rollback contract remain fixed.
- No protected colleague package will be produced without matching native
  compilation and smoke certification.

## Phase 4 Milestone 1 module inventory and selection

The baseline backend has 22,963 lines in `app.py`, 107 Flask route URLs and five
global `before_request` functions in this exact order:
`_assign_cvstudio_request_id`, `_reject_declared_oversize_request`,
`_reject_non_local_host_header`, `_require_ai_spend_browser_session` and
`_reject_cross_site_unsafe_request`. The global request limit is 80 MiB. Phase 4
will leave this registration and security boundary in `app.py`.

### Selected first area — durable-storage HTTP bridge

- Routes: the 19 existing `/storage/*` routes for usage history, PPC metadata,
  OneNote transfer records, saved OneNote links and allowlisted browser
  settings. Their exact GET/POST methods and existing endpoint function names
  remain registered in place.
- Helper/global dependencies: Flask request JSON, `jsonify`, the current
  request ID/error-payload adapters, the five repository globals,
  `BROWSER_SETTING_KEYS`, `BrowserSettingsRepository.normalize_value`, record
  normalizers and the existing recursive usage-secret filter.
- Response fields: `ok`, `request_id` and `legacy_preserved` on every success;
  store-specific `records`, `metadata`, `links`, `settings`, `imported`,
  `written` or `deleted`; and the established normalized
  `STORAGE_PAYLOAD_INVALID` or `StorageError` contract on failure.
- Locks/protected stores: no bridge-owned lock and no protected credential
  store. Repository transactions retain their existing SQLite locking and
  validation behavior.
- Filesystem/state: schema-10 SQLite plus the already-preserved Phase 2A JSON
  and browser mirrors. The bridge must not open, migrate, back up, delete or
  reinterpret those stores itself.
- Startup side effects: repository instances and schema initialization occur
  before Flask route registration. The extracted bridge receives repository
  providers after initialization so existing test/runtime compatibility
  rebinding remains effective.
- Boundary decision: extract validation and handler orchestration into
  `cvstudio_storage_bridge.py`; retain all decorators and one-line endpoint
  adapters in `app.py`.

### Selected second area — redacted runtime diagnostics/support bundle

- Routes: `/diagnostics/runtime` GET, `/diagnostics/clear_preview_cache` POST
  and `/diagnostics/support_bundle` POST, with their existing endpoint names.
- Helper/global dependencies: request JSON/current request ID, runtime snapshot
  and preview-cache callbacks, root/version/log paths, `send_file`, system
  memory/dependency probes, connection-status booleans and install-receipt
  status.
- Response fields: the runtime snapshot's established 18 top-level fields; the
  clear response's `ok`, `request_id` and `cache`; and the support ZIP's
  `runtime.json`, `browser.json`, optional roadmap, README and redacted bounded
  runtime-log tails.
- Locks/protected stores: diagnostics uses existing preview-cache locks only
  through injected callbacks. It reads redacted connection booleans and never
  receives credential values or a protected-store write dependency.
- Filesystem/state: read-only roadmap and at most 256 KiB from each of two
  bounded runtime logs. It writes only the in-memory ZIP returned to the caller.
- Startup side effects: none. Runtime logging, cache creation, protected-store
  loading and watchdog startup remain in `app.py`.
- Boundary decision: extract system-memory probing, support-text redaction,
  browser-payload sanitization and in-memory ZIP construction into
  `cvstudio_diagnostics.py`; retain runtime state assembly and route decorators
  in `app.py`.

### Selected third area — document safety/limited OCR primitives

- Directly affected routes: `/ocr/health`, `/ocr`, `/preview-file`,
  `/extract-text`, `/parse` and `/blind`. The helpers are also used by AI
  Crawler preview rendering, whose route contracts remain in `app.py`.
- Helper/global dependencies: ZIP and byte streams, Pillow, pdfplumber,
  pypdfium2 with pdf2image fallback, pytesseract, monotonic time and one bounded
  OCR semaphore.
- Response/error behavior: document-validation failures remain 400 unless they
  match the established safe-limit/resource markers, which remain 413. Existing
  route errors retain their legacy `error` text plus normalized `ok`, `message`,
  `code`, `retryable`, `request_id` and `severity` fields.
- Locks/protected stores: one process-local bounded OCR semaphore; no protected
  credential store and no persistent user-data lock.
- Filesystem/state: helpers operate on caller-supplied bytes and decoded/rendered
  images. The Poppler path remains a caller dependency; no persistent path or
  startup write is introduced.
- Startup/security side effects: none. The 80 MiB request boundary, Host/CSRF
  guards, extension-only OCR-origin exception and paid browser-session gates
  for `/parse` and `/blind` remain registered unchanged in `app.py`.
- Boundary decision: extract constants, the shared semaphore, ZIP/image/PDF
  safety validation and bounded render/OCR primitives into
  `cvstudio_document_safety.py`; keep compatibility aliases in `app.py` because
  mature route and AI Crawler helpers call the established private names.

### Deferred candidates

- Installer receipt, restart/update/rollback and runtime PID/log startup code is
  intentionally deferred because its import-time side effects and launcher
  compatibility make it a higher-risk later boundary.
- JobAdder, Microsoft Graph and AI-provider compatibility orchestration remains
  around the completed Phase 3 clients; Phase 4 will not reopen their transport
  policies.
- Protected secret vaults, OneNote desktop COM/PowerShell integration, AI
  Crawler orchestration, Lead Finder and CV-generation workflows remain in
  `app.py` for this gradual release because they have materially larger state,
  credential or behavior surfaces than the three selected boundaries.

### Milestone 1 characterization result

- Added
  `tests/test_phase4_backend_modularization_characterization.py` before moving
  production code.
- Four tests pass with `ResourceWarning` treated as an error.
- Coverage fixes the exact route methods and endpoint names for all 28 directly
  selected routes, the complete 107-route count, all five global request guards,
  the 80 MiB request boundary and the paid browser-session boundary for
  `/parse` and `/blind`.
- Storage coverage fixes every success field family across the 19 bridge routes,
  recursive usage-secret filtering and representative invalid payloads for all
  five stores.
- Diagnostics coverage fixes the 18-field runtime payload, preview-cache clear
  response, support-bundle members and credential/email/candidate-ID redaction.
- Document coverage fixes the safety constants, 400/413 classification, ZIP
  validation, missing-file errors, normalized error fields, paid-session gate
  and unsafe-request rejection.
- No production source, route registration, storage schema/data, startup side
  effect or external call changed during Milestone 1.

## Phase 4 Milestone 2 durable-storage bridge result

- Added `cvstudio_storage_bridge.py` with the Phase 2A usage/PPC validators,
  Phase 2B record/setting validators and the handler orchestration for all 19
  existing storage routes.
- `app.py` retains every original route decorator and endpoint function name.
  Each endpoint is now a one-line compatibility adapter into one explicitly
  wired `StorageBridge`.
- Repository dependencies are providers rather than captured instances. This
  preserves initialization order and the established integration-test/runtime
  ability to replace an app-level repository without rebuilding Flask.
- The extracted module has no `app` import and therefore no circular dependency.
  It receives request JSON, `jsonify`, structured error/current-request-ID
  adapters, repository providers, the exact setting allowlist and canonical
  setting normalizer explicitly.
- Schema version 10, repository implementations, migration/backup behavior,
  protected stores, legacy JSON/browser mirrors and error handlers are
  unchanged.
- Focused Phase 1/2 repository, real-Flask bridge and Phase 4 characterization
  verification passed 24 tests with `ResourceWarning` treated as an error.
- Complete Python discovery passed 52 tests. Both frontend storage fixtures and
  the 24-assertion live source smoke passed.
- Python compilation, Git whitespace validation and a direct AST check proving
  the bridge has no app import passed.
- No route URL/method/endpoint, response field, authentication/CSRF/request-size
  boundary, startup side effect, external-service behavior or user workflow
  changed.

## Phase 4 Milestone 3 diagnostics/support result

- Added `cvstudio_diagnostics.py` with cross-platform physical-memory probing,
  dependency presence probing, support-text redaction, browser diagnostic
  sanitization and in-memory support-bundle construction.
- `DiagnosticsService` receives request/response adapters, runtime/cache
  callbacks, version/root/log providers and the app-level redactor explicitly.
  It does not import `app` or receive a protected credential store.
- `app.py` retains the three original diagnostics route decorators and endpoint
  names as one-line adapters. Runtime snapshot assembly remains app-owned so
  integration-state initialization and redacted connection booleans preserve
  their existing order.
- App-level compatibility helpers retain the established
  `_cvstudio_system_memory_status`, `_cvstudio_dependency_status`,
  `_cvstudio_redact_support_text` and
  `_cvstudio_sanitize_browser_diagnostics` names.
- The runtime-log path is an injected provider rather than a captured value,
  preserving test/runtime rebinding and the existing two-tail read behavior.
- Focused Phase 1 diagnostics/support and Phase 4 characterization verification
  passed 11 tests with `ResourceWarning` treated as an error.
- Complete Python discovery passed 52 tests and the live source smoke passed all
  24 assertions. Python compilation, Git whitespace validation and a direct AST
  check proving no app import passed.
- Support ZIP membership, 256 KiB tail bounds, redaction, request IDs, route
  methods/endpoints, preview-cache locking callbacks and all 18 runtime response
  fields remain unchanged.

## Phase 4 Milestone 4 document-safety result

- Added `cvstudio_document_safety.py` with the established ZIP expansion limits,
  image/PDF page limits, one shared bounded OCR semaphore, 180-second pagewise
  OCR deadline, PDFium rendering and Poppler fallback.
- `app.py` imports the established private constant/helper names as
  compatibility aliases. Mature OCR, preview, extraction, CV parsing/blinding
  and AI Crawler call sites therefore require no orchestration or response
  change.
- The module has no `app` import, protected-store dependency, persistent path,
  route registration or startup side effect.
- The global 80 MiB request boundary, Host/CSRF guards, OCR extension-origin
  exception and paid browser-session gates remain in their original app-level
  order.
- Phase 4 characterization passed all four tests with `ResourceWarning` treated
  as an error. Complete Python discovery passed 52 tests, both frontend fixtures
  passed and live source smoke passed all 24 assertions.
- Python compilation, owner-source validation/preflight, repository consistency,
  Git whitespace validation and a direct AST check proving no app import passed.
- ZIP validation, 400/413 classification, missing-file response fields,
  page/image limits, OCR serialization and renderer fallback behavior remain
  unchanged. No external service, live credential or paid request was used.

## Phase 4 acceptance review corrections

- The first full baseline-diff review found one compatibility risk: the
  diagnostics service initially captured runtime/cache/redaction function
  objects at construction, while the former route bodies resolved those
  app-level globals on every call.
- The service wiring now uses explicit forwarding lambdas, preserving runtime
  and test rebinding without adding an app import or changing initialization
  order.
- The repeated review proves the exact ordered 107-route decorator inventory
  against master, schema version 10, no app import from any extracted module,
  all 22 Phase 3 client fixtures and all four Phase 4 characterization tests.
- No further concrete finding remains from this review pass.

## Phase 4 post-release corrective review — 26 July 2026

- The owner requested a new full review of Phase 4 commit
  `0d2b02ec924a7531d96f236396a0620674fcb994` against exact master baseline
  `7a0efcf0bce10b07e034592fb22a6021141d4146`.
- Differential probes confirmed three related call-time compatibility
  regressions that the original route/response characterization did not cover:
  - `StorageBridge` captured validators, response/error adapters, the browser
    setting allowlist and canonical normalizer at construction instead of
    resolving the established app compatibility globals on each request.
  - `DiagnosticsService` captured the current-request-ID function, Flask
    response functions and version at construction, and support-bundle browser
    sanitization bypassed the established app helper.
  - direct document-helper aliases resolved limits, the OCR semaphore and
    nested PDF helpers inside the extracted module; the baseline resolved those
    app compatibility globals at call time. The semaphore was also created
    earlier during module import instead of at its established app startup
    position.
- Corrected the three boundaries with explicit forwarding callbacks and thin
  app-level wrappers. Storage validators, structured errors, request IDs,
  setting rules and repositories now resolve per call. Diagnostics now resolves
  request/response, runtime/cache, redaction/sanitization, version, clock and
  path dependencies per call. Document safety receives the current limits,
  semaphore, nested helpers and monotonic clock explicitly.
- Restored the app-level storage constants and OCR semaphore to their original
  initialization positions. The extracted modules remain app-independent and
  introduce no circular import.
- Added three focused regression tests for storage, diagnostics and document
  dependency rebinding. All seven Phase 4 characterization tests pass against
  both the untouched master baseline and the corrected branch.
- Complete Python discovery passes 55 tests with `ResourceWarning` treated as
  an error. Both frontend fixtures and all 24 live source-smoke assertions
  pass.
- Static validation passes for 19 Python files, 20 JavaScript files plus both
  inline scripts, five Bash/command files and five PowerShell files.
  Owner-source preflight, repository consistency and Git whitespace validation
  pass.
- The repeated structural review proves the exact ordered 107-route inventory,
  five global request/security guards, all 18 established app helper
  signatures, the 80 MiB request limit, schema version 10 and no `app` import
  from any extracted module. No further concrete finding remains.
- The owner authorized the next valid corrective identity, v24.6.232, on
  26 July 2026. The immutable v24.6.231 release artifacts were not overwritten
  or reinterpreted, the branch remains unmerged and Phase 5 was not started.

## v24.6.232 Phase 4 corrective release result

- Advanced all active production, browser, installer, launcher, watchdog,
  protected-build and starter-pack version surfaces together to v24.6.232.
- Complete Python discovery passes 55 tests with `ResourceWarning` treated as
  an error. Both frontend fixtures and the 24-assertion live source smoke pass.
- All seven Phase 4 characterization tests pass against both the exact master
  baseline and corrected source, including the three new call-time rebinding
  fixtures.
- Static validation passes for all 19 Python files, 20 JavaScript files plus
  both inline scripts, five Bash/command files and five PowerShell files.
  Owner-source preflight, repository consistency and Git whitespace validation
  pass.
- Final repeated review proves the exact ordered 107-route inventory, five
  global request/security guards, unchanged error handlers, all 18 established
  compatibility signatures, the 80 MiB request limit, schema version 10,
  original app-level initialization positions and no `app` import from any
  extracted module.
- The corrective-release final review found one additional definition-order
  drift: `_phase2b_record_array` preceded the Phase 2A route declarations
  instead of following them as on master. The side-effect-free wrapper was
  restored to its exact master-relative position and all suites were repeated.
- No live credential, protected secret, external-service mutation or paid AI
  call was used. No protected colleague package or native-platform test is
  claimed.
- The authoritative private owner/source archive is
  `cv_studio_v24_6_232_phase4_compatibility_corrective_owner_source.zip`.
  It is generated from the exact final clean corrective commit with one
  `cv_formatter/` root and freshly compared with every tracked Git blob.
- The authoritative SHA-256, byte size, final `source_commit` and extraction
  counts are recorded in adjacent sidecars under
  `C:\CV-Studio-Codex\releases\v24.6.232`.
- `cv_studio_v24_6_232_phase4_compatibility_corrective_qa_report.md` records
  the corrective QA evidence and `CV_STUDIO_V24_6_232_PHASE_5_HANDOVER.md`
  refreshes the owner-gated next-phase handover.

## Phase 4 Milestone 5 acceptance and release result

- Advanced all active production, browser, installer, launcher, watchdog,
  protected-build and starter-pack version surfaces together to v24.6.231.
- Complete Python discovery passed 52 tests with `ResourceWarning` treated as
  an error. This includes the Phase 1/2 storage guarantees, all Phase 3 shared
  clients and the four Phase 4 characterization tests.
- Both frontend fixtures passed, including compilation of both inline
  `index.html` scripts. The live source smoke passed all 24 assertions on an
  ephemeral loopback port with temporary receipt, database and log state.
- Static validation passed for 19 Python files, 20 JavaScript files plus both
  inline scripts, five Bash/command files through Git Bash and five PowerShell
  files. Owner-source validation/preflight, repository consistency and Git
  whitespace validation also passed.
- Final review against exact master baseline
  `7a0efcf0bce10b07e034592fb22a6021141d4146` proves the ordered 107-route
  inventory, all five global request/security guards, the 80 MiB request
  boundary, schema version 10 and the absence of an `app` import from any
  extracted module.
- The first review finding concerning diagnostics callback rebinding was fixed
  before release. The repeated focused and full review found no further
  concrete compatibility, security, persistence or scope issue.
- No live credential, protected secret, external-service mutation or paid AI
  call was used. No protected colleague package or native-platform test is
  claimed.
- The authoritative v24.6.231 private owner/source ZIP is generated from the
  final clean release commit with one `cv_formatter/` root. Its SHA-256, byte
  size, exact `source_commit` and fresh byte-verification result are recorded in
  adjacent release sidecars.

## Phase 4 files changed

- `cvstudio_storage_bridge.py` — app-independent orchestration for the 19
  existing durable-storage routes using explicit request/response/repository
  dependencies.
- `cvstudio_diagnostics.py` — app-independent redaction, runtime diagnostics
  and in-memory support-bundle service using explicit providers/callbacks.
- `cvstudio_document_safety.py` — shared bounded ZIP/image/PDF validation,
  rendering and serialized OCR primitives.
- `app.py` — unchanged route decorators/endpoints and bounded compatibility
  adapters for the three extracted modules.
- `tests/test_phase4_backend_modularization_characterization.py` —
  pre-move and continuing route, field, security, storage, diagnostics and
  document-safety characterization.
- `owner_build_tools/build_protected.py` — owner-source inventory/preflight
  includes the three new modules.
- Production, installer, launcher, watchdog, protected-build and starter-pack
  version surfaces — advanced consistently to v24.6.231.
- `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md`, `IMPLEMENT.md`,
  `CODEX_FIRST_PROMPT.txt`, `README_FIRST.txt`, `BACKBURNER_ROADMAP.md` and
  `KEEP_PRIVATE_PATCH_BASE.txt` — Phase 4 completion and Phase 5 activation
  gate.
- `cv_studio_v24_6_231_phase4_backend_modularisation_qa_report.md` — Phase 4
  release QA evidence.
- `CV_STUDIO_V24_6_231_PHASE_5_HANDOVER.md` — owner-gated next-phase handover.

## Phase 3 authorization and constraints

- Owner authorization received on 22 July 2026.
- Work only from clean master commit
  `1be9da48d8307c418d82807cbdaedc9f876a1b15` and preserve v24.6.222 as the
  source baseline.
- Extract only `JobAdderClient`, `MicrosoftGraphClient` and `AIProviderClient`
  plus shared retry, pagination, Microsoft token refresh, bounded timeout,
  redaction and structured external-service error foundations.
- Inventory call sites, route response shapes, credential boundaries and paid-
  call risks before moving production calls. Extract one client at a time with
  characterization fixtures.
- Preserve all 107 route URLs, legacy response fields, request-ID behavior,
  credential stores, paid-call confirmation gates and Phase 1/2 storage
  contracts.
- Do not make live credentialed or paid external calls.
- Do not implement schema or credential migration, persistent background jobs,
  broad backend/frontend modularisation, lazy loading, unrelated workflows or
  roadmap items 4, 7 or 8.
- Stop after the Phase 3 private owner/source release, QA report and Phase 4
  handover. Do not begin Phase 4 automatically.

## Phase 3 entry verification

- The owner `master` worktree and this worktree were clean at entry; no remote
  is configured, and both resolved to the owner-specified master commit
  `1be9da48d8307c418d82807cbdaedc9f876a1b15`.
- All active source version surfaces identify v24.6.222.
- The authoritative v24.6.222 release directory exists at
  `C:\CV-Studio-Codex\releases\v24.6.222\` with its owner ZIP, SHA-256,
  verification JSON, QA report and Phase 3 handover.
- The independently computed owner-ZIP SHA-256 is
  `b3caa1e1d32be21f2ea32a9d9eb0a7fe06fdc6c9f687b8abe0bcb8e95fae09dc`,
  matching both adjacent sidecars. A fresh extraction contained 91 tracked
  files with zero missing, extra or byte-mismatched files.
- The documented ignored owner/source dependency was restored with exact
  `adm-zip` 0.5.17. Entry QA then passed 26 Python tests, both frontend fixtures,
  24 live-source-smoke assertions, all tracked Python/JavaScript/Bash/PowerShell
  syntax, owner-source validation/preflight, repository consistency and Git
  whitespace validation.

## Phase 3 implementation plan

### Milestone 1 - inventory and compatibility fixtures

- Inventory every JobAdder, Microsoft Graph and AI-provider HTTP call, its
  caller/route, retry, pagination, refresh, timeout and credential behavior.
- Capture success and error response shapes in no-network characterization
  fixtures before moving production calls.
- Define the smallest shared transport/error boundary and redaction contract.

### Milestone 2 - JobAdderClient

- Extract JobAdder authentication, request, pagination and retry behavior behind
  the existing JobAdder routes.
- Preserve route URLs, legacy fields, reconnect classification and upload/read
  semantics with characterization tests.

### Milestone 3 - MicrosoftGraphClient

- Extract Microsoft Graph requests, bounded pagination and token refresh behind
  the existing Outlook and OneNote routes.
- Preserve route contracts, consent/reconnect behavior and credential storage.

### Milestone 4 - AIProviderClient and shared resilience

- Extract existing OpenAI-compatible, Anthropic and DeepSeek provider calls
  behind one provider-aware client boundary.
- Centralize bounded timeouts, safe retries, response parsing, redaction and
  structured upstream-error translation without changing paid-call gates or
  legacy route fields.

### Milestone 5 - acceptance and release evidence

- Run full regression, source smoke, static validation, repository consistency
  and final route/scope review against the v24.6.222 master baseline.
- Advance completed owner/source version surfaces only after implementation
  passes, create and freshly byte-verify the private owner/source ZIP, and
  produce the QA report, SHA-256 and Phase 4 handover in the release directory.
- Stop before Phase 4.

## Phase 3 milestones

- [x] Verify the v24.6.222 master/source/package baseline and all entry gates.
- [x] Inventory external-service call sites and record compatibility fixtures.
- [x] Extract and verify `JobAdderClient`.
- [x] Extract and verify `MicrosoftGraphClient`.
- [x] Extract and verify `AIProviderClient` and shared resilience/error handling.
- [x] Run complete regression, static validation and final master review.
- [x] Create and byte-verify the Phase 3 private owner/source release.
- [x] Produce QA report, SHA-256 and Phase 4 handover; stop before Phase 4.

## Phase 3 decisions and limitations

- Phase 3 is a narrow client-boundary extraction inside the existing monolithic
  backend; it is not the Phase 4 backend modularisation.
- Characterization and integration tests use controlled fakes only. Live
  JobAdder, Microsoft Graph and paid AI requests are not authorized or claimed.
- Schema version 10 and every Phase 1/2 migration, mirror, tombstone, recovery
  and structured storage-error contract remain unchanged.
- Microsoft OneNote and Outlook continue to use separate scopes, protected
  credential stores and reconnect state. The client accepts a freshly issued
  token explicitly for account lookup so refresh never re-enters its own lock.
- Graph safe reads retry transient failures once and a rejected access token is
  refreshed and replayed once. Draft/message POSTs and other unsafe Graph
  writes are never replayed after an ambiguous network, throttle or 5xx failure.
- Graph collection traversal follows only HTTPS `graph.microsoft.com`
  `@odata.nextLink` values and is capped at 5,000 items and 100 pages. Existing
  route-level `$top` values provide the effective lower item limit.
- AI-provider timeouts retain the existing 15-second minimum and are now capped
  at 300 seconds. Anthropic, DeepSeek and OpenAI chargeable POSTs are never
  replayed automatically after an ambiguous transport or upstream failure.
- Provider request construction is centralized, while DeepSeek tool refusal,
  OpenAI request/response translation, usage normalization and every existing
  paid-call confirmation gate remain in their compatibility adapters.

## Phase 3 Milestone 1 results

### JobAdder inventory

- Protected credentials remain in `_ja_creds_store` and the existing operating-
  system-backed `_cv_secure_*` vault. OAuth authorization-code and refresh
  exchanges use `id.jobadder.com`; token responses select the validated
  tenant-specific `*.jobadder.com` API base.
- Existing request paths comprise candidate search/create/update, original and
  formatted resume upload, list/custom-field reads, Screening Call activity
  create/read diagnostics, candidate/profile/salary updates, AI Crawler option,
  candidate/detail/resume discovery, and read-only PPC placement retrieval.
- Existing request wrappers are fragmented across `_ja_get_json`,
  `_ja_post_json`, `_ja_put_json`, `_spider_get_ja_raw`, `_ppc_get_json` and
  direct route-local `urlopen` calls. Timeouts range from 8 to 40 seconds.
- AI Crawler GETs alone refresh and retry once after HTTP 401. PPC reads retry
  HTTP 429 once for a bounded `Retry-After`; other JobAdder reads and writes do
  not share those behaviors.
- Candidate discovery paginates by `Offset`/`Limit` against `totalCount`, with
  duplicate/no-progress diagnostics and a 5,000-record hard cap. PPC queries
  each placement type independently, performs a count request, advances by the
  actual rows returned, and preserves per-type completeness diagnostics.
- Legacy route successes variously return the upstream JSON unchanged,
  `(status, parsed JSON)` helper tuples, `{ok,response}` upload results, crawler
  pagination metadata, or normalized PPC rows. Failures retain route-specific
  `error`, `detail`, `status`, `needs_reconnect`, `query`, diagnostic and
  fallback fields before the additive request-ID contract is applied.

### Microsoft Graph inventory

- OneNote and Outlook retain separate delegated-token stores and scopes. Both
  use the existing protected vault, proactive 120-second refresh window,
  in-memory device-login sessions and the shared Microsoft v2 token endpoint.
- OneNote Graph calls cover account lookup, notebooks, sections, pages, page
  content and notebook resolution. Outlook calls cover account lookup and
  draft creation only; CV Studio has no Graph send-mail path.
- `_ms_graph_json`, `_ms_graph_post_json`, `_ms_graph_bytes` and
  `_ms_outlook_graph_json` duplicate request/TLS/timeout logic. They do not
  currently retry a Graph 401 or follow `@odata.nextLink`; route/helper
  timeouts range from 15 to 30 seconds.
- OneNote routes retain their established `items`, `raw_count`, `filters`,
  `pages`, `combined_text`, `content_type`, connection and legacy error/detail
  shapes. Outlook draft creation retains its request-ID idempotency cache and
  `{ok,draft_id,webLink,isDraft,mayRequireEditClick,created_at}` result plus its
  established friendly error/action/technical-detail fields.

### AI-provider inventory

- Anthropic Messages, DeepSeek's Anthropic-compatible endpoint and OpenAI
  Responses are all dispatched through `call_llm`. OpenAI request/response
  translation and provider-neutral usage normalization preserve the shared
  `{content,usage}` contract and `api_calls=1` accounting.
- Provider keys remain in the existing protected `_ai_secret_store`; request
  sentinels are resolved only inside the backend. Default provider timeout is
  180 seconds with a 15-second minimum. There is no shared retry today.
- Every successful LLM request may be chargeable. Automatic retries after an
  ambiguous AI timeout or provider error could double-spend, so Phase 3 will
  centralize policy but will not retry chargeable POSTs automatically.
- Existing callers include provider test, CV parsing and repair, generic AI,
  salary-component extraction, Lead Finder research/refinement, title
  expansion, blind CV and the owner-only paid DeepSeek probe. The paid probe
  retains its exact explicit confirmation string and is not run in Phase 3 QA.
- Tavily/SerpAPI public search, Apollo enrichment and the local update watchdog
  were inventoried as other raw network call sites. They are not silently
  folded into one of the three authorized clients and remain unchanged.

### Compatibility fixture and client-boundary decisions

- Added six no-network characterization tests covering the exact 107-route
  baseline, JobAdder success/error fields, one-refresh crawler behavior,
  candidate pagination metadata, Microsoft JSON/bytes and OneNote route
  shapes, Anthropic/OpenAI normalization, DeepSeek web-search refusal and
  credential redaction.
- The shared client module will use Python's standard library and dependency-
  injected token/base callbacks. Existing app-level helper names remain as
  compatibility adapters so the extraction does not become Phase 4
  modularisation.
- Retry is limited to explicitly safe/idempotent reads, bounded throttling and
  token-refresh operations. JobAdder mutations/uploads, Graph draft creation
  and AI-provider POSTs are never replayed after an ambiguous failure.
- HTTP status/body compatibility remains available to mature route handlers;
  shared structured errors add redacted service/code/retry/action metadata
  without removing legacy route fields.

### Milestone 1 verification

- `tests/test_phase3_external_client_characterization.py`: 6 tests passed.
- No live credentials, candidate records, email addresses or paid external
  calls were used. Fixture credential/record values are explicit placeholders.
- No application route, storage schema, legacy mirror or production behavior
  changed in this milestone.

## Phase 3 Milestone 2 results

- Added `cvstudio_clients.py` with the standard-library shared transport,
  bounded timeouts, allowlisted HTTPS service hosts, credential/header
  redaction, `HTTPError`-compatible structured upstream failures and the first
  shared client, `JobAdderClient`.
- Every JobAdder OAuth, candidate read/write, attachment upload, Screening Call
  activity, diagnostic read/write, list/custom-field, AI Crawler and PPC
  placement network call now passes through `JobAdderClient`. There are no
  JobAdder-specific raw `urlopen` calls left in `app.py`.
- The app-level `_ja_*`, crawler and PPC helper names remain as compatibility
  adapters. Existing routes and feature orchestration were not moved out of the
  monolithic backend.
- A rejected JobAdder access token now receives one centralized forced refresh
  and one retry. A second HTTP 401 clears the rejected token through the
  existing reconnect state, while mature route handlers continue to receive an
  `HTTPError`-compatible status/body and preserve their legacy fields.
- Idempotent JobAdder reads retry one bounded transient HTTP/network failure.
  `Retry-After` is capped at five seconds. Candidate/activity writes and both
  attachment uploads never replay after an ambiguous transient failure; an
  authorization rejection may be retried only after a successful token refresh.
- AI Crawler and PPC `Offset`/`Limit` traversal now share the client's defensive
  paginator. Existing duplicate-page, no-progress, empty-before-total, cap and
  completeness diagnostics remain unchanged, including per-placement-type PPC
  count queries and one bounded empty-page retry.
- Initial service URLs are constrained to HTTPS JobAdder-owned hosts. Error
  bodies and structured details redact bearer/API/OAuth credential patterns;
  authentication/cookie headers are never retained in structured metadata.
- Added a dedicated structured external-service Flask handler for failures not
  already translated by a legacy route. It returns the existing request-ID
  contract with additive redacted service metadata and does not log request or
  response bodies.
- Owner protected-build source validation/preflight now requires and compiles
  `cvstudio_clients.py`; Nuitka continues to follow the app import without a
  protected-package layout change.

### Milestone 2 decisions and limitations

- JobAdder mutation retries are deliberately narrower than read retries to
  prevent duplicate candidates, activities or attachments after an ambiguous
  timeout/5xx response.
- Existing JobAdder diagnostic route response fields remain available, but the
  shared transport strips credential-like values from upstream error text
  before those fields can be returned or recorded.
- This milestone changes no credential storage, schema, route URL, browser
  contract, background execution model or user-facing workflow.

### Milestone 2 verification

- Phase 3 client/characterization gate: 12 no-network tests passed, covering
  retry safety, redaction, timeout/host bounds, one-refresh behavior, repeated
  rejection, offset pagination, JSON helpers, uploads, PPC diagnostics and
  established JobAdder route success/error fields.
- Complete Python discovery: 38 tests passed.
- Live owner/source smoke: 24 assertions passed.
- Python compilation, owner-source validation/dependency preflight, repository
  consistency and Git whitespace validation passed.
- All 107 baseline route URLs remain; no live credential, candidate record or
  external/paid call was used.

## Phase 3 Milestone 3 results

- `MicrosoftGraphClient` now owns the OneNote and Outlook Graph request/TLS,
  bounded timeout, transient safe-read retry, one-time 401 token refresh,
  reconnect marking, JSON/byte parsing, OAuth form request and bounded
  `@odata.nextLink` traversal foundations.
- All existing OneNote and Outlook helper and route entry points remain in
  `app.py`; their separate protected credential stores, scopes, device-session
  stores, draft idempotency cache and response shapes are unchanged.
- OneNote notebook/section/page listing follows Graph continuation links only
  up to the caller's existing `$top` cap. Foreign continuation hosts are
  rejected, repeated links stop, and no draft/message POST is retried after an
  ambiguous transient failure. A definitive HTTP 401 uses the single shared
  refresh/retry contract.
- Review found and corrected a refresh-lock re-entry risk before checkpoint:
  post-refresh account lookup now supplies the newly issued token directly to
  the shared client and a regression fixture proves the token provider is not
  called in that path.
- Focused shared-client and route-characterization suites: 17 tests passed,
  covering device-start response secrecy, OneNote pagination, Outlook draft
  shape, explicit-token lookup, token endpoint form/TLS behavior, one-time 401
  refresh, reconnect marking, host restriction and unsafe transient non-replay.
- Complete Python discovery: 43 tests passed. The existing interpreter-exit
  warning for a Phase 2B temporary import directory remains non-failing and no
  Phase 3 resource handle is retained.
- Live threaded source smoke: 24 assertions passed. Owner-source validation and
  dependency preflight, repository consistency and Git whitespace validation
  passed.

## Phase 3 Milestone 4 results

- `AIProviderClient` now owns the three authorized provider endpoints, API-key
  header construction, HTTPS host restrictions, request serialization,
  response parsing, bounded timeouts and structured/redacted upstream errors.
- Existing `call_anthropic`, `_call_deepseek`, `_call_openai` and `call_llm`
  adapters preserve provider selection, the Anthropic-compatible request shape,
  DeepSeek web-tool refusal, OpenAI Responses translation and normalized
  `{content,usage}` results including `api_calls=1`.
- Chargeable AI POSTs use an explicit zero-retry policy, including HTTP 429/5xx
  and ambiguous network/timeout failures. The owner-only DeepSeek probe still
  requires its exact paid-call confirmation and was not run.
- Shared redaction now also masks hyphenated API-key/token names, candidate-ID-
  labelled values and email addresses in upstream error bodies; authentication
  and cookie headers remain fully redacted.
- Microsoft device-code creation and polling remain non-replaying. Only an
  explicit Microsoft `refresh_token` grant receives the centralized bounded
  token retry, preserving prior device-login behavior.
- Focused shared-client and characterization suites: 19 tests passed. Complete
  Python discovery: 45 tests passed under `ResourceWarning`-as-error. A missing
  historical Phase 2B module cleanup was made explicit so the suite exits with
  no implicit temporary-directory warning.
- Both frontend storage fixtures, 24-assertion live source smoke, owner-source
  validation/dependency preflight, repository consistency and Git whitespace
  validation passed.
- Raw-network audit leaves only the previously inventoried local watchdog,
  Tavily/SerpAPI search and Apollo paths in `app.py`; all JobAdder, Microsoft
  Graph and authorized AI-provider calls use the shared client foundations.

## Phase 3 Milestone 5 acceptance results

- Final source review against exact master baseline
  `1be9da48d8307c418d82807cbdaedc9f876a1b15` found all 107 route URLs intact,
  schema version 10 unchanged and no credential/background-job/frontend/
  backburner or Phase 4 implementation drift.
- The versioned v24.6.223 acceptance run passed all 45 Python tests with
  `ResourceWarning` treated as an error, both frontend fixtures and 24 live
  loopback source-smoke assertions.
- Static validation passed all 15 tracked Python files, 20 JavaScript files and
  both inline scripts, 5 Bash/command files through Git Bash and 5 PowerShell
  files through the native parser.
- Owner-source validation/dependency preflight, repository consistency and Git
  whitespace checks passed. Consistency repair changed only the expected CRLF
  form of edited Windows batch/VBS files.
- Active production, installer, launcher, owner-build and source-smoke version
  surfaces agree on v24.6.223; prior-version references remain only in
  historical evidence and baseline descriptions.
- The Phase 3 QA report and owner-gated Phase 4 handover have been produced.
  Archive SHA-256/source-commit/fresh-extraction evidence is recorded only after
  the final clean documentation commit is frozen.
- A clean archive trial from the versioned release checkpoint produced one
  `cv_formatter/` root with 96 tracked/extracted files and zero missing, extra
  or byte-mismatched files. The authoritative archive is regenerated from the
  final clean Phase 3 completion commit and receives adjacent SHA-256 and
  verification sidecars in `C:\CV-Studio-Codex\releases\v24.6.223\`.

## Phase 3 post-completion corrective review — 23 July 2026

- The owner authorized correction of all three actionable findings from the
  review of `codex/phase-3-shared-clients` against master commit
  `1be9da48d8307c418d82807cbdaedc9f876a1b15`.
- Production urllib redirects now validate every target against the service
  HTTPS host allowlist. Redirects to a different allowed origin strip
  authorization, API-key and cookie headers; foreign or HTTPS-downgrade targets
  fail through the redacted structured external-service error contract.
- Successful shared-client response headers now retain case-insensitive HTTP
  lookup semantics while preserving their received names for legacy diagnostic
  output. Lowercase `content-type` and `content-disposition` therefore continue
  to populate the existing OneNote and JobAdder fields.
- JobAdder activity diagnostic GET/POST adapters now translate shared transport
  network failures back into the established `ok`, `status`, `network_error`,
  `response_headers`, `response_body` and `response_json` fields. The POST
  adapter also retains its legacy request metadata.
- Redirect handling remains inside the production standard-library opener;
  characterization fixtures inject their no-network opener directly at the
  transport boundary.
- Focused Phase 3 client and route-characterization verification passes 22
  tests, including dedicated redirect, lowercase-header and diagnostic-network
  regression cases. No live credential, external-service or paid call was used.
- Complete regression passes 48 Python tests with `ResourceWarning` treated as
  an error, both frontend storage fixtures and all 24 live loopback source-smoke
  assertions. Static validation passes all 15 tracked Python files, 20 tracked
  JavaScript files plus both complete inline scripts, 5 PowerShell files and 5
  Bash/command entry points through the installed Git Bash runtime.
- Owner-source validation/dependency preflight, exact vetted/local `adm-zip`
  0.5.17 checks, repository consistency and Git whitespace validation pass.
- This correction changes no route URL, schema, credential store, background
  execution, frontend workflow, backburner item or Phase 4 boundary.

## v24.6.224 Phase 3 corrective release

- On 23 July 2026 the owner authorized correction of both findings from the
  follow-up review of commit `ce96cec2038e3b828a69e6536ca5b439290c0319`.
- A rejected foreign or HTTPS-downgrade redirect now closes its upstream
  response before raising the structured external-service error. Regression
  coverage exercises the standard-library `http_error_302` path and proves the
  response is closed.
- The focused shared-client and route-characterization suites pass 22 tests
  with `ResourceWarning` treated as an error. No live credential, external-
  service or paid call was used.
- The complete regression passed 48 Python tests with `ResourceWarning` treated
  as an error, both frontend storage fixtures and all 24 live loopback source-
  smoke assertions. Static validation passed all 15 tracked Python files, 20
  tracked JavaScript files plus both complete inline scripts, 5 PowerShell files
  and 5 Bash/command entry points.
- Owner-source validation/dependency preflight, exact vetted/local `adm-zip`
  0.5.17 checks, repository consistency and Git whitespace validation passed.
- The corrected source is released as v24.6.224 with a new QA report, Phase 4
  handover, clean owner/source ZIP, SHA-256 and fresh byte-verification evidence.
  The v24.6.223 artifacts remain immutable historical evidence.
- No route URL, legacy response field, schema, credential store, frontend
  workflow, background execution, backburner item or Phase 4 work is included.

## v24.6.230 Phase 3 content-negotiation corrective release

- On 23 July 2026 the owner authorized correction of the confirmed JobAdder
  content-negotiation regression against v24.6.224 commit
  `0892dcc1fbec2fb68b4668014792230249c73cae`.
- `JobAdderClient.request_raw` no longer forces `Accept: application/json`.
  Binary candidate CV and attachment downloads remain representation-neutral,
  while explicit caller accept headers retain precedence.
- `JobAdderClient.request_json` owns the JSON accept default and keeps it across
  the single rejected-token refresh. Explicit JSON caller headers are honored.
- Characterization fixtures preserve exact download bytes/content metadata and
  the established JobAdder diagnostic network-error fields while proving raw,
  JSON and caller-supplied accept behavior.
- Existing immutable release directories already occupy v24.6.225 through
  v24.6.229, so v24.6.230 is the next non-overwriting release identity.
- Focused Phase 3 client and route characterization passes 22 tests with
  `ResourceWarning` treated as an error. The cache integration subset passes 7
  tests and complete Python discovery passes all 48 tests.
- Both Node frontend fixtures pass. The live source smoke passes all 24
  loopback assertions using temporary local state.
- Static validation passes for 15 tracked Python files, 20 tracked JavaScript
  files plus both complete inline scripts, 5 PowerShell files and 5 Git Bash
  shell/command entry points. Owner-source validation/preflight, exact
  `adm-zip` 0.5.17 behavior, repository consistency and Git whitespace checks
  pass.
- The authoritative private archive is generated from the exact final v24.6.230
  commit with one `cv_formatter/` root. A fresh extraction is required to
  contain the exact 100 tracked files with zero missing, extra or byte-
  mismatched files; the adjacent SHA-256 and verification sidecars record the
  final commit and result.
- The v24.6.224 archive and sidecars remain unchanged.
- No route URL, response field, authentication boundary, retry rule, schema,
  credential store, frontend workflow, background execution, backburner item or
  Phase 4 work is included.

## Completed Phase 2B authorization and constraints

- Migrate only durable browser-backed records and selected persistent settings
  that need application backup/restore.
- Keep temporary UI/session state in `localStorage` where appropriate.
- Define explicit legacy import, mirror, export and rollback/readability behavior
  for every selected store before changing production code.
- Preserve Phase 2A WAL, foreign-key, busy-timeout, integrity, verified-backup,
  transactional migration, restart, corruption, redaction and request-ID
  contracts.
- Keep credentials and protected secrets outside plain SQLite.
- Do not implement roadmap items 4, 7 or 8.
- Do not begin shared-client work, background jobs, modularisation, lazy loading
  or new user-facing workflows.
- Stop after the Phase 2B release and Phase 3 handover.

## Phase 2B entry verification

- The worktree was clean before activation.
- Local `master` and the opened worktree both resolved to
  `a43dbb84dcc44c773527f49d0332b2eb15a37cc1`; no remote is configured, so this
  is the latest available master tip.
- All primary source version surfaces identify v24.6.219.
- The v24.6.219 release archive exists under
  `C:\CV-Studio-Codex\releases\v24.6.219\`.
- Its computed SHA-256 exactly matched the adjacent sidecar:
  `66e4be40f8f528b54281801fb0404f77ef65f61fcd365539452245f25ff510df`.
- A fresh extraction contained exactly 82 tracked files, with zero missing,
  extra or byte-mismatched files against the master Git blobs.
- Entry regression passed after installing the pinned, ignored owner/source
  `adm-zip` dependency in this worktree: 17 Python tests, the Phase 2A frontend
  fixture, 18 live-source-smoke assertions, owner-source validation/preflight
  and repository consistency.

## Phase 2B implementation plan

### Milestone 1 — inventory and compatibility design

- Inventory durable browser records, settings, localStorage/IndexedDB keys,
  read/write call sites, existing export/import behavior and sensitive fields.
- Select the smallest Phase 2B store set and explicitly leave temporary UI,
  credential-like and later-phase data in their existing storage.
- Record deterministic identities, conflict rules, limits, legacy mirrors and
  export/backward-readability behavior.

### Milestone 2 — schema and repository foundation

- Add ordered Phase 2B schema migration(s) through the existing verified-backup
  and transactional migration engine.
- Add narrowly scoped repositories for only the selected browser records and
  settings, with bounded/redacted payload validation and idempotent import.
- Prove backup verification, rollback/restart, double initialization and Phase
  2A schema/data preservation.

### Milestone 3 — backend bridge

- Add same-origin request-ID routes for import/read/upsert/delete or clear as
  required by the selected store contracts.
- Preserve structured storage errors and existing route behavior.
- Add real Flask integration coverage for every operation and recovery path.

### Milestone 4 — frontend migration and export compatibility

- Hydrate selected durable records/settings from SQLite while retaining the
  defined local browser fallback/mirror for transition compatibility.
- Serialize mutations and protect hydration/delete/clear races.
- Preserve unknown legacy fields and extend the existing local-data
  export/import contract without exporting credentials.
- Leave temporary UI state in localStorage.

### Milestone 5 — acceptance and release evidence

- Test legacy fixtures, migration twice, conflict handling, clear/delete races,
  corruption/interruption recovery, legacy preservation and export round trips.
- Run complete regression, source smoke and Python/JavaScript/Bash/PowerShell
  static validation plus repository consistency and scope audits.
- Advance all completed owner/source version surfaces to v24.6.220 only after
  implementation passes.
- Create and freshly byte-verify the private owner/source ZIP, QA report,
  Phase 3 handover, SHA-256 and release directory artifacts; then stop.

## Phase 2B milestones

- [x] Verify the v24.6.219 master/source/package baseline and all entry gates.
- [x] Record owner authorization, scope boundaries and milestone plan.
- [x] Inventory and select Phase 2B browser stores/settings.
- [x] Implement schema migration and repositories.
- [x] Implement backend bridge routes and structured recovery.
- [x] Implement frontend hydration/mirroring and export compatibility.
- [x] Complete Phase 2B acceptance and compatibility tests.
- [x] Run full regression, static validation and final master review.
- [x] Create and byte-verify the v24.6.220 private owner/source release.
- [x] Produce QA report, SHA-256 and Phase 3 handover; stop before Phase 3.

## Phase 2B Milestone 1 inventory and compatibility contract

### Selected durable records

1. **OneNote transfer record history** — browser `localStorage` key
   `cv_studio_onenote_transfer_records_v1`.
   - Existing boundary: `oneNoteRecordsLoad`, `oneNoteRecordsSave`, successful
     transfer recording, paid salary-extraction failure recording, rendering,
     cost display and explicit clear in `index.html`.
   - Existing shape is an ordered array capped at 200 records. Records may
     contain candidate contact/identifier fields, JobAdder activity links,
     salary canonical data and AI accounting metadata. They are private
     application data, not credentials, and must never enter diagnostics or
     logs.
   - New records receive an explicit stable ID. Legacy records without one use
     a canonical full-record fingerprint so exact duplicate imports are
     idempotent without inventing or reinterpreting fields.
   - SQLite is authoritative after insert-only legacy import. Live replace and
     clear operations are serialized; deleted rows retain tombstones so stale
     browser mirrors cannot resurrect them.
2. **Saved OneNote desktop links** — browser `localStorage` key
   `cvstudio_onenote_saved_desktop_links_v1`.
   - Existing boundary: read/normalize, create, edit, delete, render and use-link
     helpers in `index.html`.
   - Existing shape is an array capped at 100 records with stable IDs, name,
     notebook/section/page kind, link and timestamps.
   - Preserve unknown non-credential legacy fields. SQLite is authoritative;
     current-browser edits replace by ID and deletions retain tombstones.

### Selected persistent settings

The SQLite settings repository is limited to the existing non-secret
local-data-backup contract, excluding Phase 2A PPC metadata (which keeps its
dedicated repository) and saved OneNote links (which receive their own record
repository):

- PPC UI state, KPI visibility, column visibility, invoice recipient/greeting,
  non-secret Outlook client configuration and saved draft links;
- OneNote spelling correction, salary-AI toggle, source mode, public Microsoft
  client ID and tenant;
- CV text alignment, page-navigation pinning, AI Crawler preview-memory mode and
  JobAdder auto-upload preference;
- main/Lead/Search/Enrichment provider selections, legacy model selections,
  the known per-provider main/Lead model keys and the known per-feature AI route
  and route-model keys.

The existing export allowlist omitted the live per-provider model keys even
though its description promised provider/model selections. Phase 2B corrects
that allowlist only for the known Anthropic, DeepSeek and OpenAI model keys; it
does not admit any provider-key or credential-key prefix.

Settings import is insert-only. Live writes are authoritative upserts; live
removals retain per-key tombstones. Values remain their existing bounded
`localStorage` strings so JSON subfields and backward readability are preserved
without reinterpreting each feature's established shape.

### Explicit exclusions

- JobAdder, OneNote, Outlook and AI tokens, secrets, API keys, device/login
  sessions and legacy credential migration keys remain in their protected
  mechanisms and are never admitted by a Phase 2B route or repository.
- The PPC IndexedDB query cache, its bounded localStorage fallback and in-memory
  preview/detail caches remain regenerable caches.
- AI Crawler/Lead Finder result snapshots, activity-diagnostic candidate and
  activity IDs, current tab/filter state, browser lock flags and other session
  or diagnostic state remain browser-local.
- Background wallpaper data remains browser-local because it is cosmetic and
  may contain multi-megabyte image data. The unexported MYR rate, Boolean
  highlight toggle and Lead Finder tuning toggles also remain unchanged rather
  than silently expanding the established backup allowlist.
- Phase 2A usage/PPC mirrors and backend JSON compatibility files remain intact;
  Phase 2B does not remove or shorten their transition contract.

### Schema, conflict and export decisions

- Extend schema version 7 to version 10 with one verified pre-migration backup
  per new store: OneNote transfer records, saved OneNote links and browser
  settings.
- Every migration uses the existing transactional migration engine and must
  prove rollback/restart safety, exact history and no change to schema versions
  1–7 or their data.
- Store payloads as canonical JSON/text behind deterministic keys, with bounded
  record counts, sizes and nesting. Recursively discard credential-like fields
  before persistence while retaining private record fields needed by the
  feature.
- Legacy imports never overwrite an existing live row or tombstone. Same-page
  mutations during hydration win only for the affected record IDs/setting keys.
- Keep the legacy localStorage keys as transition mirrors. Durable clear/delete
  failures are visible and restore the prior mirror instead of claiming
  success.
- Keep the existing local-data export `product`, schema 1 and `settings` object
  so v24.6.219 can still restore the settings it understands. Add the OneNote
  transfer history as an optional top-level record collection that Phase 2B can
  restore and persist; older releases safely ignore that additive field.
- Diagnostics expose only bounded store counts/health, never record values,
  setting values, emails, candidate identifiers, links or paths.

## Phase 2B decisions and limitations

- Milestone 1 is inventory/design only; it changes no application behavior or
  user data.
- The three-store boundary is intentionally narrower than all browser
  localStorage. A key is not migrated merely because it persists between page
  loads.
- Source-level Windows testing is available in this worktree. No protected
  native build, physical installer/restore test, live external-service call or
  paid provider request is claimed or required for this owner/source phase.

## Phase 2B Milestone 2 results

- SQLite schema version is now 10. Versions 8, 9 and 10 add only the selected
  OneNote transfer, saved-link and browser-setting tables and their bounded
  active-row indexes; migrations 1–7 and their checksums are unchanged.
- A real schema-7 fixture upgraded through all three migrations with three new
  unique, independently integrity-verified backups. Phase 2A usage data and
  migration history remained intact; a second startup created no additional
  backup or history row.
- A deterministic interruption after migration 9 schema work left the database
  transactionally at version 8 with no version-9 table/history row and a clean
  integrity check. Removing the fault completed versions 9–10 on restart.
- OneNote transfer records are capped at 200 and saved links at 100. Live
  replacement preserves exact active membership/order; clear/delete marks
  tombstones so later stale legacy imports cannot resurrect removed entries.
- Browser settings accept only the selected exact key set. Known main/Lead
  provider-model and per-feature route keys are enumerated explicitly; API-key,
  token and arbitrary prefixes are not accepted.
- Private record JSON and JSON-valued settings are bounded by size/depth and
  recursively stripped of credential-like fields. Safe accounting fields such
  as `input_tokens` remain intact.
- Targeted repository suites passed 9 tests across all Phase 2A repositories,
  the three new Phase 2B repositories, schema-7 upgrade and Phase 2B interrupted
  migration recovery.
- Targeted foundation/fixture suites passed 6 tests covering WAL/foreign keys,
  busy timeout, all verified backups, double initialisation, Phase 2A
  interruption/corruption behavior and byte-preserved v24.6.217 imports.
- Python compilation passed for the storage module and all targeted migration/
  repository test modules.

### Milestone 2 files

- `cvstudio_storage.py` — schema versions 8–10, bounded credential filtering,
  the selected settings allowlist and three tombstone-aware repositories.
- `tests/test_phase2b_repositories.py` — schema-7 upgrade, backup, interruption,
  Phase 2A preservation, repository, filter and tombstone coverage.

## Phase 2B Milestone 3 results

- Added same-origin request-ID routes for OneNote transfer read/import/replace/
  clear, saved-link read/import/replace and browser-setting read/import/upsert/
  delete operations. No existing route URL or response field changed.
- All successful bridge responses state that the legacy browser mirror remains
  preserved. Invalid record counts/types, unsupported setting keys and
  non-string setting values return the established `STORAGE_PAYLOAD_INVALID`
  structured 400 response.
- Browser settings are checked against the exact server allowlist before the
  repository is called. Credential keys therefore cannot be silently accepted
  while reporting a successful write.
- Existing global `StorageError` handling remains the sole storage-recovery
  response path. A genuinely corrupt database returned path-free
  `STORAGE_CORRUPT`, the caller's request ID and `restore_storage_backup` from a
  new Phase 2B route.
- Targeted real-Flask integration passed 11 tests across the seven existing
  Phase 2A app/cache cases and four Phase 2B route cases. Coverage includes
  credential-field filtering, replace/clear/delete, oversized input, allowlist
  rejection, request-ID propagation and corruption recovery.
- Python compilation passed for the backend, storage module and new integration
  test module.

### Milestone 3 files

- `app.py` — repository wiring, bounded payload gates and 11 additive local
  storage route handlers.
- `tests/test_phase2b_app_storage_integration.py` — isolated temporary-database
  integration and structured-recovery coverage.

## Phase 2B Milestone 4 results

- OneNote transfer records and saved links now hydrate from insert-only legacy
  import into SQLite-authoritative in-memory state while retaining their exact
  browser keys as transition mirrors.
- New transfer records receive stable IDs. Existing ID-less records retain
  canonical full-record identity; no legacy record field is invented merely to
  satisfy migration.
- Hydration compares the start and current browser snapshots. Only record IDs
  or setting keys actually added, changed or removed during the in-flight
  request may override SQLite. Unchanged stale records—including rows covered
  by SQLite tombstones—remain absent and cannot be re-saved accidentally.
- Whole-array record/link writes are serialized. Transfer clear waits for
  hydration, re-saves genuinely new concurrent records after a successful
  clear, and restores the prior browser mirror with an error on failure. A
  failed saved-link replace restores its prior mirror unless a newer mutation
  has already superseded it.
- Selected setting write sites now use the exact allowlisted durable bridge.
  AI-route preview temporarily continues to use raw localStorage and is never
  persisted as a saved route. Startup awaits settings hydration before legacy
  model migration, and automatic silent UI restoration does not mark stale
  values as user changes.
- The frontend and backend both recursively remove credential-like nested
  fields while preserving private feature data and safe accounting fields.
  Export applies the same filter even if durable hydration has not completed.
- The local-data backup keeps `product`, schema 1 and the legacy `settings`
  object. It adds optional top-level OneNote transfer/link collections; older
  v24.6.219 importers ignore those fields while still restoring the settings
  they understand. Phase 2B imports both historical schema-1 backups and the
  additive record collections, then waits for durable persistence before
  reloading.
- The known Anthropic, DeepSeek and OpenAI per-provider model keys are now
  included in export/import and SQLite persistence. Unknown provider/model and
  arbitrary AI-route keys remain rejected.
- Phase 2A and Phase 2B Node frontend fixtures passed. Phase 2B coverage includes
  settings and record hydration races, stale tombstones, successful and failed
  clear/delete, saved-link rollback, allowlist/export filtering and additive
  schema-1 import persistence.
- The real owner/source preflight passed both complete inline scripts, pinned
  `adm-zip` behavior and Python/Node compilation. The 18-assertion live source
  smoke and repository consistency also passed with schema version 10.

### Milestone 4 files

- `index.html` — Phase 2B browser bridges, selected durable-setting writes,
  hydration/race recovery, mirror preservation and additive export/import.
- `tests/test_phase2b_frontend_storage.js` — focused browser-storage and backup
  compatibility fixture.
- `tests/run_phase2a_source_smoke.py` — retain the historical entry point while
  validating the current declared schema version and history count.

## Phase 2B Milestone 5 results

- Full Python discovery passed 26 tests covering the Phase 1 response contract,
  Phase 2A repositories/foundation/fixture and the Phase 2B schema,
  repositories and real-Flask route bridge.
- Both Node frontend fixtures passed. Phase 2B coverage proves authoritative
  hydration, per-key/per-record race merging, tombstone behavior, clear/delete
  failure recovery, credential filtering and schema-1 export/import round trips.
- The real loopback owner/source smoke passed 24 assertions. It exercised the
  current identity/status contract, DOCX generation, all Phase 2A store paths,
  all three Phase 2B store imports, schema version/history/integrity and durable
  Phase 2B rows after shutdown.
- Python syntax passed for 12 tracked files. JavaScript syntax passed for 20
  tracked files plus both complete inline `index.html` scripts. Git Bash syntax
  passed for 5 tracked shell/command files, and the PowerShell parser passed all
  5 tracked `.ps1` files.
- Owner-source validation/dependency preflight, repository consistency, Git
  whitespace validation and the pinned `adm-zip` 0.5.17 behavior all passed.
- Final comparison with baseline master preserved all 96 existing Flask route
  URLs and added exactly 11 Phase 2B storage routes. No route was removed or
  renamed.
- Every active product, installer, launcher and protected-build source surface
  agrees on v24.6.220; none retains a v24.6.219 production identifier.
- The application diff contains no shared-client, background-job,
  modularisation, lazy-loading, new-workflow, Flask-server-replacement, scoring
  profile or candidate decision implementation.
- The private owner/source archive is
  `cv_studio_v24_6_220_phase2b_browser_storage_owner_source.zip`. It is generated
  from the final clean Git commit with one `cv_formatter/` root. A fresh
  extraction contains exactly the tracked files with zero missing, extra or
  byte-mismatched files. Its SHA-256, source commit, size and exact extraction
  counts are recorded in the adjacent `.sha256` and `.verification.json`
  sidecars under `C:\CV-Studio-Codex\releases\v24.6.220\`.
- The release directory also contains the Phase 2B QA report and gated Phase 3
  handover. No protected colleague archive was built or claimed because no new
  native protected compilation/smoke certification was performed.

### Milestone 5 decisions and limitations

- Transfer history remains ordered newest-first using its established timestamp
  semantics; saved-link order uses the preserved array position.
- Browser mirrors and all Phase 2A legacy JSON remain present. Phase 2B does not
  shorten a compatibility window or delete user data.
- Source-level Windows execution is genuine. Physical Windows/macOS installer
  execution, native protected builds and live/paid external-service calls were
  not performed and are not claimed.
- Phase 3 is not active. Stop at this completed v24.6.220 release.

## v24.6.221 Phase 2B review-correction milestone

The owner authorized correction of all actionable review findings on
`codex/phase-2b-browser-storage`. This remains Phase 2B work: schema version 10,
all route URLs, the selected-store boundary and every Phase 3/backburner stop
gate remain unchanged.

- Record arrays are now fully normalized before import or replacement. Any
  record that exceeds the 512 KiB sanitized limit, or is otherwise invalid,
  receives the existing structured `STORAGE_PAYLOAD_INVALID` response before a
  repository transaction begins.
- Both OneNote repositories defensively reject invalid arrays before preparing
  a tombstoning replacement, so a future internal caller cannot silently erase
  the authoritative set by bypassing the HTTP validator.
- Post-hydration settings refresh now rebuilds AI-routing controls from the
  SQLite-authoritative mirror instead of only refreshing their preview.
- Post-hydration refresh reapplies the AI Crawler preview-memory profile and
  schedules one Auto-mode diagnostics load when system-memory data is absent.
- Regression coverage proves oversized transfer/link replacements return 400
  and preserve prior rows, direct repository replacement is non-destructive,
  hydrated route controls are rebuilt, and the hydrated memory mode is applied.
- Targeted correction gate: 16 Python tests and the Phase 2B frontend fixture
  passed.
- Full regression gate: 26 Python tests, both frontend fixtures and the
  24-assertion live source smoke passed.
- Static gate: tracked Python, JavaScript, Bash and PowerShell syntax passed;
  owner-source validation/preflight, repository consistency and Git whitespace
  validation passed.
- All active product, installer, launcher, protected-build source and starter
  surfaces agree on v24.6.221. Historical v24.6.220 references remain only in
  the original Phase 2B evidence and release history.
- Final master review preserves all 96 baseline routes and the 11 additive
  Phase 2B storage routes; no existing URL or response contract was removed.
- The private owner/source archive is
  `cv_studio_v24_6_221_phase2b_corrective_owner_source.zip`. It is generated
  from the final clean release commit with one `cv_formatter/` root; its
  SHA-256, source commit, byte size and fresh byte-verification counts are
  recorded in adjacent sidecars under
  `C:\CV-Studio-Codex\releases\v24.6.221\`.

### Corrective decisions and limitations

- Reject the complete record request rather than partially persisting it. This
  preserves atomic replacement semantics and prevents the browser mirror from
  being overwritten with a silently shortened SQLite response.
- Existing duplicate-identity conflict rules remain unchanged; this correction
  concerns records that cannot be safely normalized and persisted.
- Rebuilding AI route rows after authoritative hydration is intentional. It
  closes the startup race in which controls rendered from a stale mirror could
  later overwrite SQLite when saved.
- This source-level correction does not claim a new protected native build,
  physical installer test, live external-service call or paid AI call.
- No shared client, background job, modularisation, lazy loading, new workflow
  or roadmap item 4, 7 or 8 was implemented. Phase 3 remains unauthorized.

## v24.6.222 Phase 2B second review-correction milestone

The owner authorized correction of the two remaining actionable findings on
`codex/phase-2b-browser-storage`. This is a second narrow Phase 2B corrective
patch. Schema version 10, the 11 additive storage routes, every legacy mirror
and the Phase 3/backburner stop boundaries remain unchanged.

- Browser-setting import/upsert validation now uses the repository's canonical
  value normalizer before reporting success. Oversized or suspicious scalar
  values receive the existing structured `STORAGE_PAYLOAD_INVALID` response;
  JSON-valued settings still have credential-like fields removed recursively
  and persist in canonical form.
- Schema-1 local-data restore now associates a confirmed count with every
  requested durable write. A rejected promise or a helper result other than
  explicit success rejects the restore, so the caller does not show the success
  message or reload the application after an unpersisted setting or record.
- PPC metadata write failures are no longer swallowed by the restore path.
  Transfer-record and saved-link restores require their exact last-write
  promises to succeed; saved-link synchronous rollback is also failure-visible.
- Targeted correction gate passed: 16 Python Phase 2A/2B repository and real-
  Flask integration tests plus the Phase 2B frontend storage fixture.
- Regression coverage proves rejected setting values return HTTP 400 without
  changing the existing authoritative value, sanitized JSON remains accepted,
  successful restore counts are exact, and setting, saved-link and PPC durable
  failures reject the restore.
- Full regression gate passed: 26 Python tests, both frontend fixtures and the
  24-assertion live loopback source smoke.
- Static gate passed for 12 tracked Python files, 20 tracked JavaScript files,
  both complete inline scripts, 5 Bash entry points and 5 PowerShell scripts.
- Owner-source validation/preflight, repository consistency and Git whitespace
  validation passed. Repository consistency repaired only the expected CRLF
  presentation of edited Windows batch/VBS launcher files before the final pass.
- Final master review preserves all 96 baseline routes and the 11 additive
  Phase 2B storage routes, for 107 current URLs and zero removed URLs.
- The application diff contains no shared client, background job,
  modularisation, lazy loading, new workflow, Flask-server replacement, scoring
  profile or candidate-decision implementation.
- All active product, installer, launcher, protected-build source and starter
  surfaces agree on v24.6.222. Historical v24.6.221 references remain only in
  prior release evidence and compatibility history.
- The private owner/source archive is
  `cv_studio_v24_6_222_phase2b_second_corrective_owner_source.zip`. It is
  generated from the final clean release commit with one `cv_formatter/` root;
  its SHA-256, source commit, byte size and fresh byte-verification counts are
  recorded in adjacent sidecars under
  `C:\CV-Studio-Codex\releases\v24.6.222\`.

### Second corrective decisions and limitations

- The backend and repository share one setting-value normalization contract;
  route success can no longer mask an entry omitted by repository preparation.
- The existing browser helpers retain their established live-write behavior and
  transition mirrors. This correction changes only backup-restore confirmation.
- Independent store writes cannot form one cross-store SQLite transaction. If a
  later requested store fails, earlier confirmed stores may already be restored;
  the operation is reported as failed and does not reload, allowing a safe retry.
- No schema migration, credential migration, shared client, background job,
  modularisation, lazy loading, new workflow or roadmap item 4, 7 or 8 is part
  of this correction. Phase 3 remains unauthorized.

## v24.6.219 corrective plan

- Keep SQLite usage rows authoritative when a stale legacy browser mirror has the same record ID.
- Reject stale PPC metadata conflicts using the existing `updatedAt` contract.
- Report usage-history clear failures and restore the local compatibility mirror instead of claiming success.
- Distinguish transient/operational SQLite failures from genuine database corruption.
- Recursively exclude credential-like fields from usage-history payloads before SQLite or backup persistence.
- Add focused regressions for every finding, then rerun the complete Phase 2A and release validation set.
- Advance release surfaces and owner/source evidence to v24.6.219 only after all tests pass; stop without starting Phase 2B.

## Verified baseline

- Git 2.55.0.windows.3 is available.
- The opened folder was already a clean Git worktree, so no repository initialisation was required.
- `HEAD` is the existing clean commit `CV Studio v24.6.217 baseline`.
- Backend, frontend, installer, protected-build workflow and owner-tool version surfaces all identify v24.6.217.
- The supplied baseline records all identify the approved owner ZIP SHA-256 as `c499ea8043f274bf47a4981c84794759f38fc7c761b98ba3939626114a898a59`.

## Phase 2A storage inventory

### In-scope durable stores and call sites

1. **Usage history** — browser `localStorage` key `guo_lab_stats`.
   - Read/write boundary: `statsLoad`, `statsSave`, `statsRecord`, `statsAttachJobAdderUrl`, `clearStats`, stats rendering and CSV export in `index.html`.
   - Producers cover format/blind/create, CV scoring, Owl/Owl chat, AI Crawler, summary, OneNote salary/activity, provider tests, paid-AI failures, company and Lead Finder runs.
   - Legacy rows predating v24.6.215 may contain cost only. Their missing detailed token/call/cache fields must remain missing; they must not be reconstructed.
2. **Lead-title cache** — `lead_title_cache.json` beside `app.py`.
   - Read/write boundary: `_lead_title_cache_load`, `_lead_title_cache_save`, find/store/touch helpers, stats/clear routes and the Lead Finder search route.
   - `merge_title_cache.py` remains a supported legacy JSON producer during the transition release.
3. **Lead-contact cache** — `lead_contact_cache.json` beside `app.py`.
   - Read/write boundary: `_lead_contact_cache_load`, `_lead_contact_cache_save`, find/store/touch helpers, enrichment routes and stats/clear routes.
4. **Salary-component cache** — `runtime/salary_ai_component_cache.json`.
   - Read/write boundary: `_ja_salary_ai_cache_load`, `_ja_salary_ai_cache_get`, `_ja_salary_ai_cache_put` and salary AI extraction.
5. **PPC metadata** — browser `localStorage` key `cvstudio_ppc_meta_v1`.
   - Read/write boundary: `ppcMetaLoad`, `ppcMetaSave`, `ppcUpdateMeta`, `ppcMetaFor`, PPC filtering/KPI/rendering.
   - The browser IndexedDB/fallback placement-query cache, PPC UI preferences, invoice recipient, Outlook draft links and client settings are separate and remain unchanged.
6. **Diagnostic state** — v24.6.217 has no durable user-data diagnostic JSON to import.
   - Recent browser API errors are bounded in memory only; runtime diagnostics are generated on demand.
   - Phase 2A will persist only non-sensitive storage health/migration state. It will not store request content, paths, emails, candidate identifiers, tokens or keys.

### Explicitly inventoried but out of scope

- `install_receipt.json`, `update_state.json` and `install_health_report.json` remain owned by the Phase 1 installation/rollback contract.
- `cvstudio.<instance>.pid.json` and the legacy PID file remain the Windows launcher/stop-process compatibility contract; they are not user data and will not be reinterpreted.
- JobAdder, Outlook/Microsoft and AI secret/token JSON stores remain in their existing protected mechanisms.
- Browser OneNote records/links, notes, saved settings, UI state, invoice settings and credential-like settings remain for Phase 2B or later as already scoped.
- In-memory AI Crawler preview/resume caches and the in-memory PPC detail cache remain ephemeral.

## Concrete implementation plan

### Milestone 1 — SQLite safety foundation

- Add a narrowly scoped storage module using Python's built-in `sqlite3`.
- Store the database in the existing per-user CV Studio state directory, with an environment-only test override.
- Enforce WAL, foreign keys, a bounded busy timeout and integrity checks on every managed connection/initialisation.
- Add ordered schema migrations, `PRAGMA user_version`, schema metadata and durable migration history.
- Before every schema-changing migration, create a unique timestamped SQLite backup with the SQLite backup API and verify the backup with `PRAGMA integrity_check`.
- Run each migration transactionally and support deterministic failure injection in tests to prove rollback/restart safety.

### Milestone 2 — repositories and backend JSON caches

- Add repositories for usage history, lead-title cache, lead-contact cache, salary-component cache, PPC metadata and non-sensitive diagnostic state.
- Import legacy data by deterministic keys/fingerprints inside transactions; record import fingerprints; never rename or delete legacy files.
- Convert lead-title, lead-contact and salary reads to SQLite first with safe JSON import/fallback.
- Dual-write those three legacy JSON formats for one-release backward readability, including clear/touch paths and compatibility with `merge_title_cache.py`.

### Milestone 3 — usage history and PPC metadata bridge

- Add same-origin local storage routes for idempotent import/read/upsert/clear operations.
- Hydrate browser state from SQLite on startup while using the existing local value as the import/failure fallback.
- Continue writing the existing localStorage keys after every mutation so v24.6.217 remains able to read the data.
- Preserve unknown legacy fields and the v24.6.215 DeepSeek detailed-cost cutoff exactly.

### Milestone 4 — structured recovery and diagnostics

- Expose redacted storage health in runtime diagnostics.
- Return structured request-ID errors with explicit recovery guidance for corruption and migration failures.
- Persist only non-sensitive diagnostic state and exclude database paths, legacy paths, tokens, keys, emails and candidate identifiers from responses, logs, tests and support bundles.

### Milestone 5 — acceptance and release evidence

- Test a v24.6.217 fixture, migration twice, duplicate-free import, legacy JSON preservation and SQLite-first read/write behaviour.
- Test corruption and an injected interrupted migration; verify no partial schema/data and successful restart after removing the injected failure.
- Run targeted and full regression checks plus Python, JavaScript, Bash and PowerShell syntax checks and repository consistency.
- Bump the completed private owner/source release surfaces to the next patch only after implementation passes.
- Create the private owner/source ZIP, extract it freshly, compare every included byte, produce the Phase 2A QA report and Phase 2B handover, and record SHA-256.
- Stop after Phase 2A.

## Milestones

- [x] Verify source baseline and repository state.
- [x] Inventory existing backend JSON/cache stores and read/write call sites.
- [x] Design database path, connection policy, migration order and compatibility boundary.
- [x] Implement SQLite connection, integrity and backup foundation.
- [x] Implement schema-version and migration history.
- [x] Implement repository interfaces.
- [x] Migrate usage history.
- [x] Migrate lead-title cache.
- [x] Migrate lead-contact cache.
- [x] Migrate salary-component cache.
- [x] Migrate PPC metadata.
- [x] Implement non-sensitive diagnostic state.
- [x] Prove SQLite-first reads, legacy fallback/import and one-release dual writes.
- [x] Prove migration idempotency.
- [x] Test corrupt and interrupted migration handling.
- [x] Run complete regression and static validation.
- [x] Create and byte-verify private owner/source ZIP.
- [x] Produce QA report, SHA-256 and Phase 2B handover.

## Decisions and limitations

- A dedicated Phase 2A storage module is permitted only as the requested repository/foundation boundary; no unrelated backend route or client modularisation will be performed.
- Browser notes/settings are not being migrated. Usage history and PPC metadata are the two explicitly named Phase 2A browser-origin stores and will retain legacy localStorage mirrors.
- Legacy backend cache files remain byte-present throughout migration and continue to receive compatible writes for the transition release.
- The runtime PID JSON is deliberately not moved because current Windows stop/launcher scripts require it and changing that contract would exceed Phase 2A.
- Schema changes are ordered as seven migrations so each store receives its own verified pre-change backup and restart-safe checkpoint.
- Migration tests found and eliminated two Windows file-handle leaks before any existing store was connected to SQLite.
- No protected colleague package will be produced without matching native compilation and smoke testing.
- Genuine native Windows/macOS installation testing is not part of the current local source run and will not be claimed.
- The archive checksum is recorded in an adjacent sidecar generated after the archive; the ZIP cannot reliably contain its own authoritative hash.

## Blockers

None.

## Test results

### v24.6.219 corrective review patch

- Focused Python suites: 16 tests passed across storage foundation, repositories and real Flask integration.
- Frontend storage fixture: passed.
- Stale usage imports with an existing ID are insert-only; SQLite retains newer URL/audit fields.
- Usage hydration keeps SQLite authoritative except for the specific records mutated in the active page while hydration was in flight.
- PPC stale or timestamp-free conflicts cannot replace newer SQLite metadata; a genuinely newer `updatedAt` value still wins.
- A failed usage clear restores the compatibility mirror, reports an error and does not emit a false success notification.
- A real SQLite writer lock returns retryable `STORAGE_BUSY` with `retry`, then initialises normally after the lock is released.
- Recursive credential-key exclusion drops top-level, nested, camel-case and hyphenated credential fields while preserving safe usage audit fields such as `input_tokens` and `output_tokens`.
- Python compilation, inline frontend syntax and diff whitespace validation passed for the corrective checkpoint.

- Baseline Git worktree: clean before Phase 2A edits.
- Baseline/version surface inspection: passed.
- Storage call-site inventory: complete.
- SQLite foundation targeted suite: 4 tests passed.
  - WAL, foreign keys, 5-second busy timeout, integrity check, schema metadata and exact migration history.
  - Seven distinct pre-migration backups created and independently integrity-verified.
  - Second initialisation created no duplicate history and no extra backup.
  - Injected interruption rolled schema and history back to version 3, then a clean restart completed versions 4–7.
  - Corrupt database returned `STORAGE_CORRUPT`, path-free recovery guidance and left legacy fixture bytes unchanged.
- Python syntax: `cvstudio_storage.py` and the foundation test module passed `py_compile`.
- Repository targeted suite: 4 additional tests passed; 8 Phase 2A tests pass in combination.
  - Usage imports are fingerprinted/idempotent and legacy cost-only rows retain missing detailed fields.
  - Lead-title signatures deduplicate deterministically without duplicate rows.
  - Lead-contact and salary cache documents round-trip and clear correctly.
  - PPC metadata imports/upserts idempotently; diagnostic state drops fields outside the non-sensitive allowlist.
- Python syntax: storage module plus both Phase 2A test modules passed `py_compile`.
- Backend cache integration suite: 4 additional tests passed.
  - Lead-title, lead-contact and salary legacy JSON imported without deletion and repeated reads produced no duplicates.
  - SQLite remained authoritative when a previously imported legacy file became malformed.
  - Cache updates wrote SQLite first and retained the exact v24.6.217 JSON shapes as compatibility mirrors.
  - Corrupt storage returned a structured `STORAGE_CORRUPT` response with the caller request ID and recovery action; legacy bytes were unchanged.
- Runtime diagnostics expose path-free durable-storage health only.
- Usage/PPC backend route coverage: import, upsert, read and explicit clear passed with request IDs and legacy-preserved flags.
- Frontend storage fixture: passed.
  - Both inline `index.html` scripts compile in Node.
  - Usage and PPC hydrate from SQLite while synchronously retaining their v24.6.217 localStorage keys.
  - Writes are serialized; usage clear is protected from an in-flight import restoring deleted history.
  - Legacy usage rows without IDs use stable sorted-key identity, avoiding duplicates when JSON property order changes.
  - PPC mirror conflicts use `updatedAt`; browser mutations are re-upserted if they race hydration.
- Complete Python discovery suite: 16 tests passed.
  - Includes explicit all-store v24.6.217 fixture migration twice, byte-exact legacy preservation and restart without extra backups.
  - Includes preserved Phase 1 request-ID/error normalization, Host/CSRF defense, JobAdder reconnect classification, owner local-health/DOCX checks and support-bundle regression.
- Live threaded source smoke: 18 loopback assertions passed on an ephemeral port with temporary receipt, database and log state.
- Owner-source validation and dependency preflight: passed, including vetted adm-zip 0.5.17 behavior and both inline JavaScript blocks.
- Static validation checkpoint passed: Python (tracked modules), JavaScript (19 files), Bash (5 files through Git Bash) and PowerShell (5 files, zero parser errors).
- Repository consistency: passed; no lock file, exact Git bytes, approved encodings and platform line endings.
- Scope audit: the Phase 2A diff adds no Flask server replacement, scoring-profile workflow, candidate-decision workflow, shared API client, background job, lazy loading or credential persistence.
- Final v24.6.218 rerun: 16 Python tests, frontend fixture and 18-assertion live source smoke all passed after the version bump.
- Final version audit: 8 primary version surfaces agree on v24.6.218.
- Route compatibility audit: all 88 v24.6.217 Flask route URLs remain present; Phase 2A adds 8 local storage routes.
- Final v24.6.219 rerun: 17 Python tests, frontend fixture and 18-assertion live source smoke all passed after the corrective changes and version bump.
- Final version audit: 8 primary version surfaces agree on v24.6.219.
- Corrective scope audit: no prohibited Phase 2B/backburner implementation definitions or shared-client/background-job/lazy-loading symbols were added.
- v24.6.219 clean archive trial: `git archive` produced one `cv_formatter/` root with 82 tracked source files; fresh extraction found 82 files, zero missing files, zero extra files and zero byte mismatches.
- The authoritative v24.6.219 owner/source ZIP is generated from the final clean phase-record commit. Its SHA-256, byte size, source commit and repeated fresh-extraction result are recorded in adjacent sidecars.
- Clean archive trial: `git archive` produced the required single `cv_formatter/` root with 80 tracked source files; fresh extraction found 80 files, zero missing files, zero extra files and zero byte mismatches.
- The authoritative owner/source ZIP is generated from the final clean documentation commit. Its SHA-256, byte size, source commit and repeated fresh-extraction result are recorded in adjacent checksum and verification sidecars because an archive cannot contain its own authoritative digest.

## Historical Phase 2A files changed

- `PHASE_STATUS.md` — baseline evidence, storage inventory, milestone plan and results.
- `cvstudio_storage.py` — SQLite lifecycle, safety PRAGMAs, integrity checks, ordered schema, migration history, verified backups and redacted diagnostic state.
- `tests/test_phase2a_storage_foundation.py` — foundation, idempotency, corruption and interrupted-migration coverage.
- `tests/test_phase2a_repositories.py` — repository import, round-trip, clear, compatibility-cutoff and diagnostic allowlist coverage.
- `app.py` — storage initialisation, structured storage recovery, SQLite-first backend cache reads/imports, JSON dual writes and redacted health diagnostics.
- `tests/test_phase2a_app_cache_integration.py` — real Flask-module cache and corruption-route integration coverage.
- `index.html` — asynchronous SQLite hydration and ordered mirroring for usage history and PPC metadata, retaining existing synchronous localStorage compatibility.
- `tests/test_phase2a_frontend_storage.js` — inline-JavaScript syntax plus usage/PPC hydration, deduplication, write and clear fixtures.
- `tests/test_phase2a_v217_fixture.py` — complete legacy store fixture, double import, byte preservation and restart evidence.
- `tests/run_phase2a_source_smoke.py` — bounded real-loopback source smoke with temporary local state and 18 assertions.
- Production/installer/launcher/protected-build version surfaces — advanced consistently to v24.6.219.
- `AGENTS.md`, `ROADMAP.md`, `IMPLEMENT.md`, `CODEX_FIRST_PROMPT.txt`, `README_FIRST.txt`, `BACKBURNER_ROADMAP.md` and `KEEP_PRIVATE_PATCH_BASE.txt` — v24.6.219 completion/stop gate and next-phase entry instructions.
- `cv_studio_v24_6_218_phase2a_sqlite_foundation_qa_report.md` — Phase 2A release QA evidence.
- `CV_STUDIO_V24_6_218_PHASE_2B_HANDOVER.md` — owner-gated next-phase handover.
- `cv_studio_v24_6_219_phase2a_corrective_review_qa_report.md` — corrective review and release QA evidence.
- `CV_STUDIO_V24_6_219_PHASE_2B_HANDOVER.md` — updated owner-gated next-phase handover.

## Phase 2B files changed

- `cvstudio_storage.py` — schema versions 8–10 and three bounded,
  tombstone-aware repositories.
- `app.py` — repository wiring and 11 additive same-origin storage bridge
  routes.
- `index.html` — selected durable-setting writes, OneNote record/link hydration,
  serialized mutation recovery and additive schema-1 export/import.
- `tests/test_phase2b_repositories.py`,
  `tests/test_phase2b_app_storage_integration.py` and
  `tests/test_phase2b_frontend_storage.js` — focused Phase 2B migration,
  repository, route and browser compatibility coverage.
- `tests/run_phase2a_source_smoke.py` — the retained source-smoke entry point now
  verifies all three Phase 2B stores and 24 assertions.
- Production, installer, launcher and protected-build source version surfaces —
  advanced consistently to v24.6.220.
- Project control/starter files — Phase 2B completion and the Phase 3 activation
  gate.
- `cv_studio_v24_6_220_phase2b_browser_storage_qa_report.md` — Phase 2B release
  QA evidence.
- `CV_STUDIO_V24_6_220_PHASE_3_HANDOVER.md` — owner-gated next-phase handover.

- `cv_studio_v24_6_221_phase2b_corrective_review_qa_report.md` — corrective
  review and release QA evidence.
- `CV_STUDIO_V24_6_221_PHASE_3_HANDOVER.md` — refreshed owner-gated Phase 3
  handover preserving all corrected Phase 2B contracts.
- Production, installer, launcher, protected-build and starter-pack version
  surfaces — advanced consistently to v24.6.221.
- `cv_studio_v24_6_222_phase2b_second_corrective_review_qa_report.md` — second
  corrective review and release QA evidence.
- `CV_STUDIO_V24_6_222_PHASE_3_HANDOVER.md` — refreshed owner-gated Phase 3
  handover preserving both Phase 2B corrective contracts.
- Production, installer, launcher, protected-build and starter-pack version
  surfaces — advanced consistently to v24.6.222.

## Next action

None. Stop before handoff or merge. Do not implement Phase 6 or any backburner
item without a new explicit owner authorization.
