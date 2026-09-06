# Contextual topic setup

Today, event discovery/registry, Impact inbox, a monitored document and a comparison
now offer **Monitor this topic**. The shared control opens
`/topics?from=event|law|comparison&record=<id>` and preserves the interface locale.
It does not create a monitor, request a model or subscribe to additional sources.

## Review before activation

The organization-scoped `GET /api/monitoring-context?kind=...&id=...` resolves the
saved title, reference, HTTP(S) publisher link and accessible saved evidence.
Titles and goals never come from URL query text. A private Law, Comparison or
RegulatoryWork is unavailable even through the helper's privileged-session path.
Public discovery metadata can be inspected without granting access to an
unadmitted saved document body. Evidence links reuse the shared exact-version
access policy. Up to twenty current-organization document watches are shown,
including paused watches, with a link to the registry if more remain. These are
existing watches, not suggestions of a confirmed legal relationship.

**Use as a topic starting point** explicitly copies a name and editable goal into
the existing editor. It leaves concepts blank: a long legal title is not silently
turned into a keyword query. The user chooses the actual matching concepts and can
edit every field. Enabled organization source packs provide the existing editor's
defaults, not a new subscription. The jurisdiction/language defaults are visible
editing choices, not metadata inferred about this particular document.

A recovered tab draft is never overwritten by context. A dirty current draft
requires the existing discard decision. The normal read-only preview then checks
at most 500 admitted saved events and shows at most ten matching examples with
sample/coverage limitations. It neither predicts future volume nor calls AI.
Only the existing explicit administrator activation creates the shared topic,
with the same idempotency key/retry lifecycle. Success links directly to the saved
topic. Changing a plan invalidates its old preview as before.

## Choose the monitoring type

The Topics page and every resolved contextual entry now offer three explicit
paths. This is a shared entry chooser, not another event store or an automatic
model action:

- **Topic:** focus the existing manual editor or explicitly copy the saved context.
  Terms and coverage stay user-chosen, followed by bounded saved-match/source
  readiness/duplicate review and the existing authorized, idempotent save.
- **One law or document:** open the existing AddDocumentDialog. A valid HTTP(S)
  source URL and its document title are initial editable values; generic chat
  messages without a source leave both fields blank. URLs with credentials or
  other schemes are not prefilled. No fetch happens on opening. The existing
  explicit preview enables saving, then the created document page opens directly.
  An already active or paused contextual watch offers its existing page instead
  of another creation action. The dialog also retains its URL-duplicate check.
  Viewers can open existing watches but cannot add a shared document.
- **Source package:** navigate to `/sources#source-packs` to inspect the existing
  catalogue's coverage, languages, cadence and current subscription state. After
  asynchronous loading, that section receives focus below the sticky header once,
  without stealing focus again on subscription refresh. Activation remains an
  explicit admin action; viewers use the existing structured request workflow.
  A package supplies sources to the radar; it is not itself a topic or law watch.

Leaving a dirty topic draft through these paths uses the existing explicit
accept/cancel confirmation. Navigation never enables a package, fetches a
source, saves a document, creates a topic or invokes inference. The existing
preview/activation endpoints and authorization policies are reused, not replaced.

`npm run check:monitoring-choices:browser` covers 30 intercepted journeys over five
locales, 390/1280/1440px and both roles, including actual preview/save/direct-link
and package activation/request actions against synthetic APIs. This does not prove
a deployed live-source end-to-end journey, source availability, shared cross-kind
transaction/idempotency, independent native copy or physical-device accessibility.
The new chooser does not carry a topic draft into the source-package request or
preserve permanent origin metadata on the resulting document/package.

## From a saved cited answer

Ask and AI history now offer the same Monitor this topic action beside succeeded,
supported answers with citations. The URL contains `from=answer` and the saved
Ask record ID, never the question, answer or a model-generated URL. The context
endpoint explicitly checks the Ask record's organization, visible comparison/law,
and both saved versions' owner and law bindings. Failed/pending/unsupported or
uncited records, malformed citation metadata, and citations to unrelated versions
are unavailable, including to a privileged session inspecting this organization.

The editor shows the recorded user question and answer timestamp beside the saved
document title. Only **Use as topic starting point** copies the question into an
editable goal; concepts remain blank and required. Existing dirty/recovered drafts
are protected. The usual source-readiness and duplicate review, bounded preview
and explicit authorized save remain unchanged; viewers retain their personal draft
flow. No automatic extraction of search rules or additional inference occurs.

The context read projects only the question, timestamp and supported/citation
metadata, never the answer prose, chat transcript, full comparison diff or document
bodies. It does not increment answer reuse counters or create monitoring/history
records. Citation metadata is an eligibility check against the saved answer's
existing validation; this action neither redisplays quotes nor independently
revalidates their legal meaning. Old answers are not represented as current legal
conclusions. The return link opens that saved comparison's Ask panel; it does not
promise to locate an older turn beyond the existing history display window.

