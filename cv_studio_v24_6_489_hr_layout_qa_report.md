# Saved-ad HR layout / pagination corrective — v24.6.489

Base master `d9b91d9`; branch `codex/v24.6.489-hr-layout`.

The owner clarified that the failure occurs under Find HR people on a saved ad.
Read-only live Brave inspection found a correct company filter and visible HR
results. Ten modern cards were nested as list/wrapper/listitem; only the first
wrapper had a SearchResults key. The old selector matched one card. Page-two
URLs also contained native spellCorrectionEnabled/prioritizeMessage options,
which the worker treated as a different search. Both defects were reproduced
with failing synthetic tests before implementation. This does not establish
which reader exception caused the owner's earlier generic error.

The correction adds the bounded wrapped-item selector, excludes only the two
native pagination options from identity, and safely waits when the Locations
button has not hydrated before a click. Fixed reader errors now distinguish
company, country controls, result reading and paging. No arbitrary exception
or page text is returned. Existing company/country/keyword authority, five-term
query groups, budgets, profile ownership, storage isolation and action non-replay
remain in place.

Verification:

- All 49 JavaScript suites passed, including new paging-metadata/identity tests.
- Existing company HR controller, reader, joining-date, keyword-group and
  suspension/non-replay fixtures passed.
- Focused Python HR service, Sourcer route and version tests passed.
- Real isolated Chromium with the actual companion worker/content reader and
  intercepted fictional LinkedIn pages read all ten wrapped cards, all eleven
  keywords across three groups/six result pages, both Any country and Malaysia,
  native paging flags, delayed navigation and unchecked-company rejection.
- No real profile details or private browser data entered fixtures or Git.

No installed companion update, live completed HR scan, owner record write,
outreach, paid provider call, PR, push or merge is claimed. The local integrated
follow-up branch will retain the separate awards and email corrections.
