# Personal dossier research updates

Status: VERIFYING — scoped stage 4e, release 1.20 implementation and local gates pass; exact production acceptance is pending.

## Scope recorded before implementation

MV2-021/022: a personal in-app following and research-update journey for both
Pharma and Loyer. Extend the existing public follow/read-marker contract to
include completed living research; add opt-in private dossier following for every
current reader, including invited guests. The existing Following page presents
both audiences, bounded lists and an expandable evidence-linked update history.
No subscription is created for another person. Following does not enable email,
publish material or change monitoring/research authorization.

One update represents an actual completed investigation with newly captured
source evidence. Use its retained completion event, not a progress tick, failed
run or wall-clock animation. Unchanged recurring captures do not create updates.
Show actual source/finding/comparison counts and bounded exact source quotes;
possible contradictions remain machine proposals with both original citations.
Read markers are personal and shared between the dossier and Following page.
Opening an update is not review; an explicit acknowledgement cannot mark a newer
completion seen. Unfollow/refollow and exact retries preserve revision guards.

Dependencies: native accounts/sessions and organization locks, current dossier
roles/guest scope, ProductPublication/PublicDossierFollow, InvestigationEvent,
immutable captured evidence and ClaimChange, the existing product gateway and
brandbook UI. Native Monitoring's Today/review queues remain authoritative for
their source observations; this projection describes completed dossier research,
not a second source-review state. Reuse current jobs and evidence, adding no
scheduler, provider request or copied notification contents.

Readiness: all required records are already stored in the native database;
source exclusions, both sides of saved-page access and public contribution/
revision eligibility have shared SQL predicates. No new external source rights,
model configuration, email account or provider registration is required. One
additive migration stores private personal follows and public research read time.
Cascade ownership integrates with the native account-erasure inventory.

Acceptance before scoped DONE:

- Actual private/public native research completion produces one accessible update;
  active/failed/empty/unchanged research produces none. Personal opt-in and current
  counts/history work across more than one page, without exposing another account.
- Current workspace/guest/draft/team/product permission checks precede list counts
  and paging. Revoked memberships, removed guests, source/corpus exclusions,
  unpublished/revised publications and moderated contributions remove evidence.
- Current-session checks and organization serialization protect mutations;
  stale markers/revisions, logout races and duplicate commands cannot acknowledge
  new work. No email/delivery/review/source rights are changed.
- Both clients provide follow/unfollow, refresh, explicit mark-seen, loading/empty/
  error states, older research, direct investigation/source/claim links and safe
  transient state on account/workspace changes. Use existing brandbook tokens,
  controls and accessible text, without fabricated Lens activity.
- New migration/erasure, permission, real-job and failure cases pass with affected
  integration tests, exact API Ruff, final backlog smoke, both client tests/lint/
  types/builds. Push exact validated main source and verify native activation,
  current public Sites versions, HTTP boundaries and emitted assets.

Full dynamic/visual specifications, outbound dossier digests/noise controls,
independent professional quality and corpus-scale semantic retrieval remain
IN PROGRESS. This background cycle does not claim browser/human visual or
authenticated production user-workflow acceptance.

## Implementation and local verification — 28 September 2026

The native projection groups retained `investigation_finished` events by completed
investigation, choosing its latest completion. An accessible newly captured source
with a literal excerpt is required; an `unchanged_from` capture does not qualify.
There is no copied notification body or delivery job. Source and comparison readers
reuse current public eligibility, source exclusions and both retained-page version
permissions. Comparisons show currently active, eligible links with both citations;
a reading acknowledgement does not change ClaimChange review or claim status.

Private follows are contained by dossier/organization and owned by one account.
Listing includes the selected native workspace and verified dossier-only guests,
with visibility before total/offset. Native guest grants retain their verified
account requirement even if that person later joins the host workspace. Other
workspaces are selected through the existing session interface. Revoked access
hides retained subscriptions; erasure cascades personal preferences while retaining
other members' evidence. Existing public follows keep their original marker when
there is no eligible research, and gain a research head when living research exists.

Migration `05d495bef125` adds `product_private_follows` and the nullable public
`research_seen_at` position. New/refollowed subscriptions start at current history;
older public subscriptions expose previously unacknowledged eligible research.
Organization serialization, current native principals, explicit revisions and head
markers guard personal writes. A newer completion rejects an older read marker;
exact retries are no-ops. Acknowledgement remains separate from research review.

Both clients share fourteen source/test files. The existing Following route adds
private dossiers and expandable histories for both audiences. Lists page by twenty
dossiers; histories page by ten investigations, with previews of three sources,
findings and comparisons per result. Quotes are limited to six hundred characters
and link to the complete captured reader. Exact private/public investigation,
claim and source links include IDs only. An unavailable pinned private investigation
cannot silently fall back to the latest one. Current counts and evidence refresh
at fifteen-second intervals while open and on window focus. Session events clear
private results; errors discard old payloads and late responses are fenced.
Nothing is persisted in browser storage. Brandbook tokens/primitives remain in use.

Local verification: twenty-five new native integration cases pass in a 157-case
regression covering public/private following, actual recurring/public/page jobs,
source comparison, guests, both-source withdrawal, migration and erasure. The first
28-case following regression passed; four additional permission cases are included
in the final broader run. An earlier empty-history null-date failure was corrected
before these passes. Both clients pass 115 tests, lint, strict types and final
portable Sites builds. Exact API Ruff and the final backlog smoke are required
before publication. PostgreSQL accepts both new completion projections on random
nonexistent scopes without reading user records. Three configured provider values
are absent from 195 source and 137 built files per client and 1,782 native source
files. No paid requests, user-record changes or browser/visual QA were performed.

The scoped release still requires exact native activation and both existing Sites
public deployments, served-asset/auth checks and a sanitized release receipt.
