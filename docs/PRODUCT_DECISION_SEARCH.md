# Jev and Laya decision search

Status: DONE for the scoped Pharma/Loyer discovery release, 27 September 2026.
Broader semantic private-corpus and recurring-search/pilot gates remain open.

The owner requested one decision abstraction with hosted Jev as primary and local
Laya as fallback, including actual search and an inspectable comparison of latency,
accuracy, cost and confidence. Existing dossier ownership, publication, source rights,
review and delivery consent remain in force. Broader Monitoring acceptance stays open.

## Provider contract and readiness

- TypeSafe: https://docs.typesafe.ai/api, fixed HTTPS POST /v1/systemone, jev-latest.
- Laya: https://github.com/NandhaKishorM/laya, Apache-2.0, compatible System One
  HTTP endpoint; separate bounded local service. Its README explicitly distinguishes
  its entropy-derived confidence from Jev confidence and recommends task evaluation.
- Search1API: https://s1.dev/docs, public web index, separate from decision models.
- Reference architecture: https://github.com/superagents-lab/jev-search (MIT),
  inspected for documented provider contracts; no branded frontend is copied.

Account registration and key generation were explicitly authorized. The owner
accepted TypeSafe's terms and funded its account on their own device; the named
Helvetic Lens Pharma and Loyer API key was then created and configured. Both
products use the same protected native core credentials. Search1API retrieval,
Jev 1.13.0 and the pinned local multilingual Laya checkpoint all passed actual
inference. No credential, model weights or private document is in public source.
Local serving remains separate from the native API's generative model runtime.

## Acceptance

1. A single typed adapter boundary validates exact question IDs, answer kinds,
   choices/probabilities and bounded responses. Errors expose no provider payload/secret.
2. Public-query text is reviewed explicitly. No private dossier, file, note or saved
   research is silently submitted to either hosted decision or search providers.
3. Real retrieval returns linked snippets, not invented text or claimed fetched full
   documents. Both engines rank the same bounded candidates; external data is data,
   never executable instructions or permission to expand access.
4. Default primary/fallback, explicit local-only and deliberate comparison remain
   distinguishable. Local-only means local decisions, with disclosed remote retrieval.
   Unavailable engines/indices have actionable states; no fake success or implicit
   generative substitute. Cancellation, timeouts and malformed responses are bounded.
5. Latency is measured; reported usage is optional, missing means unknown. Cost
   estimates carry their basis; local hosting is not automatically priced at zero.
   Accuracy requires explicit human labels on the actual candidates, with sample
   counts and model/evaluation identity. It never equals confidence.
6. Private search receipts/labels obey current account and selected workspace access,
   erasure and expiration; request quotas bound third-party costs and local resources.
7. Existing signed source import and provenance workflows accept safe public results;
   no automatic source approval, monitoring activation, publication or notification.
8. Native privacy/failure/migration tests, exact API lint, both client tests/lint/types/
   builds, main publication and production verification are recorded truthfully.

## Retrieval and source inspection

Quick evaluates at most eight Google candidates. Broad/Deep federate Google and
Bing plus Europe PMC for Pharma, deduplicate exact safe HTTPS URLs, and select at
most 24/36 candidates by reciprocal-rank fusion (k=60). Final ordering combines
semantic decision rank twice, Unicode-token BM25 once, and index fusion once.
Decisions use multilingual Laya or Jev on the same query/title/snippet pairs.
There is no claim of a universal index, translated-query expansion, private-corpus
embeddings or measured cross-language recall. Failed lanes are displayed; absence
of results does not establish absence of evidence.

A separate explicit action anonymously inspects up to three saved sources per run,
with robots checks, public-network validation, no redirects/cookies, 1 MB responses,
55-second total timeout and the native extractor. It examines up to the first
24,000 extracted characters, lexically selects eight passages, optionally ranks
those via the requested decision engine and displays three exact extracted passages.
The SHA-256, capture time, truncation and method remain attributable. Up to twenty
safe outgoing links support a reviewed new search. Links are not certified citations;
no protected content, exhaustive crawl or citation-graph coverage is implied.

## Persistence and operations

Migration `f9c495bef124` adds owner-private search runs and a non-personal daily
aggregate budget. Organization locks, current principal checks before/after I/O,
CSRF and admin write roles protect mutations. Request UUID/fingerprint makes retries
return the original receipt without repeated external retrieval. Last-50 retention,
original source-import expiry, private labels, stale revision rejection and native
account erasure apply. Label accuracy is sample agreement at a 0.5 threshold; Brier
score is computed only from reviewed candidates, not model confidence. The global
25-search/day budget survives personal erasure without retaining query/user data.

Local service installation, pinned checkpoint, resource limits and protected
operator environment are in [deploy/laya](../deploy/laya/README.md). No production
credential or model weights are committed. Browser readiness returns booleans only.

## Verification

Live samples on 27 September 2026: Google/Bing/Europe PMC retrieval plus Laya selected
24 candidates for “Swissmedic medicine safety” in 11.67 seconds. An explicit read of
Swissmedic's Safety Update page extracted 5,544 characters and three passages with
Laya, preserving its SHA-256. These are controlled latency/functionality probes,
not accuracy benchmarks; no human relevance labels or Jev live comparison are claimed.
Search1API has startup credits and auto top-up is off. TypeSafe was subsequently
funded by the owner; its key is active and auto-recharge remains off.

Local verification passed: 234 native cases (233 integration and one backlog smoke),
including 30 new decision-search cases; exact API lint passed. Both clients passed
63 contracts/SSR cases, authored-source lint, strict TypeScript and production builds.
Main publication and production verification are complete: both Sites version 8
releases succeeded and exact-head GitHub checks passed. Each custom domain passed
36 HTTP/gateway checks and 33 exact served-asset comparisons. Core
`git-6df711fc0842` is ready after all 755 standard release checks.

A paired Pharma probe used the same 24 cached public candidates: Jev 1.13.0 took
12.61 seconds and Laya 6.76 seconds, with no second index request. A separate actual
public legal query inside the deployed core returned eight candidates in 5.16
seconds, Jev selected, both engines successful. Reported Jev inference usage for
that run was 3,744 input / 279 output tokens, an estimated $0.000157248 at the
configured rates. Search/hosting costs remain unknown. These latency samples are
not general benchmarks and no labelled accuracy is invented.

Immutable release evidence: [1.6.0](product-releases/2026-09-27-1.6.0.json).
No authenticated customer record was created, and browser interaction QA or a
professional user pilot is not claimed.
