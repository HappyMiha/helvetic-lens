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

HL-077 remains IN PROGRESS: this slice creates contextual **topics** and links
existing watches. It does not yet unify new law-watch/source-pack subscription
choices, detect semantically equivalent topics beyond the same-rule warning, show predicted cadence/volume,
submit a viewer proposal to administrators, or add per-answer/global-assistant
entry points. Selected-source operational readiness and configured cadence are now shown by
the explicit preview (see `MONITORING_TOPICS.md`). This records subscriptions,
schedules and health without predicting actual future delivery or volume.
No production deployment, migration, live source/model call or message is required
by this implementation. Native-language and independent user acceptance stay open.
