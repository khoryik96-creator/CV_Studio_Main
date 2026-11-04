# CV Studio v24.6.564 — ad recovery and browser completion badges

Local source on `codex/full-ad-recovery-browser-badges`, from merged563 / PR300.
The owner supplied job4456899159 and confirmed several failures load manually.
This environment cannot inspect that signed-in browser page; fixtures use the
same numeric URL with explicitly fictional content. No live-site fix is claimed
as reproduced against the owner's current DOM.

Full-ad recovery:

- Existing visible DOM parsing remains first. Modern exact-job components now
  work under a semantic main element without requiring its old workspace id.
- A standalone job whose DOM remains unrecognized can use embedded JobPosting
  data. Exact URL/ID or a single canonical posting binds identity; readable role,
  employer and description are required. Conflicting metadata, other IDs, visible
  access/captcha checks and ambiguous postings reject. HR company-only reads keep
  their DOM employer checks. Inert template content prevents metadata resources
  from being loaded while extracting text. Rich markup still passes through the
  existing server formatter before presentation; source dates retain their day.
- After an ordinary public 200 document lacks supported ad markup/body, try one
  exact jobs-guest/jobs/api/jobPosting/<id> endpoint. Its transport path establishes
  fragment identity, with conflicting canonical metadata still rejected. Redirects
  are not followed there. Primary access, invalid redirects, bad types/size,
  transport errors, captcha/sign-in or rate-limit responses do not trigger it.
  Both stages share the existing time budget, size cap, semaphore, no-credential
  transport and cross-ad public cooldown. No added paid search or AI request.

Browser notifications:

- Sourcer previously called finishTabRun directly and skipped the notifier.
  Sourcer, Job Leads and Email Verifier now use the existing Done/Failed browser
  title/favicon path with focused completion enabled.
- Discovery starts background-loading activity before retiring its own token,
  so the browser does not announce Done before all full-ad attempts finish.
  Standalone loading/retries and manual reads have their own balanced tokens.
- Fresh runs optionally acknowledge only their own previous completion/failure
  when no nested run is active. Successful retry removes stale red status while
  retaining other modules' unread results. Existing tab-click/focus acknowledgement
  and other modules' default behavior remain in place.

Validation:

- Public parser/transport tests exercise unsupported/empty-body recovery,
  exact guest URL and rich content, prior response closure, identity/access/no
  redirect boundaries, shared 429 cooldown, type/size caps and deadline expiry.
- Actual Chromium runs the real reader against fictional embedded metadata and
  checks mismatched IDs/URLs, conflicting postings, date preservation, HR and
  captcha/sign-in boundaries. The real local UI/controller/status code confirms
  focused Done/Failed title/favicon updates for all three modules, one final
  Job Leads notification after three background reads, acknowledgement and
  successful retry preserving another module's completion. All browser requests
  are local or intercepted; verifier/AI/companion replies are fictional.
  Reproduce with tests/browser/job_ad_recovery_badges.py after starting the isolated
  job_leads_email_composer_server.py fixture.
- Existing Chromium loading-document/cache/queue, orange-activity/mobile and
  public-rate-limit workflows pass. No page errors or live provider mutations.
- All 98 JavaScript fixtures pass in the final serial run. All 130 focused public
  reader, saved-ad/markup and version checks pass. JavaScript/Python syntax,
  whitespace and repository consistency pass.

No route/storage schema or extension permission changes. Apply both app and
companion updates. No push, merge, installed update or live LinkedIn/paid action.
