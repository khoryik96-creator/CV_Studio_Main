# v24.6.525 Job Leads corrections - QA and handover

Base: merged v24.6.524 `0161728fc285287705fd273c96593dae6efa647f` / PR268.
Branch: `codex/v24.6.525-job-leads-corrections`. Owner requests the following
features/fixes and separately explicitly approves confirmed manual JobAdder
recovery. This checkpoint is local only, not pushed/merged. HeldPR257 excluded.
No new production route, SQL migration, protected build or installation update.

## Employment evidence

Read-only inspection of the four supplied profiles found two exact linked
company groups with overlapping Present roles and another with a shorter
secondment inside a longer bridging role. The old reader rejects multiple
Present ranges and processes prior roles in start-date order, allowing the
shorter role to hide the bridge. It now takes the earliest overlapping current
start within one exact group and processes ended roles by end coverage.
Collapsed groups, conflicting identities, separate ambiguous stints, missing
links and imprecise dates retain conservative handling. No description/tenure
inference or company-name guessing was added. Synthetic native fixtures cover
both root defects and fail on the pre-change reader for the overlapping-current
case, then pass after correction. Existing native cases continue to pass.

One observed current role has no LinkedIn company hyperlink, despite visible
employment text. It cannot be automatically attributed to the selected employer.
After a failed single check, the compact Set dates from LinkedIn fallback
requires month/year values and explicit employer/date confirmation. It saves
optional user-confirmation provenance, retains revision guards and round-trips
through backup/restore. Dashboard deduplication retains the selected observation
and Excel includes Date confirmation. A later automatic check removes the
manual marker. No actual owner's dates were changed. Live DOM inspection is
not acceptance of an installed updated extension; that remains owner testing.
The app requires new `hr_employment_shapes_revision:1` from its companion.

Check missing dates runs the current dashboard filters, one person at a time,
up to500 people/one hour per explicit click. Progress/Stop and activity indicators
use existing mechanisms. Every result saves immediately, and the next person
uses refreshed ad revisions so shared-ad saves do not conflict. Restarting skips
already dated people; failures retain earlier results and remain eligible.
There is no durable auto-resume or new HR search. An already-started atomic local
save can finish while Stop prevents the next person.

## Unlocked contacts

Company, scan country and Apollo-status filters intersect with text search;
server filtering and Excel match the visible selection. Inputs are bounded and
unknown filter keys/types reject. Source strings remain text and workbook cells
remain literal. Country is explicitly the scan filter, not a verified country.

An explicit per-contact Verify email uses the existing first-party Deep check,
with no new provider or enrichment request. Its address is read-only. Results
remain in page memory across filter/page redraws and clear on reload, without
rewriting Apollo status or contacts. Verification keeps existing SMTP limits,
catch-all/timeout uncertainty and no-mail behaviour. Excel exports Apollo status,
not a new durable verification outcome. A real concurrency regression also
covers a bounded local-read wait instead of overlapping dashboard/card refreshes
returning a normal409 busy error. Paid/account-changing calls retain the
immediate busy gate and are never queued/replayed by that correction.

## JobAdder guidance and confirmed manual recovery

Missing/next fields or buttons receive red outlines and appropriate aria-invalid
state. Existing review/create/critical-write/account boundaries remain. Checking
the previous result no longer depends on edited new-review names, assignments
or company choice. Recovery still checks the original account/email/company.
The documented409 duplicate rejection is treated as a rejected POST rather than
an unknown outcome. The original live response was not retained, so this is not
a claim that409 caused the owner's historical failure.

A credentialed read-only exact-email JobAdder GET returned zero matches. No
real contact, email, account ID, token, raw provider reply or profile is retained
in this report/tests/source. The owner confirmed the contact is absent and
explicitly authorized adding the manual recovery option. No live operation
marker was reset and no live contact POST was sent.

Check previous result now issues a ten-minute proof only after a complete
zero-match read. Only its hash is protected on that account/email's operation.
The user must confirm checking JobAdder and choose Review a new request. The
server rechecks duplicates, validates proof/confirmation/expiry, preserves the
old protected attempt and then permits a fresh Review and separate Create.
Late matches prevent a reset (or confirm the original exact-company contact).
Old/replaced/cross-account proofs cannot resolve another attempt. Up to five
manual recoveries are retained without evicting old history. Recovery itself
sends no contact POST. A late-created record can still cause a duplicate; the
confirmation shows this consequence. No duplicate override is used.

## Domain audit

The Apollo broker's remaining brand-prefix wildcards are replaced by an exact
mailbox-domain list. Corporate lookalikes such as outlook.example or mail.example
are eligible for the existing identity/company/email checks. Known listed
personal-mail domains remain filtered. This is business-email selection policy,
not mailbox validity or an exhaustive provider-domain database. Lead Finder's
separate exact/subdomain-boundary policy is unchanged. Primary references:
- https://support.microsoft.com/en-us/outlook/pop-imap-and-smtp-settings-for-outlook-com
- https://help.yahoo.com/kb/account/identify-domain-extension-yahoo-mail-sln36743.html
- https://api.jobadder.com/v2/docs and its public /v2/openapi.json (contact search,
  company identity and documented409 response).

The hosted Worker remains524; the original corporate Proton fix is already
live, while these additional domain-policy changes need a later authorized
service deployment. No new Apollo lookup, Wrangler login or deployment was
performed in525. Existing negative caches and protected acceptance journals stay.

## Validation and bounds

- Final isolated Windows Python:2231 passed,4 skipped,8418 subtests passed.
- All81 standard JavaScript fixture files pass. Final guidance-specific root
  fixtures and native workflow were rerun after the final guide adjustment.
- New recovery matrix covers explicit confirmation, hashed/replaced/expired/
  cross-account proofs, late matches under either company, a fresh Review/Create,
  previous-attempt retention/non-replay and the history limit. Existing
  unauthorized/stale/restart/ambiguous/duplicate/account tests remain passing.
- Actual Chromium DOM regression covers current/former ranges, grouped
  promotions, overlapping current roles, contained secondment ordering,
  collapsed/foreign/unlinked metadata and month/year precision. No real browser
  profile or LinkedIn network is used by these fixtures.
- Native actual-app test uses an explicitly marked fictional server and
  isolated receipt/SQLite/credential directories. It covers shared-ad bulk saves,
  skip-on-restart, Stop with a late reply, manual date confirmation, contact
  filters/Excel/explicit verifier state, missing/next guidance and a simulated
  lost create followed by confirmed manual recovery and one fresh create.
  Final run has zero page errors and zero HTTP errors; mobile stays within width.
  Provider transports and SMTP are fictional; no owner records or credentials
  are copied into that fixture. The final exported Excel has exactly one matching
  row, the expected scan country/status and no formula cells.
- Tracked-language/MJS syntax, single-source version/repository consistency,
  owner-source/protected-asset preflight, genuine local Windows Antiword and
  Tesseract checks, and24 source-smoke assertions pass. git diff --check clean.
- No genuine macOS, protected colleague build, live updated-extension run,
  real SMTP delivery/accuracy guarantee or new live contact-create claim.

Ignored evidence: runtime/final525_python.log, runtime/final525_js.log,
runtime/final525_static.log and runtime/job-leads525-native/{hr525,manual525,
contacts525,jobadder525,recovery525,mobile525}.jpg plus filtered525.xlsx.
Optional fictional preview: http://127.0.0.1:5097/?module=jobleads&preview=v24.6.525 .
Apply the app and companion update after publication to use the real workflow.
