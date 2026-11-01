# v24.6.528 Signed clients list - QA and handover

Base: merged v24.6.527 / PR #273 / `3ea7880`.
Branch: `claude/job-leads-signed-clients` (restarted from that master).

The owner reported that after reloading and ticking statuses in Job Leads >
Signed clients, no clients were shown. Two causes were found in the view:
Reload statuses discarded ticks that were not saved yet, and saving statuses
did not list any clients until the owner opened "Find signed clients in
JobAdder" further down and clicked Search. One more possible cause was made
safe, because the live JobAdder company list could not be inspected from the
build environment: a company listed without a status was dropped.

## Behavior

- **Reload statuses** keeps unsaved ticks (only statuses JobAdder no longer
  lists are dropped) and says the ticks are not saved yet.
- **Save statuses** saves, opens the client list and loads the first page of
  signed clients at once. If the list cannot be read, the message says the
  choice was saved and why the list failed.
- **Opening the view** with statuses chosen, none stale and nothing followed
  lists the signed clients straight away. With clients followed it does not
  read the list.
- **The list** keeps companies JobAdder lists with a chosen status, and now also
  companies listed without a status (shown unlabelled). Companies listed with
  another status are still left out, and only a chosen status is ever shown as
  a label. Follow still re-reads the company and refuses it unless its own
  status is a chosen one.
- **An empty page** where JobAdder listed companies but none had a chosen status
  says how many were checked and offers Next. The service returns this count as
  a new `checked` field.

No route was added or changed (still 124, same SHA). JobAdder is only read.
There is no new automatic LinkedIn action, paid request or companion change.
Updating the app is enough; the companion needs no reload for this version.

## Validation

- **Python:** see below. New service tests: companies listed without a status,
  or with a status without an id, are kept unlabelled; another status is still
  left out; `checked` is returned; Follow refuses a company whose own status is
  not chosen.
- **Node:** the Signed clients page test covers Reload keeping unsaved ticks,
  Save listing the clients, the first open listing them only when nothing is
  followed, the explained empty page with Next, and a saved choice when the
  list read fails.
- **Deliberate breaks:** 13 (each new behaviour removed in turn); all caught.
- **Real browser:** Chromium against the fictional demo server. Two statuses
  ticked, Reload statuses kept both ticks, and Save listed the 4 signed demo
  clients without a Search click (the Prospect company was left out).
  Reopening listed them again. No horizontal overflow at 390 px.
- No live JobAdder or LinkedIn call, no paid call and no owner installation
  change was made.
