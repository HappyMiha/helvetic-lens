# Whole-dossier saved-evidence retrieval

Status: DONE — scoped stage 4f / release 1.21, with local and exact production
acceptance. Broader product and professional-quality work remains IN PROGRESS. The pre-implementation
scope, readiness, dependencies, method selection and acceptance gates are in
BACKLOG_MONITORING_V2.md under MV2-021/023/051. MV2-063/pgvector remains DEFERRED.
This scoped feature does not close the dynamic or visual specifications.

## User journey

In either Pharma or Loyer, Search saved evidence and the global dossier evidence
entry now default to meaning search across the authorized retained dossier.
Older records participate immediately in ranking once preparation completes.
First-use preparation advances 16 records per short native request, with real
saved counts. Stop, close, sign-out or a changed session stops further requests;
completed cache work is reusable after returning. Queries and results are never
written to browser storage, URLs or a server query-history table. Ranked pages
retain exact quotes, source hashes, locations, claim status and original links.
All compared candidates remain available, including negative/uncertain Laya
opinions. Source reading and fact verification stay separate from relevance.

Words still filters across the complete eligible ledger before paging. Direct
comparison retains the previous 12-record, newest-first Laya journey. Neither
uses the new preparation service as a dependency. Public web discovery remains
an explicit separate query using the existing hosted Jev/local Laya abstraction.

## Architecture and rights

Reuse the existing private source/citation ledger and current principal, team,
guest and paired-page visibility rules. The new source-contained native cache
stores 384-dimensional binary float vectors plus exact input/model hashes and
truncation metadata. Composite foreign keys bind dossier, organization, source,
claim and investigation; native cascades erase derivatives with their originals.
No query, copied quote, inferred fact, source approval or publication is stored
in the cache. A cache row is never a source of permissions or a result/count.

The local embedding adapter admits only operator-controlled loopback or the
private retrieval service and an exact path. It validates pinned model, input
hash, order, finite normalized dimension and token/truncation bounds. The native
API selects only current eligible cache rows, rechecks the full evidence fence
before/after local inference, and commits preparation under the existing
organization lock with fresh principal/source checks. Exact retries and concurrent
preparation update one derived row per record. Current full-source hashes remain
in the fence even when only a prefix enters the model. Withdrawn sources and
unavailable previous/current watched-page versions disappear before counts/ranks.

Pinned E5-small embeddings and existing BM25 rank fusion use weights 2:1 and
constant 60. Zero-score lexical entries contribute nothing; arbitrary ID ties
cannot bias a query with no shared words. Laya independently assesses the twelve
displayed records without changing or suppressing the corpus order. Failures of
those opinions retain complete retrieval with an explicit unavailable state.
Preparation/query failures retain prepared work and offer Words/direct recovery.

## Bounds and measurement

Full ranking is bounded to 20,000 current eligible records. A larger ledger gets
an explicit capacity response; no newest-record cutoff is silently labeled full
coverage. Uncaptured originals, public discussion and live-web content are outside
this private saved-evidence ledger. E5 reads at most 512 tokens from a 300-character
title, 600-character finding and 2,400-character quotation prefix. Exact source
readers retain the rest. Preparation reports token truncation per result.

Database operations have 3s statement limits; model bodies, concurrency and local
calls are bounded. Preparation and interactive inference have separate native
rate limits. The corpus handler has a 40s deadline and a 32s decision budget,
including elapsed query preparation. Check-only refreshes never invoke models.
Actual per-request latency and completed calls are disclosed. Compute/hosting
cost and dossier-specific accuracy remain unknown, not zero or confidence.

## Independent relevance experiment

