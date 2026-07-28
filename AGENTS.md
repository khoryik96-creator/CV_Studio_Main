# CV Studio Codex Rules

## Completed release

- Phase 2A migration source baseline: **CV Studio v24.6.217**.
- v24.6.217 baseline owner ZIP SHA-256:
  `c499ea8043f274bf47a4981c84794759f38fc7c761b98ba3939626114a898a59`
- Phase 2A was completed in v24.6.218 and its five post-release review findings were corrected in **CV Studio v24.6.219**.
- Phase 2B browser-backed durable records and selected settings were completed
  in **CV Studio v24.6.220**.
- Its three post-release review findings were corrected in **CV Studio
  v24.6.221** without changing schema version 10 or the Phase 2B scope.
- Two remaining review findings were corrected in **CV Studio v24.6.222**:
  local-data restore now fails visibly when any requested durable write fails,
  and browser-setting routes reject values the repository cannot persist.
- Shared JobAdder, Microsoft Graph and AI-provider client foundations were
  completed in **CV Studio v24.6.223** without changing route or storage schema
  contracts.
- Their five post-release review findings were corrected in **CV Studio
  v24.6.224**: redirect targets and cleanup are enforced, response headers keep
  case-insensitive semantics, diagnostic network failures retain their legacy
  fields, and the correction has its own immutable release identity.
- The confirmed JobAdder raw-request content-negotiation regression was
  corrected in **CV Studio v24.6.230**: JSON requests retain their default
  `Accept: application/json`, while binary downloads remain
  representation-neutral and caller-supplied Accept headers are honored.
- Gradual behavior-preserving backend modularisation was completed in **CV
  Studio v24.6.231** with three bounded app-independent modules.
- Its three post-release compatibility findings were corrected in **CV Studio
  v24.6.232**: storage and diagnostics dependencies again resolve through
  app-level compatibility globals at call time, and document safety again uses
  the established app limits, nested helpers and OCR semaphore.
- Persistent background jobs and resumable task state were completed in **CV
  Studio v24.6.233** for the existing safe AI Crawler preview-prefetch
  boundary.
- Its ten post-release persistence-boundary findings were corrected in **CV
  Studio v24.6.234** without changing schema version 10, routes, security
  boundaries or the authorized Phase 5A integration.
- Central AI cost guardrails and provider-billing reconciliation were completed
  in **CV Studio v24.6.235** without changing routes, security gates, storage
  schemas, provider retry/non-replay behavior or Phase 5A journal semantics.
- Its post-release guardrail, usage-validation, reconciliation, precision,
  redaction and paid-boundary findings were corrected in **CV Studio
  v24.6.236** without changing any preserved Phase 5B contract.
- The JobAdder candidate-not-found dialog and upload-queue `esc2` scope
  regression were corrected in **CV Studio v24.6.237** without changing
  JobAdder routes, requests, candidate creation, uploads or response contracts.
- The duplicated standalone Blind JD experience summary was removed from the
  browser preview, Word export and PDF export in **CV Studio v24.6.238**.
  `exp_range`, the AI prompt/output schema and recruiter-critical body content
  remain unchanged.
- The Blind JD PDF header metadata and long Location/Work tile text were
  corrected to wrap within the available page width in **CV Studio
  v24.6.239** without changing any Blind JD data or content.
- Current completed private owner/source release: **CV Studio v24.6.239**.
- Phases 1, 2A, 2B, 3, 4, 5A and 5B are complete.
- Phase 6 remains inactive. There is no active implementation target.

## Completed scope: post-Phase-5B Blind JD PDF metadata-overflow corrective

v24.6.239 wraps the first-page Blind JD PDF metadata summary within the
available header width and wraps long Location/Work values within their padded
tiles. Present metadata tiles retain the complete 174 mm content width, the
established 4 mm gap and a shared calculated height.

The v24.6.238 standalone experience-summary removal remains unchanged.
Structured `exp_range`, the AI prompt/output schema, preview, Word export,
requirements, nice-to-have items and all recruiter-critical body content remain
unchanged.

Focused regression coverage uses the exact long Work Arrangement from the
owner-supplied PDF and proves both header and tile lines stay inside their
right content edges. Real jsPDF export plus Poppler rendering confirms the
corrected layout visually.

