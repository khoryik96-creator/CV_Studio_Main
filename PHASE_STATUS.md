# Current Phase Status

## Release state

- Approved baseline: v24.6.217
- Active phase: Phase 2A
- Status: not started
- Current milestone: baseline verification and storage inventory

## Milestones

- [ ] Verify source baseline and repository state.
- [ ] Inventory existing backend JSON/cache stores and read/write call sites.
- [ ] Design database path, connection policy and schema.
- [ ] Implement SQLite connection foundation.
- [ ] Implement schema-version and migration history.
- [ ] Implement timestamped backup and restore validation.
- [ ] Implement repository interfaces.
- [ ] Migrate usage history.
- [ ] Migrate lead-title cache.
- [ ] Migrate lead-contact cache.
- [ ] Migrate salary-component cache.
- [ ] Migrate PPC metadata.
- [ ] Migrate diagnostic state.
- [ ] Implement SQLite-first and legacy-JSON fallback/import.
- [ ] Prove migration idempotency.
- [ ] Test corrupt and interrupted migration handling.
- [ ] Run complete regression and static validation.
- [ ] Create private owner/source ZIP.
- [ ] Produce QA report, SHA-256 and Phase 2B handover.

## Decisions

None yet.

## Blockers

None yet.

## Test results

Not started.

## Files changed

None yet.

## Next action

Verify the baseline, initialise/check Git, inspect the existing storage paths, and create the Phase 2A implementation plan.
