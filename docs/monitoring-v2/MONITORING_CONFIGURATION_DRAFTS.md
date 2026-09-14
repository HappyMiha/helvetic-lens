# Natural-language changes in native monitoring editors

## Scope selected 14 September 2026

MV2-023 acceptance criterion 4, with MV2-017/018 editor integration. Dependencies:
the nine existing native configuration contracts and editors, MV2-010/020, and
the MV2-051 independently reviewed model capability boundary. Parent tasks remain
IN PROGRESS. This feature edits an explicitly supplied configuration; it does not
claim complete conversational creation, geocoding, source onboarding or activation.

All nine directions remain visible. No additional source acquisition is needed:
only the configuration and request explicitly submitted by the signed-in editor
are sent to the configured model. Station, location and transport reference IDs
are retained. IP deadline assumptions cannot be inferred by the model. Credentials,
source documents, evidence histories and other users' monitors are not inputs.

## Acceptance criteria

1. Each native editor offers an explicit natural-language request. A valid existing
   configuration is required. A returned proposal is loaded only on explicit action,
   remains an unsaved native editor draft, and still uses native preview/save.
2. Responses must satisfy the exact native configuration schema. Unknown fields,
   malformed JSON, duplicate keys, non-finite numbers, invented reference IDs and
   unsupported requests produce no usable proposal. No external command is executed.
3. Generation uses an independently reviewed `monitoring_configuration` task/locale
   grant bound to the actual runtime and measured token budget. Missing review,
   unavailable models and provider failures preserve manual editing.
4. Requests/results are transient and not integration-log bodies. Current membership
   is checked before and after generation. Responses carry request/configuration,
   locale, prompt and capability bindings. Changed editor state discards late results.
5. Five locales, keyboard access, mobile layout, offline/manual fallback, explicit
   apply without persistence, cancellation, schema failures and privacy have tests.

## Implementation and local verification

All nine native editors expose the same explicit request / proposal / open-in-editor
flow, both on their own pages and in `/monitoring/settings`. Loading a proposal
clears old preview state and moves focus to the native fields. Normal native
preview, optimistic save and consent boundaries remain authoritative. An editor,
identity, locale, request or visibility change cancels/discards pending output.
Hazard's fields now use controlled state, including point/municipality choices;
Auction's separate budget, reminder and multiline inputs are kept in sync.

`POST /api/monitoring-centre/configuration/draft` accepts a bounded configuration
and explicit request. It returns a transient proposal with request, configuration,
locale, prompt and capability bindings. Current membership is checked before and
after inference. Native schema validation rejects missing top-level settings as
well as malformed/duplicate JSON, unknown authority fields and protected changes.
This prevents omitted values silently resetting to defaults. The route has a
per-user limit of six requests per minute, one generation attempt and a shared
60-second inference budget. It returns no provider prose or raw provider errors.

A fresh ModelClient deliberately has no IntegrationLogger. The application keeps
its normal content-free administrative request audit; no prompt/configuration or
generated body is retained. There is no monitor mutation, collection or delivery.
An independently reviewed `monitoring_configuration` task/locale grant must match
the observed model runtime and measured token budget. A profile can hold all
twenty scopes (four tasks, five locales); every scope still needs its own verified
review artifact. This change does not create any production approval.

Local checks:

- 136 API/capability regression tests passed in 106.17 seconds. The final expanded
  feature/backlog suite passed 51 tests in 11.21 seconds; the twenty-scope artifact
  integrity test passed separately after the registry capacity change.
- Exact `ruff check services/api deploy/release_manager.py`, the root build
  (including existing web contract checks and TypeScript), and diff checks passed.
- `npm run check:monitoring-configuration:browser` passed 94 full-document
  browser/axe checkpoints: nine saved native editors, five locales, 390/1440 px,
  explicit unsaved apply, offline fallback, mismatched and late responses, and
  controlled point-location preview/focus. Synthetic saved configurations and
  model replies are used; these checks are not a live model-quality evaluation.
- Browser verification found and fixed a narrow-screen overflow in the native
  Air/River rule fieldsets with long French labels. Mobile and desktop screenshots
  were inspected. Other axe incomplete findings remain in the test report and
  are not certified accessible by this run.

The model-semantic evaluation, independent language/human acceptance and exact
production activation remain open. MV2-023/017/018 are not DONE.
