# LinkedIn Sourcer module verification

Historical verification snapshot, 2026-10-19. Current release identity is the
repository-root `VERSION`. Branch: `codex/v24.6.446-linkedin-sourcer-module`.
Base main: `480678d5bdc190408d9f04b769cbe3c71115aa1b`, with the owner-approved
local POC checkpoint `de14854` preceding this integration.

The owner requested a dedicated module inside CV Studio. The brief, Start/Stop,
limits, progress, results and exports now live there. A bundled companion handles
only bounded browser commands; the separate POC server is not required.

## Evidence

- Ten new Python tests cover three modes, consent, bounds, exact quote/URL
  grounding, budget reservation, malformed paid output accounting, concurrent
  Stop, the real guarded route, exact legacy route preservation, the companion
  ZIP and central provider/cost wiring. No transport reaches a paid provider.
- The new frontend suite checks explicit tab/document binding, source/owned-tab
  restrictions, observed links, no provider endpoint in the companion, Stop,
  page limits even after repeated Begin, three complete 15-page simulations,
  detail provenance and CSV formula escaping.
- Native Chrome exercised the actual app with a simulated companion and provider:
  module navigation, required consent, query planning, screening, profile detail,
  candidate links/provenance, request/token counters, ordinary cost-history calls
  and results retained across tab switching. Layout was rendered and inspected.
- The full regression initially identified two stale route inventories. They now
  include the authorized new route while retaining the older baseline proof.
  The UI check caught and corrected the Start-button run-status helper name.
- **Final isolated full: 1,607 passed, four skipped, three documented local
  environment cases deselected; 7,599 subtests passed.** All 30 frontend suites
  pass. After adding bare Chrome-manifest version stamping, the five shared
  single-source version checks pass, including idempotence.
- Tracked-language syntax, byte consistency, architecture/build/source preflight
  and the 24-assertion source smoke pass. No protected compilation occurred.

The unchanged local exclusions are
`test_python_runtime_resolver_returns_the_exact_validated_interpreter`,
`test_real_update_preflight_uses_launcher_path_python_before_stale_fixed_install`,
and `test_downloaded_preflight_is_self_contained_for_v357_upgrade_transition`.
No hosted-check result is claimed for this local, unpushed change.

Only one route is added: GET/POST `/linkedin-sourcer` (119 total). Excluding it
reproduces the exact old 118-route digest. All five ordered guards remain, and
the new POST uses the existing AI-spend cookie and CSRF rules. No extension-origin
exception was added. Keys resolve server-side through the established protected
store. Paid calls retain central limits, usage/billing envelopes and ambiguous
non-replay. Candidate content is excluded from usage labels, logs and fixtures.
CV formatting logic/fixtures, storage schemas and journal semantics are unchanged.

Preview state/receipt is isolated from the installed owner app. The preview reads
the saved DeepSeek key into memory only, without logging or persisting it. No live
LinkedIn search, paid API call, real Chrome companion installation, JobAdder write,
owner installation/receipt update, native Mac check, protected package, push, PR or
merge was performed. Those limits remain explicit in the module notes.
