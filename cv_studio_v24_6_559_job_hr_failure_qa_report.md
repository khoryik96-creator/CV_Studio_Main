# CV Studio v24.6.559 — Job Leads and HR failure highlights

Local unmerged source on `codex/job-read-queue-recovery`, including v555–558.
Uses Sourcer's static red outline and warm error tint for the Job Leads search
panel and single-ad HR panel. Existing error messages provide the explanation.

Job discovery failure marks the search panel red until a new valid search or
Clear. Full-ad background failures mark the search panel and loading status red
once the queue settles, including partial failures and failed preflight. While
the queue is active its progress remains orange. Successful retries clear failed
ad flags through the existing capture path; new background attempts clear failed
preflight state. Clear resets the search/description and current HR error state.

A failed single-ad HR scan or abnormal cleanup marks its current HR panel red.
Retry and selecting another ad clear it, so a different employer cannot inherit
the failed scan's highlight. HR queue progress turns red for partial failures or
an abnormal stopped reason and resets on a new queue. Intentional Stop without
an actual failure remains neutral. Error flags are ephemeral and do not change
saved records, checkpoints, provider calls, queue decisions or consent gates.

Validation:

- All 96 JavaScript fixtures pass in the final serial run. Existing search,
  background, HR and bulk-HR fixtures assert failed outlines, successful retry,
  success and intentional Stop behavior while retaining prior workflow checks.
- Five version-source tests, JavaScript syntax, repository consistency and
  whitespace checks pass. No Python behavior or companion logic changes.
- Actual Chromium with fictional companion replies confirms red computed borders
  for failed discovery and HR scans, successful job-search retry and Clear,
  immediate HR retry reset, orange running state, enabled Stop, normal Stop
  cleanup, reduced-motion handling and mobile fit. No page errors or live reads.
  Temporary check scripts: `/tmp/check_job_failure559.py` and
  `/tmp/check_hr_failure559.py`; screenshots under `/tmp/cvstudio559`.

No push, merge, installed update or live provider action. Included v556 changes
still require both app and companion updates for improved full-ad readiness.
