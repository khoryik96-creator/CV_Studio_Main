# CV Studio v24.6.460 — modern job location review corrective

Historical QA record; root `VERSION` remains the release reference.

The owner requested merging the v459 ad curation changes. PR #231's automatic
review identified that the initial-location reader counted every expandable
header button as a location. Read-only inspection of the current Jobs page
confirmed Malaysia alongside expandable promoted-jobs and AI-search help
controls. Those unrelated labels made the initial handshake wait until timeout.

The reader now accepts only visible controls carrying a Location accessibility
label themselves or on a visible rendered child. The actual page exposes
`aria-label="Location Malaysia"` on a child. The corrected scoped read returns
Malaysia alone. No browser click, search, page navigation or LinkedIn write was
performed for this verification.

The modern reader regression failed against v459 with the unrelated filters
and help controls present, then passed with the correction. It also checks that
unrelated controls alone supply no location and conflicting recognized locations
still reject. Existing new-search handshake/strict-filter tests pass.

This correction changes no route, schema, guard, permission, provider boundary,
direct-add behavior or saved data. v459 remains an immutable checkpoint; version
surfaces were generated with `bump_version.py`. The owner installed app and
authorization remain untouched. Full installed-companion end-to-end testing
remains unverified, as recorded in the v459 QA report.

Final local verification on Windows x64:

- Full isolated unfiltered Python suite: **1,737 passed, four skipped, 7,599
  subtests passed** in 168.86 seconds.
- **All 41 JavaScript suites passed**, including direct capture, source/run
  authority, job search lifecycle, initial normalization and strict later filters.
- Tracked/new source syntax, repository consistency, whitespace checks,
  owner-source preflight and **24 source smoke assertions passed**. Genuine
  bundled Windows Antiword and installed Tesseract/English functional checks
  passed. No protected compilation or native Mac test was performed locally.

The v459 head's three GitHub checks passed before this corrective; updated
hosted checks must pass on the corrected head before the authorized merge.
Automatic approval review rejected restarting preview 5074 without a specific
reason, so its existing process remains running. No preview record, installed
app, owner receipt or browser draft was changed by that rejected command.
