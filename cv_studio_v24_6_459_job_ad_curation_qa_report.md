# CV Studio v24.6.459 — ad preview and direct LinkedIn capture

Historical QA record; root `VERSION` is the current release reference.

Owner requested both curation inside CV Studio and Add to CV Studio buttons
on LinkedIn, replacing the need to copy job URLs individually. Branch
`codex/v24.6.459-job-ad-curation` starts from merged v458 `f807c08` / PR #230.

## Result and confirmed search failure

Job Leads now shows a side-by-side ad preview, with full-read and single-ad
save actions. Checkbox selections still support bulk import into the chosen
folder. Saved/duplicate states and summary/full-content/excerpt labels remain.

The companion adds direct-add controls to recognized visible Jobs cards and
loaded job-view pages. Real clicks re-read the visible ad, verify source and
bound destination documents, and forward it through the local content bridge
to the initialized Job Leads controller. That controller uses its established
guarded duplicate-safe save and keeps the manual draft intact. No direct
extension-origin HTTP exception or LinkedIn Save/Apply/message action exists.

Read-only inspection of the actual owner v458 screen found zero discoveries
and the generic browser-action error. Its SAP FICO/Malaysia search opened a
modern search URL containing keywords but no location query parameter. The
rendered search header still showed Malaysia. The previous exact key check
therefore rejected the normalized URL before any result read.

A new-search-only initial handshake accepts a resolved location/geo identity
only with unchanged keywords/non-location filters and a recognized rendered
location matching the request. Unloaded location waits; conflicting location
or changed keywords rejects. Once settled, filters remain pinned across all
later reads and worker suspension. Existing open-search mode is unchanged.

## Verification

Performed on Windows x64 on 20 October 2026 with isolated receipts/state.

- Full unfiltered Python suite: **1,737 passed, four skipped, 7,599 subtests
  passed**, 157.06 seconds.
- **All 41 JavaScript suites passed.** New content/worker suites cover trusted
  clicks, duplicate UI installation, exact app/document/channel authority,
  top-frame/host/identity checks, concurrent/busy operations, replaced app
  documents and timeout non-replay. Existing lifecycle/profile/batch/CV suites
  remain passing.
- Worker/search fixtures verify normalized initial URLs, delayed/ambiguous/
  wrong locations, changed keywords, suspension and later filter revocation.
  Modern reader tests cover rendered location context, observed direct-add
  targets and excluding injected control labels from saved content.
- Controller tests verify preview selection, single save without importing
  other checked rows, folder-specific direct capture, duplicate preservation,
  rejected URLs/storage failures and unchanged manual notes.
- Tracked/new Python/JavaScript syntax, PowerShell/POSIX shell syntax,
  repository consistency, whitespace checks, owner-source preflight and
  **24 source smoke assertions passed**. Actual bundled Windows Antiword
  and Tesseract functional/English-data checks passed; no native macOS or
  protected-compilation claim. The final bounded collection-ad target addition
  passed its focused modern reader and syntax checks afterward.
- Actual isolated browser UI with sample data and a simulated extension
  transport verified three discovered ads, full semantic content in the new
  preview and saving one previewed ad. A second local sample Jobs page ran the
  actual reader/content-button code; a trusted click passed through the actual
  Job Leads capture receiver and backend save, showed Added/Priority Finance,
  updated the saved list and left the manual draft note intact. The service
  worker authority boundary is covered separately by the focused VM tests.
  Screenshots remain in ignored runtime; owner data was not used as fixtures.
- Persistent source preview 5074 reports v24.6.459. Read-only before/after
  SQL value hashes prove its two saved lead rows are exactly unchanged. It had
  no active sourcing run when restarted. Earlier draft tabs were preserved;
  the installed port-5000 app and its authorization were not changed.

## Boundaries and limits

The same four companion files, existing host permissions, 120-route seal,
five guards, schemas and provider boundaries remain. The manifest adds a
Jobs-only content-script match within its already-authorized LinkedIn host.
No paid call, remote LinkedIn mutation, owner saved-record mutation, installed
app update, protected compilation, push, PR or merge is part of this checkpoint.

Live owner browser inspection was read-only. An installed-companion end-to-end
run remains unverified; synthetic transport is not claimed as that live test.
Users need the new app/companion files, Reload, both pages refreshed, Job Leads
open in the connected app tab and reconnection from its toolbar icon.
