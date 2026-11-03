# CV Studio v24.6.554 — public-read rate-limit recovery

Source work on `codex/job-public-rate-limit-recovery`, from merged v24.6.553 / PR297.
The associated PR records current CI, review and merge status. Source validation
below preceded publication; no installed-app update was performed.

A public-reader HTTP 429 previously stopped the entire full-ad queue, replacing
its progress with a generic instruction to connect the companion even when it
was already connected. The loader now continues sequential companion reads and
pauses the public fallback. Failed browser reads retain their own summaries and
retry controls; successful rich content remains cached. The status identifies
public reads as paused and the companion as the remaining read path.

The public service shares a process-local cooldown across all ad requests. It
checks that pause before each HTTP request/redirect, honors numeric or HTTP-date
Retry-After (bounded to a safe integer representation), and defaults to five
minutes for absent/invalid values. Long valid cooldowns are not replaced with a
short default. Other windows and later redirects do not repeat public traffic
during the pause. Expiry permits a later requested read; no timer automatically
replays a failed request. Existing slots, deadlines, redirect identity and
credential-free public requests remain unchanged.

The existing error route keeps its status, code, request ID and retryable=false,
adding validated remaining seconds and a Retry-After header. Frontend state
honors the cooldown for background/manual full-ad retries and across Clear/new
searches. Access, changed-ad, cancellation and public-busy failures retain their
existing stop rules. This does not guarantee that every browser layout can be
read; unreadable ads keep their summaries. A process restart resets transient
cooldown state. No durable schema or route inventory changes.

Validation:

- All 95 frontend fixtures pass. Expanded fallback regressions cover mixed
  companion success/failure after a public limit, exactly one public request,
  preserved saved records/cache, manual retries, new searches, malformed timing
  metadata and expiry including long upstream cooldowns.
- 204 focused public-ad, Job Leads/folder/organization/HR, version and composition
  checks pass. New tests cover shared cooldowns, slots remaining free, numeric /
  HTTP-date / invalid / long Retry-After, another window limiting a redirect, and
  safe API timing metadata. One existing pytest deprecation warning remains.
- Chromium against the isolated fictional server confirms public 429 → companion
  capture → later browser failure, preserved rich preview/summaries, continued
  queue and no repeated public request on a manual retry. Reproduce with
  `tests/browser/job_public_rate_limit.py` after starting the existing
  `tests/browser/job_leads_email_composer_server.py` fixture.
- The existing Chromium card/background/focus/scroll/Stop/Clear workflow passes.
  No page errors, unblocked external requests or saved-record changes occurred.
- JavaScript syntax, whitespace and repository consistency pass.

All responses are controlled fixtures. No live LinkedIn, email, JobAdder write,
Apollo or AI provider action was made. LinkedIn's actual restriction is respected;
no alternate accounts, proxy rotation, hidden APIs or repeated public retries
were added.
