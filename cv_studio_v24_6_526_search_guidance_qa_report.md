# v24.6.526 search guidance - QA and handover

Base: merged v24.6.525 / PR269 / `0c30448`.
Branch: `codex/v24.6.526-search-guidance`.

The owner requested the red outline guidance from contact creation in Job Leads
and LinkedIn Sourcer. The changes remain in their existing frontend controllers
and scoped CSS. Only summary IDs were added to the shell; generated version
surfaces were stamped with `bump_version.py`.

## Behavior

- One next-step target per active module workflow. Normal guidance is separate
  from `aria-invalid`; only failed input validation marks the input invalid.
- Editing moves the outline and clears invalid state. Collapsed option panels
  reveal missing inputs before focus. No focus is moved by ordinary typing.
- Job Leads guides ad keywords/limits/open-tab discovery, companion setup,
  company/role/link and Save, selected search imports/previews, and single/bulk
  HR country/keywords/pages. Selecting ads switches to bulk HR guidance.
- Sourcer guides the brief, explicit paid consent, limits, tab discovery/setup
  and Start. An interrupted run points to Stop first. Its resolved local
  validation notices clear on edit without clearing unrelated remote errors.
- Busy modules clear their guide targets. Existing activity indication, disabled
  controls, Stop, persistence, account isolation and consent remain authoritative.

No backend route/response/storage, provider or companion reader behavior changed.
There is no new automatic action, paid request, replay or owner record update.
Updating the app is required to use this UI; no companion capability was added.
The hosted Apollo service remains524, independently of this UI checkpoint.

## Validation

- All82 root JavaScript fixture files passed. The extended Sourcer UI fixture
  covers consent, invalid limits, interrupted-run Stop and outline clearing.
  The new Job Leads fixture covers search/form/HR/bulk edits, connection guidance,
  no work for invalid settings, clearing during a scan and Stop/non-replay.
- Five version-source Python tests and repository byte/asset consistency pass.
- Source/protected-asset preflight passes, including tracked syntax, real local
  Windows Antiword/Tesseract verification and embedded JavaScript. No package
  was built and no macOS native result is claimed for this local checkpoint.
- Native Chromium guidance tests pass against an isolated fictional server:
  computed red outlines, keyboard focus/native form validation, hidden options,
  no stale invalid attributes after edits, bulk settings, connection summary,
  clear outlines while busy, Stop before paid work and mobile width.
- Guidance tests intercept provider/browser responses; no AI request or record
  save is sent. Source fixtures contain fictional data only. Ignored screenshots
  are in `runtime/search-guidance526`.
- The existing native525 actual-app workflow also passes with this UI change:
  shared-ad missing-date writes/retry/Stop, manual confirmation, contact filters/
  Excel/verifier, guided JobAdder creation/recovery and mobile. Its writes and
  provider responses are fictional and isolated from owner records/accounts.

The complete Python/backend suite was not repeated for this frontend-only change;
merged525 has its own complete regression record. No installed owner app or
hosted service was changed, and no PR/merge is authorized for526 yet.
