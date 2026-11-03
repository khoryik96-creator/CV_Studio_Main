# CV Studio v24.6.551 — job-ad card visual refresh

Source work on `codex/job-search-results-scroll`, including v24.6.550.
[PR295](https://github.com/khoryik96-creator/CV_Studio_Main/pull/295) records current
CI, review and merge status. Not installed on the owner's machine.

Search-result cards now group role/company beside a company-initial tile, place
selection/saved indicators in the header, and present location and capture state
in a compact metadata row. Cards have contained borders, consistent spacing and
rounded corners; preview/selection feedback does not shift the layout. Actions
are compact and aligned, with the LinkedIn link separated from preview/read
buttons. Existing error messages remain visible. The preview uses clearer title
hierarchy and content spacing. Colors use the existing application variables.

Validation:

- All 94 existing frontend fixtures pass, including search selection, pagination,
  background capture, cached reads, stop/retry, saved-data protection and focus /
  scroll / expanded-content preservation. No new behavior tests were added for
  this visual change.
- Five version-source tests, JavaScript syntax, whitespace and repository
  consistency checks pass.
- The existing fictional Chromium background workflow passes with the new markup.
- Chromium checks desktop, 390px and 320px layouts, including long title/company /
  location strings, with no card/list overflow or page errors. Sample desktop
  and mobile screenshots are `/tmp/cvstudio551/job-ad-cards-desktop.png` and
  `/tmp/cvstudio551/job-ad-cards-mobile.png`.

No live LinkedIn, email, JobAdder, Apollo or AI provider calls were made. Existing
search/capture/storage behavior, routes and schemas were not changed. The fixture
uses sample content; its named companies do not represent verified current ads.

PR295 review correction: background redraws also preserve keyboard focus on
LinkedIn anchors and description summaries. The Chromium workflow now focuses
both elements across successive background reads; it reproduces the lost anchor
focus before correction and passes afterwards. Existing button/input focus,
expanded summaries and list position remain covered by that workflow.