Tests execute an actual synthetic Ask first, then verify unchanged inference and
record counters, explicit owner guards and malformed/unsupported cases. Separate
PostgreSQL checks cover JSON projection and private-version denial. Browser checks
exercise Ask/history button eligibility, actual navigation to the original question,
explicit editable goal copy, no question text in URLs, both roles and five locales.
The personal Marvin message entry is described below. The shared chooser above
now offers all three paths; durable origin metadata on the saved topic and
unbounded historical-turn deep links remain separate work.

## From a personal Marvin message

Each displayed saved **user** message in Marvin has a Monitor this topic action.
Assistant replies, spontaneous remarks and unsent text do not. Navigation closes
Marvin and carries only conversation/message identifiers, never private prose.
The topic editor shows the selected message/date and a five-language privacy note:
the conversation stays personal; explicitly saving a topic makes the chosen,
editable name/goal visible to the organization. Matching terms remain blank and
required. This action works even when the local model is stopped. It is manual
intent selection, not semantic detection of a monitoring request.

`GET /api/monitoring-context?kind=assistant&id=<conversation>&message=<message>`
requires the current principal and organization. Another member or administrator
cannot read somebody else's personal conversation through this endpoint. It
selects one existing conversation's bounded message JSON (at most 40 retained
messages), not its draft/handoffs or an ORM conversation object. Only the selected
nonempty user message (at most 2,000 characters), its recorded date and authorized
context metadata are returned; no assistant replies/transcript are serialized.
A missing/expired/duplicate/invalid message fails closed. A law/comparison context
re-resolves current authorized metadata and existing watches, not the chat's cached
title. Other routes carry the personal message alone, with no fabricated source,
legal claim or entity link. There is no arbitrary historical-chat deep link.

The resource key includes both IDs and uses session scope, reset on account or
workspace changes. Selecting another message in the same conversation cannot
reuse the first message's cached content. Context navigation does not overwrite a
current draft; explicit replacement uses the existing accept/cancel confirmation.
Viewers retain personal drafts and preview, but cannot activate shared topics.
No model call, topic write or chat mutation occurs in the context endpoint. The
existing Marvin component still opens/updates its route conversation as before;
this slice does not redesign that existing lifecycle or retention policy.

`npm run check:marvin:monitor:browser` checks 20 intercepted production-UI journeys
across five locales, 390/1440px and admin/viewer roles. API and PostgreSQL tests
cover privacy, bounded retention and no inference/shared writes. This is not a
native-language, physical-device or independent research sign-off. Durable topic
origin metadata and older message recovery remain separate work. The shared
chooser above now offers law, topic and package paths.

## Viewer behavior

Viewers can now edit a **personal browser-tab draft** and use the same read-only
preview. The existing user/organization-scoped sessionStorage recovery keeps it
for up to 24 hours; closing the tab, denied storage or expiry can remove it. This
is not cross-device storage, an admin request or shared active monitoring. The UI
states that boundary. Restoring the draft never restores an accepted preview.

The server permits the exact preview endpoint to viewers, subject to existing
session/CSRF checks and a 30-per-five-minute preview limit. Creating/editing shared
topics, requesting AI drafts, history scans and status mutations remain blocked.
The UI hides activation/edit controls and disables AI drafting for viewers.

## Verification and remaining scope

- `test_monitoring_context.py` covers native context without writes/body hydration,
  existing paused watches, law/comparison identity, private records, invalid input,
  publisher fallback, preview without activation and idempotent explicit creation.
- `test_monitoring_topics.py` proves the authenticated viewer preview is allowed
  while shared writes and AI drafting are rejected.
- `check:monitor-this:browser` exercises twenty five-locale × mobile/desktop × role
  journeys with synthetic APIs, including explicit copy, editable concepts,
  preview, save/deep link, viewer reload/restore and missing-context handling.
- Scratch PostgreSQL runner suites `monitoring-context` and
  `monitoring-context-activate` verify the actual SQL/API flow in empty local DBs.

HL-077 remains IN PROGRESS: the shared chooser now links contextual topics,
document previews/existing watches and source-package review. Consistent richer
metadata/cadence across all previews, broader semantic-equivalence suggestions
beyond the same-rule warning, predicted volume, and structured viewer topic
requests remain open. Saved cited Ask/history answers and
personal Marvin messages now have their own contextual entry. Selected-source operational readiness and configured cadence are now shown by
the explicit preview (see `MONITORING_TOPICS.md`). This records subscriptions,
schedules and health without predicting actual future delivery or volume.
No production deployment, migration, live source/model call or message is required
by this implementation. Native-language and independent user acceptance stay open.
