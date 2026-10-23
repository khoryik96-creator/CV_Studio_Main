# Historical — v24.6.475 job-ad rich formatting corrective

Current release identity always comes from root `VERSION`. This report records
the owner-requested corrective on the unmerged company-HR feature branch.

## Cause and correction

The owner reported missing original bullets and bolding despite improved
alignment. Read-only inspection of the current signed-in LinkedIn About panel
found semantic strong headings and an ordered list, plus an aria-hidden
`expandable-text-button` labelled “… more” before benefit text. The old reader
copied that button into plain text. Its trailing Show/See more removal did not
match this label/position; the HTML sanitizer correctly removed the button, so
the exact-text guard rejected all rich formatting for the otherwise valid ad.

Both legacy/modern companion captures now use one bounded passive DOM traversal
for plain text and markup. It excludes controls, hidden/active nodes and source
attributes/URLs. Original lists/headings/emphasis remain, computed bold/italic
become semantic emphasis, and block/list roles retain structure. Original pages
are not modified. Visible expansion buttons still label excerpts.

Two related losses are corrected within the same formatting boundary:

- At the existing 20,000-character limit, a matching rich prefix is clipped
  before final validation rather than all formatting being discarded. Full
  retained text must still match; short/manual or within-prefix mismatches fail.
- A single canonical public description may provide richer markup when it
  matches the metadata's retained words exactly. Metadata fields/text remain;
  mismatched or oversized optional visible markup is ignored.

The existing shared renderer and durable passive-tree schema remain. No guessed
formatting, raw source styles, HTML execution or automatic saved-record rewrite
is introduced. Older captures require explicit Refresh ad content and Save.

## Regression evidence

The modern-reader reproduction failed before the correction: an embedded
“… more” label survived in plain text, invalidating the rich result. Existing
date/modern-reader fixture expectations remain. New cases prove headings,
lists, embedded benefit text and excerpt markers survive while UI text does not;
computed emphasis, CSS block separation, ARIA lists and hostile attributes/URLs
are handled passively. Legacy date/capture checks exercise the same helper.

The long-prefix and canonical-rich-body tests also failed before correction.
They now prove list/bold retention, no unretained suffix, exact-text/manual-edit
protection, unchanged metadata fields and optional-markup bounds.

- Full isolated Windows Python: **1,767 passed, 4 skipped, 8,392 subtests**,
  187.22 seconds.
- All **45 JavaScript suites passed** after the final reader refinements,
  including company-HR, Jobs discovery/direct-add/folders and Sourcer lifecycle.
- Python/JavaScript/shell/PowerShell syntax inventory, whitespace, repository
  consistency, owner-source validation/preflight and **24 local source smoke
  assertions passed**. Native Windows Antiword was trusted/functional and
  Tesseract English functional. No protected build or native Mac run was made.
- A read-only snapshot retained the observed LinkedIn DOM structure/computed
  typography but replaced ad text with synthetic labels before local replay.
  The production capture helper and real backend formatter/store retained the
  original bold sections plus computed emphasis, one ordered list and seven
  items, excluding the embedded expansion control from both representations.
- Browser QA on isolated temporary state at port 5085 rendered the real
  controller/store/formatter result. Bold nodes computed to weight 700; the
  seven-item ordered list used decimal markers. No “… more” text remained.
  This is a synthetic-text structural replay, not a live installed-extension
  end-to-end claim. Preview image is ignored under `runtime/`.

## Preserved boundaries and handover

The company-HR feature remains in this branch. All 120 routes/five guards and
their seal, main SQLite schema 10, Job Leads schema 2, journal schema 1,
existing response fields and four-file companion permissions remain. No paid
call, outreach, login bypass, owner record/receipt/installation mutation or
protected package was performed. Existing notes, folders, status, manual contact,
HR evidence and duplicate Add semantics remain.

Use the updated backend/companion, reload the companion and refresh/reconnect
pages. Refresh and save older ads to re-capture typography already lost in their
stored plain text. No PR or merge was requested for this corrective.
