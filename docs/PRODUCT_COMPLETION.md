# One complete research and monitoring experience

Owner request, 1 October 2026: implement all four confirmed product gaps together.
Scope: MV2-020/023 research and MV2-022 updates, shared Legal/Pharma clients.
Depends on released mission dcfa85b6119a, source adapters, native jobs, ownership,
source consent, dossier capacity and current publication/guest access boundaries.

## Outcome

1. Durable deeper discovery: follow source-owned pagination and accessible archive
   indexes, retain channel cursors and exact query/coverage receipts, deduplicate
   across pages, and stop on exhaustion or no useful progress rather than an
   aggregate query quota. A failed channel cannot stop other accessible sources.
   Keep provider adapters replaceable; never treat a provider cursor as a URL.
2. Scheduled research uses the same completion-based mission, retained knowledge,
   whole-original reading and cited answer as an initial investigation. Remove the
   legacy two-start daily quota. A dossier's existing account slot covers all its
   research. Retain cadence, current authorization, one active research per dossier
   and no catch-up storm; report what changed against the prior answer.
3. One dossier control surface for its public question, daily/weekly/off monitoring,
   personal in-app updates and explicitly opted-in dossier email. Existing topic
   and page controls remain accessible as advanced source settings. Saving or
   opening a dossier never grants email or public-query consent. Delivery is
   durable, deduplicated and checks current recipient access before sending.
4. Evaluate complete real research on neutral public questions with independent
   primary-source expectations. Record retrieval coverage, conclusion support,
   contradiction handling, named gaps, elapsed time and measured/unknown costs.
   Repair reproduced failures and preserve honest partial/failed outcomes. An
   evaluator or passing fixtures alone are not evidence of live answer quality.

## Acceptance and boundaries

Use affected controlled cases for pagination/resumption, schedule/retry/access,
delivery consent/revocation and the shared reader, plus the repository's required
lint/backlog/client build gates. The owner's explicit real-quality request now
authorizes isolated public-source/model evaluation; no production fixture dossiers,
private material, new credentials, real fixture email or frozen 1.35/1.37 evaluation
is involved. Preserve existing provider accounts/configuration and report actual
provider failures and unmeasured spend. No claim of exhaustive internet coverage,
professional certification or every enterprise architecture capability.

Publish the complete integrated outcome to all three main branches and existing
production targets. Track exact release and evaluation evidence in the parent
product-completion checkpoint. Do not issue unfinished substep releases.

## Implemented behavior and checks

Discovery stores provider-owned cursors and the query/coverage history on each
branch. SearXNG pages, Crossref/Europe PMC, ClinicalTrials.gov, openFDA and the
accessible Swiss Federal Supreme Court publication-day index can continue.
EMA/FINMA remain current feeds, not historical archives. Source selection is
question-specific across domain catalogues. Explicit public URLs are read first;
the normal URL, robots, permissions and source-review gates still apply.

Scheduled checks create the same research mission as initial exploration, refresh
retained originals and compare corresponding sections of long documents. Repeated
evidence stays quiet; failures remain coverage gaps. The account's three-dossier
allowance is unchanged. No additional per-day start/retry quota is imposed.

Both clients expose one Monitoring surface for the question/schedule and personal
in-app/email choices. Dossier email is off by default, requires verified explicit
consent, and supports immediate, daily or weekly delivery. Native jobs fence
changed consent, disabled accounts, membership and withdrawn evidence. An uncertain
SMTP result requires explicit retry rather than an automatic duplicate message.

Live trials reproduced truncated/incorrect JSON, invented optional metadata,
paraphrased quotes, unsupported arithmetic and premature final-answer retries.
Hosted research now has an increased per-request output allowance, recognizes a single
schema-name wrapper, and attempts one format/citation repair with the original
input. Exact-cited sibling findings survive rejected proposals; rejected claims
and observations are recorded as unresolved interpretation gaps, with the answer
marked partial. Required section identity and whole-original reconciliation remain
mandatory. Literal quotation checks do not certify truth, provenance or all unit
conversions; independent quality review is still required.

Controlled acceptance covers saved pagination/resumption, three scheduled starts
in one day without overlap, corresponding long-document sections, explicit email
consent, revocation and uncertain-delivery replay. Client suites: 462 passing
functional cases per product; changed-controls cases, lint, type checking and
production builds pass. Core lint passes. Final affected-worker acceptance and
public-trial/release receipts are recorded in the parent completion checkpoint.

## Live quality evidence

Public trials run against the configured hosted Apertus, Jev/local Laya and local
SearXNG using isolated local databases. They create no production dossiers and send
no fixture email. Independent expectations come from NOAA (mountain measurement
baselines), NASA (annual versus multi-year sea-level rates), and original BIPM
resolutions (adoption versus publication dates). The criteria and final measured
outcomes are recorded in `PUBLIC_RESEARCH_ACCEPTANCE.md`.

Mountain and sea-level trials, including recovery attempts, did not produce accepted answers.
Relevant NOAA evidence was captured; sea-level discovery mostly found irrelevant
NASA pages. Model formatting/citation failures and actual provider 429/timeout
responses blocked synthesis. These failures are retained as
quality evidence, not renamed successful pilots. Model token usage is recorded
when returned; missing billing costs remain unknown. This release does not claim
exhaustive web coverage or validated professional accuracy.

## Document failure isolation

MV2-020, following aaa397ba23dc. Saved public-pilot state reproduces two fully
read, section-validated originals blocked by a third document's failed extraction.
No whole-document model request was attempted. A review failure also marked every
unfinished document failed, and a reflection retry could skip failed extractions.

Scope: reconcile ready originals independently, identify the exact failed review,
and retry only unavailable sections/reviews before reflection. Dependencies are
the existing immutable reader, exact-citation validation, native worker and retry
authorization. Saved public traces provide reproduction; no new live calls or
source credentials are needed. Access and source-dependency fences remain strict.

Acceptance: a failed extraction cannot starve another complete original; a failed
or interrupted whole-document review cannot poison its siblings; failed documents
remain incomplete; authorized retry preserves completed source/review work and
unresolved interpretation gaps. Verify these through the native worker, plus the
existing whole-document recovery case, exact API lint and backlog guard. Release
and live quality remain separate; this repair alone cannot prove live answers.

Implementation isolates review selection and failure receipts by original. A
failed reflection retry first resumes failed sections; completed reviews stay
saved. Interrupted review marks only its persisted original. Previously completed
originals are skipped when resuming an earlier read. Parser warnings still leave
coverage incomplete; this change neither clears them nor proves OCR recovery.

Controlled native recovery with three originals passes: a failed extraction and
failed review leave the third original completed; explicit retry extracts only
the failed section and reviews only the unfinished originals. Rejected-proposal
limitations survive. Interruption, unreadable-page completion and resumed-read
fences pass, along with existing contribution retry and dense reconciliation
recovery. Read-only replay of the saved public pilot now selects its two valid
originals despite the unrelated failed extraction. No network/model request or
database write is part of that replay. Release receipt follows in the parent
checkpoint; live final-answer quality remains NOT ACCEPTED.
