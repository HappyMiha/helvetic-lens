# Monitoring-triggered private dossier research

Release 1.16, scoped stage 4b1. DONE within the scoped automated and production acceptance below. Full dynamic dossier and visual specifications
remain IN PROGRESS. This scope covers native topic-match metadata, not recurring
web discovery or changed-page-body research.

## User outcome

An editor with native workspace monitoring authority can enable ongoing private
research in an active Pharma or Loyer dossier. The saved authorization explicitly
continues after sign-out. The existing one-minute scheduler observes new native
matches after enablement, retains exact trigger identities and starts the same
durable investigation engine. Independently extracted findings enter the existing
paired-citation comparison. The original findings and historical status remain
unchanged. Both clients show settings, last check, actual daily usage, paged signal
history, source provenance and links to investigations and Changes over time.

Default three, maximum six research starts per UTC day. Explicit resume/retry
also consumes a start. Changing the limit does not reset usage. Unused capacity
is not carried over. One metadata snapshot and one extraction request, followed
by at most one comparison request, bound each attempt. No external source fetch,
search query, provider registration or public contribution is performed by this
mode. Existing personal notification consent and native digest delivery remain
unchanged. A matching signal is not automatically a material change or a reason
for an additional notification.

## Authority and evidence

Migration `02d495bef125` adds two organization-scoped tables contained by the
existing dossier. Policies bind the actual authorizing account, profile revision,
topic set and monitoring audience. Every scheduler step and worker boundary checks
that account's current native membership, dossier role and monitoring authority.
No login session is fabricated. Guests may read their dossier's history but cannot
configure host monitoring, even with an EDITOR dossier role. Native session/CSRF,
optimistic revision and exact request identity apply to policy changes.

Each trigger binds the policy revision, exact match ID/evaluation fingerprint and
optional investigation through composite dossier/organization foreign keys.
Unique match/fingerprint identities survive policy disablement and re-enablement.
Receipt, quota consumption, investigation and native job/outbox commit together
under the existing organization lock. The scheduler admits up to 100 unrecorded
signals per policy per check and visits up to 50 due policies per timer invocation;
oldest due policies get priority. It starts at most one investigation per dossier
per check, serializes with existing work and defers pending signals at the daily
limit. Capacity/freshness limits are visible; no exhaustive coverage is claimed.

Before capture, network work and result retention, the exact match must remain in
one of the current dossier topics, admitted to the organization, current under
native evaluation fingerprints and not currently rejected, muted or excluded.
Only the deterministic retained event-metadata excerpt (up to 12,000 characters)
is analysed; source title, URL, capture date and excerpt hash are retained. This
is not the full linked document. Model strings remain untrusted, citations must
match the captured excerpt and entity-triggered public discovery is disabled.
Earlier claims never enter extraction; the separate comparison retains 1.15's
bounded, audience-safe identity-only output and exact paired citations.

Disabling or changing settings cancels prior pending/paused/active work with a
generation fence. Completed evidence remains. Settings apply to future matches,
not a retroactive scan. Revoked authority or changed profile settings disable the
policy when checked; worker checks reject late results immediately. Changed or
withdrawn evidence pauses a started run or skips a waiting trigger. Interrupted
paid work is not automatically repeated; an explicit authorized retry must still
satisfy the original policy, source identity and daily budget.

No private trigger enters public research, anonymous search, public source
projections or publication updates. The mode does not change the dossier audience.
Private exports include complete trigger history within the 2,000-item interactive
limit and the existing 100-investigation bound. User deletion clears the policy's
account reference; dossier deletion cascades contained records. Migration downgrade
refuses retained policy/trigger data rather than silently discarding it.

## Client behavior and validation

Both clients reuse Brandbook v1.0 tokens and native accessible controls, poll saved
history every 15 seconds, display actual saved checks/usage, retain explicit consent
and hide cached history after access failure or dossier change. Research activity
uses the existing persisted Lens state, never a timer-generated animation. Source
links require credential-free HTTPS. Settings changes are revision-checked and
an exact failed request can be replayed without a second mutation.

Nineteen new native cases exercise both-product native matching -> scheduled job
-> citation -> comparison, duplicate delivery, signed-out authority, rollback,
budget deferral, explicit interrupted-step retry, source/admission/profile/account/
membership races, editor/guest/CSRF/consent boundaries, schema equivalence,
foreign keys, retained migration and complete paginated export. The broader affected
regression passed 160 cases. After the final request-identity/check-timestamp
corrections, all 34 affected monitoring/coordinator cases passed. Exact API Ruff
passed. Exact production acceptance passed, as recorded below.
Client tests/lint/types and production builds pass with 99 cases each.
This automated evidence is not independent professional factual-quality or human
visual acceptance. The background cycle does not open a browser-only preview or
perform browser interaction QA.

## Exact production acceptance — 27 September 2026 UTC

Native functional `4bcbdeedf6b6d0a337f4e1daf57e9202ffde4937` activated at
22:05:38 UTC. Pharma `9ce13ba7165ab6ab2d4e4ae98a2f114e96189323` and Loyer
`ebc605887a924c3d862b92c9e9ef0118185b578d` published as existing public Sites19
at 22:06:42 and 22:07:14 UTC. Each exact custom origin passed 97 HTTP/auth/gateway/
guide checks and 47 served JS/CSS hash comparisons. Both exact-head GitHub CI
runs succeeded (36353813699 and 36353814238).

Read-only native inspection confirms 46 module hashes, migration `02d495bef125`,
contained policy/trigger foreign keys and unique receipts, the registered one-minute
scheduler task on `monitoring_control`, four required native runtime containers,
the scheduler's own three module hashes, the existing stdin-only parser fixture
and healthy local Laya. No authenticated production user records or paid provider
probes were created. Each client build's137 files and188 source files contained
none of the three configured provider secrets. The broader native160-case gate
and final affected34-case gate passed, as did both99-test client gates, lint,
strict types and builds. Browser interaction and professional factual-quality
acceptance remain unclaimed. The existing hourly heartbeat stays ACTIVE.

[Exact release evidence](product-releases/2026-09-27-1.16.0.json). Future complete
outcomes include watched-page-version triggers, recurring open-web discovery,
private semantic indexing, independent evaluation and full native visual migration.


Release 1.17 extends this policy through an explicit watched-page scope, retaining
topic-only defaults for existing authorizations. Source bodies, exact old/new
version references and corpus visibility are governed by the separate
[watched-page architecture and acceptance](PRODUCT_WATCHED_PAGE_RESEARCH.md).
This does not add recurring web discovery or complete either full specification.
