# Research from saved page changes

Status: DONE within scoped stage 4b2 / release 1.17 production acceptance. Full dynamic and visual
specifications remain IN PROGRESS. The next complete outcome is recurring
open-web discovery; private semantic indexing, independent quality evaluation
and native visual migration remain separate directions.

## User outcome

An editor with native workspace monitoring authority may explicitly select
**Include changes to saved source pages** in **Keep this dossier current**.
Existing settings remain topic-only. The form explains the chosen source scope
before a new standing authorization is saved. Scope changes are revision-checked,
idempotent, revocable and cancel previous pending work without resetting the
daily budget or deleting completed evidence.

Future retained versions of linked active daily page watches can start a private
investigation. The history shows its cause, exact version and evidence revision,
earlier/new text around the first difference, and revision-pinned readers for
both originals. Extraction sees only the new excerpt. A separate comparison
step can relate its independently extracted findings to previous dossier claims.
Text changes are candidate evidence; neither a changed page nor an AI relation
establishes verified truth or source independence.

## Native reuse and source readiness

DocumentWatch, Law, Version and the existing daily acquisition scheduler remain
authoritative. The research scheduler only observes retained live, non-synthetic
versions; it neither fetches pages nor retries source acquisition. A dossier's
monitor entry and the watch must predate a candidate version. Versions saved
before the scope was enabled form the baseline and are never retroactively
analyzed. Current Law/Version corpus visibility, linked organization watch,
active daily checks and source exclusions are enforced on capture and around
inference. Both the new and earlier evidence revisions are pinned and rechecked.

Workspace page watches remain unavailable in members-only dossiers. Page research
does not expand the private audience, convert body text into a public query,
publish findings, create provider accounts or subscribe anyone to email.
Current native actor, dossier role, profile and standing-policy checks remain
those of [topic-triggered research](PRODUCT_MONITORING_RESEARCH.md).

The source must contain readable changed text and an earlier retained live
version. Comparison reads at most 200,001 characters per side to enforce a
200,000-character ceiling. It captures a contiguous window of at most 12,000
characters starting 180 characters before the first difference. Both bounded excerpts are retained with the private trigger; its history shows
a preview limited to 1,500 characters per side and explains incompleteness. Full version readers remain
paged. Oversized, unchanged or unavailable evidence produces a durable skipped
reason. This is not an exhaustive diff or a completeness score.

## Durable state, cost and privacy

Migration `03d495bef125` adds an explicitly false `include_page_changes` policy
field and typed trigger identity `(dossier, source_kind, source_identifier,
source_revision)`. Existing topic receipts are backfilled from their exact
match/fingerprint without rewriting source JSON, IDs, history or consent. Topic
columns remain present; page receipts leave them null instead of overloading
them. Page identity is watch + version, with its native evidence revision.
Downgrading retained page scope/receipts is rejected instead of losing history.

Both trigger types share one-minute bounded scheduling, oldest observed evidence
first, the existing default 3 / maximum 6 starts per UTC day, serialized dossier
work, atomic trigger/job/quota/outbox writes and interruption handling. One start
has at most one extraction and one independent comparison. An interrupted paid
call is never automatically repeated; explicit retries consume the same budget.

Late results are discarded after policy disablement, watch revocation, unlinking,
source exclusion, corpus withdrawal, author-role changes or either source revision
changing. Completed source evidence keeps its private history while authorized.
Corpus withdrawal/unlinking removes its excerpts from research readers, trigger
details, streams, comparisons and private export; turning off acquisition alone
does not erase a permitted historical source. No private material enters public
search or public dossier research through this feature.

## Verification

The broader native regression passes 169 cases (1 smoke, 168 integration). Both
clients pass 101 behavior contracts, lint, strict type checking and final Sites
production builds. Exact native API Ruff passes. Configured-secret scans checked
137 built and 188 source files per client against all 3 configured provider values,
with zero matches. The final 25 native cases pass, including all 24 new page cases and the retained
monitoring schema contract. Exact production acceptance passed, as recorded below. Native
integration fixtures use the real page acquisition/version, scheduler, durable
job, extraction and paired-comparison paths with controlled model responses.
Production checks use read-only code/schema/process and anonymous route/asset
evidence. They do not create authenticated production user records or establish
professional factual accuracy. Browser interaction and human visual acceptance
are not claimed in this background cycle.


## Exact production acceptance — 27 September 2026 UTC

Native functional `210e5bf81e33a3665e5d1f546493d7f60806209c` activated at
23:08:29 UTC. Pharma `74f693bd1f47806e0bd65801042d8a7670f4dc48` and Loyer
`b2862842abec13a6237730b4dffae204ce222633` published as existing public Sites 20
at 23:09:14 and 23:09:48 UTC. Each custom domain passed 98 HTTP/auth/gateway/guide
checks and 47 exact served JS/CSS hashes. Both exact-source GitHub CI runs passed
(36357327464 and 36357338157).

Read-only native inspection confirms all 47 module hashes, migration
`03d495bef125`, false page-scope defaults, typed source identities and their unique
constraint, preserved topic receipts and dossier/organization foreign keys,
one-minute scheduling, four required native runtime containers, four scheduler
module hashes, the local parser fixture and healthy Laya. Evidence uses no
production user records or paid model probes. The 169-case broader native gate,
25-case final affected gate and both 101-test client gates pass; source lint,
types, builds and configured-secret scans pass. Browser interaction and
professional factual-quality acceptance remain unclaimed.

[Exact release receipt](product-releases/2026-09-28-1.17.0.json).
The existing hourly heartbeat remains ACTIVE. Recurring open-web discovery,
private semantic indexing, independent evaluation and full native visual migration
are still open; this completes the scoped saved-page outcome, not either full
specification.
