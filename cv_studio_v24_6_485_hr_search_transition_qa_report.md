# CV Studio v24.6.485 — HR search loading and modern filters

The current release is always repository-root `VERSION`. This local correction
starts from merged master `d90c676` (v24.6.484) on
`codex/v24.6.485-hr-search-transitions`.

## Report, cause and remedy

The owner reported "The HR search changed. Start again from the saved ad."
Inspection of the normal Brave app confirmed v484 and that exact message. Its
retained LinkedIn tabs had the intended company and HR keywords. The modern
filter DOM also showed checked company inputs named by associated labels,
role-based Locations buttons, option rows and a separately rendered popover.
Inspection opened then closed a location chooser without applying a search or
saving a lead. No private page/profile content was added to fixtures or reports.

Chrome's navigation promise does not establish that the destination document is
ready. The old worker immediately marked the People search readable after
`tabs.update`, so an old complete company document could be rejected as a changed
search. A persisted `search_wait` stage now awaits only the requested exact
destination, tolerating the preceding exact company page but never reading it as
results or navigating again. Different pending destinations still fail. The old
company page is no longer accepted after the search becomes ready.

A load beginning between source checks and reader injection now produces an
internal pre-action loading sentinel. It permits retry only when the reader
action was never invoked. Unknown/missing results after invocation remain
interrupted; clicks/navigation cannot silently replay after suspension. Deferred
page clicks restore their reserved budget, and the UI polls explicit loading
responses within 90 attempts with Stop/unload checks. A timeout preserves previous
saved evidence instead of saving a false completed scan.

The reader supports associated visible company/country labels, modern role-based
Locations controls and exact suggestion rows, and selected countries/Show results
inside the location popover. It prefers the actual primary content section.
Existing legacy markup remains supported. Checked state, exact label/word matching,
company/current-company URL identity and country filter identity remain required.

## Verification

New worker regressions failed on the v484 navigation behavior before the fix.
New reader and UI cases likewise failed for associated labels and loading paging
responses. They pass after the fix, along with the existing original assertions.
Cases cover persisted waiting, delayed committed metadata, different pending
company/login targets, injection-time loading, one navigation/click, page budgets,
ambiguous mutation non-replay, legacy/modern controls and paging wait exhaustion.

Actual isolated Chromium ran the production worker and reader against synthetic
offline company/People HTML. An explicit simulated toolbar callback establishes
the test-only pairing; HR source-tab creation returns a pre-created controlled
page, while the worker uses native tab navigation and real DOM injection/actions.
The metadata fault hook deliberately returns the preceding complete company
document twice after accepting navigation. The v484 baseline reproduces the exact
reported "HR search changed" error. Corrected code passes worldwide and Malaysia
searches, native portal controls, both results pages, filter rejection and retained
source cleanup. Hook counters assert the injected stale reads actually happened.
Outbound networking is blocked by a dead proxy; no live account/provider access
occurs in this disposable test browser. This is not a completed live owner scan.

Final-code checks passed: **1,779 Python tests, four skipped, 8,392 subtests**
(239.29s), all **47 JavaScript suites**, repository/tracked-language syntax and
owner-source preflight, and all **24 source smoke assertions**. Native Windows
preflight confirmed trusted functional Antiword 1.3.5 and Tesseract 5.5 English.
No protected compilation was performed. Git whitespace validation passed.

## Preserved boundaries and delivery

All 120 routes and their sealed digest, five guards, 80 MiB limit, main SQLite
schema 10, journal schema 1 and Job Leads schema 2 remain. Extension permissions,
pairing/proof handling, document/run isolation, page/profile/time ceilings,
joining-date evidence, saved ad rich content/folders and paid-call non-replay
remain. No provider charge, outreach, protected build or native macOS application
test is claimed. Owner installation, receipts, browser profiles and saved leads
were not edited. No new PR or merge is authorized by this bug report; this work
ends at a tested local Git checkpoint.

Ignored local evidence: `runtime/hr485_baseline_native.log`,
`runtime/hr485_native.log`, `runtime/pytest_485_full.log`,
`runtime/js485_*.log`, `runtime/preflight_485.log`. Baseline metadata simulation
and browser harness are in ignored `runtime/companion485_hr_browser.js`.
