# Organization impact inbox

The Impact inbox is a saved-data read model. It does not ask a model while the page is loading and it does not duplicate source events. One `RegulatoryEvent` becomes one card, with every organization-scoped `OrganizationRelationCandidate` grouped beneath it as an affected monitored law.

## Presentation states

Each affected law has one of five explicit states:

- **Confirmed relation** — either immutable confirmed source metadata, or a separate organization review decision. The UI always labels which one supplied the confirmation.
- **Possible impact** — the latest valid local-AI result supports a review lead.
- **Awaiting analysis** — the candidate is saved, but no valid analysis exists yet.
- **Analysis failed** — the latest attempt failed and no earlier valid result exists.
- **No supported impact** — a valid result found no supported impact, or the organization rejected the review lead.

Official relations and organization review decisions remain separate records. A model cannot modify either. A failed reanalysis is retained in history and does not displace the last valid conclusion.

## Personal and shared state

Unread, read, dismissed, and muted are stored in `regulatory_event_user_states` with organization, event, and principal keys. They only affect the current user. They never delete or mutate the shared event, another user's state, or the organization's candidate and analysis history. Anonymous development mode uses one explicit local principal.

Viewers may read the inbox and change their personal event state. Organization administrators additionally may run reanalysis, confirm or reject an organization review lead, and add a confirmed official successor to monitoring.

## Evidence and replacement links

Each affected-law row links to the monitored-law timeline, latest comparison when one exists, exact official relation or cited analysis evidence, source artifact, official source, and all saved analysis attempts. A confirmed `replaces` relation exposes reciprocal predecessor/successor labels. Adding the successor creates or reactivates its watch; it never removes the predecessor or its history.

## API

- `GET /api/impact-inbox` with `source`, `severity`, `item_type`, `watched_law`, and `state` filters.
- `PATCH /api/impact-inbox/events/{event_id}/state` with `unread`, `read`, `dismissed`, or `muted`.
- `POST /api/relation-candidates/{id}/reanalyse-jobs` creates a new attempt even when the evidence fingerprint is unchanged.
- `POST /api/relation-candidates/{id}/reviews` records an organization `confirmed` or `rejected` decision without changing source metadata.
- `POST /api/relation-candidates/{id}/monitor-successor` adds a confirmed official replacement to monitoring.
- `GET /api/relations/{id}` returns the exact saved relation and provenance for a candidate visible to the organization.