This correction preserves all 107 routes, five guards, 18 compatibility
signatures, SQLite schema 10, Phase 5A journal schema 1, the v24.6.237 `esc2`
and v24.6.238 Blind JD experience-summary corrections, every Phase 1–5B
contract and the Phase 6 stop boundary.

## Completed scope: post-Phase-5B Blind JD display/export corrective

v24.6.238 removes only the duplicated standalone `exp_range` summary from
`renderAnonJDCard()`, `exportAnonJDDoc()` and `exportAnonJDPDF()`.

The PDF renders the remaining Location and Work tiles across the full available
metadata width. The source JD, AI prompt, structured Blind JD object/schema,
requirements, nice-to-have items and all recruiter-critical body content remain
unchanged.

Focused regression coverage proves the three omissions, retained body
experience requirements, retained structured `exp_range`, Location/Work
rendering, output escaping and unchanged unrelated Blind JD sections.

This correction preserves all 107 routes, five guards, 18 compatibility
signatures, SQLite schema 10, Phase 5A journal schema 1, the v24.6.237 `esc2`
correction, every Phase 1–5B contract and the Phase 6 stop boundary.

## Completed scope: post-Phase-5B JobAdder esc2 corrective

v24.6.237 replaces only the three invalid out-of-scope `esc2` calls in
`showJADialog()` and `renderJAUploadList()` with the established global `esc()`
helper. The upload renderer's local ID variable was renamed because it shadowed
global `esc`; its value and uses are otherwise unchanged.

The valid locally scoped `esc2` helpers inside `renderAnonJDCard()` and
`renderCompanyCard()` remain unchanged. A source-scope regression requires
every `esc2` definition and call to remain inside those two renderers. No global
alias was added.

This correction preserves all 107 routes, five guards, 18 compatibility
signatures, SQLite schema 10, Phase 5A journal schema 1, every Phase 1–5B
contract and the Phase 6 stop boundary.

## Completed scope: Phase 5B

Phase 5B added the app-independent `cvstudio_ai_costs.py` foundation for
provider-neutral usage normalization, existing-rate estimates, an opt-in
per-request cost ceiling and strict reconciliation with explicitly
authoritative provider billing data.

Standard Anthropic, DeepSeek and OpenAI inference responses provide usage, not
invoice-authoritative per-call cost. CV Studio therefore labels the established
numeric `cost` as a local estimate, keeps missing authority nullable and
failure-visible, and never converts missing billing into zero or authoritative
cost. Tavily/SerpAPI/Apollo billing remains separate and explicitly unavailable
when those provider responses supply no authoritative amount.

The v24.6.236 corrective release makes missing/partial usage, delayed/partial
billing, malformed or over-precise authority, multi-call coverage and
duplicate-record ambiguity explicit. Exact authoritative decimal text is
retained beside compatible numeric fields, and successful paid output is never
discarded because its billing envelope is malformed.

`CVSTUDIO_AI_MAX_ESTIMATED_REQUEST_USD` is disabled when unset. When configured,
the central compatibility adapters conservatively evaluate the request before
provider transport. Invalid limits and requests over the ceiling fail visibly;
no paid request is automatically replayed.

Phase 5B preserves:

- all 107 Flask routes, methods, endpoint names and established response
  fields;
- all five ordered request/security guards and every authentication, CSRF,
  request-size and paid-call confirmation boundary;
- all 18 compatibility helper signatures, Phase 4 call-time dependency
  rebinding and established initialization order;
- SQLite schema version 10 and Phase 5A journal metadata schema 1, lifecycle
  states and non-replay guarantees;
- Phase 3 provider endpoints, headers, retries, timeouts and the rule that
  ambiguous paid operations are never automatically replayed;
- the v24.6.215 DeepSeek detailed-cost history cutoff, redaction boundaries and
  existing protected credential stores.

Changing any preserved schema, data authority, Phase 5A journal semantics,
paid confirmation gate, provider retry/non-replay behavior, response contract
or recovery semantics requires separate explicit owner authorization.

## Completed scope: Phase 5A

Phase 5A added an app-independent bounded atomic JSON lifecycle journal,
separate from schema-10 SQLite. It tracks only the existing safe, idempotent AI
Crawler preview-prefetch request boundary. No new Flask route, worker, frontend
workflow or result store was introduced.

