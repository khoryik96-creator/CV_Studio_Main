# Job Leads posting date and saved ad content — 2026-10-19

Historical release evidence; root `VERSION` is the live release identity.

## Scope and behavior

Owner requested a posting date when available and a View more option to read
job-ad content. Source v24.6.450 on `codex/v24.6.450-job-ad-details` starts from
unmerged v449 `087fa36`. Posting date is an optional validated calendar date;
public JobPosting metadata or exact metadata within the companion's recognized
job panel can fill it. Time zones never shift the source calendar day. Relative,
invalid and missing values remain blank, with Not available on saved cards.
Manual dates and other populated fields remain protected during auto-fill.

Each saved card has a native expandable View more section containing its saved
plain-text description. No network request or AI call is needed to expand it.
The draft has a larger editable content section. The existing 20,000-character
limit remains; excerpt flags now survive persistence and backup/restore and
produce an explanatory label. Empty descriptions have a recovery hint. Contact
stays manual and optional, status starts New and follow-up dates remain manual.

The existing record JSON stores both additive fields. Old rows and backups
default to an unknown date and false excerpt flag. Posting dates appear in CSV;
JSON backup/restore preserves both fields. No migration, new route or worker:
the 120-route seal, five ordered guards, main schema 10, Job Leads schema 1,
journal schema 1 and all provider/Sourcer contracts remain unchanged.
Version surfaces were generated through bump_version.py.

## Verification

- Baseline focused persistence, extraction and architecture checks: 67 passed.
- Changed extraction/persistence suites: **82 passed**. Cases cover exact dates,
  time zones, leap days, invalid/relative dates, legacy rows, typed excerpt flags,
  save/reopen and backup/restore. Existing request bounds, identity/credential
  protections and non-AI lookup checks remain covered.
- Full isolated Windows local run: **1,689 passed, four skipped, three deselected,
  7,599 subtests passed**, 158.80 seconds. Existing updater environment exclusions:
  `test_python_runtime_resolver_returns_the_exact_validated_interpreter`,
  `test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`,
  `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`.
  No unfiltered hosted CI result is claimed.
- All **33 frontend suites** passed. New/updated checks exercise date auto-fill,
  manual override preservation, same-panel companion metadata, source calendar
  days, missing content, plain-text hostile content, saved descriptions, excerpt
  hints and CSV dates; existing companion and sourcing ownership tests pass.
- Real in-app preview opened the existing saved public ad's description through
  View more. That public ad currently supplies no exact date accepted by the
  reader, so its saved card correctly shows Not available. Public read checks
  did occur; no login, access-check bypass or private LinkedIn API was used.
  No owner lead was added or modified during this verification.
- A separate synthetic preview proved Posted: 2 Oct 2026, unknown dates, expanded
  saved multiline content and missing-description guidance in the actual UI.
  Screenshot retained as ignored local proof; synthetic rows never entered the
  owner's persistent preview store. The test-only preview is stopped afterward.
- Python/JavaScript/shell syntax, tracked byte/source inventory validation,
  verified Windows Antiword/Tesseract and adm-zip owner-source preflight passed.
  Live source smoke passed **24 assertions**. No protected compilation or Mac
  native testing is claimed.

The persistent isolated preview remains on 5074. Existing owner browser drafts
and installed app/receipt remain unchanged. No provider charge, candidate access,
JobAdder write, outreach, push, PR, merge or packaged release occurred.
