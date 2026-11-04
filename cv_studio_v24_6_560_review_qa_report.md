# CV Studio v24.6.560 — combined review and validation

Source: `codex/job-read-queue-recovery`, based on merged v24.6.554 / PR298.
The associated pull request records current CI, external review and merge status.
Includes the v555–559 full-ad recovery/cache and activity/failure visual changes.

Local review found two reproducible UI-state defects and fixed both:

1. A background preflight failure kept the search/loading status red even after
   manual reads recovered every full ad. Terminal failure styling now requires
   remaining unread content. Current per-ad errors remain visible when relevant.
2. An individual HR failure stayed red after a later bulk scan saved that ad
   successfully. Confirmed scanned/copied bulk results clear that ad's old error.
   Failed scans or abnormal cleanup still require attention.

Both regression cases failed on the prior source and pass with the corrections.
No saved record, queue decision, provider call, authorization, ownership or
cleanup rule changes. VERSION was advanced through bump_version.py.

Combined validation is recorded in the pull request. The included v559 source
passed all 96 JavaScript fixtures and fictional Chromium activity/failure/retry
checks; this review reruns those checks on the final source. No live LinkedIn,
paid provider call, email send or installed update is involved. Both app and
companion updates are needed for the committed-document reader improvement.
