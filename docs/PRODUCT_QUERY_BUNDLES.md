# Reviewed multilingual query bundles

Status: DONE (scoped release), verified 1.7.0, 27 September 2026.

## Product outcome

A research question should not depend on one phrasing or one language. Users can
review a primary question plus two alternative queries and search the bundle once.
An optional native AI draft proposes complementary terms in selected English,
German, French, Italian or Ukrainian; manual queries remain available. Drafting
does not retrieve web results or submit any private dossier context.

## Acceptance

- Explicit, bounded language selection and per-query edits; new text invalidates
  prior disclosure confirmation. Draft/model failure retains manual fields.
- Main question drives Jev/Laya relevance decisions. Every reviewed alternative
  has a separate visible retrieval lane; comparison ranks identical candidates.
- A maximum of three queries and five retrieval lanes, with one deduplicated
  8/24/36-candidate pool. Partial failures remain visible; no corpus-wide recall
  or translated-meaning accuracy is implied.
- The global daily guard counts actual requested query units, including retries
  only once. The API records primary question and exact alternatives in the
  receipt fingerprint, history and found-by-source provenance.
- A signed imported source retains all queries that found it, alongside the
  original question, capture time and URL. Old single-query receipts still work.
- Query proposals/results remain owner-private and current-membership bound;
  no automatic source approval, watch activation, publication or notification.
- Native privacy/idempotency/budget/provenance/model-failure cases, both client
  workflow gates, main publication and production evidence are required.

## Source and model readiness

The 1.6.0 Search1API, hosted Jev and pinned multilingual Laya runtime are verified.
The existing configured generative planner drafts text; Jev and Laya are decision
engines and are not presented as text generators. No new credential is required.
Native model access is checked through its existing boundaries; unavailable or
malformed drafts are explicit and never substituted with fabricated suggestions.

## Verification

Implementation and exact production activation are verified. Both product clients have 66 passing workflow/render/gateway cases,
clean authored lint, strict TypeScript and successful Sites production builds.
The full affected native suite passed 255 cases (254 integration plus the backlog
smoke). Final interrupted-run provenance and legacy receipt coverage passed 53
focused cases after the last correction, including 22 dedicated bundle cases.
Exact API lint passes. No browser interaction QA or authenticated production records
were used in this background cycle.

An operator probe ran the development query/retrieval modules in a separate
process with existing native production provider settings, using public terms:
`Swissmedic GLP-1 medicine safety`, German and French alternatives. The configured
Swisscom `swiss-ai/Apertus-v1.5-70B` drafted valid DE/FR proposals in 2.63 seconds;
these proposals were not automatically searched. Separately reviewed terms used
five successful retrieval lanes and returned 24 candidates in 15.99 seconds.
All 24 retained exact query provenance; five were found by more than one query.
Jev 1.13.0 and the pinned local Laya multilingual model both ranked this one pool.
This is an operational smoke sample, not a labelled accuracy/recall benchmark.
Jev decision-token cost was estimated at USD 0.000442596; retrieval, drafting and
hosting costs remain unmeasured. No private query, customer record or provider key
is included in public evidence.

Core `git-437c58938841` deployed successfully at 13:28:03 UTC after 755 standard
release checks. Pharma/Loyer Sites version 9 deployments and their exact-head
GitHub checks succeeded. Both custom domains passed 39 HTTP/gateway/guide checks
and 36 exact JavaScript/CSS asset comparisons each. All six affected deployed
native modules match the verified development source; Jev, Laya, retrieval and
planner credentials remain configured. [Immutable release proof](product-releases/2026-09-27-1.7.0.json)
records source identities, deployment outcomes, runtime hashes and boundaries. Private-corpus semantic retrieval, representative
professional evaluation and recurring rediscovery remain separate acceptance.