The journal stores opaque identities/request correlations and bounded lifecycle,
progress, attempt and recovery metadata. Candidate identifiers, credentials,
document/profile content, results and private paths are excluded. Startup
reconciliation never executes work: safe interrupted reads wait for an explicit
identical request, cancellation closes, and paid/externally mutating ambiguity
is non-retryable and requires review.

Phase 5A preserves:

- all 107 Flask routes, methods, endpoint names and established response fields;
- all five ordered global request/security guards and every authentication,
  CSRF, request-size and paid-call confirmation boundary;
- all 18 compatibility helper signatures, Phase 4 call-time dependency
  rebinding and established initialization order;
- request-ID propagation, structured errors and redaction;
- SQLite schema version 10 and every Phase 1–4 storage, client and
  modularisation contract;
- protected credential stores, external-service URLs, headers and retry
  behavior;
- the rule that unsafe or paid operations are never replayed after ambiguous
  failure.

SQLite remains schema version 10. Existing data authority, compatibility
contracts, paid-call behavior and established recovery semantics did not
change.

## Completed scope: Phase 4

Phase 4 extracted the durable-storage HTTP bridge, redacted diagnostics/support
service and shared document-safety/OCR primitives. Each area was inventoried and
characterized before movement. The new modules use explicit dependencies, avoid
circular imports and preserve route registration, initialization order and
required app-level compatibility adapters.

Phase 4 did not change the 107 Flask routes, methods or response contracts;
authentication, CSRF or request-size boundaries; schema version 10; Phase 1/2
storage guarantees; Phase 3 client policies; update/receipt/backup/restore/
rollback behavior; request-ID/error/redaction contracts; credential stores; or
paid-call confirmation gates.

The v24.6.232 corrective release preserves runtime/test rebinding through
explicit forwarding callbacks and restores the original app-level
initialization position of storage compatibility constants and the OCR
semaphore. The three extracted modules remain app-independent.

## Completed scope: Phase 3

Phase 3 conservatively extracted behind the existing route contracts:

- `JobAdderClient`;
- `MicrosoftGraphClient`;
- `AIProviderClient`;
- centralized retry, pagination, token refresh, timeout, redaction and
  structured external-service error handling.

All 107 route URLs, legacy response fields, credential mechanisms and paid-call
confirmation gates remain. Safe reads receive bounded retries, Microsoft access
tokens receive one refresh/retry, pagination is capped, and chargeable or other
unsafe writes are not replayed after ambiguous transient failures. No live credentialed or paid
external calls were made during implementation or QA.

## Completed scope: Phase 2B

Phase 2B added schema versions 8–10 and migrated only:

- OneNote transfer record history;
- saved OneNote desktop links;
- the explicitly allowlisted non-secret browser settings used by local-data
  backup/restore.

SQLite is authoritative after insert-only legacy import. Tombstones prevent
stale mirrors from resurrecting deleted values, selected browser keys remain as
transition mirrors, schema-1 backup files remain readable, and credentials are
filtered from record/settings persistence. Temporary UI state remains in
browser storage. No Phase 3 or backburner scope was implemented.

## Explicit backburner

Do not implement these unless the owner explicitly reactivates them:

1. Roadmap item 4 — replace Flask's built-in local server.
2. Roadmap item 7 — saved and versioned AI Crawler scoring profiles.
3. Roadmap item 8 — AI Crawler Shortlist / Maybe / Reject / Reviewed workflow.

## Completed scope: Phase 2A

The SQLite foundation and lower-risk backend durable data migration now include:

- local SQLite database;
- WAL mode;
- foreign-key enforcement;
- busy timeout;
- integrity checks;
- schema-version and migration history;
- timestamped backup before schema changes;
- repositories for usage history and non-sensitive caches;
- one-store-at-a-time migration for:
  - usage history;
  - lead-title cache;
  - lead-contact cache;
  - salary-component cache;
  - PPC metadata;
  - diagnostic state;
- SQLite-first reads;
- safe legacy JSON fallback/import;
- one-release backward readability;
- idempotent migration.

The following were not included during Phase 2A. Shared external-service client
foundations were later completed within Phase 3; the other items remain out of
scope:

- browser notes/settings migration;
- credential migration;
- background jobs;
- backend or frontend modularisation;
- lazy loading;
- new user-facing workflow features;
- Flask server replacement;
- saved scoring profiles;
- candidate decision workflow.

## Safety rules

