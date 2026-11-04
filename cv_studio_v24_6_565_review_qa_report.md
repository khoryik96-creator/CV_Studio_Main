# CV Studio v24.6.565 — recovery and notifications review

Source on `codex/full-ad-recovery-browser-badges`, based on merged563 / PR300.
Includes v564 full-ad recovery and browser title/favicon completion indicators.
The associated pull request records current CI, external review and merge state.

Local review found two reproducible defects and corrected both:

1. JobPosting identifiers encoded as LinkedIn job URLs or URNs were treated as
   opaque strings. A conflicting explicit ID could be accepted under a canonical
   page URL. Normalize supported references before checking identity in the public
   and companion readers. Unsupported URI identifiers do not gain authority from
   canonical metadata. Existing matched numeric/opaque canonical identifiers and
   matching URL/URN forms remain readable.
2. The new focused completion indicators remained after Clear. Shared targeted
   acknowledgement now clears only that feature's completed/failed notification
   and idle state. Active work and other features' notifications remain. Job Leads
   clears after stopping its background queue, so a late read cannot leave Done
   for discarded results.

Both conflicting-reference regressions failed on prior code, and the Chromium
Clear assertion failed before the correction. New checks pass after the fixes.
Chromium covers all three modules' Done/Failed, successful retry, normal
acknowledgement, Clear with another pending module, and Clear during a held job
capture. Existing cache/queue recovery remains intact. Backend tests cover matching
and conflicting URL/URN identities along with the included guest endpoint bounds,
access, canonical identity, cooldown, size/type and deadline checks.

Local verification: all 98 JavaScript fixtures and 134 focused Python checks
passed, as did repository consistency, syntax/whitespace checks, and Chromium
recovery/badge and queue-recovery workflows. CI and external review are recorded
in the associated PR. Native signed-in
LinkedIn contents remain unavailable here; browser fixtures use fictional content
and all provider/verifier/companion replies are synthetic. No live provider action,
email send, route/storage schema or permission change. Both app and companion
updates are required for the complete behavior.
