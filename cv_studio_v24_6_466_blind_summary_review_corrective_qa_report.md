# CV Studio v24.6.466 — Blind summary review corrections

Historical QA record; root `VERSION` is authoritative.

This corrective retains v465's source About/summary preservation and addresses
all three review findings before the owner-authorized merge:

- `/extract-text` now uses the same direct/inherited Word numbering detector
  as legacy extraction. Genuine body and table list paragraphs keep a marker;
  `numId=0` remains plain. Body/table order keeps lists beside their headings.
  Enumerated lists retain an enumeration signal distinct from ordinary bullet
  lists, including native Word numbered section headings. This signal identifies
  layout; it does not claim to reconstruct Word's displayed list counter.
- Source summary recovery recognizes supported skills/certification/training
  aliases and numbered, uppercase or colon-emphasized section headings, while
  ordinary marked title-case words remain content. Candidate-details table
  labels after a floating About box also stop recovery.
- Selected source points guide the existing parse call. Instructions remain in
  the system prompt, and all selected source content stays in user-message data.
  The same context is retained through existing repair attempts, without adding
  a call or changing retry/non-replay policy. Matching provider mechanics and
  explicitly requested small spelling corrections survive source restoration.
  Numeric anchors and order remain protected; unrelated/reordered output falls
  back to the selected source. Exactly matching provider splits survive when
  unmarked text is ambiguous. The existing pay filter runs on the selected
  points before matching corrections, so a salary point correctly omitted by
  the parser cannot discard corrections to the remaining points. Removed pay
  is still reported once, and a pay-only box cannot revive a later Summary.

The original review reproductions failed before the fixes. Additional failing
checks caught floating-summary candidate headers and native Word numbering.
Coverage includes actual synthetic Word extraction, body/table lists, table
position, explicit zero numbering, generated Word re-upload, language-toggle
behavior and grounded correction/refusal cases. All original fixture
expectations remain unchanged. Real provider/JobAdder calls are mocked; owner
installation, receipt and private documents are untouched.

Final validation:

- Full isolated Windows Python: **1,748 passed, four skipped, 7,665 subtests**,
  171.52 seconds. Temporary receipt, SQLite, journal, salary and credential state
  were isolated before collection. Earlier intermediate checks caught and
  corrected a numbering-namespace fallback and an unmarked broad catch; the
  final exact-source run passes both regressions and the unchanged exception
  ratchet.
- All **42 JavaScript suites passed**; subsequent corrections changed no
  JavaScript implementation. Source syntax, whitespace, repository consistency,
  Windows owner-source native-dependency preflight and **24 source smoke
  assertions passed**. No protected compilation or native macOS test occurred.
- Added **18 B1 fixtures** without changing the 1,001 pre-existing cases or their
  expectations. All 16 earlier source-reader cases return identical results.
  The original master's 985-case registry replay passes against exact master
  and current blind helper modules. Repository sentence comparison covers over
  **226,000 code/test/documentation lines**, with no changed legacy promotions or
  standalone false recoveries.
- Generated correction checks retain 100 aligned spelling/casing pairs and
  reject 100 changed-number pairs. Existing marked-list and salary-generated
  cases remain. Hostile input checks bound source, section, item, spelling and
  oversized-output work. Numeric decimal boundaries, negation, polarity,
  transpositions, unrelated sections and reordered points have refusal cases.
- Seven in-memory reader/recovery mutations are detected, covering numbered
  boundaries, aliases, strong headings, candidate-header exclusion, language
  correction retention, numeric anchors and unmarked splits. Two actual-route
  mutations separately confirm the Word-numbering and raw-overwrite regressions
  fail when their fixes are disabled.

Both v465 and this corrective are included in the owner-authorized PR/merge.
Private inputs, the already-delivered corrected Word copy and owner installation
remain unchanged. No live provider request, external candidate write or new
release ZIP was produced. The earlier v465 six-page document rendering remains
applicable; this corrective changes source reading/selection, not the renderer.
