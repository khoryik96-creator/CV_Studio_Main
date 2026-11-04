# CV Studio v24.6.563 — captured-tab cleanup and review

Local source on `codex/browser-tab-grouping`, includes unmerged v561/v562.

Full-ad reads accepted path-only LinkedIn job aliases, including trailing slash
and SEO/title paths, while exact cleanup matching rejected them. These same-job
aliases now retain ownership for normal cleanup. Queries, fragments and changed
job IDs remain outside this normalization. User-activated/viewed and pre-existing
tabs stay protected. Successful/background captures close their created tabs.

Current Sourcer readProfile requests set close_after_read. Only successful,
non-loading, nonempty exact-profile reads close/release their background tab and
return profile_tab_released. The controller clears its reused-tab reference before
AI detail review and creates a fresh tab for the next observed profile. Viewed
profiles are released without closing. Loading responses remain open to poll.
Older callers/companions retain their reuse/End behavior. Search result tabs are
still available; this change closes captured ad/profile detail tabs.

A failed native remove retains exact ownership for a later normal cleanup retry.
Saved evidence, paid-call counts/consent, source/tab identity, navigation/closure
authority and non-replay behavior are unchanged.

Independent review of v561/v562 found one P2: sessionChrome.create awaited app
window metadata without rechecking a completed End/Stop. The binding/run/capture
snapshot is now revalidated after that await, immediately before native creation.
The original reproduction changed from one post-End tab to zero. Cancellation
of a single-ad capture during that lookup also produces zero new tabs.
Independent follow-up review of the fixes and capture changes found no additional
findings; the reviewer changed no files.

Validation:

- Real-worker/core capture fixture closes both observed profiles before the
  single AI detail-review call, opens fresh subsequent profiles, preserves viewed,
  changed/incomplete/user tabs and legacy behavior, and retries a transient close
  at End. Path-alias and Stop/cancel regressions cover the identified issues.
- Nineteen version/Sourcer Python tests, syntax, whitespace and repository
  consistency pass. All 98 JavaScript fixtures pass in the final serial run.
  Existing concurrent scans, lifecycle and viewed-tab
  protection checks pass.
- Native extension loading remains blocked by the managed browser's administrator
  (as recorded in v562); actual native tab-strip behavior remains unverified.
  All companion/provider replies are fictional. No live LinkedIn/provider call,
  email send, backend route/schema change, push, merge or installed update.

Apply both CV Studio and the companion update for immediate Sourcer capture
cleanup and the worker alias/Stop corrections.
