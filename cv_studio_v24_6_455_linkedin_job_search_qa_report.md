# CV Studio v24.6.455 — LinkedIn job discovery and content

Owner scope: a new branch for searching/crawling LinkedIn job ads, reviewing
results and adding selected ads to Job Leads; cleaner ad content, a retained
Save to folder choice and more reliable reading of delayed job details.

Branch `codex/v24.6.455-linkedin-job-search` starts from merged v24.6.454
`c0bdca47078823200a12515884a533c30f841cb4` on `origin/master`.

## Result

- Job Leads has a collapsed Find job ads on LinkedIn panel with keywords,
  location, 1–15 pages, new search or an explicitly chosen open filtered search.
  It reads through the Chrome companion. Search cards supply company, role,
  location, canonical ad link and a labelled summary, with exact posting dates
  only when supplied. Read full ad optionally captures the description.
- Review/select/Add selected to list uses existing local duplicate-safe saves
  and folders. Existing records, including Trash and manual notes, are never
  overwritten by importing the same ad. Partial failures preserve unprocessed
  selections. Searching does not replace or automatically save a manual draft.
- Companion runs separate Jobs actions from profile sourcing. Sender/document,
  source, current/pending URL/filter identity, deadline, page and scroll limits
  apply before/after DOM execution. Session-memory counters survive ordinary
  worker recreation. Recognized search-list scrolling and pagination are the
  only new page actions. Stop/end preserve results without further paging.
  Newly opened searches remain available for user review; existing tabs are
  not repurposed or closed. No login/rate-limit bypass or remote write.
- Single-ad readiness waits on the same loaded DOM when role/company or the
  selected job detail panel is still loading. At most 16 reads, 350 ms apart;
  missing description gets a shorter allowance. Each read rechecks authority
  and current/pending identity. No network replay or navigation retry is added.
- Nested LinkedIn layout divs were mapped to nested paragraphs by the previous
  rich-content parser. The new parser emits sibling semantic blocks instead.
  Allowed headings, emphasis and bullets survive; scripts, attributes and
  active content do not. Exact retained text comparison and existing limits
  still apply. Older nested paragraph captures flatten only while rendering;
  explicit plain-text bullets become displayed lists. Saved rows are unchanged.
- Save to folder retains explicit selections in origin-local UI storage.
  New/captured drafts use the default while existing records retain their own
  folder. Explicit Unfiled is remembered, deleting the matching folder clears
  the default, and reload clears a default for a missing folder. Blocked browser
  storage falls back to session-only behavior.

## Verification

Performed on Windows x64 on 20 October 2026 with isolated state/receipts and
synthetic data. No owner-installed authorization receipt was replaced.

- Complete unfiltered Python regression: **1,732 passed, four skipped,
  7,599 subtests passed**, 214.25 seconds.
- **All 37 JavaScript suites passed**, including new scoped DOM extraction,
  worker authority/suspension/page/scroll/redirect tests and real-controller
  multistep discovery/import/Stop/partial-failure tests. Existing Sourcer modes,
  profile ownership, CV, batch, JobAdder and storage fixtures also pass.
- Rich parser/folder organization focused Python suite: **24 passed**. The
  nested layout fixture checks equal text and proper sibling heading/list
  structure, while existing hostile payload/depth/size tests remain unchanged.
- Existing Job Leads actual-controller fixtures additionally verify sticky
  folders across New/capture/edit/reinitialization, explicit Unfiled, deletion,
  legacy paragraph rendering, explicit bullets and literal markup safety.
  Link-capture fixtures verify delayed DOM readiness and its fixed read bound.
- Syntax checks for tracked and nonignored new Python/JavaScript plus shell
  and PowerShell sources, repository consistency, whitespace checks,
  owner-source preflight and **24 source smoke assertions** pass. Actual bundled
  Windows Antiword and Tesseract functional preflights pass; no protected
  compilation or native macOS test is claimed.
- Actual in-app UI with a separate synthetic companion/server: two overlapping
  result pages produce three unique ads; a full ad shows headings, emphasis and
  bullets; selected import saves into Priority Finance and marks the result
  Already saved. Legacy nested content displays cleanly. New lead and reload
  retain the folder preference. Screenshot evidence remains in ignored runtime.
- Persistent source preview on 5074 runs v24.6.455. Read-only before/after SQL
  value hashes confirm both owner lead rows are exactly preserved across restart.
  Installed app on port 5000 is untouched. Temporary synthetic server is stopped.

## Preserved contracts and limits

120 routes and the existing digest
`ee8d33baeb48b961a2f50723faacbeb7fed86b55454b3518ab4a07bcd1e90033`,
five ordered guards, 80 MiB global limit, main SQLite schema 10, dedicated Job
Leads schema 2 and journal schema 1 remain. Existing save, backup, Trash, folder,
paid-provider and profile-sourcing contracts remain. Four companion assets and
host/permission allowlists are unchanged. VERSION and generated surfaces are
24.6.455.

Live signed-in LinkedIn layouts, an installed Chrome extension update and real
Chrome worker suspension were **not** exercised by the synthetic tests. Existing
installations must download the updated companion, replace the unpacked files,
Reload it and reconnect the CV Studio Chrome tab. LinkedIn can still require
sign-in, show access checks or limit reads; the run stops and retains partial
results. There are no paid calls or credentials involved in job discovery.

No owner records were edited for QA. No push, PR, merge, protected package or
owner installation update is part of this checkpoint.
