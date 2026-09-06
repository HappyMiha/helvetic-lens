# Personal getting-started guide

Implemented in HL-073, 6 September 2026. This is a starting-intent and navigation slice, not verified completion of onboarding.

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

Remaining HL-073 requirements include independently measured first value, actual persisted interest/evidence milestones and distinct actionable empty/degraded states. Do not infer those from this guide. Normal code publication does not authorize applying this migration to production.
