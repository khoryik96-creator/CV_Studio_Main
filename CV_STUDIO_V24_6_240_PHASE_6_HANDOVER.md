> **Historical — do not use as the current release reference.** This document is a point-in-time record. The authoritative current version is the repository-root `VERSION` file; see `HANDOFF.md` for current state.

# CV Studio v24.6.240 Phase 6 handover

## Owner gate

Phase 6 is inactive. This handover records completion of the separately
authorized mandatory Antiword dependency milestone and does not authorize
Phase 6, JobAdder settings/sign-out, AI Crawler behavior changes, backburner
work, handoff or merge.

## Release identity and platform boundary

- Release: CV Studio v24.6.240.
- Supported platform: Windows x64 only.
- Mandatory dependency: bundled, hash-pinned and functionally verified
  Antiword 1.3.5 (engine 0.37).
- Exact source baseline: v24.6.239 master commit
  `a5762488f7d90fe58f00870b2c0b2944be084e71`.
- No v24.6.240 Intel or Apple Silicon macOS support claim or artifact was
  produced.
- macOS users remain on v24.6.239 until a separately authorized milestone
  performs matching native validation.

## Windows completion

The Windows installer will not complete or issue its final receipt unless the
managed/bundled runtime passes:

- official distribution and corresponding-source SHA-256 pins;
- complete 37-file runtime manifest and exact file-set validation;
- every runtime-file hash and executable hash;
- x64/native trust checks and reparse/link exclusions;
- controlled genuine legacy `.doc` fixture hash;
- bounded functional extraction of both expected phrases.

Runtime discovery never trusts PATH, Program Files, `ANTIWORDHOME` or another
arbitrary executable location. The child environment removes `ANTIWORDHOME`
and binds `HOME` to the verified executable directory. All genuine legacy Word
OLE content gates on verified Antiword before weak metadata, caching,
LibreOffice, OCR or native-parser alternatives. Failure uses the established
structured request-ID response and recovery guidance.

## Deferred macOS work

The final production tree restores the v24.6.239 macOS installer, launcher,
rollback script and historical Mac builder command to exact baseline bytes.
The v24.6.240 builder and private CI workflow cannot produce a Mac artifact.
The unvalidated Mac archives and extracted runtimes are not shipped.

Provenance retains the upstream Intel/Apple Silicon URLs, hashes and prior
inspection notes solely as future-work inputs. A future owner-authorized
milestone must validate installer, managed copy/repair, diagnostics, runtime
extraction, protected build/smoke, signing/Gatekeeper behavior and final
artifacts on both genuine architectures before any newer macOS claim.

## Preserved contracts

The milestone preserves:

- all 107 Flask routes, methods, endpoint names and legacy response fields;
- all five ordered global guards and authentication, CSRF, request-size and
  paid-call confirmation boundaries;
- all 18 compatibility signatures and call-time dependency rebinding;
- SQLite schema 10 and Phase 5A journal schema 1/lifecycle semantics;
- provider retry, timeout, paid non-replay and credential boundaries;
- every completed Phase 1-5B contract and the v24.6.237-v24.6.239 corrections.

## Validation and release evidence

- Focused Windows Antiword/installer plus document-boundary tests: passed.
- Exact-v24.6.239 macOS production-file and no-v24.6.240-Mac-build tests:
  passed.
- Complete regression suite: passed once after the scope adjustment.
- One focused exact-master self-review: clean; no repeated review loop or
  independent reviewer was started.
- Only Windows-x64 owner/source and protected colleague artifacts were created.
- Each verification sidecar's `source_commit` equals final HEAD.
- No v24.6.240 macOS artifact was created.

Exact artifact names, paths, hashes, smoke evidence and final commit are
reported with the release and its adjacent verification sidecars.

Stop before handoff or merge. Do not begin JobAdder work or Phase 6 without a
new explicit owner authorization.
