# CV Studio v24.6.558 — Sourcer activity and failure highlight

Local unmerged source on `codex/job-read-queue-recovery`, including v555–557.
The complete LinkedIn Sourcer control card, including its heading, has an orange
border, warm fill and the shared gentle pulse while a valid search runs. Busy
cleanup keeps the highlight until the run settles. Success and normal Stop clear
it. Search failure leaves a static red outline/tint with the existing error text.
Starting a new valid search or Clear resets failure. Reduced motion removes the
orange animation; Stop remains enabled. The adjacent candidate results card and
provider/consent/accounting/browser/storage contracts are unchanged.

Validation:

- Existing Sourcer UI fixture passes with activity assertions for held planning,
  success, reservation failure, successful retry and Stop during location setup.
  Its DOM mock now supports classList. Candidate-folder and assessment fixtures
  also pass. No new mirrored test suite was added for this visual change.
- Five version-source checks, JavaScript syntax, repository consistency and
  whitespace checks pass. Included v556 previously passed all 96 JS fixtures.
- Chromium uses the actual UI/core with intercepted fictional API and companion
  replies. Held planning shows the orange border and animation across the card;
  Stop remains usable. Empty successful search and normal Stop clear activity.
  Synthetic planning failure shows a red border with its error; Clear resets it.
  Reduced motion removes animation and mobile widths fit. No page errors or live
  provider calls. Screenshots under `/tmp/cvstudio558/`: `sourcer-running.png` and
  `sourcer-failed.png`. The fixture server was restarted when no longer listening.

Not pushed, merged, installed or verified against a live signed-in LinkedIn page.