- Make conservative additive changes. Do not perform a broad rewrite.
- Preserve all existing route URLs unless explicitly required.
- Preserve legacy response fields and the structured error contract.
- Never delete legacy JSON during the transition release.
- Never place API keys, OAuth tokens or protected credentials into plain SQLite.
- Create and verify a backup before every schema-changing migration.
- Migrations must be transactional, restart-safe and idempotent.
- A failed migration must not leave a partially upgraded database.
- Corruption and migration failures must return structured errors with request IDs and recovery guidance.
- Never expose tokens, keys, emails, candidate IDs or private paths in logs, tests or diagnostic bundles.
- Do not claim genuine Windows/macOS native testing unless it was actually performed.
- Do not create a protected colleague ZIP without matching native compilation and smoke testing.
- Preserve the v24.6.215 DeepSeek detailed-cost history cutoff.
- Keep owner-source and protected colleague packaging rules separate.

## Working method

Before changing code:

1. Read `ROADMAP.md`.
2. Read `PHASE_STATUS.md`.
3. Read `IMPLEMENT.md`.
4. Read `CV_STUDIO_V24_6_239_PHASE_6_HANDOVER.md`.
5. Read
   `cv_studio_v24_6_239_blind_jd_pdf_metadata_overflow_corrective_qa_report.md`,
   `CV_STUDIO_V24_6_238_PHASE_6_HANDOVER.md`,
   `cv_studio_v24_6_238_blind_jd_exp_summary_corrective_qa_report.md`,
   `CV_STUDIO_V24_6_237_PHASE_6_HANDOVER.md`,
   `cv_studio_v24_6_237_jobadder_esc2_corrective_qa_report.md`,
   `CV_STUDIO_V24_6_236_PHASE_6_HANDOVER.md`,
   `cv_studio_v24_6_236_phase5b_ai_cost_guardrails_corrective_qa_report.md`,
   `CV_STUDIO_V24_6_234_PHASE_5B_HANDOVER.md`,
   `cv_studio_v24_6_234_phase5a_persistent_jobs_corrective_qa_report.md`,
   `cv_studio_v24_6_233_phase5a_persistent_jobs_qa_report.md`,
   `CV_STUDIO_V24_6_232_PHASE_5_HANDOVER.md`,
   `cv_studio_v24_6_232_phase4_compatibility_corrective_qa_report.md`,
   `cv_studio_v24_6_231_phase4_backend_modularisation_qa_report.md`,
   `cv_studio_v24_6_230_phase3_content_negotiation_corrective_qa_report.md`,
   the v24.6.224 corrective QA report, the
   v24.6.223 Phase 3 QA report, the
   Phase 2B QA reports and the historical Phase 2A QA reports.
6. Inspect the relevant existing storage paths and tests.
7. Verify the baseline before implementation.

During work:

1. Work only on the active milestone.
2. Make the smallest safe change.
3. Run targeted tests.
4. Fix failures before proceeding.
5. Update `PHASE_STATUS.md`.
6. Commit a Git checkpoint when a milestone is stable.
7. Continue automatically to the next milestone.

Stop and ask the owner only when:

- an operation could delete or irreversibly reinterpret user data;
- credentials or a paid external call are required;
- administrator approval is required;
- genuine native Windows/macOS testing is required;
- two choices have materially different compatibility consequences.

Routine implementation decisions do not require owner confirmation.

## Completed definition of done for Phase 3

- The three shared clients cover the inventoried existing external-service
  call sites without changing route URLs or legacy response fields.
- Retry, pagination, Microsoft token refresh, bounded timeouts, redaction and
  structured error translation are centralized and characterization-tested.
- Credentials remain in their existing protected stores and never enter plain
  SQLite, logs, fixtures, diagnostics, support bundles or release evidence.
- No live credentials, paid calls, schema migration, persistent background job,
  broad modularisation, frontend lazy loading, unrelated workflow or roadmap
  item 4, 7 or 8 is introduced.
- Targeted and full regression tests pass, including source smoke and static
  validation.
- A clean private owner/source ZIP is freshly extracted and byte-verified; its
  SHA-256, QA report and Phase 4 handover are copied to the new release folder.
- Stop after Phase 3. Do not begin Phase 4 automatically.

## Completed definition of done for Phase 5A

- Existing background/long-running routes, helpers, process-local state, locks,
  queues, filesystem/SQLite interactions and startup/shutdown behavior are
  completely inventoried before production implementation.
