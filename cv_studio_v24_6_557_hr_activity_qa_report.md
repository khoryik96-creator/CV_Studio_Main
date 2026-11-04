# CV Studio v24.6.557 — HR panel activity

Local, unmerged source on `codex/job-read-queue-recovery`, including v555/v556.
The single-ad HR people panel uses the same orange pulse as search progress, with
an orange border and warm background. It remains highlighted while a stopped read
settles, then returns to its normal appearance. Successful and failed scans also
clear the highlight. Bulk HR and unrelated busy operations do not activate it.
Reduced motion uses a static orange highlight; Stop remains usable.

Validation: existing HR scan and bulk-HR fixtures pass, including success, held
reads, Stop, failure and cleanup. Five version-source checks, JavaScript syntax,
repository consistency and whitespace checks pass. Chromium with fictional
companion replies verifies computed orange border/animation, enabled Stop,
reduced-motion suppression, mobile wrapping, Stop and failure reset. Screenshot:
`/tmp/cvstudio557/hr-running.png`. No live LinkedIn read or provider mutation.
The complete 96-fixture JavaScript suite passed for the included v556 work;
v557 reruns the affected HR/bulk fixtures. No route/storage/companion behavior
changes beyond generated version stamps. Not pushed, merged or installed.
