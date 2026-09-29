# Completed Monitoring release commentary

Archived verbatim from the active backlog on 28 September 2026 to keep its
validated 512 KiB reader bound. The active queue and task acceptance remain in
[BACKLOG_MONITORING_V2.md](BACKLOG_MONITORING_V2.md); these are historical results.

## Research continuation — 1.37 conservative local rejection

DONE within uncertainty repair, evaluation and verified publication; recorded before code. MV2-002/020/023/051: preserve uncertain
candidate decisions, develop a versioned local Laya rejection guard, and measure
its extra review burden against reduced false exclusion. Existing provider,
worker, cumulative budgets and public NoMIRACL cache only; no private dossiers or
paid calls. Development uses dev hash offsets 12–13, validation uses test offsets
42–43, two questions per relevance subset/language (EN/DE/FR), all judged
candidates; verify no overlap with prior project query IDs. Development is capped at 121 and validation at 120 local calls; each has
240 seconds / 12 seconds per call (total 241 / 480). This pre-inference size
correction retains one development query with 11 candidates; no labels/results
were used to alter sample selection.
Raw source passages stay outside Git. Threshold candidates are fixed before calls:
0.50, 0.65, 0.80, 0.90, 0.95. Only low-score unrelated → uncertain is permitted;
never auto-admit uncertain records or label confidence as accuracy.
Selection: zero development positive exclusions, retain at least half the baseline
negative exclusions, extra uncertainty <=20% of all cases, retain most negative
exclusions, then lowest threshold. If no candidate qualifies, no promotion.
Freeze selection before opening validation labels/results. Validation promotion:
complete matched inputs/model, positive exclusions <= baseline and <=5% of positive
labels, retain >=50% of baseline negative exclusions, extra uncertainty <=20%,
at least one low-score rejection deferred. A failure prevents production promotion.
Independently preserve final uncertain review events instead of calling them rejected.
Acceptance: deterministic privacy/budget/uncertainty tests; frozen development and
fresh validation receipts; exact API/script lint, affected tests, native publication.
Clients stay at verified 1.36 unless a user-visible reader change is required.
No threshold passed development; validation stays unopened and no guard is
promoted. Worker activity now distinguishes uncertain/unavailable from rejected;
raw provider scores and policy version are retained. 65 affected cases pass.
Core git-09ab8bcfff5f is verified live; both clients retain verified 1.36 assets.
Native health, 25 module hashes, five containers, nine routes and schema passed.
See [scope](docs/PRODUCT_RESEARCH_GATE_POLICY.md). Parents and professional quality OPEN.



## Product decision — 1.29 domain-aware dossier setup

DONE within verified 1.29 scope; recorded before implementation on 28 September. Scope, dependencies,
source readiness and acceptance are in [PRODUCT_DOMAIN_SETUP.md](docs/PRODUCT_DOMAIN_SETUP.md).
MV2-002/020/023: server-selected LegalPack/PharmaPack for common profile suggestions,
refinement, source advice and honest discovery capabilities; visible saved direction
in both clients. Full target architecture and broader parent gates remain open.



## Owner priority — 1.30 readable dossier

DONE within verified 1.30 implementation/release scope; recorded before code
on 28 September. The owner requested a document-like dossier before further
architecture work. Human usability and broader parent gates remain open. See
[PRODUCT_DOSSIER_CLARITY.md](docs/PRODUCT_DOSSIER_CLARITY.md) for MV2-002/020/024
scope, dependencies, unchanged source readiness and acceptance. Separate reading,
human discussion, AI research and original sources while preserving every workflow.



## Architecture continuation — 1.31 structured dossier context

DONE within the bounded 1.31 scope; recorded before code on 28 September.
C03/C33 and MV2-002/020/023 now include optional, versioned Legal/Pharma subject
fields on the common dossier with existing roles and audit. Both clients and the
shared Core are published and verified; 105 API checks and 173 tests per client passed. See [scope and acceptance](docs/PRODUCT_STRUCTURED_CONTEXT.md).
This does not establish entity resolution, applicability or source coverage.



## Architecture continuation — 1.32 versioned dossier templates

DONE within the bounded 1.32 scope; recorded before code. C33/C44/C48 and
MV2-002/020/023 now include optional versioned template selection and retained
guidance on the existing shared dossier. Core and both products are published
and verified; 116 API checks and 179 client tests each passed. See [scope and acceptance](docs/PRODUCT_DOSSIER_TEMPLATES.md).
This does not complete source readiness or the Market Access proving journey.



## Research continuation — 1.38 captured-source relationships

DONE within the verified source-provenance scope; recorded before code. MV2-002/020: explain matching captured content,
same-address versions and unknown source independence beside exact paired quotes
in Changes over time. Capture time is distinct from publication/effective time.
Reuse existing comparisons, source snapshots, visibility, review and client basis
rendering. No provider call, schema change or automatic claim merge. See
[scope, source readiness and acceptance](docs/PRODUCT_SOURCE_RELATIONSHIPS.md).



## Research continuation — 1.39 reviewed entity identity

DONE within verified pair-review/publication scope; recorded before code.
61 affected Core checks and 203 tests/lint/types/build per client passed. Core
git-5b03c488e5bf and both existing Sites 39 are live; 38 HTTP/access checks and
47 exact assets per client plus native runtime/schema verified. MV2-002/020/024: exact cited cross-run entity
suggestions and explicit reversible editor decisions in the same dossier/audience.
Reuse original mentions, sources and native review/visibility contracts. Existing
captured identifiers only; no source acquisition or model call. See
[scope, dependencies and acceptance](docs/PRODUCT_ENTITY_IDENTITY.md).
Full canonical registry, professional quality and broader parent acceptance OPEN.



## Research continuation — 1.35 bounded evaluation

DONE within bounded evaluation/publication scope. MV2-002/020/023/051 reuse the pinned public
NoMIRACL cache, existing local Laya adapter, 1.34 gate instructions and saved
controlled-worker traces. Freeze a disjoint sample and explicit call/time budgets;
measure three-way relevance outcomes and deterministic citation/follow-up integrity.
Publish IDs/hashes/metrics only. No paid probes or private production records.
[Scope, readiness and acceptance](docs/PRODUCT_RESEARCH_EVALUATION.md).
Live hosted/full-workflow quality and all broader parent gates remain OPEN.



## Owner priority — 1.34 iterative dossier research

DONE within the verified 1.34 scope; scope defined before implementation. MV2-002/020/023 and the new
[Investigation Engine specification](docs/INVESTIGATION_ENGINE_SPEC.md), sections
42–43. [Architecture audit, dependencies, readiness and acceptance](docs/PRODUCT_ITERATIVE_RESEARCH.md)
record the current gaps and additive vertical slice: question-first creation,
planner, candidate gate, cited claims/entities/edges, persistent open questions,
a real second search updating existing evidence, budgets and readable UI.
Core and both clients are published and verified. 64 API checks and 189 tests per
client passed, alongside exact runtime/assets and anonymous access checks. Legacy
monitoring/source rights remain intact. Full specifications and live quality remain OPEN.