- Current success, progress, cancellation, failure, recovery, retry and
  idempotency contracts are characterization-tested without live credentials,
  external mutations or paid calls.
- Only existing authorized background work receives persistent lifecycle state,
  bounded recovery and idempotent restart handling.
- Every durable job-state write is failure-visible. No paid or externally
  mutating operation resumes silently after an ambiguous failure.
- All 107 routes, five ordered global guards, 18 compatibility signatures,
  initialization order, schema version 10 and every Phase 1–4 contract remain.
- Complete regression, both frontend fixtures, source smoke, tracked-language
  static validation, owner-source preflight, repository consistency and final
  baseline review pass.
- A clean private owner/source ZIP is freshly extracted and byte-verified; its
  SHA-256, verification sidecars, QA report and next owner-gated handover are
  copied to the new release directory.
- Stop before handoff or merge. Do not begin Phase 5B or Phase 6.

## Definition of done for Phase 5B

- Every paid-provider route/helper, confirmation gate, normalized accounting
  field, historical cutoff/calculation, authoritative billing field, retry/
  timeout/ambiguity boundary, credential boundary and reconciliation response
  is inventoried before production behavior changes.
- Pre-change no-network characterization fixes existing success, failure,
  usage, cost and reconciliation response contracts.
- One bounded central foundation distinguishes estimates from provider-
  authoritative billing, keeps missing authority explicit and makes guardrail
  or reconciliation failures visible.
- All 107 routes, five guards, 18 compatibility signatures, schema version 10,
  journal schema 1/recovery semantics, initialization order and prior-phase
  contracts remain.
- No live credential, paid call, additional persistent-job family, automatic
  worker, credential migration, frontend modularisation/lazy loading, Phase 6,
  unrelated workflow or backburner item 4, 7 or 8 is introduced.
- Complete regression, both frontend fixtures, source smoke, tracked-language
  static validation, owner-source preflight, repository consistency and
  repeated exact-master review pass.
- A clean next-version private owner/source ZIP is freshly extracted and
  byte-verified; its SHA-256, verification sidecars, QA report and Phase 6
  handover are copied to the new release directory.
- Stop before handoff or merge. Do not begin Phase 6.

## Completed definition of done for Phase 4

- Each selected backend area has a recorded pre-move dependency/state inventory
  and characterization coverage for established success and error behavior.
- Each extraction is bounded, uses explicit dependencies, has no circular
  import, preserves app-level compatibility adapters and passes targeted tests
  before the next area begins.
- All 107 routes, methods, response fields and authentication/CSRF/request-size
  boundaries remain unchanged.
- Schema version 10, every Phase 1/2 storage guarantee and every Phase 3 shared-
  client retry/refresh/pagination/redaction/content-negotiation contract remain
  unchanged.
- No credential migration, persistent background job, central AI cost
  guardrail, frontend modularisation/lazy loading, unrelated workflow, Flask
  server replacement or roadmap item 7/8 is introduced.
- Complete regression, source smoke, tracked-language static validation,
  owner-source preflight, repository consistency and final review pass.
- A clean private owner/source ZIP is freshly extracted and byte-verified; its
  SHA-256, QA report and Phase 5 handover are copied to the new release folder.
- Stop after Phase 4. Do not begin Phase 5 automatically.

## Completed definition of done for Phase 2B

- No user-data loss from the v24.6.219 source/schema-7 baseline.
- Migration is transactional and idempotent.
- Running migration twice produces no duplicate or destructive effect.
- A verified timestamped backup is created before schema changes.
- Database corruption produces a structured request-ID error and recovery guidance.
- Legacy JSON and selected browser mirrors remain intact and readable.
- OneNote records, saved links and allowlisted settings read and write through
  SQLite while retaining transition mirrors and schema-1 export/import.
- Credential-like fields are excluded recursively.
- Phase 2A repositories and compatibility contracts remain unchanged.
- Items 4, 7 and 8 remain untouched.
- Targeted and full regression tests pass.
- Python, JavaScript, Bash and PowerShell syntax validation pass.
- Repository consistency passes.
- A clean extraction is byte-verified.
- A new private owner/source ZIP is created.
- A SHA-256, QA report and Phase 3 handover are produced.
- Stop after Phase 2B. Do not begin Phase 3 automatically.
