# Reviewed entity mentions — 1.39

Status: DONE within the tested pair-review and verified release scope. Scope and acceptance recorded before product code.
Contributes to MV2-002/020/024; broader architecture and human acceptance OPEN.

## Existing contracts and dependencies

Run-local DossierEntity rows retain exact cited identifiers, issuer, jurisdiction,
kind and original mentions. DossierRelationship requires same-run entities.
ClaimChange supplies the existing audience-filtered, source-paired editor review
pattern. This stage reuses those entities, captured sources, native membership,
current guest roles, source exclusions, publication revision/consent, and readable
client research chapter. No new source acquisition, provider, credential, model
request, registry, graph database or inferred identifier is required.

Unified Target Architecture §§7–13,23,26,61,65 and Investigation Engine §§13–16
apply. The fully read unified specification remains byte-identical at SHA-256
f5cb4d2218f377b317295b26c75c0c3eef2130c0624de668ded1c5308ecf048a.
Source readiness: only literal, valid existing source citations with complete
identifier namespaces qualify. Missing/unsupported identity remains unresolved.

## Bounded outcome

An optional folded Entity matches reader offers exact identifier/issuer/
jurisdiction/kind matches across completed runs in one dossier and one audience.
Suggestions examine at most 120 recent eligible entities, with an explicit limit
and at most 30 suggestions. Saved decisions paginate independently of that window.
A current editor can record same entity, different entities or unresolved with a
reason, revision fence and both current citation fingerprints. Public review
requires explicit publication consent. Suggestions are never human acceptance.

Add one contained append-only review table, referencing both original entities
and sources in their own runs, with reviewer FK SET NULL for account erasure.
Each revision retains its decision, reason, timestamp, evidence fingerprint and
request identity. Reuse existing authorization, publication and source visibility
filters before counts/pagination. Latest decisions and their bounded history are
readable; changed evidence marks a decision stale until explicitly reviewed again.
No original entity/claim/relationship/source is rewritten. No transitive merge,
name matching, canonical registry, claim acceptance or automatic Ask promotion.

## Acceptance

- Exact namespaces only; both quoted originals and source hashes readable.
- Same dossier/organization/audience, different runs; source eligibility before
  counts/pages, replay and writes; public revision, withdrawal, exclusion and
  current-role revocation fail closed. Private notes never become public reviews.
- Immutable reviewer-attributed history, optimistic revision and idempotent retry;
  stale evidence rejects writes, duplicate/cross-scope requests cannot add reviews.
- Eligible private reviews included in export; source/parent deletion cascades;
  reviewer erasure retains de-identified history. Additive migration preserves
  originals; downgrade refuses retained review data.
- Both client readers show bounded suggestions, saved decisions, source pairs and
  explicit review controls. Closed reader makes no request. Failed reads hide
  cached decisions; failed writes are not automatically replayed. Preserve 1.36
  unique React keys and query retention. Reuse current primitives and Brandbook.
- Affected API behavior/migration/privacy tests, exact API lint, backlog invariant;
  both clients test/lint/types/build. No browser, private production records or
  paid probes. Push completed main changes and publish exact tested builds to
  existing Sites projects; verify normal Core activation and deployed assets.

Dependency chains, effective dates, unrestricted canonical identity, professional
quality and human acceptance remain OPEN. Existing evaluation datasets and
threshold experiments remain frozen and no guard is enabled.

## Implementation and verification

`product_entity_identity.py` derives exact-namespace suggestions and current
pair/history projections. `product_entity_identity_api.py` reuses native editor,
public participation and source visibility gates. `EntityIdentityReview` has
composite entity/source containment, canonical pair order, different-run and
revision constraints. Migration `0ad495bef125` only adds this table and indexes.
Each saved row retains its reviewer through a nullable erasure-aware FK.

Both clients add a folded Entity matches reader beside Changes over time.
It loads only when opened, retains both citations and distinguishes a suggestion,
an editor decision and stale evidence. Earlier decisions remain in the source-pair
history. Public consent is explicit and a lost write response is not replayed
without another user action; that action reuses its request identity.

The controlled fixtures use fictional registry evidence and no model calls.
They test both product aliases, private/public review and anonymous reading,
current guest roles (including workspace viewers), revocation, hidden/revised/
withdrawn public material, source exclusions, stale capture fingerprints,
revision conflicts/retry, export, bounded suggestions, independent saved pages,
account erasure, additive migration and source cascades. Initial public fixture
setup incorrectly omitted analysis consent and was corrected to use the existing
consented contribution run. Anonymous reading exposed a missing allowlisted route;
that route and the viewer write exception now reuse the existing public contract.

Client checks exercise the real reader/reconciler: zero requests while folded,
input and request identity retained on write failure, hidden cached pairs after
access failure, paired quotes, stale labels and isolated proxy paths. Both clients
passed 203 tests, lint, types and the exact production build. Existing duplicate
search regression remains covered. All 61 distinct affected Core checks and the exact API lint passed: 25 new
identity cases, 34 retained comparison cases, one existing dossier/export journey
and the backlog invariant. Initial Core and both client activations are verified below. Full canonical registry, professional and human
acceptance remain OPEN.

The active backlog reached its existing 512 KiB parsing bound. Completed 1.37
protocol commentary was archived verbatim in `BACKLOG_MONITORING_V2_RELEASE_HISTORY.md`;
task definitions, statuses and deferred work remain in the authoritative queue.
The byte-limit safeguard was not raised. Its invariant passed after the move.

## Verified publication

Core `5b03c488e5bf17fafa098c0f44063abfe111672c` activated normally as
`git-5b03c488e5bf` at 2026-09-28T21:05:51Z. Migration `0ad495bef125`, 32 exact
runtime module hashes, five running containers and all nine native Monitoring
navigation routes were verified. The contained review table, nullable reviewer
and source/revision constraints are active. The two products each passed 38
anonymous HTTP/access checks and 47 exact static asset SHA-256 comparisons.

- Legal source `406e2230e4fe7592227e5b9bbfeaaf53d201ec5b`, existing Sites version 39,
  activated at 2026-09-28T21:07:17.311248Z.
- Pharma source `ee9692fb8822180b0c645965b50260551580ff8f`, existing Sites version 39,
  activated at 2026-09-28T21:07:50.459478Z.

See [the frozen public release receipt](product-releases/2026-09-28-1.39-entity-identity.json).
All three main checkouts were freshly fetched, clean and aligned at verification.
The final evidence-only Core commit follows the same normal native deployment;
its activation is recorded in the parent workspace checkpoint/final receipt.
Native backups still pause API/tunnel; zero downtime is not claimed. No private
production dossier, browser or inference was used. 1.37 selection remains null
and its validation dataset remains unopened.
