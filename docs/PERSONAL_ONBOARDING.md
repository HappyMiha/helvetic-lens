# Personal getting-started guide

Implemented in HL-073, 6 September 2026. Personal intent, navigation and first recorded actions are implemented; verified completion of onboarding is not.

## User flow

The workspace menu exposes **Getting started** at `/onboarding` on desktop and mobile. Choose **Follow a topic**, **Find a law**, or **Explore first** to save a personal intent and enter the existing topic editor, saved discovery catalogue, or Today. **Continue later** preserves an earlier intent and records deferral. Returning or signing in again retains that choice. Nothing is activated merely by opening or leaving the guide.

Four links explain source-package review, existing monitored interests, personal notifications, and saved evidence. Organization availability is read from enabled package subscriptions, active visible document watches and active topics. These facts do not prove a successful synchronization, fresh coverage, matches, or that this user opened evidence. Viewers receive role-specific guidance and retain the existing source-request/preview paths; shared-write permissions do not change. All copy exists in DE/FR/IT/RM/EN; native-language acceptance is still independent work.

## Persistence and API

Migration `fc49b83e521a` adds `user_onboarding`, unique on `(organization_id, principal_key)`. The authenticated principal is server-derived `user:<id>`; anonymous development uses `anonymous-development` only in its explicitly allowed development workspace. Records contain intent, first-start, deferral and update timestamps. They are organization scoped; user deletion cascades through the nullable user foreign key.

- `GET /api/onboarding` returns personal state and scalar organization availability without creating a record, fetching sources, enqueueing work or invoking AI.
- `PATCH /api/onboarding` accepts only `{action: topic | law | explore | later}`. Authentication and existing CSRF checks apply, including viewers. Client-supplied organization, principal or completion fields are rejected. Insert-on-conflict plus a row lock handles simultaneous first use on PostgreSQL; identical retries retain timestamps. Resuming clears deferral but keeps the first-start timestamp.
- Authentication's `onboarding_required` now tests explicit personal state, never shared-document presence. A colleague adding or pausing a watch cannot finish/reset another person's introduction.
- The browser stores this response in the existing session-scoped resource cache. Account/workspace changes clear that scope; an in-flight save checks its scope epoch and mount before applying results or navigating. Errors leave the choice available for retry.

No terminal `completed` state exists; `completion_verified` is always false. Merely clicking a navigation link is not a measured milestone. Enabling source packages, saving topics and notification preferences still use their existing explicit confirmation and permission boundaries.

## Verification and remaining work

API regression covers passive reads, active/paused watches, duplicate actions, defer/resume, forged fields, CSRF, viewer permissions, separate users in the same organization, workspace switching, logout/login and additive migration preservation. Disposable PostgreSQL additionally checks migration and two simultaneous first-use requests. `npm run check:onboarding:browser` runs the production UI with synthetic intercepted APIs across five languages, 390/1440px and admin/viewer roles; no real emails, models or sources are contacted.

Remaining HL-073 requirements include independently measured first value and recovery beyond Today. Today now has distinct actionable empty/degraded states; see [empty-feed recovery](EMPTY_FEED_RECOVERY.md). Do not infer complete live coverage or user comprehension from these recorded actions. Normal code publication does not authorize applying this migration to production.


## First recorded actions

Migration `fd50c94f632b` adds `onboarding_milestones`, unique on organization, server-derived principal and one of three kinds. Each stores the first timestamp and object kind/reference, without copying the document, question, email or model output. The personal GET returns only kind, object kind and date. It does not expose the object ID or another user's milestones. There are at most three rows per principal/organization; retries and later shared changes do not rewrite first dates. Existing use is not retrospectively inferred from current shared objects.

- **Interest saved:** successful topic creation or explicit HTTP document-watch creation records the actor in the same transaction. Internal automated document ingestion does not award a personal milestone. Existing idempotent topic replay or rejected duplicate document does not credit a second actor. A failed transaction leaves neither an interest, queued topic job nor milestone.
- **Notification choice saved:** explicitly saving personal digest preferences records the first choice, including opting out. Opening a preview, requesting email delivery or merely reading preferences does not imply this choice. Existing delivery consent and permissions remain unchanged.
- **Saved text displayed:** the existing native and legacy evidence viewers observe actual non-empty text intersecting the viewport while the document is visible. Missing passage targets, demo evidence, metadata-only views and hidden-tab loading are excluded. Pagination does not repeat a successful write during the mounted viewer. `POST /api/onboarding/evidence-displayed` accepts only a saved version kind/ID; the server rechecks current organizational access, non-demo metadata and non-empty saved text using scalar queries before recording. It never treats a passive GET, route prefetch, or artifact download as a display event. Viewers may record their own event through the existing CSRF boundary. Failed recording is silent and has one bounded retry, so it cannot prevent reading.

The guide displays first recorded dates separately from its navigation steps. No completed badge or inferred understanding is added: the display signal is browser-reported, not independent proof a human read or understood a source. `completion_verified` remains false. No model, external analytics service, source fetch or outgoing email is involved. Applying the additive migration to production is a separate deployment action.


## Personal source selection review

The Sources package section now offers **Save my source choice** after the existing package descriptions, coverage limitations and activation/request controls. It summarizes which packages are enabled. With no enabled packages, it explains the coverage gap and that directly watched documents remain a separate path. Saving is available to viewers as well as administrators and does not activate, deactivate, request, synchronize or send anything. Opening the section never saves a review.

Migration `fe61da50643c` adds one `personal_source_reviews` row per organization and principal, separately from intent and shared subscriptions. It keeps the first-review timestamp, latest changed-review timestamp and latest acknowledged selection: catalogue revision plus sorted package IDs, definition revisions and enabled flags. It is a decision record, not an append-only review history. Passive onboarding reads return the caller's review and whether that selection still matches. They do not expose another person's choice or equate it with reading comprehension, live health or full coverage. Source schedules and runtime health are not part of this selection equality; their existing status remains independent.

`POST /api/onboarding/source-review` requires this exact displayed selection and existing CSRF protection. The server re-reads active starter subpackages and the current organization's subscriptions through bounded scalar queries. An outdated catalogue/revision/subscription, missing package or duplicate entry returns 409 without rewriting the prior review. The user can reload the source selection and save again. Duplicate retries retain dates; a new selection retains the first date and updates the latest date. Changes after saving make the review non-current on subsequent reads, rather than being overwritten by an old success response. Account/workspace changes and unmounts prevent applying stale client results.

Input and projection are bounded to 100 subpackages (current catalogue: five); exceeding that limit requires a different review workflow rather than silently omitting packages. Payload identity and unknown fields are rejected. Anonymous development remains explicitly scoped to its development principal. No personal intent is created merely by recording a source choice, and `completion_verified` remains false. The guide links a saved or stale review back to Sources. This completes the explicit source-choice persistence portion of HL-073, not independent first-value acceptance.
