# Historical QA record — v24.6.437 review follow-up

Tested on 2026-10-02. Root `VERSION` and `HANDOFF.md` provide current state.
This corrects all three findings from the delegated v436 review. It extends
`codex/v24.6.436-review-date-corrections` at `c705b88`, based on merged master
`cf48a558` / v24.6.435. The owner requested “fix all”; issue #35 received a
new shared-file claim before edits. No PR or merge was requested.

## Corrections

- **Mixed-layout repeated stints (D2):** a two-line header could overwrite the
  dates of another stint because only two-line sightings counted. The existing
  work-row reader now supplies additional employer/title sightings before date
  recovery. Title-first, employer-first, date-first, borderless and place rows
  block an ambiguous repair, even when their dates match. Reconciliation reuses
  its existing row scan. Direct helper calls skip that scan if no repair is
  eligible. Exact identity, section limits and date-only recovery remain.
- **OCR scheduling (D3):** optional reads ran between mandatory pages, so their
  time could cause a later primary page to fail. All selected primary pages now
  finish first. Optional scans use only the original deadline's remaining time;
  exhaustion/failure keeps the complete primary result. The semaphore, page
  and pixel limits, ten-second optional timeouts and two-page recheck cap remain.
- **Month consensus (D3):** chronology's absent-month defaults could treat
  missing months as observed January/December. Consensus now also compares
  actual month presence and normalized spelling. Missing/added start or end
  months refuse correction. Equivalent full/abbreviated months and year-only
  ranges still work. Only an agreed single start-year digit may change.

## Evidence

New regressions were added before production edits and failed on v436:
mixed-layout stints, missing/added months and optional scans consuming primary
page time. The pre-fix run recorded 66 failed cases/subtests. The OCR cap test's
provider sequence was updated to the explicitly corrected primary-first order;
its seven-call/two-page cap and expected results remain enforced.

All **905** previous registry case objects and expectations are unchanged.
Ten appended cases cover six mixed layouts/identical-date controls, three
missing-month controls and the shared-deadline schedule. Generated repeated
stints cover forty years; existing generated unique-date and 20,000-header
hostile-input/performance checks remain. No old case was weakened or removed.

Validation on the final production code:

- Focused pure helper/review/registry gate: **51 passed, 1,082 subtests**.
- Complete isolated Python gate: **1,569 passed, four skipped, 7,038 subtests**
  in 215.33 seconds. Only the same three previously reproduced updater
  environment fixtures were deselected:
  `test_python_runtime_resolver_returns_the_exact_validated_interpreter`,
  `test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`,
  `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`.
- All **29** frontend suites passed.
- **22** deliberate mutations in temporary copies were caught by behavioral
  assertions, including removing cross-layout ambiguity, observed-month
  agreement and primary-first scheduling. No tracked source was mutated.
- Tracked/nonignored-source syntax inventory: 165 Python, 80 JavaScript,
  nine PowerShell, three shell and two command files. Syntax, repository
  consistency, version-source tests and owner-source preflight passed.
- Isolated live source smoke: **24 assertions passed**; no protected compilation.
- Real offline OCR of the supplied four-page scan completed all four primary
  pages first, then rechecked only the affected page at 150/160 DPI. The agreed
  start-year digit was corrected; all other primary OCR text stayed identical.
  Candidate contents and private paths remain outside tracked QA/test evidence.
- Whole-suite capture recorded **939** distinct serializable source inputs.
  Replay includes repository code/test/document fragments and compares exact
  v435 master and v436 source. Existing row-reader outputs remain unchanged;
  every observed difference is confined to date fields, the already-approved
  resolved-review filtering, or the bounded OCR year correction. Both
  comparisons report zero unexpected differences. Final replay counts are in
  the follow-up evidence below.

Final corpus replay: **3,039 inputs**. Against v435 master: fifty date-only
reconciliations, nineteen resolved-review subsets and five OCR year-only
corrections; zero unexpected differences. Against v436: fifty-two ambiguous
date overwrites and eleven incomplete-month OCR corrections are prevented;
zero unexpected differences. Each v436 corrective difference additionally
must equal the original input parse/text exactly. Existing row-reader results
and all unrelated fields remain unchanged.

## Preserved boundaries and preview

No routes, schemas, provider calls/retries, credentials, paid confirmations,
Apply/Undo, upload behavior or Word export layout changed. The 118-route
contract, five ordered guards, 80 MiB limit, SQLite schema 10 and journal schema
1 remain. Application tests and smoke used temporary receipt/data/credential
roots; the owner installation and receipt were untouched. No live AI/JobAdder
write, protected build, release artifact, PR or merge occurred.

The separate source preview on loopback **5071** was restarted with its existing
isolated temporary state. HTTP 200, v24.6.437 and the listener's exact preview
runner/root were verified. The installed app remains on merged v24.6.435.
No browser visual verification or genuine macOS testing is claimed.
