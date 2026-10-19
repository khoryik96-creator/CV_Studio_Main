# POC verification — 2026-10-19

Base: merged main `480678d5bdc190408d9f04b769cbe3c71115aa1b`, release identity
from root `VERSION` (unchanged). Branch: `codex/v24.6.445-linkedin-sourcer-poc`.
This is an isolated experiment, not a new CV Studio release.

## Performed

- **15 Python tests passed:** explicit paid/data-use confirmation, all three
  modes, host/origin/pairing protections, page/request/body bounds, observed URL
  and evidence checks, missing usage, failed-call accounting, serial execution,
  Stop during an in-flight call, no automatic retries, response-size/shape guards
  and native DeepSeek function-call payloads. Transport and keys are synthetic.
- **Nine controller tests passed:** a full 15-page synthetic run in each mode,
  duplicate/provenance handling, CSV formula escaping, repeated-page stop,
  cancellation before further browser actions, fabricated-link rejection and
  rejecting an incompatible open page before any paid request.
- **Two real Chrome fixture tests passed:** result readers for People search,
  Recruiter Lite and Recruiter, duplicate anchors, next/disabled/stale-page
  controls, profile identity checks, unrelated profile links, login/usage checks,
  session restore, HTML-safe candidate display, data-use confirmation and narrow
  side-panel layout. All LinkedIn requests were intercepted and fulfilled with
  synthetic HTML before network access. The panel's Chrome APIs were mocked;
  installation and live extension-to-account integration are not claimed.
- Python compilation, JavaScript parsing, PowerShell parsing and whitespace
  checks passed. The launcher created its own Python environment, installed only
  the pinned POC dependencies, started the loopback bridge, stopped its verified
  process tree and restarted successfully on native Windows. The bridge was left
  running locally at `http://127.0.0.1:5073/` for the owner to try.
- Existing Windows DPAPI key presence/decryption was checked read-only and
  reported as a Boolean only. No key was printed, copied into browser storage,
  committed, or sent to a provider. No receipt/vault write occurred.

## Remaining live check

The owner must load the unpacked extension into Chrome, pair it with the local
bridge, open their account's search page and confirm a small paid run. Different
LinkedIn layouts can require selector adjustments, particularly Recruiter keyword
entry and detail views. Unknown layouts, checks and restrictions stop the run;
they are never bypassed. Public profile URLs are never guessed when only a
Recruiter link is visible. Unloaded/collapsed profile content stays unknown.

No DeepSeek call, live LinkedIn interaction, message/connection, JobAdder write,
main-app route/schema/version/installation change, push, PR, merge, protected
build or release package was performed. The main application regression suite
was not rerun for this isolated experiment; its production source is byte-identical
to the verified base. POC tests exercise the new standalone surface directly.
