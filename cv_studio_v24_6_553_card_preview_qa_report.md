# CV Studio v24.6.553 — click-card previews

Local work on `codex/job-card-click-preview`, from merged v24.6.552 / PR296.
Not pushed, merged or installed on the owner's machine.

Clicking a job-search card opens the existing preview. The redundant Preview
button is removed; the role title is a visually plain native button supporting
Enter/Space and a visible focus indicator. Selection controls, links, read/retry
buttons and expandable descriptions keep their own actions. Selecting text
inside a card does not activate the preview. The surrounding search panel's
`details` element does not block card clicks. Busy guards, cached content and
list scroll/focus/expanded state remain preserved. No capture starts on a
preview click.

All 95 frontend fixtures and five version-source tests pass. The existing
Chromium background workflow now exercises title/company/initials card clicks,
keyboard activation, checkboxes, summaries, LinkedIn links, text selection and
390px mobile preview visibility, plus existing capture/cache/focus/scroll/Stop /
Clear behavior. No page errors or unblocked external requests occurred. Syntax,
whitespace and repository consistency checks pass.

No new routes, storage or companion behavior. Tests use fictional browser and
local fixture data; no live LinkedIn/provider action was performed.
