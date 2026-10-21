# CV Studio v24.6.465 — Preserve source profile summary points when blinding

Historical QA record; root `VERSION` is authoritative.

The supplied original CV has a first-page About box with six separate points
and a Note. Its blinded Word output instead contains a generic paragraph from
a later Summary section. The Word renderer already creates one paragraph per
`summary_bullets` item, and the blind finalizer already rejects a provider
dropping summary items. The missing boundary is earlier: parsing can select the
later generic Summary and discard the original About points before masking.

Single and batch Blind CV now explicitly request `preserve_source_summary`
during parsing. A bounded, pure source reader retains a unique headed summary,
preferring an explicit About box over a later generic Summary. Marked points
stay separate, physical line wraps stay within their point, hyphenated wraps
retain spelling, and a separate Note becomes its own item. A real prose
paragraph stays a paragraph. Repeated headings, excessive input/sections and
possible continuation beyond a footer defer to the existing interpretation.
Known section boundaries and template footers are excluded from the summary.

Recovery runs before the existing salary filter and blinding provider, never
after masking. Competing parsed summary categories are removed before pay
filtering, preventing an emptied pay-only About box from resurrecting a later
generic paragraph. The existing provider count check, employer/candidate scrub
and gender preference remain. A summary the user explicitly linked replaces the
parse result afterward. Normal Format CV and Create Profile do not opt in.
No route, schema, credential, provider retry or paid-confirmation gate changed.

Validation:

- Added 16 anonymized B1 cases without changing any existing fixture. The initial
  new reader test failed before implementation. The exact v464 parse function
  also fails the new end-to-end About/paragraph regression as expected.
- Full isolated Windows Python: **1,741 passed, four skipped, 7,645 subtests**,
  167.64 seconds. Temporary receipt, database, journal and credential state were
  isolated from the owner's installation before collection.
- All **42 JavaScript suites passed**. Payload evaluation covers single/batch
  blind mode independently of language correction and confirms Create Profile
  remains unchanged. Existing linked-summary tests pass.
- Mock-provider parse → blind → real DOCX integration verifies separate numbered
  paragraphs in both DrawingML/VML copies, exclusion of the later paragraph,
  salary removal and deterministic identity/employer masking even when the
  provider echoes source identity. No real provider request was made.
- Replayed all **985 pre-existing registry cases** with exact v464/current blind
  helper modules; both pass. Compared legacy summary promotion on **225,519
  repository source/test/documentation lines**: no changes, and no standalone
  sentence incorrectly becomes a headed source summary.
- Generated marked lists include 1, 2, 6, 20, 21 and 100 items across five marker
  forms. Excessive character, line, section and item counts fail closed within
  the test's one-second limit. Eight deliberate in-memory reader mutations are
  caught: precedence, ambiguity, boundaries, wraps, continuation, section limit,
  hyphenated wrap and undefined PDF bullet. A route mutation disabling competing
  summary removal is caught by the pay-only regression.
- Source syntax, whitespace, repository consistency, Windows owner-source
  native-dependency preflight and **24 source smoke assertions passed**.
  No protected compilation or macOS native testing was performed.

A corrected copy of the supplied blinded Word file was created locally without
changing either original. Six source points and the separate unbulleted Note
are retained, with employer labels matched to its existing blinded history.
Only `word/document.xml` changes; all other ZIP entries and body text outside
the textboxes remain intact. Its long-summary first-page layout follows the
existing generator's table-before-anchor arrangement and starts work history
on the next page. The packaged renderer initially lacked LibreOffice on this
Windows host, so its conversion stage was adapted to a separate 32-bit
PowerShell/Microsoft Word instance while retaining its Poppler PNG pipeline.
All six final page images were inspected for readable, unclipped output.
Candidate documents, extracted text, conversion scripts and page images remain
local/ignored; no private source content was added to tracked fixtures or QA.

Branch: `codex/v24.6.465-blind-profile-summary-lists`, based on merged v464
`02af520af35169623ff23503b74f46740e55cda4`. Saved source checkpoint only; no
push, PR, merge, private release ZIP, live paid call, external candidate write or
owner installed-app/receipt update was performed.
