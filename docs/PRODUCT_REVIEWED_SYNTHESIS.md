# Explicit reviewed context for AI research — 1.45

Status: IMPLEMENTED; production activation pending. Scope recorded before implementation; MV2-002/020/023/024.

The research preview can explicitly include an editor's claim classification and
source-specific role assessments. Each own or related claim keeps its independent
review context. The default claims_v1 and legacy saved provider inputs remain
unchanged. This is typed input context, not automatic typing of generated findings:
the resulting research note remains an AI draft requiring human review.

## Dependencies and source readiness

Reuse DomainPack, ClaimReview, retained eligible captures, exact quotation checks,
the existing research preview/provider, DossierEntry, answer review, export and
follow-up actions. No new sources, tables, migration, provider, credentials or paid
probe. Fixture evidence is fictional. No browser or private production inspection.

## Bounded outcome and acceptance

- Add opt-in claims_typed_v1 with its own preview fingerprint, request identity
  and explicit UI choice. Preparing or switching previews never calls a model.
  Show exactly which classifications and source roles accompany each claim.
- Preserve complete selected contradiction groups and existing 12-candidate,
  two-group/eight-quote limits. Related classifications come from their own review,
  never the selected claim. Every displayed role binds to its exact input citation
  and captured source within that claim's assessment context.
- Current editor metadata may be sent; missing or stale metadata is explicitly
  unknown, never silently promoted. Do not send reviewer reasons, identities or
  history. Editorial roles and acceptance do not establish truth, authority,
  applicable law, effective dates, regulatory status or clinical value.
- Pin all included claim-review dependencies, including related claims' extra
  source contexts, with a bounded maximum of 42 distinct claim contexts. Check
  before and after inference. Changed reviews/evidence invalidate acceptance;
  unavailable supporting dependencies hide notes, replays, export, brief and
  derived actions. Existing old scopes retain their original bounds/behavior.
- Preserve exact quote validation and all dossier/editor/source/CSRF fences.
  Keep source capture time distinct from publication/effective dates.
- Retain the supplied context in saved notes, export and printable brief. The
  existing folded preview/claim display is extended without new dashboard panels.
- Test independent own/related types, mixed-source roles, missing/stale contexts,
  consent/replay separation, pre/post-inference changes, second-degree dependency
  withdrawal across readers/actions, quote rejection and whole-group omission.
  Run affected Core tests/exact lint/backlog invariant and both complete client
  tests/lint/types/builds. Push main and verify existing Sites/native activation.

Full typed extraction/generated finding schemas, authority ranking, applicability,
GENERAL, full Market Access and professional/human acceptance remain OPEN.

## Implementation

The new scope extends the existing selection and provider path. The default
preview still uses claims_v1. A dedicated choice enables claims_typed_v1; its
fingerprint and retry identity cannot be reused for another scope. The prompt
explains editorial assessments, source/user/AI separation and capture dates.
The ResearchAnswer schema is deliberately unchanged: generated notes remain AI
interpretations and do not create classified source facts or canonical claims.

Each selected group carries current compact editor context, with independent
related-claim human state/classification and per-citation source roles. Missing
and stale values are unknown. Reasons, identities and review history are absent.
The source role can differ for the same capture across two reviews. Extra sources
used by a related review are access dependencies even when their text is not in
the bounded model input; their withdrawal hides retained derived content.

The same retained-state guard covers both claim scopes, acceptance, replay, the
brief/export and action origin inheritance. Supplied classifications are immutable
note metadata, not a live replacement. Both clients retain periodic/focus access
rechecks for either scope. The folded note reader and brief show supplied context;
preview dates explicitly distinguish capture from publication/effectiveness.

## Verification

81 distinct affected Core cases passed (80 on the first run and the corrected
concurrency harness case on targeted rerun). The harness had invoked synchronous
TestClient from its event loop; asyncio.to_thread now exercises the concurrent
review through the real API. No product code changed after that suite. Exact API
lint and the active-backlog invariant passed. Both clients passed 228 tests, lint,
types and production builds.
New real-render coverage exercises explicit scope selection, no automatic model
request, loading guards, failure/retry identity, independent labels and escaping.
The first test harness lacked document.cookie and attempted to stringify React
fiber children; both harness issues were corrected. Accessibility lint identified
a missing explicit select/label association; useId/htmlFor now links the control.
The protected-value scan and shared-client parity check passed. Exact production
activation remains pending; browser and human acceptance are separate.
