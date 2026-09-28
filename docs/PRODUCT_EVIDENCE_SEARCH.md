# Private saved-evidence search — product release 1.19

**Status: DONE within this scoped release.** Scoped MV2-021 stage 4d; full dynamic dossier and visual
specifications remain IN PROGRESS. Native and both client production acceptance
are recorded below. MV2-063 remains DEFERRED.

## User outcome

In Pharma and Loyer, `Search saved evidence` lives inside each private dossier and
is reachable from the global Ask/Search. A current reader, including an invited
guest viewer, can ask a question of retained passages and source-linked claims.
Results contain exact quotations, source capture fingerprints and locators, claim
status/revision and a focused link into the original investigation's source or
finding. No generated answer, new finding, publication or monitoring action occurs.

Meaning mode compares successive newest-first windows of twelve records through
the existing local Laya System One adapter. Candidates are not filtered by query
words; another language or a paraphrase can rank highly. A semantic rank and a
literal all-word rank are fused with reciprocal rank fusion (2:1, constant 60).
Every successfully compared candidate remains available, even when the classifier
chooses its negative label. Such records are explicitly candidates for review,
not asserted matches. Previous/older windows retain the search capture time so
new source captures cannot shift the ongoing traversal.

Words mode filters the whole current eligible ledger before counting and
pagination, without inference. When Laya fails or exceeds its deadline, semantic
mode returns only literal matches within that window, explains the failure, and
points to Words for full-ledger literal recovery. A new search includes new
captures. A lack of matches never establishes absence of evidence.

## Scope and privacy

Only completed private investigations in the selected dossier are included:
all retained source passages and each source-linked claim citation, including
historical, disputed and superseded claims. Counts describe these records, not
unique sources or verified facts. Files without captured text, uncaptured
attachments, live internet pages, public discussion and other dossiers are outside
this reader. No vector index, embedding model or background ingestion is added.
Long passages send/show only their first 2,400 characters; the full retained
passage remains available through its original source reader. Literal matching
uses the full retained text before that preview truncation.

The request uses POST with native CSRF and a read grant, so an authorized viewer
does not need editor authority and private questions do not enter URLs. Neither
queries nor results are stored by this feature in a database or browser storage.
The configured local adapter rejects remote provider URLs. No Jev, public search,
collector or configured generative model is called by private evidence search.
Existing Jev-primary/Laya-fallback public-web search remains unchanged.

Current native session, active account, organization, dossier product, draft/team
membership and invited guest access are checked in fresh transactions before
candidate capture, before every local decision and before returning data. SQL
source predicates filter before counts/pagination, including latest exclusion,
linked corpus access and both versions in watched-page trigger receipts. The
canonical URL, earlier URL and each current retained version URL are also checked.
The shared derived-source predicate now applies those paired-page gates to
comparison readers too. A change in selected evidence, revisions or visibility
invalidates the pending response. UI results are revalidated every fifteen
seconds and on focus without repeating inference; failures clear results. Session
changes and unmount fence late responses.

## Resource and truthfulness limits

- At most twelve local decisions per search window, a 32-second comparison
  deadline and the adapter's existing per-request timeout. No automatic retry.
- At most 2,400 quotation, 600 claim, 300 title and 300 question characters per
  local request, subject to the existing service's additional state/body limits.
- Six semantic searches per user per minute and thirty platform-wide per minute,
  through the native Redis-backed limiter; production protection fails closed.
- PostgreSQL reads have a three-second statement deadline; transactions are not
  held during inference. Pagination is explicit and capped at offset 1,000,000.
- Latency measures the request's actual elapsed time; completed local calls and
  model identity are retained in the response. Local compute cost is unknown,
  never zero. Model probability and confidence are not measured accuracy.

This is direct-context retrieval within declared windows, not global semantic
ranking over a large archive. Independent professional/multilingual relevance
validation, ingestion-scale benchmarking and the conditional vector trial remain
open. This feature makes no claim of internet-wide coverage or clinical/legal
correctness.

## Validation and acceptance

The [retained development trial](product-evaluations/2026-09-28-private-evidence-search.json)
uses non-confidential synthetic archive-storage and unrelated meeting passages,
with queries/passages in English, German, French, Italian and Ukrainian. Labels
were authored for development, not independently reviewed. Twenty requests cover
fourteen unique query/passage pairs. Laya ranks the relevant record above its
unrelated comparator in all ten paired presentations, but its binary classifier
rejects seven relevant presentations (13/20 classifications correct, compared
with 10/20 for an all-word baseline). This observed false-negative behavior is why
search retains every ranked candidate instead of hard-filtering at 0.5. These
numbers are not a production accuracy claim and do not activate MV2-063.

Reproduce with the native Python environment, `PYTHONPATH=services/api` and
`scripts/evaluate_product_evidence_search.py --output <report.json>`. Optional
`--credentials-file` reads an explicitly chosen protected operator JSON file;
`--laya-base-url` remains constrained by the local adapter. The fixture lives in
`demo/private-evidence-search/fixture.json`. No confidential production records
or hosted/paid queries were used in this trial.

SQLite functional fixtures exercise actual native auth, dossier/team/guest
membership, retained sources, claims, page captures, corpus withdrawal, exact
citations, paging, local failures and permission races. A read-only PostgreSQL
query with nonexistent random scopes checks the generated production-dialect
query without returning user records. Both clients require tests, lint, types and
final builds. Exact source/asset/runtime activation, anonymous gateway denial and
production readiness are separate from local fixture behavior. Browser, human
visual and authenticated production workflow acceptance are not claimed.


Local gates, 28 September 2026: 25 new native search cases pass within the final
102-case permission/evolution/page/public-research regression. The earlier
139-case wider regression passed 137 cases and identified the paired-page
visibility gap; the final affected regression verifies its fix. Both clients pass
111 tests, required lint/types and final portable builds. Exact API Ruff passes.
The actual PostgreSQL generated query and JSON-passage projection pass using
random nonexistent dossier/organization scopes; no user records were returned.
Three protected provider values are absent from each client's 192 source files
and 137 built files and all 1,776 core source files. Exact production acceptance is recorded below.


Production acceptance, 28 September 2026: native functional
`58d0d99890ee5b0a1ad5ca6c34dbc9cf0dfbd491` activated at 01:11:40 UTC.
Pharma `6503a026f14096f9c014a012f0f4f26fa39a52b6` and Loyer
`9e1a4ecf209674e3625f94e1ddca9b73c75516c1` are active as their existing public
Sites version 22, completed at 01:12:36 and 01:13:08 UTC respectively. Both
exact-source GitHub CI runs passed (36364780422 and 36364797173). Each custom
origin passes 110 HTTP/auth/gateway/guide checks and 47 exact JS/CSS asset checks.
Read-only runtime verification matches fifty module hashes, unchanged migration
04d495bef125, paired-source SQL projection, four required runtime containers,
five scheduler module hashes, the existing minute scheduler, parser fixture and
healthy local Laya. The [sanitized production receipt](product-releases/2026-09-28-1.19.0.json)
retains exact versions, deployment identities, commits and scope. No production
user records were created or inspected, no paid provider query was made, and
browser/human visual or authenticated production workflow acceptance is not
claimed. The full specifications and independent quality evaluation remain open.
