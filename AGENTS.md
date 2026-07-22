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
- Current completed private owner/source release: **CV Studio v24.6.222**.
- Phases 1, 2A and 2B are complete.
- The owner explicitly authorized **Phase 3** on 22 July 2026 from clean
  `master` commit `1be9da48d8307c418d82807cbdaedc9f876a1b15`.
- Active implementation target: shared external-service client foundations
  only. Stop after the Phase 3 owner/source release and Phase 4 handover.

## Active scope: Phase 3

Phase 3 is limited to conservative extraction behind the existing route
contracts of:

- `JobAdderClient`;
- `MicrosoftGraphClient`;
- `AIProviderClient`;
- centralized retry, pagination, token refresh, timeout, redaction and
  structured external-service error handling.

Inventory existing call sites and response shapes before extraction. Move one
client at a time with characterization fixtures. Preserve every route URL,
legacy response field, credential mechanism and paid-call confirmation gate.
Do not make live credentialed or paid external calls during implementation or
QA.

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
foundations are now activated only within the Phase 3 boundary above; the other
items remain out of scope:

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
4. Read `CV_STUDIO_V24_6_222_PHASE_3_HANDOVER.md`.
5. Read `cv_studio_v24_6_222_phase2b_second_corrective_review_qa_report.md`,
   the v24.6.221/v24.6.220 Phase 2B QA reports and the historical Phase 2A QA
   reports.
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

## Phase 3 definition of done

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
