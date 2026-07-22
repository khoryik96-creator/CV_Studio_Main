# CV Studio v24.6.223 → Phase 4 Handover

Source release: private owner/source v24.6.223

Completed phase: Phase 3 — shared external-service client foundations

Phase 3 source baseline: v24.6.222 at
`1be9da48d8307c418d82807cbdaedc9f876a1b15`

## Activation gate

Phase 4 is not active. Start it only after an explicit owner instruction. Read
the v24.6.223 Phase 3 QA report, this handover, the Phase 2B QA reports and the
historical Phase 2A reports. Verify the v24.6.223 owner/source archive against
both adjacent sidecars before changing production code.

## Preserve the Phase 1/2 storage and route contracts

- Keep all 107 Flask route URLs and every established success/failure response
  field. Module extraction must not rename routes, alter methods or move a
  request across an authentication/CSRF/size boundary.
- Preserve request-ID propagation, additive structured error normalization,
  support-bundle redaction, update health checks, receipt validation and
  rollback behavior.
- Keep `cvstudio_storage.py` at schema version 10 unless a separately authorized
  phase explicitly requires data migration. Preserve WAL, foreign keys, busy
  timeout, integrity checks, migration history and verified pre-change backups.
- Retain SQLite authority, insert-only legacy import, tombstones, selected
  browser mirrors, schema-1 local-data backup/restore and all failure-visible
  durable writes. Never delete a legacy JSON file during transition.
- Keep API keys, OAuth tokens and protected credentials out of plain SQLite,
  browser backup, logs, fixtures, diagnostics and support bundles.
- Preserve the v24.6.215 DeepSeek detailed-cost history cutoff.

## Preserve the Phase 3 client contracts

`cvstudio_clients.py` is the established external-service boundary. Future
module moves must retain its dependency-injected adapters and policies:

- `JobAdderClient` owns JobAdder OAuth/API request behavior, safe-read retry,
  one rejected-token refresh/retry, reconnect marking and bounded offset
  pagination. Mutations/uploads do not replay after ambiguous transient failure.
- Separate `MicrosoftGraphClient` instances retain the OneNote and Outlook
  protected stores and scopes. Graph safe reads receive bounded retry,
  `@odata.nextLink` traversal remains host-restricted/capped and an HTTP 401
  receives one refresh/retry. Draft writes do not replay after ambiguous
  transient failure; device-code operations remain non-replaying.
- `AIProviderClient` retains exact Anthropic, DeepSeek and OpenAI endpoints/
  headers, 15–300 second timeout bounds, HTTPS host restriction and zero retries
  for every chargeable POST.
- Keep DeepSeek web-tool refusal, OpenAI request/response translation, usage
  normalization, route-specific friendly failures and paid-call confirmation
  gates unchanged unless separately characterized and authorized.
- Preserve redaction of credentials, authentication/cookie headers, email
  addresses and candidate-ID-labelled values in upstream errors.
- The local watchdog, Tavily/SerpAPI search and Apollo enrichment remain outside
  the three Phase 3 clients. Do not silently expand client scope during module
  movement.

## Candidate Phase 4 scope

If explicitly authorized, Phase 4 is limited by `ROADMAP.md` to gradual backend
modularisation without behavior or route changes.

Before moving each cohesive backend area:

1. inventory its routes, helper/global dependencies, response fields, locks,
   protected stores, filesystem state and startup side effects;
2. capture route/helper characterization fixtures, including error paths;
3. extract one bounded module with explicit dependencies and no circular import;
4. retain route registration, initialization order and app-level compatibility
   adapters where callers depend on them;
5. run targeted tests, update `PHASE_STATUS.md`, record limitations and create a
   stable Git checkpoint before selecting the next module.

Do not use Phase 4 as a broad rewrite. Prefer small mechanical moves and keep
feature orchestration close to the existing route until its behavior is fully
characterized.

## Still out of scope

- credential or protected-secret migration;
- persistent background jobs or resumable task state (Phase 5);
- central AI cost guardrails/provider-billing reconciliation (Phase 5);
- frontend modularisation or lazy loading (Phase 6);
- unrelated user-facing workflows;
- Flask server replacement (backburner item 4);
- saved/versioned AI Crawler scoring profiles (backburner item 7);
- Shortlist/Maybe/Reject/Reviewed workflow (backburner item 8).

## Required Phase 4 entry checks

1. Verify the v24.6.223 owner ZIP and fresh extraction against the adjacent
   SHA-256 and verification sidecars.
2. Verify Git is clean and based on the completed v24.6.223 release commit
   recorded in the verification sidecar.
3. Read `AGENTS.md`, `ROADMAP.md`, `PHASE_STATUS.md`, `IMPLEMENT.md`, this
   handover, the v24.6.223 Phase 3 QA report and prior Phase 2A/2B reports.
4. Run all 45 Python tests with resource warnings treated as errors, both
   frontend fixtures and the 24-assertion live source smoke.
5. Re-prove migration idempotency, interruption rollback/restart, corruption
   recovery, tombstones, rejected-replacement preservation, strict setting
   validation, restore failure visibility and legacy bytes.
6. Run all tracked Python, JavaScript, Bash and PowerShell syntax checks,
   owner-source validation/preflight, repository consistency and Git whitespace
   validation.
7. Re-prove the exact 107-route inventory and all Phase 3 no-network client
   characterization fixtures.
8. Inventory the first proposed module boundary and record the authorized Phase
   4 milestone plan before moving code.

## Native-test caveat

v24.6.223 has genuine Windows source execution and controlled local fixtures,
but no new protected native compilation, protected-binary smoke certification
or physical installer/restore test. Do not create a protected colleague package
without matching native evidence.

## Stop boundary

Stop after Phase 3. Phase 4 or any later phase requires a new explicit owner
instruction.
