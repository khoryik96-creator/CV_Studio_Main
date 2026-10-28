# v24.6.504 — normal People-query planning

Local, unmerged correction on `codex/v24.6.504-sourcer-queries`, based on merged
v503 `e689e39` / PR #255. The owner's screenshots show a real LinkedIn empty
page despite the correct native Malaysia filter.

## Cause and change

Read-only live A/B/A check: four SAP aliases returned ten cards; the reported
seven aliases returned No results found; four restored ten cards with the
same observed Malaysia geography filter. No candidate was opened, messaged,
saved or sent to a provider. LinkedIn's primary guidance confirms that consumer
queries have a Boolean-operator limit, but does not publish a numeric threshold:
https://www.linkedin.com/help/linkedin/answer/a524411/boolean-query-limitations.

New normal searches use a conservative three-operator planning schema. An
oversized flat positive OR list is bounded to four aliases; complete matching
requirements and country remain. More complex overbudget logic is rejected
without deleting mandatory AND/NOT/nested conditions. Recruiter/Lite and
review-existing-filtered searches use the existing planner path. One private
in-memory Run flag records the already-sent reuse choice; summaries and durable
state do not change. No extra paid plan/retry. An empty first page now says no
matches rather than implying that prior pages were reviewed.

## Validation

The new service-level regression initially produced seven failures on v503,
including the exact seven-alias query and mandatory-clause guards. Twenty
new Python cases cover accounting, country/criteria preservation, unchanged
short plans, Recruiter/reuse compatibility, quoted operators, duplicates,
malformed aliases and no automatic paid replay. Controller cases distinguish
first-page empty from later exhaustion and prevent review calls on zero results.

Controlled native Chromium runs the real old/new backend planners and current
reader against fictional LinkedIn responses matching the observed behavior:
old plan empty, bounded plan ten cards, same geography/criteria and one plan
call. Provider calls are synthetic. Full Python suite: 1,976 passed, 4 skipped,
8,416 subtests passed. All 69 JavaScript fixture files pass. Tracked syntax,
repository/source/native dependency preflight and 24 source-smoke assertions
pass. Final checkpoint identity is recorded in coordination issue #35.

No routes, database schema, saved records, credentials, native country reader,
permissions, provider replay policy, mail/outreach actions or owner installation
changes. This prevents the reproduced query-size failure; genuine no-match,
access restriction and future LinkedIn parser changes remain explicit outcomes.
