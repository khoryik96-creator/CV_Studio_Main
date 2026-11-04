# CV Studio v24.6.555 — search activity visuals

Local source on `codex/job-search-running-indicator`, from merged v24.6.554 / PR298.
Not pushed, merged or installed on the owner's machine.

During the main LinkedIn search, the result cards dim and turn grayscale. The
live search progress message has an orange border/dot/fill and a gentle 1.8-second
pulse. Stop remains outside the dimmed region. `aria-busy` identifies the updating
results region while the existing status message remains available to assistive
technology. Existing control locking remains unchanged.

After search discovery finishes, results return to normal. Background full-ad
capture pulses its own progress message and leaves results usable. The initial
companion check and stopping stage show meaningful text immediately. Indicators
clear on completion, Stop cleanup and failures. With reduced-motion preference,
the highlight is static and the dimming transition is disabled.

Validation:

- All 95 frontend fixtures pass in the final serial run. Existing search and
  background fixtures assert busy/activity state and reset; two older DOM mocks
  now support classList. One initial run overlapping Chromium encountered the
  existing Apollo broker timing fixture flake; it passed unchanged in isolation
  and in the final full run.
- Five version-source tests, JavaScript syntax, whitespace and repository
  consistency pass. No backend behavior changed.
- Chromium checks 50 streamed ads while a third page is held, orange animation,
  dimmed results, enabled Stop, normal completion, Stop and failure reset,
  background activity without dimming/locking results, reduced motion and narrow
  screen wrapping. Reproduce with `tests/browser/job_search_activity.py` after
  starting `tests/browser/job_leads_email_composer_server.py`.
- Existing Chromium card/keyboard/focus/scroll/capture/Stop/Clear and public-rate
  limit workflows pass. No page errors or unblocked external browser requests.
- Sample screenshots: `/tmp/cvstudio555/search-running.png` and
  `/tmp/cvstudio555/background-running.png`.

All browser/companion/provider replies are fictional. No live LinkedIn or paid
provider operation, route/storage change or companion behavior change was made.
