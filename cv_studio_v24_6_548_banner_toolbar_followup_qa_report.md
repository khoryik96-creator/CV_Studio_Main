# v24.6.548 — Banner placement, compact toolbar and follow-up email editing

Local branch `codex/email-banner-placement-toolbar`, from merged v24.6.547 / PR292.

## Fixes

- File-picker focus and the async readonly lock could reset the live selection
  to the top. Banner insertion now restores the previously captured editor range,
  appends when no valid range exists, and includes editable lines before/after the
  image with the caret below it. Enter above the banner moves it down normally.
- Later generic action-row CSS overrode the toolbar's flex/min-width rules.
  Specific toolbar and control rules keep the color picker at 30x28px, with
  compact font/size controls and wrapping on mobile.
- The global caret guard applied transparent caret color directly to formatted
  descendants. Editable email text, bold/italic spans and links now show a caret.
- Confirmed sending leaves fields editable without New message. The first edit
  rearms submission with a fresh durable id, preserves recipients/files/body and
  activates unload protection. A fresh explicit confirmation remains mandatory.
  Immediate duplicate clicks and uncertain-result replay remain blocked. Draft
  completion behavior and backend send/consent contracts are unchanged.

## Independent bug test

The reviewer reproduced one P2: banner insertion or paste as the first edit after
confirmed sending triggered input -> follow-up edit transition -> editor lock while
an async mutation was inserting HTML, dropping focus and subsequent typing. The
edit transition now updates the send identity without re-entering an already-held
async lock. Controls stay locked until that operation's existing finally unlocks.

Chromium regressions cover the real file chooser and clipboard paste as the first
post-send edit, active editor focus, immediate typing, and fresh confirmation/id.
The reviewer independently verified both fixes and reported no actionable findings.

## Validation

- 234 relevant backend/architecture/version/Outlook tests passed.
- All 92 frontend fixtures passed on the final full run. An earlier run hit the
  unchanged Apollo broker fixture timing assertion; both its isolated retry and
  the complete rerun passed without broker changes.
- The focused frontend fixture passed; the focused composer fixture covers retained
  fields, new send identity, unsaved follow-up protection and cancelled confirmation.
- Chromium exercised a real file chooser, insertion into an empty editor and
  between existing paragraphs, typing below a banner, Enter/text above it, visible
  carets in nested formatting, desktop/mobile size bounds, and sending an edited
  follow-up in the same composer. Existing template and rich-email flows passed.
- Syntax, whitespace and repository byte/line-ending consistency passed.

Validation used no live email or provider action and did not update the installed
app. These results were recorded before publication/merge. Browser/server fixtures use sample data, fictional Graph calls and
isolated temporary state. Native Outlook rendering/delivery was not tested.
