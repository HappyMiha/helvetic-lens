# Research from saved page changes

Status: VERIFYING, scoped stage 4b2 / release 1.17. Full dynamic and visual
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
monitoring schema contract. Exact production acceptance is pending. Native
integration fixtures use the real page acquisition/version, scheduler, durable
job, extraction and paired-comparison paths with controlled model responses.
Production checks use read-only code/schema/process and anonymous route/asset
evidence. They do not create authenticated production user records or establish
professional factual accuracy. Browser interaction and human visual acceptance
are not claimed in this background cycle.
