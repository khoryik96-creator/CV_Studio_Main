# v24.6.502 — observed LinkedIn layouts and compact Job Leads

Local, unmerged work on `codex/v24.6.502-hr-layout-compact`, based on merged
v501 `b646d8d` / PR #254. The owner requests a compact panel and correction of
repeated HR failures, then adds Sourcer timeouts/one result/missing pagination.

## Confirmed causes and corrections

- Read-only live inspection found the same icon-only Verified job anchor in
  both failed standalone headers. The v499 structural detector rejected every
  title containing an anchor. Allow only the exact current job's named badge;
  keep foreign/textual links, buttons, ambiguous employers and descriptions out.
- The failed company tab was an empty completed document. A read-only reload
  hydrated its company heading and native employee links. Add one inactive,
  unchanged-source reload after twelve passive blank polls, with bounded
  persisted markers and normal exact-company verification after reload.
- Modern People cards contain mutual connections' profile links. The old
  uniqueness guard skipped their primary candidates; occasionally one card
  without mutual links survived. Scope identity to the first name paragraph,
  exclude mutual/sidebar profiles and recognise uniquely scoped native Next.
- Folder/move/HR controls measured 339px rather than 666px at the same desktop
  size, a 49% reduction. Accessible labels, remembered country/pages, folder
  actions, bulk Stop/progress and small-screen wrapping remain.

## Verification

- New Verified-job regression failed before the parser correction. New unit
  cases cover foreign/unnamed/text-bearing badge links, duplicate headings,
  descriptions and conflicting employers.
- Blank-company fixtures cover hydration, suspension, a single reload, active
  takeover, nonblank layouts, access changes, write failure and interrupted
  reloads. Passive reads can continue; no reload, filter or profile mutation
  is replayed.
- Controlled native Chromium runs the real worker/reader through both country
  modes, eleven keywords/three query groups, six pages each, joining-date
  loading, cached identity/rename handling and one blank-document recovery.
- Controlled native People DOM reproduces nested main anchors and mutual links.
  Unmodified v501 loses primary cards and misses Next; the new reader gets all
  ten cards on two pages, excludes sidebar/mutual profiles, retains geography
  and recognises the disabled final Next. No AI calls are needed.
- Actual isolated-app browser checks cover desktop/mobile controls, remembered
  settings, folder editor, repeated/cached HR scans and Stop/activity/save
  preservation using fictional/intercepted responses.
- Full Python suite: 1,956 passed, 4 skipped, 8,416 subtests passed. All 69
  JavaScript fixture files pass; tracked syntax/repository consistency,
  Windows source/native dependency preflight and 24 live source-smoke
  assertions pass. The final additive capability gate was rechecked through
  the complete JavaScript suite, native app and source validation.
- The new blank-company test fails against the unmodified v501 worker; the
  current implementation passes it. `hr_layout_revision:1` is additive to
  existing capabilities, so the updated companion remains compatible with
  older CV Studio pages while new pages reject an outdated reader.

## Boundaries and practical limits

No live AI/mail/provider/outreach calls, new permissions, saved-record migration,
route/schema changes, owner installation changes or protected build. Browser
inspection read the reported pages only; no live HR queue was run or saved.
Capability gates require the updated companion before scan/paid work. LinkedIn
access restrictions, missing identity and unknown nonblank layouts remain
explicit stops; a single reload cannot guarantee every network failure recovers.
