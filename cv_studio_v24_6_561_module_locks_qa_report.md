# CV Studio v24.6.561 — module lock preferences

Local source on `codex/module-lock-preferences`, from merged v24.6.560 / PR299.
CV Summary is permanently unlocked: no prompt or saved unlock flag is needed and
new versions do not relock it. Existing compatibility helpers remain callable.
Static/dynamic tab labels identify CV Summary immediately.

LinkedIn Sourcer uses code1212 with the existing version-scoped local/session
unlock storage. Tab navigation, deep-link navigation and direct Start calls
require unlock. Locked initialization does not start browser/provider work.
The tab keeps its name with a lock icon, and correct unlock updates its title.
Shared companion setup/update support for Job Leads remains callable.

The owner corrected the initial request before implementation: Lead Finder stays
locked. Its code1571, frontend gates/payload and backend route guards are unchanged.
This is the existing local tab-code pattern; no backend route or storage schema
changes were introduced. Paid consent and AI accounting are unchanged.

Validation: actual Chromium checks Summary without prompts across reload and a
simulated new build; Lead Finder still rejects1212; Sourcer wrong/cancelled codes,
direct Start while locked, correct1212, reload persistence and next-version reset.
No paid requests or page errors. Existing Sourcer UI fixture checks that locked
initialization/direct Start send no browser or paid requests. Five version-source
tests, all 96 JavaScript fixtures, syntax, whitespace and repository consistency
pass. No live provider action,
push, merge, installation or external mutation.
