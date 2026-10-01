# Unified research core

Owner request: 1 October 2026. Implemented and locally verified. Core activation pending at source publication; both clients are deployed.

Legal and Pharma share the existing durable coordinator. This change connects its
capabilities rather than adding another engine, queue, database or configuration wizard.

## Five delivered outcomes

1. **Common task routing.** `research_contracts.py` registers twelve versioned tasks;
   `research_gateway.py` dispatches source discovery, reading, relevance decisions and
   synthesis. Empty comparisons return deterministically. Each dispatched step commits
   its task, pack, provider/model, schemas, input hash/references and reason before the
   request, and retains timing, outcome, output reference/hash and fallback afterwards.
   Synthesis also records the actual prompt and response-schema fingerprints. Existing
   leases, deadlines, budgets, revocation checks and interruption semantics remain.
2. **Connected evidence memory.** `research_knowledge.py` reads the native claim,
   citation, capture, comparison and review records. `/dossiers/{id}/knowledge` provides
   a paginated view of exact evidence, contradictions, claim history and human decisions.
   There is no independent truth store. New research can cite retained public passages
   in its own source namespace, with original dates and revocable origin links. A mixed
   private/public finding never enters public planning because one citation is public.
3. **Saved evidence before discovery.** New iterative research recalls permitted public
   captures and current reviewed findings before planning. The planner sees the remaining
   source scope; normal source discovery/read steps omit already retained URLs. A planner
   branch can explicitly request fresh reads when the question needs current verification.
   Private saved material remains in its separate authorized extraction context. The
   direct source and configurable broad-web lanes share the same candidate contract.
   Manual discovery now also survives both decision providers being unavailable, with
   an explicit unranked result. Total discovery failure retains every failed channel.
4. **Per-run coverage.** `research_coverage.py` projects committed receipts into one
   manifest of channels, retained/new captures, reading/analysis outcomes, unattempted
   candidates and unresolved questions. Rejected irrelevant candidates are distinct
   from unfinished checks. Run payloads and `/dossiers/{id}/coverage/research` expose
   this under current access. Both clients show a collapsed **What was checked** reader
   alongside the existing research answer, without another form or settings screen.
5. **Composable domain contracts.** GeneralPack, LegalPack and PharmaPack register
   actual shared task and source capabilities, context schemas, template/type/source-role
   definitions and versioned review policies. Source discovery resolves the selected
   pack's catalogue bindings; the gateway rejects unregistered tasks. Review writes pin
   their policy, and the knowledge/saved-search readers separate current human acceptance
   from machine support. New pack definitions are version 2.0.0; retained older context,
   template and review records remain historical and are not rewritten. GeneralPack is
   the reusable base contract, not a newly published third product.

## Scope and invariants

- Recall examines up to 20,000 eligible public captures using BM25 and retains up to six
  sources. Within selected sources it prioritizes current reviewed findings; this is
  not a claim of whole-ledger accepted-first semantic ranking. Existing local multilingual
  E5/BM25 saved-evidence search remains available under the same permission boundaries.
- A reused capture is historical evidence, not a newly downloaded or current document.
  It remains usable only while its origin capture, exact text and source access remain
  valid. Source withdrawal/deletion/text change removes it from derived readers/search.
- Policy-required review does not block exploratory findings. It prevents a machine
  finding from being represented as human-accepted. Explicit current human decisions
  retain their exact evidentiary basis, including considered contradictions.
- Registration is not source availability or coverage. Native feed/page acquisition
  retains its own permissions and scheduling. Authenticated archives, enterprise
  connectors and unimplemented domain-specific extraction tools are not invented.
- Existing native consent governs public queries, hosted analysis and monitoring.
  This release creates no production test dossiers and makes no paid model calls.
- This delivers the five shared research outcomes; it does not certify professional
  correctness or close every requirement in the much larger target specification.

## Verification and release

Controlled native Legal and Pharma journeys exercise exact retained-source reuse,
new discovery, citations in the resulting briefing, execution receipts and coverage.
Withdrawal/capture mutation, private/mixed evidence, human review changes and provider
outages are checked through real API/worker paths with fictional external adapters.
Client checks render the actual coverage reader and distinguish empty/unavailable,
retained/fresh, unsafe links and missing legacy receipts without browser automation.

Validation completed on 1 October 2026:

- Eight new native-core cases cover both product journeys, exact reused briefing
  citations, current-origin withdrawal, mixed/private evidence, human review and
  model-outage discovery. The final 17-case run, including recovery, budget and
  all six recurring-research audience/product journeys, passed.
- Affected saved-evidence, whole-ledger search, public research, domain/context,
  templates, source authority, claim review/interpretation and decision-search
  cases passed. A CTE keeps origin permission checks shallow enough for SQLite's
  nested count/search readers. Anonymous withdrawal remains enforced. Legacy
  incomplete step records do not break the additive coverage reader.
- Existing fixture readers now accept the deterministic reader options; budget
  assertions count the four actual search requests per balanced discovery pass
  (two broad-provider requests and two direct catalogues), rather than one logical
  query. No assertion about privacy or completed evidence was relaxed.
- Exact API Ruff gate and backlog guard passed. Both clients passed 455 tests,
  lint, type checking and production builds. No browser automation was used.
- Legal `5f08faecf3547c978bf02f15232bd0e647c572a7` and Pharma
  `1fad3e30034adce66a4823396f306f4475585869` are pushed and deployed as application
  1.85.0 / Sites version 81. Both custom origins return 200; their served research
  reader assets match the validated local builds by SHA-256.

The Core automatic deployment must activate this source before the new manifests
appear. The final activation identity is recorded in the product workspace's
`unified-core-production.json` after its public readiness check. No separate
report-only Core release is required.
