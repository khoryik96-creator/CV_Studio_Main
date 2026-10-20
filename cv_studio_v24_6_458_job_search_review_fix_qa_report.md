# CV Studio v24.6.458 — job-search count review corrective

Historical QA record; root `VERSION` is the current release reference.

The owner requested fixing all review findings and merging the unmerged
v455–v457 LinkedIn job discovery changes. The review identified one actionable
defect. Branch `codex/v24.6.458-job-search-review-fix` continues v457 `ca9c92d`
against unchanged merged v454 `c0bdca47078823200a12515884a533c30f841cb4`.

## Root cause and correction

The empty-result expression matched `0 jobs` anywhere in the rendered search
text. It therefore also matched positive counts such as `10 jobs`, `100 jobs`
and `1,000 jobs`. If that header loaded before the cards or results region,
the reader reported an empty search and the controller stopped immediately.

The numeric alternative now requires a standalone zero count, excluding word,
numeric and numeric-separator prefixes. Existing explicit no-results messages
remain supported. Positive-count snapshots wait for cards; a real empty search
still finishes without needless polling. No controller, paging or save behavior
was otherwise changed by this corrective.

## Verification

Performed on Windows x64 on 20 October 2026 with isolated test receipts/state.

- Added legacy and modern reader regressions first. Both failed on the previous
  reader at `10 jobs`, then passed after the correction. Coverage includes
  positive counts ending in zero, grouped thousands, a missing results region,
  real numeric zero/no-results messages and cards becoming readable afterward.
- All **39 JavaScript suites passed**, including search/controller/worker,
  companion lifecycle, profile sourcing, Job Leads/drafts/folders, link fallback
  and the existing CV/batch/export suites.
- Full unfiltered Python regression: **1,737 passed, four skipped, 7,599
  subtests passed**, 201.76 seconds.
- Tracked/new Python and JavaScript syntax, tracked PowerShell/POSIX shell
  syntax, repository consistency, whitespace checks, owner-source preflight
  and **24 source smoke assertions passed**. The bundled Windows Antiword and
  Tesseract functional/English-data checks passed. No protected compilation.
- Persistent source preview 5074 reports v24.6.458. Read-only before/after SQL
  value hashes confirm both saved lead rows are exactly unchanged. The preview
  had no active sourcing run when restarted. Earlier browser drafts and the
  installed port-5000 app/authorization are untouched.

## Scope and remaining verification limit

The merge candidate includes the reviewed v455–v457 keyword/open-search job
discovery, selected duplicate-safe folder import, sticky folder preference,
content formatting, automatic eligible public-read fallback and modern layout
support. Their QA records describe the broader implementation and limits.

The 120-route seal/digest, five guards, 80 MiB limit, main SQLite schema 10,
dedicated Job Leads schema 2, journal schema 1 and companion permissions remain.
No paid/provider call, LinkedIn write, owner saved-record mutation, installed
app update, protected compilation or native macOS test is part of this work.

A complete live installed-companion search/import session remains unverified;
synthetic tests and the earlier read-only live selector inspection do not imply
that end-to-end check. Existing users need the updated companion files, Reload,
an app-page refresh if needed and reconnection from its toolbar icon.
