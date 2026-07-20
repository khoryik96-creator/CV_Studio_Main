# CV Studio v24.6.217 — Phase 1 Release Safety, Error Contract and Owner Integration QA Report

**Build type:** Private owner/source patch base  
**Patch base:** v24.6.216  
**Release:** v24.6.217  
**Date:** 20 July 2026

## Release intent

This release implements Phase 1 of the staged stability roadmap. It adds a broad additive JSON error contract, pre-activation installation health checks, transactional rollback and an owner-source-only integration-test foundation.

It deliberately does **not** begin SQLite migration, shared API-client extraction, background-job management or backend/frontend modularisation. Roadmap items **4, 7 and 8 remain explicitly backburnered**:

- 4 — replace Flask's built-in local server;
- 7 — saved/versioned AI Crawler scoring profiles;
- 8 — AI Crawler candidate decision workflow.

## Implemented changes

### 1. Additive structured JSON error contract

- Every request receives a bounded request identifier.
- A valid caller-provided `X-CV-Studio-Request-ID` is preserved.
- Every response returns `X-CV-Studio-Request-ID` where available.
- Legacy JSON failures are normalised after route execution into a common additive shape:

```json
{
  "ok": false,
  "error": "Legacy-compatible display message",
  "message": "Canonical message",
  "code": "JOBADDER_RECONNECT_REQUIRED",
  "retryable": false,
  "request_id": "...",
  "severity": "warning",
  "action": "open_jobadder_settings"
}
```

- Existing route-specific fields remain present.
- Existing successful response bodies are not rewritten.
- Human-facing OAuth callback pages remain HTML intentionally; the central contract applies to local JSON/API failures.
- Unhandled Flask/HTTP exceptions now use the same structured contract.
- Secret-like values in error messages are bounded and redacted.

### 2. Central browser request/error handling

- All same-origin browser requests receive a request ID.
- Unsafe same-origin methods retain the existing `X-CV-Studio-Request: 1` anti-CSRF opt-in.
- Legacy error displays gain action guidance and the associated request ID without requiring every feature to be rewritten immediately.
- Browser network failures receive a local `NETWORK_ERROR` diagnostic record and retain the request ID on the thrown error.
- A bounded recent-error history is available to the redacted diagnostic bundle.
- Recent-error paths, messages, emails, tokens, query values, candidate IDs and home paths are sanitised before inclusion.

### 3. Pre-activation update health checks

Windows and macOS installers now:

1. detect the currently active CV Studio folder from the stable Desktop launcher or saved update state;
2. preserve its root-bound signed install receipt;
3. complete mandatory dependency setup;
4. issue the new release's signed receipt;
5. start the exact new folder on a temporary loopback port;
6. verify version/status, package identity, root identity, runtime diagnostics, signed-receipt validity and request-ID generation;
7. commit rollback state;
8. replace the stable Desktop launcher only after all checks pass.

A failed health check restores the prior receipt, leaves the existing launcher unchanged and does not activate the new folder.

### 4. Transactional rollback

Added:

- `RESTORE_PREVIOUS.bat`;
- `RESTORE_PREVIOUS.ps1`;
- `restore_previous.sh`.

Rollback switches the following as one transaction:

- the active root-bound signed receipt;
- the stable Desktop launcher;
- `update_state.json` current/previous pointers.

If verification, launcher creation or state writing fails, the original receipt and launcher are restored. The previous extracted release folder is never automatically deleted.

State locations:

- Windows: `%LOCALAPPDATA%\TheGuoLab\CVStudio\update_state.json`
- macOS: `~/.guo_lab_cv_studio/update_state.json`

The installer creates a **Restore Previous CV Studio** Desktop launcher only when a valid previous release and receipt were preserved.

### 5. Owner-source-only integration-test foundation

A hidden card is available under **Settings → Integrations** only in the readable private owner/source build.

Available checks:

- local runtime/receipt/dependency health;
- local DOCX generation and Word-package validation;
- read-only JobAdder candidate lookup using an owner-supplied dedicated test candidate ID;
- read-only OneNote Graph request;
- read-only Outlook Graph request;
- one small paid DeepSeek probe, requiring an explicit warning plus exact typed confirmation.

Reports contain pass/fail/skipped counts, durations, request ID, redacted details and downloadable JSON.

Protected colleague packages report the feature disabled and cannot run owner tests because the private-source marker is absent.

