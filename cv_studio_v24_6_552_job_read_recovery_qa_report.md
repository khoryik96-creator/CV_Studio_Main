# CV Studio v24.6.552 — company and full-ad read recovery

Branch `codex/company-jobs-button-resolution`, based on merged v24.6.551 / PR295.

## Company-number recovery

The old reader could parse an existing company-filter link but could not perform
the “See all jobs” action its error recommended. The companion now checks passive
ID evidence first, then permits one native action in its own unchanged, inactive
company Jobs tab. It accepts only a stable resulting job search with one numeric
`f_C` filter. The source page remains authority; no company ID is guessed.

The reader checks visible/native or aria-labeled controls, rejects ambiguous,
disabled, hidden, foreign-employer and unsafe-link controls, and rechecks before
clicking. The worker retains scoped authority, cancellation, access checks,
ownership protection and bounded polling. It never repeats the action. A tab
taken over by the user is preserved. Distinct failures replace the generic
number-not-found message after an incomplete action.

`company_jobs_action_revision:1` identifies this behavior. Resolving an unknown
named company asks for a companion update if it is missing; already-known exact
IDs continue to work.

## Full-ad recovery

Manual and background full-ad reads use the existing public lookup once after a
recognized companion layout/empty-content/timeout failure. Successful content
must match the exact job URL and include company, role and a readable description.
Rich formatting and cached previews remain available; saved ads and drafts are
not overwritten. Access, cancellation, changed-ad and connection failures never
trigger this fallback. Public busy/rate-limit errors pause the queue without
replaying requests. Stop aborts the pending browser request and rejects late
results; the bounded server reader may still finish its own read.

## Validation and limits

- All 95 frontend fixtures pass, including expanded company reader/worker and
  client capability tests and the new full-content fallback fixture.
- 192 relevant public-ad, Job Leads/folder/organization/HR, version and composition
  tests pass under isolated paths. One existing pytest deprecation warning.
- Chromium tests native and aria-labeled company Jobs buttons, rejected hidden /
  ambiguous / other-employer actions, and actual same-tab filter navigation on
  intercepted fictional pages. Reproduce with `tests/browser/company_jobs_button.py`.
- Chromium also verifies companion timeout → one exact-URL public lookup → rich
  cached preview, followed by Stop with preserved content, against the isolated
  existing fixture. No external browser requests or page errors occurred.
- JavaScript syntax, repository consistency and whitespace checks pass.

Reported URLs are `https://www.linkedin.com/company/lear-corporation/`,
`https://www.linkedin.com/jobs/view/4437968792/` and
`https://www.linkedin.com/jobs/view/4373530413/`. The user confirmed the second
description is visible in their browser. Public web views expose descriptions
for the two job URLs; one redirected to LinkedIn's Malaysian public site. This
does not reproduce the user's authenticated DOM. Direct requests through the
existing public reader in this cloud environment returned `JOB_AD_UNAVAILABLE`.
Therefore live success for Lear or either ad on the owner's installation is not
claimed. The implemented recovery paths are verified with controlled responses.

No routes, schemas, credentials or provider/paid-call boundaries change. No live
email, JobAdder write or paid provider action was made. Both app and companion
need updating to use the company-action recovery.
