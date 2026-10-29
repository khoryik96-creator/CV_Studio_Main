# v24.6.518 — observed HR employment ranges

Local correction stacked on v517 `8a7025d` (reviewed JobAdder company contacts),
based on merged master v516 `fad1a39`. The owner now authorizes publication and
merge of both tested checkpoints; issue #35 records their publication/merge
identity. Held PR #257 remains excluded.

The owner reports dates visible in LinkedIn but absent from saved HR cards,
and requests month/year start/end ranges, including Present. Read-only scoped
inspection confirmed the modern Experience entry is currently readable by the
existing parser once hydrated. The previous saved scan had empty dates; its
historical DOM was not retained, so its exact event is not claimed as proven.

The reproduced reader gap is company role/logo links appearing before date
metadata. That stage now reports loading within the established 20-poll,
four-scroll, exact-owned-tab budget. Observed start/end/current evidence flows
through guarded RPC, UI, existing JSON storage and backup. The exact profile,
company link/ID and original search filters remain bound throughout. No paid
call, external record or owner browser tab is changed during testing.

Cards show `Employment: Oct 2026 to Present` or a completed month/year range.
Year-only evidence stays year-only. Old start-only records remain readable and
do not gain invented Present/end values. A fresh scan with the updated companion
is required for evidence missing from a previous save. Current stints win over
separate earlier stints; ambiguous/collapsed groups, incomplete continuity,
unorderable endpoints and duration-only text cannot create dates. No broad
description/About/education fallback. `hr_employment_revision:1` requires the
new reader before single or bulk scanning. Existing DB version stays 2.

Self-review also found and reproduced a pre-publication v517 non-replay gap:
after an uncertain contact POST, a different company could receive a new review
for the same email. Protected operation identity now spans company choices for
that account/email, while its payload proof still binds the selected company.
Read-only recovery checks the original POST company. The regression failed
before this correction and passes after it. No live contact was created.

## Validation

- Domain/route/date storage tests: 66 focused cases passed, including invalid
  ranges, lossless backup, unchanged DB schema and cross-company non-replay.
- All 77 standard JavaScript fixture files passed, including new worker/UI
  ranges and old-companion rejection, single/bulk scans, legacy dates, Stop,
  source changes, owned tabs, concurrent sessions and bounded loading.
- First complete Python run passed 2,135 tests, four platform skips and all
  8,418 subtests. Final confirmation on the completed code passed **2,136 tests,
  four skipped and all 8,418 subtests**, including the added JobAdder guard.
- Optional native Chromium fixture uses fictional modern/legacy Experience
  markup with all network fulfilled locally: delayed metadata, current/former
  ranges, grouped promotions, exact-company isolation and collapsed groups pass.
- Actual isolated Flask/browser acceptance passed with fictional JobAdder/Apollo
  transport and temporary protected storage: selecting the saved ad displays
  current/former employment cards; existing company selection, authoritative
  source email, review invalidation, one POST, duplicate reopen protection and
  desktop/mobile dialog layout pass. Inspected native screenshots are retained
  only in ignored runtime output. The older Contacts visibility regression also
  passes again at desktop/mobile sizes. Temporary synthetic server 5096 is
  stopped after acceptance; retained isolated preview 5095 serves v518.
- Syntax, version/repository consistency, genuine Windows dependency preflight
  and all 24 source-smoke assertions passed. No genuine macOS application test,
  protected build or live account-specific JobAdder acceptance is claimed.

The retained isolated preview is port 5095. Owner installation/records and the
running owner server on port 5000 are separate and unchanged by these features.
