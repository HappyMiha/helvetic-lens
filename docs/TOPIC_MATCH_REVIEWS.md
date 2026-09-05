# Shared topic relevance review

Today links each topic match to `/topic-review?match=<match-id>`. The topic's
Saved matches control also pages through retained proposals, including rejected
or stale ones. Rejecting relevance therefore does not erase the recovery route.
The decision means **relevant to this topic**, not a verified legal conclusion.

## Roles and evidence

Organization admins can confirm or reject with a 3–2,000 character rationale.
Viewers inspect evidence and history but cannot change shared relevance. Existing
local development mode permits review with a null actor; authenticated requests
obtain the actor from the server identity, never the request body. The UI labels
null actors as local/deleted accounts. Existing platform/workspace access policy
still applies; this feature grants no additional cross-organization access.

Each append-only TopicMatchReview stores date, actor ID, decision, rationale,
match/topic/revision/event/work IDs, evaluation/rule fingerprints, reasons,
confidence and the exact saved evidence metadata reviewed. Original documents
remain in their existing stores; snapshots do not copy their bodies or recursively
embed earlier review snapshots. Displayed actor names are current account names;
a deleted account leaves a null actor without deleting the review. This is
application-level append-only history, not a tamper-proof database audit service.

A current rejection suppresses only this topic's eligibility in Today. Other
qualifying topics or watched-law relationships can keep the event visible.
Confirmation can restore eligibility. Neither action changes anyone's personal
read/dismissed/muted state. Changed evidence, rules or topic revisions require a
new decision; a previous review remains inspectable and is never silently applied
to the corrected proposal. Paused/expired/unmatched proposals cannot be reviewed
as current matches. This flow makes no inference, email or legal-status mutation.

## Persistence and concurrency

- GET `/api/monitoring-topics/{id}/matches/page`: saved-match keyset pages.
- GET `/api/topic-matches/{id}/reviews`: current proposal and review history.
- POST `/api/topic-matches/{id}/reviews`: `decision`, `note`, `request_key`,
  `expected_evaluation_fingerprint`, and nullable `expected_review_id`.

Reads/writes check organization, topic revision ownership, work visibility and
current organization event admission. A revoked admission returns 404 even for a
retained historical review. Both readers default to 20 records and accept 1–50,
using date + ID ordering and a scoped record-ID cursor. Invalid/removed cursor
positions return 422 and the UI offers the first page. This is a live authorized
view: match reevaluation can move its position, so it is not an immutable export.

The writer locks the same match row as the matching worker. The expected evidence
fingerprint plus previous review ID prevents overwriting a colleague's decision
or reviewing an obsolete proposal (409). Identical retries under the same
organization request key return the original receipt without reapplying it;
reusing a key with a different actor or payload returns 409. The browser retains
the key for an unchanged retry, disables writes during save/evidence refresh and
invalidates organization-scoped feed/review resources without reloading the page.
A new account or organization remounts the review form.

Migration `fb38a72e4109` adds the review table and history indexes; it does not
rewrite existing match evidence or fabricate audit rows for older snapshots.
Operational expiry cleanup retains any match with a new review row, including a
rejection. A broader retention/export/organization-erasure policy remains separate
work. Downgrading drops the new review history, so is not a lossless rollback for
populated reviews. The regression roundtrip uses an empty review table with a
populated original match. No working or production database was migrated here.

## Checks and limits

Run `python -m pytest services/api/tests/test_topic_reviews.py -q` and the affected
organization/feed/topic suites. The two PostgreSQL concurrency cases intentionally
skip SQLite. Run them with `scripts/check_inbox_history_postgres.py` suites
`topic-review-race` and `topic-review-retry`; `topic-reviews` verifies the full
review/feed path and `topic-review-migration` the empty-history migration roundtrip.
The runner accepts only an empty disposable loopback `hl099_regression` database.

After `npm run build`, run `npm run check:topic-reviews:browser`. It launches an
isolated production Next instance and headless browser with every API intercepted.
Five-locale mobile/desktop journeys test required rationale, same-key retry,
conflicting evidence/reload, history paging and read-only viewer controls.
They are synthetic functional/geometry checks, not independent accessibility,
native-language, physical-mobile or user-research sign-off. No real AI or mail.

AI briefs, source-story deduplication, topic notification delivery, fuller source
coverage/jurisdiction presentation and the remaining HL-076 criteria remain open.
