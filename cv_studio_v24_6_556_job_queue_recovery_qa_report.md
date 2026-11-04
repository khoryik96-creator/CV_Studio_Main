# CV Studio v24.6.556 — full-ad queue recovery

Local source on `codex/job-read-queue-recovery`, from unmerged v24.6.555 / commit
120e58e and merged v24.6.554 / PR298. Includes the orange activity indicators and
dimmed main-search results from v555. Not pushed, merged or installed.

The reported screenshot showed the first ad failing with a browser-loading
message, all remaining ads left unread, and a complete saved description already
visible. The worker waited for Chrome's entire load event, even if the ad DOM was
ready. Its outer loading timeout also lacked the per-ad error code, stopping the
queue instead of trying the existing fallback and moving on.

Full-ad reads can now inspect the exact committed job document while its unrelated
resources load. Both script injection stages request immediate execution. Known
transient frame/context disappearance is retried as a bounded passive observation
on the same URL; navigation is never replayed. Pending navigation, access pages,
job identity, cancellation, connection and user-tab ownership remain checked.
HR company-only capture still requires complete loading and stable employer
observations. Existing DOM parsing and full-body/identity validation are retained.

The outer timeout is classified HR_AD_TIMEOUT. The frontend recognizes only the
exact known no-code timeout from older companions, so the existing public fallback
and queue continuation also work before the companion is updated. Other arbitrary
errors, access restrictions and disconnection retain their stop behavior. Public
cooldown, cancellation and no-replay handling are unchanged.

Exact-URL saved ads count as ready when non-deleted, explicitly non-truncated and
nonempty. Their rich body is reused without a browser read. Unknown flags,
excerpts, empty content and trash do not count. This is checked during discovery,
queue startup and before each queued read. Saved-content labels distinguish reused
content from fresh captures. Saved records and editing drafts are not overwritten.

Validation:

- All 96 JavaScript fixtures pass in the final serial run. New and extended
  regressions cover committed/loading reads, immediate injection, pending
  navigation, stricter HR readiness, bounded transient-context recovery, typed
  timeout, legacy fallback/continuation, saved-rich reuse/readiness, excluded
  incomplete/trash records, all-saved results and absence of durable writes.
- Five version-source tests, JavaScript syntax, whitespace and repository
  consistency pass. No Python behavior or route/storage schema changed.
- `tests/browser/job_read_queue_recovery.py` uses real Chromium and the real DOM
  reader against intercepted fictional HTML. A held image keeps document loading
  while a complete rich ad reads successfully. A separate fixture reuses saved
  rich content, fails the next ad with the old no-code error and an unavailable
  public fallback, then completes the following ad: 2/3 ready, one failed, no
  redundant saved-ad capture, one public request, no record writes/page errors.
- Existing Chromium `job_ads_background.py` and `job_search_activity.py` checks pass
  for card clicks, keyboard/focus/scroll, captures/Stop/Clear, orange activity,
  dimmed discovery, cleanup, reduced motion and mobile wrapping.
- An initial JavaScript run overlapping Chromium hit the existing Apollo broker
  timing fixture failure; it passed unchanged in isolation. Final serial result
  is recorded above; no unrelated broker code changed.

All browser/companion/public replies are fictional. The owner's live signed-in
LinkedIn DOM was not reproduced, so these checks do not promise every ad will
load. Apply both the app and companion update for the worker readiness change;
frontend timeout compatibility and saved-content reuse need the app update.
