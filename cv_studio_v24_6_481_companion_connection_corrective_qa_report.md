# Companion connection corrective — v24.6.481

Owner authorized correcting both v480 review findings and then merging. Continue
`codex/v24.6.480-companion-easy-updates` from local v480 `738b68c`, retaining all
automatic connection and bundled-folder update work based on merged master
`065e75e8890e9f126196f811ef809eab237f39e4` (v479). Merge evidence belongs to the
final PR and coordination issue #35 after exact-head checks/review complete.

## Corrections

1. **Connection before load completion.** Chrome may inject document_idle while
   the tab still reports loading. The worker keeps its complete-status guard,
   but sends a bounded readiness notification when the current local root tab
   completes, only to its top-level content script. The trusted extension
   notification waits for a previous handshake to settle before a fresh attempt.
   This cannot coalesce into the original loading rejection. Closed, replaced,
   nonlocal, wrong-path and pending-navigation tabs gain no authority. No search,
   navigation, read, write or paid action is replayed by connection recovery.
2. **Search ownership during paid planning.** The real controller now reserves
   its existing worker run before sending the planning request. Another CV Studio
   tab becoming visible cannot steal an already-preparing search. Later browser
   steps reuse that same run, preserving limits; reservation failure or Stop
   before acknowledgement sends no paid plan. Late successful acknowledgement
   after Stop is cleaned up by the existing end/finally path. Already-sent paid
   responses retain existing accounting and non-replay behavior.

The v480 setup and local-file update flow remains; no forced page refresh,
browser-profile write, extra permission, route or persistence schema was added.
Ordinary app/document verification, active-capture/HR protection, profile
ownership, ad imports, duplicate safety, folders, saved content and cancellation
remain under existing regressions. No live LinkedIn or paid provider calls were
used, and no owner installation/receipt/record/browser state was changed.

## Verification

- New worker/content completion regressions and pre-plan controller regression
  failed on v480 before production changes. All pass after correction.
- Additional tests cover completion after an in-flight rejection, forged ready
  messages, nonlocal/wrong-path/pending destinations, one reservation per run,
  reservation failure and Stop during reservation with late acknowledgement.
- Full isolated Windows Python: **1,777 passed, 4 skipped, 8,392 subtests**, in
  **131.96 seconds**. **All 47 JavaScript suites passed**. Tracked-language
  syntax, repository consistency, whitespace, owner-source/native dependency
  preflight and **24 source-smoke assertions passed**.
- Actual isolated Chromium exercised a delayed image so document_idle connected
  while loading. The initial attempt retained no authority; releasing the image
  produced automatic connection from the completion event, without any app RPC
  or tab switch. Its disposable worker included passive counters/diagnostics.
- Repeated native checks caught a Chrome trial with no tab-complete notification.
  The correction therefore also observes the document load event and allows at
  most 20 handshake-only retries 250 ms apart for the worker's explicit
  same-URL loading hint. Foreign/pending-other-URL requests get no retry hint;
  pagehide cancels recovery. Focused tests prove success stops polling, missing
  completion notifications recover, and the ceiling prevents indefinite work.
- The actual frontend/controller and companion also held a simulated plan
  response while a second app tab became active. The original worker run and
  document retained ownership, and Stop released it without another plan call.
  LinkedIn URLs were intercepted with offline fixture pages; provider responses
  were simulated and no external provider request was sent.
- After the final load-event fallback, **10 consecutive isolated native browser
  cycles passed both cold-load recovery and planning ownership/Stop checks**.
- The final v481 bundle also passed the actual local-file update/reload and full
  browser-restart reconnection checks, with the draft retained until an explicit
  page refresh. Only a disposable manifest was advanced to a synthetic version.

No protected package or native macOS build is claimed. The five guards, route
seal, main SQLite schema 10, job journal schema 1 and Job Leads schema 2 remain.