The [NoMIRACL data card](https://huggingface.co/datasets/miracl/nomiracl) describes
human relevance labels in multiple languages. Dataset revision
`ecd08778d0426a5ca28ac99763b0c9ddc2c78e68`, immutable file URLs and SHA-256 hashes
are recorded in the receipts. Its Apache-2.0 dataset declaration and underlying
Wikipedia attribution/share-alike rights remain distinct. Raw passages remain
local evaluation inputs; this repository publishes IDs, judgments and metrics.
Model license, authors and provenance: [pinned model card](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/README.md)
and deploy/retrieval/THIRD_PARTY_NOTICES.md.

Selection used 12 answerable development queries plus 4 non-answerable per language
(English/German/French), deterministic hash order, no fitting or label edits.
Development candidate nDCG@10 favored the predeclared 2:1 fusion over direct Laya
and BM25. An initial unseen test passed; a subsequent zero-score lexical-tie
correction required a fresh disjoint test slice at offset 20. That final slice
contains 60 answerable and 12 non-answerable queries; the reused development rows
are not a second independent test. Final pooled candidates: 1,217 passages.

Final held-out candidate nDCG@10: selected hybrid 0.78913, direct Laya 0.72839,
BM25 0.60347. Top-ranked relevant result: 0.61667 vs Laya 0.46667 / BM25 0.25.
Known-positive recall@12 in the selected pooled corpus: 0.96667 vs BM25 0.90444.
These are selected encyclopedia pools, not the full MIRACL corpus, open-web
recall, professional medical/legal accuracy or Italian/Ukrainian validation.
Other-query passages are unjudged, not negatives. A hash-based recency ceiling
is an artificial coverage illustration, not actual user-history performance.
E5's publisher discloses MIRACL training-set use; pretraining contamination is
unknown. No classifier threshold is promoted from this experiment.

Local two-CPU encoding of 1,217 passages took 152.7s; mean query embedding 13.74ms.
Direct Laya averaged 521.81ms per judged pair in the final report. This is model
compute timing, not an authenticated production search SLA. Actual native
end-to-end fixture measurement and production acceptance are recorded below.
No paid inference or private production records were used in the experiment.

[Development receipt](product-evaluations/2026-09-28-dossier-retrieval-dev.json),
[initial held-out receipt](product-evaluations/2026-09-28-dossier-retrieval-initial.json),
[final independent held-out receipt](product-evaluations/2026-09-28-dossier-retrieval.json).
Reproduce with scripts/evaluate_dossier_retrieval.py prepare/encode/decisions/report,
using an ignored/private directory and explicit protected local credentials.
Final sampling uses `prepare --test-offset 20`.
Never add downloaded corpus files or provider tokens to a public archive.

## Acceptance

The new native integration/adapter/service and existing affected suites, both
client test/lint/type/build gates, exact native schema/module/runtime, exact
both-origin assets and GitHub CI must pass before scoped DONE. No browser or
human visual QA, authenticated production user exercise or full-spec completion
is claimed. Exact scoped production acceptance is recorded below.


Local acceptance: 196 affected native integration cases passed, including the new
whole-ledger, guest, concurrent-preparation, cache-migration/cascade, source/page
withdrawal and three-phase revocation cases, plus strict local adapter failures.
The isolated service's two auth/limit/concurrency/cancellation contracts pass.
Both clients have 119 passing tests; final lint, type checks and portable builds
pass. GitHub CI passed for each exact published client revision.

The [actual local native probe](product-evaluations/2026-09-28-corpus-native-probe.json)
uses a synthetic 64-record dossier per product, real native HTTP/SQLite and both
actual pinned local services. Checkpoints 16/32/48/64 complete, the older exact
quote ranks first for a German question and a later English question, and the
warm request performs one query embedding plus 12 Laya opinions. Pharma cold
journey 11.04s / warm 5.94s; Loyer 10.65s / 5.93s. These are fixture measurements,
not professional relevance evidence or an authenticated production user workflow.
The service is reachable only on the private Docker network; no host port is
published. The fixture resolver mapped only the fixed local service alias to its
observed bridge address. No production accounts/data were involved.

## Exact production acceptance — 28 September 2026

Native functional revision `52cb35ef028ff2b58aad74e96d2d639493390b4e` activated
at 03:37:41 UTC. Both public Sites version 24 deployments succeeded from their
exact validated source and archives: Pharma `8c91e617f9052f9c0a852e6f3f17edb29538a15c`,
Loyer `4c903cb2444256bc1e8af52dc9af23f39dba5254`. Each custom origin passed
120 HTTP/auth/gateway/guide checks and 47 exact served JS/CSS asset hashes.

Read-only native verification matched 57 current source modules, migration
`06d495bef125`, cache ownership/source/claim cascades, unique record keys and
permission-filtered SQL on nonexistent scopes. Four native runtime containers,
five scheduler modules, the minute schedule and retained research schema gates
passed. The existing Laya service remains healthy. The isolated retrieval image,
service/notice hashes and pinned weight SHA-256 match; it runs with a read-only
root, two CPUs, 3 GiB and no published host port. A synthetic authenticated call
through the actual native embedding adapter returns the pinned 384-dimensional
model; the service rejects unauthenticated inference. No production user records
were accessed or created.

Public source and final client builds contain none of the three actual protected
provider values. GitHub CI runs 36374171378 and 36374173757 passed. This evidence
verifies deployment and bounded mechanics, not browser/human visual acceptance,
a private production user journey or professional relevance. Full dynamic and
visual specifications, remaining native visual migration and broader MV2 parent
tasks stay IN PROGRESS. The existing hourly continuation remains active.

[Sanitized release receipt](product-releases/2026-09-28-1.21.0.json) records exact
source, archives, deployments, runtime, source checks and validation limits.
