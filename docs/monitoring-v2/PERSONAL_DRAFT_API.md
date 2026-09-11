# C01b1 — private draft HTTP API

Implemented for the Monitoring instance, disabled by default. This API stores
validated personal settings; it does not establish live coverage or start delivery.
It uses the existing session cookies, workspace context, CSRF, audit and rate limiter.

## Access boundary

`Settings.monitoring_rollout` / server environment `MONITORING_V2_ROLLOUT` accepts
the MV2-001 policy. The current draft implementation requires global enablement
and one exact `shadow` grant for the authenticated workspace, `pollen-watch`,
template version 1. Other workspaces, conflicting grants, legacy mode and enabled
mode without accepted sources remain unavailable. The instance must be
`monitoring-v2`. No route grants this policy and no deployment configuration was
changed to activate it. Passing environment settings into the managed serving
containers remains an explicit later rollout operation.

Anonymous development mode never supplies a personal identity. Active workspace
membership and ownership are checked by the repository on every operation.
Administrator membership can write its owner's drafts; viewers can read their
own drafts but cannot mutate them. A workspace administrator cannot read another
member's private draft. All responses, including errors, use `private, no-store`.

There is one 60-request/minute bucket per authenticated user for this route
family, including reads. Varying subject IDs does not create a fresh bucket.
Existing app body limits, bounded configuration fields, request keys and list
limits also apply. This is an initial bound, not a completed C06 workload study.

## Routes

All paths below start with `/api/monitoring-subjects`. Mutations require the
existing CSRF cookie and matching `X-CSRF-Token` header.

| Method/path | Request | Result |
|---|---|---|
| POST root | `request_key`, validated `configuration` | 201 private draft/current revision; original key replay cannot overwrite later edits |
| POST `/preview` | `configuration` | Configuration-only result, unknown coverage, empty source series, explicit Start blockers; no draft/job created |
| GET root | `limit` 1–100, optional UUID `cursor` | `items`, `next_cursor` |
| GET `/{id}` | UUID subject ID | Current owned subject/revision/configuration |
| PATCH `/{id}` | `expected_revision`, `configuration` | New immutable configuration revision, or 409 on stale/non-draft state |
| GET `/{id}/history` | `limit` 1–100, optional positive `before_revision` | `items`, `next_before_revision` |
| DELETE `/{id}` | JSON `expected_revision` | 204, removing the draft and its private history; conflicts remain 409 |
| POST `/{id}/start` | `expected_revision` | Always rejects pending source/live acceptance with `pollen_source_not_ready`; no state/job/delivery change |

Create input forbids caller-supplied ownership, rollout or source-ready fields.
Configuration is the versioned [Pollen contract](POLLEN_CONTRACT.md). Error
responses omit submitted values; request bodies are not placed in audit records.
The existing audit still records authenticated mutation paths/statuses, including
preview and rejected Start requests.

List order is creation time descending, then UUID ascending. The cursor anchors
to a still-owned row; a foreign, missing or deleted anchor returns 404 and the
client should restart pagination. Equal timestamps are supported. History pages
continue below the last immutable revision number; new revisions do not move an
older continuation. No cursor relaxes workspace or owner predicates.

## Remaining acceptance

This is C01b1, not full C01b. Source/coverage/category acceptance, operational
rollout, successful explicit Start, active/pause/archive lifecycle and UI remain
open. The preview must be labelled as validation of configuration; never display
its empty arrays as a current zero concentration or as proof of a forecast.
The blocked Start route is a temporary enforced boundary, not acceptance of the
user's complete Pollen Watch scenario.
