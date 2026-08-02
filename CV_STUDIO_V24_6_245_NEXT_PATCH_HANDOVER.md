# CV Studio v24.6.245 Next-Patch Handover

## Entry state

- Base: merged Phase 6C source v24.6.244 at
  `c75aa20c5a99ea5e9af84204a19703c90e0c2d36`.
- Candidate: `agent/v24.6.245-long-cv-access-corrective`.
- The pre-review owner/source sidecar references commit
  `956eb4d8faf96980a7c4c12739f00a985b6ca2ef`. That archive remains immutable but
  is superseded and must not be treated as the corrected PR head.
- Installed source identity: v24.6.245.
- Owner/source only; no protected colleague or macOS artifact is authorized.

## Preserved contracts

- Existing 108 routes, five ordered guards, 18 compatibility signatures,
  SQLite schema 10 and journal schema 1 remain unchanged.
- Phase 6A–6C behavior and the immutable v24.6.243 tag remain preserved.
- AI calls retain paid-action guardrails and zero ambiguous retry. The new
  timeout is a bounded wait increase only; it does not replay, truncate or add
  provider calls.
- CV Scoring code `1996` is a local casual UI lock, not authentication.
- AI Crawler is intentionally unlocked; do not reintroduce its password unless
  the owner explicitly reverses this decision.
- Standalone responsibility/achievement labels are headings only at the role
  bullet boundary; text nested inside an existing group remains bullet content.
- Bounded inferred-title removal covers inferred, implied, assumed, guessed and
  likely annotations only when parenthetically tied to source duties,
  responsibilities, content or context.

## Next action

Confirm GitHub Windows-x64 CI on the corrected PR head, then create a new
commit-bound source artifact rather than overwriting the superseded archive.
Merge only through the repository PR flow. Do not start Phase 7, protected
packaging or macOS support work without separate authorization.