The existing controlled Screening Call fixture remains separate and unchanged. It is still locked to dummy candidate **Max Low / 41262878**, exact confirmation `CREATE ONE MAX LOW TEST`, and its existing one-per-session protection. It was not made automatic.

### 6. Protected-build and repository integration

- Protected workflow/artifact names updated to v24.6.217.
- Platform-specific rollback launchers are included correctly:
  - Windows package: `.bat` and `.ps1` rollback files;
  - macOS package: `restore_previous.sh`;
  - incompatible platform launchers are pruned.
- Protected-build validation rejects missing/incomplete rollback launchers.
- Repository consistency validation now covers rollback script encoding and line endings.
- Generated health reports and installer logs are excluded from protected artifacts and source-control state.

## QA results

### Live temporary-port source suite

**15 assertions passed, 0 failed**

Covered:

- healthy v24.6.217 status;
- caller request-ID preservation;
- runtime diagnostics and valid signed receipt;
- generated request IDs;
- structured HTTP 404 errors;
- automatic normalisation of a legacy JobAdder JSON error;
- feature classification and request-ID preservation;
- structured unsafe-request rejection;
- structured invalid-Host rejection;
- owner-source-only status;
- safe owner local-health/DOCX integration suite;
- diagnostic ZIP creation;
- recent browser-error token, email, candidate-ID and path redaction.

### Frontend transport fixture

**6 assertions passed, 0 failed**

Covered:

- request-ID header creation;
- unsafe-method anti-CSRF header;
- action guidance;
- response request-ID display;
- bounded browser diagnostic history;
- network-error request-ID/history handling.

### Transactional macOS rollback fixtures

**2 scenarios passed, 0 failed**

- successful receipt/state/launcher switch;
- failed previous-receipt verification leaves receipt, state and launcher byte-for-byte unchanged.

### Controlled protected-package assembly

**3 scenarios passed, 0 failed**

- Windows x64 fixture;
- macOS ARM64 fixture;
- Linux proof fixture.

Each scenario verified archive root, manifest, private-source pruning and correct platform-specific rollback files. These are controlled assembly fixtures, **not native compilation or physical operating-system smoke tests**.

### Static and repository validation

Passed:

- Python compilation for `app.py`, `merge_title_cache.py` and both owner build tools;
- Node syntax for `generate.js` and both inline JavaScript blocks;
- Bash syntax for installer, launcher, rollback and owner command scripts;
- PowerShell syntax-tree parsing with zero error nodes across five `.ps1` files;
- deterministic protected-build source validation and Node/DOCX dependency preflight;
- repository consistency with exact bytes, no stale lock file, correct BOM policy and platform line endings;
- version-surface consistency;
- no Waitress/Gunicorn dependency or backburner workflow/profile implementation.

## Source/package measurements

- Source files: **65**
- `app.py`: **22,454 lines**
- `index.html`: **18,752 lines**
- Flask routes: **88**
- Broad `except Exception` occurrences in `app.py`: **379**

## Not genuinely tested in this environment

- live JobAdder candidate or Screening Call operations;
- live Outlook authentication/read;
- live OneNote authentication/read;
- paid DeepSeek billing comparison;
- Windows-native Nuitka compilation and smoke launch;
- physical Windows installer/restore execution;
- physical Apple Silicon or Intel Mac installation/restore execution.

The owner integration foundation is present for those tests, but no external credentials or paid calls were used during this release QA.

## Known operational limitations

- Rollback requires the previous extracted CV Studio folder to remain on disk.
- A first installation has no previous release to restore.
- The rollback launcher is created only after an update from a valid prior folder.
- This is not a self-downloading updater; the owner still extracts each release into its own folder and runs the normal authenticated installer.
- No protected colleague ZIP is released from this environment. A distributable package must be compiled on the matching OS and pass native smoke JSON with `"ok": true`.

## Deliberately not included

- SQLite/localStorage migration;
- shared JobAdder/Microsoft/provider clients;
- persistent background-job manager;
- backend/frontend module extraction;
- lazy feature loading;
- AI budgets and provider-statement reconciliation;
- Flask server replacement;
- saved/versioned AI Crawler scoring profiles;
- Shortlist/Maybe/Reject candidate workflow.

## Owner-package verification

- Exact archive root: `cv_formatter/`
- Source files: **65**
- Extracted files: **65**
- Byte mismatches after fresh extraction: **0**
- ZIP size: **1,350,234 bytes**
- SHA-256: `c499ea8043f274bf47a4981c84794759f38fc7c761b98ba3939626114a898a59`
