# Domain-aware dossier setup — release 1.29

Status: VERIFYING production activation. Scope recorded on 28 September 2026 before implementation.
This is the first bounded Phase 1 contribution to the Unified Target Architecture,
not completion of DomainPack, typed contexts, templates or domain acceptance.

## User outcome

Pharma setup and refinement propose pharmaceutical monitoring interests; Legal
retains legal monitoring interests. The saved dossier shows its actual direction.
The existing common engine resolves a versioned internal pack from the stored
product relationship, including calls through the common monitoring-profile API.
Native profiles preserve Legal behavior; legal/loyer remain compatible.

## Scope, dependencies and source readiness

MV2-002/020/023 scoped contribution. Depends on the existing product identity,
profile authorization, model validation, revision checks and proposal review.
Use an immutable internal registry, additive profile metadata and existing client
primitives. Reuse the current source catalogue and Europe PMC discovery routing.
No new source adapter, source approval, paid probe, account, migration or executable
plugin is needed. Declared pack capabilities do not establish source coverage.
Preserve current activation requirements, source rights, manual setup, model
failure handling, nine directions, author consent and private audience rules.

## Acceptance

1. Saved product identity selects LegalPack or PharmaPack on both product and
   common profile APIs. Arbitrary client fields cannot change this assignment.
   Standalone native legal profiles keep their established instructions.
2. Topic suggestion, active dossier refinement and catalogue advice receive the
   same server-selected pack context. Proposals preserve pack ID/version alongside
   provider/model provenance, without automatic topic application.
3. Legal aliases behave identically. Wrong tenant, role, stale revision and
   permissions changed during inference fail before results are accepted.
4. Both clients expose the saved monitoring direction using the shared contract.
   Missing metadata on an older server remains readable and is not fabricated.
5. Existing Europe PMC capability and federation behavior use the same pack
   definition; no new discovery coverage is claimed. Unknown products fail closed.
6. Affected API checks, exact API lint, backlog invariant and both client test,
   lint, type and Sites builds pass. Tested main sources are pushed and ordinary
   native/Sites activation is verified before this scoped feature is DONE.

## Explicit remaining work

Persisted typed domain contexts, dossier-pinned pack revisions and explicit
pack migration, GENERAL product creation, SourceRegistry, actual Market Access
templates/adapters, common client packaging and professional evaluation remain
open. This registry is application-owned runtime policy; every generated proposal
pins the pack revision used. Existing rows are not silently rewritten.

## Evidence

Implemented in the common API: immutable LegalPack/PharmaPack definitions,
server-owned lookup for both profile and product routes, pack-aware topic prompts,
source guidance and active refinement. Saved draft/refinement proposals retain
pack descriptors; the profile DTO exposes the current runtime definition. Existing
source selection and explicit proposal application are unchanged. Europe PMC
capabilities and federation now consume the same registry.

Both product clients display the saved direction in setup and the dossier heading;
missing older metadata renders no invented direction. Shared modified client
contracts/components/styles are identical. Their test, lint, type and Sites build
gates passed (164 tests each, including actual restored-wizard server rendering).
Exact API lint and all 95 affected API checks passed: 94 integration checks
(profile setup, dossiers, roles, decision search and investigations, including 13
new domain-policy checks) and the backlog invariant smoke check. Wrong tenant,
stale revision, in-flight role/revision changes, Legal aliases, native profiles,
manual activation and pack-aware refinement passed. No production records or
paid providers were used. Production activation remains pending; no live model
accuracy or human evaluation is claimed.
