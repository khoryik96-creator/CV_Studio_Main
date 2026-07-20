# CV Studio v24.6.218 — Phase 2A SQLite Foundation QA Report

**Build type:** Private owner/source release  
**Migration base:** v24.6.217  
**Release:** v24.6.218  
**Date:** 21 July 2026

## Release intent

This release completes Phase 2A only. It adds the local SQLite foundation and
migrates the explicitly selected lower-risk durable stores without deleting
or renaming any legacy JSON data.

It does not begin browser notes/settings migration, credential migration,
shared API-client extraction, background jobs, backend/frontend
modularisation, lazy loading or new user-facing workflows. Roadmap items 4,
7 and 8 remain backburnered.

## Implemented

### SQLite safety foundation

- Per-user cv_studio.sqlite3 beside the existing CV Studio state/receipt data.
- WAL journal mode, foreign-key enforcement, a 5-second busy timeout and
  normal synchronous mode on managed connections.
- Full integrity check before and after schema migration.
- Seven ordered schema migrations with PRAGMA user_version, schema metadata,
  checksummed migration history and one store per migration checkpoint.
- A unique timestamped SQLite backup before every schema-changing migration.
- Every backup is opened read-only and independently verified with
  PRAGMA integrity_check before migration proceeds.
- Transactional DDL/data migration with rollback on failure and safe restart.

### Repositories and migrated stores

- Usage history.
- Lead-title cache.
- Lead-contact cache.
- Salary-component cache.
- PPC payment/guarantee metadata.
- Non-sensitive diagnostic storage state.

Repository payloads preserve the established v24.6.217 shapes. Legacy usage
rows created before the v24.6.215 detailed-cost cutoff retain their historical
cost but do not gain invented token, call or cache-detail fields.

### Compatibility transition

- Backend cache reads import valid legacy JSON idempotently and then read
  SQLite first.
- Lead-title, lead-contact and salary updates write SQLite first and retain
  compatible legacy JSON mirrors.
- Usage history retains the guo_lab_stats localStorage key.
- PPC metadata retains the cvstudio_ppc_meta_v1 localStorage key.
- Browser hydration is asynchronous; current local data remains immediately
  usable while the SQLite bridge starts.
- Legacy files are never deleted by migration.
- The owner title-cache merge utility remains compatible because new releases
  continue to read and write lead_title_cache.json during the transition.

### Recovery and diagnostics

- Corruption returns STORAGE_CORRUPT with a request ID, recovery action and
  path-free guidance.
- Migration failure returns STORAGE_MIGRATION_FAILED with the same structured
  contract.
- Runtime diagnostics expose only schema version, health, journal mode,
  foreign-key/busy-timeout state, integrity result and backup count.
- Database paths, legacy paths, credentials and private record content are not
  included in storage diagnostics or support bundles.

## QA results

### Python regression suite

**16 tests passed, 0 failed**

Coverage includes:

- all-store v24.6.217 fixture import;
- double import with no duplicate effect;
- byte-exact legacy fixture preservation;
- v24.6.215 detailed-cost cutoff preservation;
- WAL, foreign keys and busy timeout;
- seven verified pre-migration backups;
- exact schema metadata and migration history;
- second startup with no extra backup;
- injected interruption after schema work and transactional rollback;
- successful restart after the injected interruption;
- corrupt database recovery contract;
- repository round trip, update and clear behavior;
- real Flask-module cache import and dual-write behavior;
- usage/PPC import, read, upsert and clear routes;
- Phase 1 request-ID, structured error, Host and CSRF regression;
- owner local-health/DOCX integration checks;
- support-bundle storage redaction.

### Frontend storage fixture

**Passed**

- Both inline index.html scripts compile in Node.
- Usage and PPC hydrate from SQLite and retain their legacy localStorage keys.
- Ordered writes prevent clear/update races.
- An in-flight usage import cannot resurrect explicitly cleared history.
- Legacy usage rows without IDs use stable sorted-key identity.
- PPC conflict resolution honors updatedAt.

### Live source smoke

**18 assertions passed, 0 failed**

The real threaded source server ran on an ephemeral loopback port with a
temporary signed receipt, database and runtime log. Checks covered status,
version/instance identity, response request IDs, durable-storage health, WAL,
integrity, path-free diagnostics, structured 404, usage import, detailed-cost
cutoff, PPC import, owner status, local owner DOCX generation and post-shutdown
schema/integrity/history.

No external credentials, live provider calls or paid requests were used.

### Static and repository validation

Passed:

- owner-source validation and vetted adm-zip 0.5.17 behavior;
- Python syntax validation;
- JavaScript syntax validation, including both inline browser scripts;
- Bash syntax validation through Git Bash;
- PowerShell syntax-tree parsing with zero error nodes;
- repository consistency, dependency policy, encoding and line-ending checks;
- Phase 2A scope audit.

## Data-safety result

- No data loss from the complete v24.6.217 fixture.
- Migration twice is idempotent.
- Interrupted migration leaves no partial schema upgrade.
- Corruption leaves legacy bytes untouched.
- Legacy JSON/localStorage remains readable.
- Credentials remain in their existing protected storage mechanisms and are
  not written to SQLite.

The SQLite file is local user data, not an encrypted credential vault. It can
contain usage labels/links, PPC placement metadata and cached public business
contact data already held by the migrated features. Treat it and its backups
as private application data.

## Not genuinely tested

- Windows-native Nuitka compilation or protected-binary smoke launch;
- physical Windows installer/restore execution;
- physical Apple Silicon or Intel Mac installation/restore execution;
- live JobAdder, Outlook or OneNote calls;
- paid AI-provider calls.

No protected colleague ZIP was created. A colleague artifact still requires
matching native compilation and smoke testing on its target operating system.

## Private owner/source archive

The final archive is created from the clean release commit with exact
cv_formatter/ root layout, freshly extracted and compared byte-for-byte.
Because an archive cannot reliably contain its own checksum as release
content, the authoritative SHA-256, size, file counts and verification result
are recorded in the adjacent checksum and verification sidecars generated
after archive creation.

## Known limitations

- One-release legacy mirroring is transitional and should be reassessed in the
  owner-authorised phase after Phase 2B compatibility requirements are known.
- Browser hydration is asynchronous by design; when SQLite is unavailable,
  the existing local copy remains visible while storage API calls return the
  structured recovery contract.
- Rollback still requires the previous extracted release folder.
- No automatic database restore is attempted after corruption; recovery is
  explicit to avoid reinterpreting user data.

## Stop boundary

Phase 2A is complete. Phase 2B was not started.
