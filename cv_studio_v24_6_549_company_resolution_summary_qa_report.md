# v24.6.549 — Company-header evidence and pull summary

Local branch `codex/client-company-resolution-summary`, from master v24.6.548.
User report: a repeat pull showed zero ads found alongside 31 new to review and
an unresolved company id for the supplied Lear Corporation company-page URL.

## Confirmed causes and changes

The summary's ads-found counter actually counted new queue additions this run,
while new-to-review counted every unsaved queued ad, including earlier pulls.
It now labels those quantities and reports retained unsaved entries explicitly.
A repeated 31-ad pull with one unresolved second client reproduces the old
confusing numbers and verifies the clearer summary without clearing the queue.

The Jobs reader accepted fewer visible company-header link formats than the HR
reader. The shared helper preserves all old HR evidence rules and makes its
corroborated connections-link fallback available to Jobs. HTTP-valued links are
parsed only, never requested or followed, and need a matching visible HTTPS
associated-members group plus exact native origin/network filter evidence.
Groups alone cannot select one company, and conflicting ids remain errors.
No company id was guessed or hard-coded from the user's supplied company name.

## Validation

- 128 relevant JobAdder clients, Job Leads and version tests passed.
- All 92 frontend fixtures passed, including HR identity/filter tests and company
  Jobs worker authority, cancellation, redirect, bounded polling and cleanup tests.
- Added Jobs reader tests cover positive corroboration and negative absent/wrong
  group, missing network evidence, group-only ambiguity and conflicting job ids.
- Queue regressions verify repeated pulls, retained entries, per-run counts and
  an unresolved second company. Existing Stop/full-list/save/account cases pass.
- Syntax, whitespace and repository byte/line-ending checks passed.

The exact authenticated Lear page could not be observed here. This evidence
confirms the parser gap and summary behavior, but does not prove Lear now resolves
in the owner's browser. No live browser/account action, LinkedIn access, paid call,
push, merge or installed-app/extension update was performed. Deploying the fix
requires the app update and updating/reloading the browser companion.
