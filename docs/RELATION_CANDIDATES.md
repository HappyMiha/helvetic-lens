# Explainable relation candidates

HL-044 runs after each committed connector page and narrows a new regulatory event to a bounded set of monitored works. It does not call an AI model and does not treat similarity as legal evidence.

## Retrieval and evidence

Confirmed connector relations from official metadata, ELI/SR identifiers, court citations, and exact source fields are reused directly. Their existing relation ID and provenance remain authoritative.

The second stage searches only watched works. PostgreSQL uses a `simple` multilingual full-text GIN index over normalized work titles; deterministic scoring then records title-token overlap, exact SR/RS overlap, article overlap, authority, and compatible document types. A title or full-text match creates a `proposed` `potentially_impacts` relation with `candidate_only=true`. It cannot replace or supersede a confirmed relation.

Each shared candidate stores the event, source and target works and versions, score components, human-readable reasons, rule revision, source URL, status, and expiry. `organization_relation_candidates` delivers that same row to every organization watching the target, with its own workflow status and watch reference.

Defaults cap retrieval at 20 candidates per event and delivery at 10 per organization per event. `RELATION_CANDIDATES_PER_EVENT`, `RELATION_CANDIDATES_PER_ORGANIZATION`, and `RELATION_CANDIDATE_TTL_DAYS` can tighten those limits. Reprocessing an event is idempotent; expired rows are marked before new retrieval.

## Labelled regression gate

The checked-in fixture covers enactment/amendment wording, repeal, a parliamentary initiative, a court decision, an official notice, an exact confirmed relation, and an unrelated control. It requires all six relevant cases to be retained and the unrelated control to remain absent. This is a small deterministic gate for rule changes, not a production relevance claim. HL-051 may add embeddings only if a larger labelled evaluation later proves a material recall gap.
