# Private evaluation checkpoint and evidence ledger v1

MV2-070 C02c1, 11 September 2026. The internal `monitoring_evaluations` repository
stores numeric draft rehearsals. It has no route, worker, source collector or
dispatcher caller. Every returned/stored request is labelled `draft_rehearsal`;
synthetic input does not become accepted live source evidence.

## Binding and access

Generic `monitoring_evaluation_streams` and `monitoring_evaluation_entries` tables
are additive after the subject/revision migration (`a1738bc2e54f` follows
`f0627ab1d43e`). Both participate in the existing organization session policy.
Composite foreign keys prevent cross-organization attachments. A stream refers to
an existing subject configuration revision, with its full private/source binding
and canonical hash; each source series/forecast issue has a separate stream.

Every read/write checks the current authenticated owner and active workspace
membership. Writes require the existing organization-admin role. The selected
station, allergen and exact rule must match the persisted configuration. Reading
old configuration history remains possible after editing; writing an old revision,
an active/paused/archived subject, or another owner's subject fails. This internal
draft-only boundary must be deliberately replaced by accepted source and lifecycle
admission before any live workflow can use the component.

## Transaction and retry contract

`evaluate_draft` takes a `NumericBinding`, current sample, optional rapid baseline,
aware evaluation time, expected checkpoint sequence and bounded request key.
The caller owns the surrounding commit/rollback. A conditional subject UPDATE
holds a write lock through that transaction, preventing concurrent configuration
editing/deletion between admission and append. Access is rechecked after the lock.
This deliberately serializes streams for one subject; callers should keep the
transaction short and perform no network work while holding it.

Sequence zero means no stream yet. Evaluation uses the persisted checkpoint,
not a caller-supplied state or decision. A conditional sequence update and immutable
entry append share a savepoint. An entry failure or caller rollback reverts both.
Concurrent requests with the same key and complete input return one original entry;
different requests against a stale sequence receive a conflict. Retrying requires
the original evaluation time, samples and expected sequence. Reusing the key with
changed input fails. An old request returns its original entry even when the
checkpoint has advanced; use `get_checkpoint` for current state.

Each entry retains the versioned request (including evaluation time), full decision,
sequence and optional candidate material ID. Unique constraints protect sequence,
request and material identity per stream. Source replay with a fresh request key
may retain another non-material evaluation but cannot emit another transition.
`history_required` evaluations retain attempted inputs without rolling back the
checkpoint; their ledger sequence still advances. No outbox row is created.

`evaluation_history` pages descending sequence with an exclusive continuation and
a maximum page size of 100. Reads return copies of JSON. Entries are append-only
through this repository, not protected from a privileged database administrator.
Subject deletion cascades through configuration, stream and entry records.

## Remaining gates

This is checkpoint/evaluation evidence storage, not an authoritative historical
sample ledger. Source rights/freshness admission, historical correction selection
and recomputation, retention/export policy, active lifecycle, review decisions,
outbox/dispatch and user-facing history remain open. Candidate material IDs are
neither delivery consent nor proof that source gates passed. The schema can deploy
without activating Pollen Watch, and rollout remains unchanged.
