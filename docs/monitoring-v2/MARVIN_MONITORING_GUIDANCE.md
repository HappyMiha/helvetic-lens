# Marvin guidance across the nine Monitoring directions

Scope: MV2-023 and MV2-024, 14 September 2026. Whole user outcome: opening
Marvin on any of the nine sections or their management centre identifies that
section, gives the relevant next steps in all five product languages and keeps
navigation help available with the local model offline. Previously every route
fell back to Today and linked to the regulatory registry.

Dependencies: existing private companion conversations, established section
routes and existing configuration/evidence readers. No new source access is
needed to explain the interface. Evidence-aware answers and natural-language
monitor drafts remain separate required MV2-023 work; this feature does not
declare the parent complete or satisfy independent language/pilot acceptance.

Acceptance:

1. All nine section names and the centre have their actual route in the client
   and server context. The primary action opens the Monitoring centre.
2. The same five-language guidance catalogue supplies the UI and deterministic
   chat response. A visible help action works when the model is stopped, without
   losing a typed draft or attempting inference.
3. Help explains actual domain controls, current source/evidence checks and
   separate start/email choices. It never claims to have read private records,
   guarantees safety/deadlines, activates monitoring, submits bids or sends mail.
4. Route contexts reject attached record references and write intents. Existing
   private history isolation, detach/pause and late-response handling remain.
   Spontaneous jokes are suppressed because this context does not inspect risk.
5. Browser checks cover every route, all locales, offline help, navigation and
   mobile/keyboard use. API checks cover actual private conversation persistence,
   model-offline handling and rejected context injection. Required lint/build
   gates pass before publication; exact release activation is recorded separately.

## Implemented behavior and validation

The packaged `monitoring-screen-help.v1` catalogue is shared by the API and web
build. Exact section routes retain distinct personal conversations; no private
monitor identity, query string or form value is attached. A dedicated section
help action preserves a typed draft on success and failure. Generic questions in
this screen-only mode return explicitly labelled guidance, without inference or
an unsupported promise to answer from private records. Source-backed factual
Ask remains outside this completed navigation-help feature.

The final 44 API contract/offline guidance/backlog checks passed in 63.57 seconds.
The earlier combined run also passed the unchanged private history and explicit
monitoring-message context suites. All five catalogue locales cover the same ten
routes (nine directions plus centre). Injection/write contexts are rejected;
actual HTTP conversation persistence is exercised with a model that refuses calls.
The exact API Ruff gate and isolated root `monitoring-guidance` build passed.
The root build includes existing i18n, shell, resource, report and guide checks.
Browser acceptance evidence is recorded after the final navigation run below.

The main site remains on `1188f18190e0` while automatic attempt `4434cf94da05`
is Deploying, verified through the authenticated Deployments Refresh action.
This candidate has no verified production activation. All nine sections and
source switches remain enabled. Source credentials/coverage, evidence-aware
answers/drafts and independent language/human acceptance remain open.

A fresh source-access check followed the API Manager's My apps link and reached
its sign-in form. The open SIMAP tab also shows sign-in. Neither session currently
proves authenticated access to required keys/documents. No credentials, source
grants or new account terms were submitted in this feature.

Final built-browser acceptance: 55 full-document axe checkpoints passed, covering
all ten routes in all five locales and five real client-side returns to the
Monitoring centre. Names match the visible navigation. Tests verify offline
help, a failed help request/retry without losing the unsent draft, absence of
record/form data in context, and keyboard help activation/reopening. Desktop and
mobile screenshots were inspected. No browser runtime exception was recorded.
Other incomplete axe findings and independent human accessibility/language
review remain unverified. Source APIs and model state are synthetic fixtures.