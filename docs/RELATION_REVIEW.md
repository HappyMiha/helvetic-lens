# Relation review workflow

Helvetic Lens keeps a proposed relation separate from the organization's review of it. An administrator can confirm the lead, reject it, or add a note after inspecting the saved source evidence. These actions never rewrite an official relation, a model result, or an earlier review entry.

## Product flow

1. Open **Impact inbox** and inspect **Why this appears**, the official artifact, timeline, comparison, and relation evidence.
2. Expand **Review this proposed relation**.
3. Enter a concrete reason, evidence note, or follow-up question. Empty and two-character notes are rejected.
4. Choose **Confirm lead**, **Reject lead**, or **Add note**.
5. The complete organization review history remains below the form with decision, author, time, and note.

An annotation does not change the current confirmed/rejected decision. A later confirmation or rejection becomes the current organization decision while preserving the earlier decision. Confirmed official metadata cannot be overridden by this workflow.

Viewers can read the review history but cannot create entries. Review records are scoped to the active organization, and the API returns `404` for a candidate outside that organization.

## API and persistence

- `POST /api/relation-candidates/{organization_candidate_id}/reviews` accepts `confirmed`, `rejected`, or `annotated` with a required 3–2,000 character note.
- `GET /api/relation-candidates/{organization_candidate_id}/reviews` returns the immutable newest-first history and a total count.
- `organization_relation_reviews` stores organization, candidate, decision, note, actor, and timestamp. Updates and deletes are deliberately absent.
- The Impact Inbox exposes the latest decisive review, the latest entry, and the history count separately so an annotation cannot accidentally change the impact status.

## Baseline measurement

The same review row stores three bounded fields needed to decide whether a graph is worthwhile: `workflow_variant`, server-validated `review_duration_ms`, and `evidence_opened`. The browser starts the timer only when the administrator expands the review panel; after 30 minutes the value is capped. It records the evidence flag only when the evidence link inside that panel is used.

The platform dashboard aggregates decision-time p95, sample count, and evidence-open rate without organization names, candidate IDs, notes, source text, or high-cardinality labels. It also returns the same measures under `relation_review.by_variant`, so experimental results cannot be hidden inside an all-workflow average. Historical entries without these fields remain valid and are excluded from measured-rate denominators. The production variant remains `inbox_list_v1`; `graph_review_v1` must not be accepted by the API until an authorized prototype exists.

## Graph experiment decision gate

Use [the blank experiment template](../demo/relation-graph-experiment.template.json) outside the repository to record pseudonymous raw trials. Do not add participant names, email addresses, source text, or free-form notes. Both arms must use the same five or more tasks, separate participants, at least 30 trials and 10 participants per arm, and cover German, French, Italian, Romansh, and English. Every trial explicitly records completion, correctness, evidence use, authorization, non-color status, and the availability of the complete list alternative.

Validate a completed result from a clean checkout at the exact tested commit:

```powershell
python scripts/check_relation_graph_experiment.py C:\evidence\relation-graph-results.json --results
```

The gate fails closed if the sample, build binding, safety, accessibility, task matching, or quality evidence is incomplete. Graph quality is noninferior only when correctness and completion are within two percentage points of the inbox and evidence use is within five points. Promotion additionally requires at least 20% lower median decision time or five percentage points higher correctness.

A passing experiment without that material benefit returns `retain_inbox_list_only`; it is valid evidence that no graph should be shipped. A promoted graph is a secondary evidence view only. The timeline, list, and inbox remain complete alternatives, and no essential action may require graph interaction.
