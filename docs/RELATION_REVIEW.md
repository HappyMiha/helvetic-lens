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

The graph portion of HL-053 remains deferred until measured list/inbox use shows that a graph improves review time or correctness.
