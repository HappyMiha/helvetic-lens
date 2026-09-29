# Quoted saved text and AI interpretation — 1.46

Status: DONE within the verified bounded release. Scope recorded before code; MV2-002/020/023/024.

Offer an explicit research answer format that separates literal saved text from
model interpretation. A checked citation proves text provenance, not the truth,
current authority or semantic validity of an interpretation. Quoted team notes
and source snapshots retain their actual source kind; quotations are never
automatically classified as source facts or binding/domain claims.

## Dependencies and source readiness

Reuse the existing research preview, model provider, DossierEntry, citations,
claims_v1/claims_typed_v1 dependency guards, answer review, export/brief and client
note renderer. Retained eligible evidence and fictional test fixtures suffice.
No new source, table, migration, provider, credentials, paid probe or private
production dossier. No browser/preview inspection in this background cycle.

## Bounded outcome and acceptance

- Optional answer_format=source_analysis_v1 on the two existing claim scopes;
  standard remains the default. Require explicit current preview. Unsupported
  combinations, formats or missing previews fail before inference.
- Preview states the versioned output contract and its limitations. Fingerprint
  and retry identity include the chosen format/contract; changing either invalidates
  consent. Default saved/claims_v1/claims_typed_v1 requests, provider input/schema,
  fingerprint and old immutable notes remain compatible.
- A strict output kind distinguishes SOURCE_QUOTE from AI_INTERPRETATION. A
  SOURCE_QUOTE has one citation and claim text equal to that citation's quote;
  every citation must match a supplied excerpt using existing whitespace-normalized
  contiguous verification. Reject missing/unknown kinds, paraphrases disguised as
  quotes, multiple-source composite quotes and invented evidence without saving.
- The label is “Quoted saved text”, never “verified fact”. Model selection of an
  excerpt does not establish authority, applicability, completeness or correctness.
  Human answer acceptance remains a separate workflow state. No automatic domain
  claim type, ledger insertion or source authority assignment.
- Render each quotation once within its finding, with source identity/kind and separate AI paragraphs
  and exact citations. Preserve kind/contract in retained note and JSON export;
  printable brief keeps the same distinction and escapes untrusted text. Legacy
  notes keep their original presentation. No additional dossier dashboard panel.
- Preserve complete contradictions and independent editor context; validate sources
  and rights before/after inference. Changes still block accepting stale notes;
  withdrawn direct/related dependencies hide note/replay/export/brief/follow-ups.
- Prove old-format compatibility, explicit choice without inference, format-bound
  retries, strict citation/kind failures, both products, empty evidence, changed
  previews, stale/hidden dependencies and real rendered/source-access behavior.
  Run affected API tests/exact lint/backlog invariant, full client tests/lint/types/
  builds, main pushes, existing Sites and exact native/product activation checks.

Full canonical Findings, domain extraction, semantic entailment verification,
authority ranking, applicability, GENERAL, Market Access and human acceptance
remain OPEN.


## Implementation

The opt-in output is an extension of the existing research request, not another
retrieval engine or evidence scope. ResearchInput and the preview query accept
answer_format; research_bundle adds the explicit source-analysis/v1 contract to
its fingerprint only when selected. Provider input evidence remains identical
for the corresponding claim scope. The provider receives a separate strict
SeparatedResearchAnswer schema and instructions; default ResearchAnswer and
previous prompt/input contracts remain unchanged.

SOURCE_QUOTE permits exactly one citation whose quote equals the finding text.
Every quote in both kinds also passes the existing normalized contiguous source
check. This validates provenance, not entailment, source authority or factual
correctness. DomainPack labels are not assigned to generated output. No new
DossierClaim or review is created automatically.

Both clients prepare a new preview when Answer style changes. Generation requires
the selected scope and format to match the prepared data. The retry helper rejects
unknown formats/contracts and keeps separate keys while preserving old identities.
The retained note, generic entry body, JSON export and printable brief retain the
kind distinction; one finding renders its literal quotation once. The existing
folded input context may separately repeat source text for provenance. Current
source access, uncertainty, supporting/contrary input context and review controls
remain in their existing locations. There is no additional dossier panel.

## Verification status

Client checks: 232 tests, lint, typecheck and portable production builds passed in
each product. Real React tests cover explicit selection without inference, wrong
format responses, exact failed-request retry identity, escaped rendering and legacy
presentation. Ten new server cases passed, including both products, strict kind/citation failures,
contract consent/retry, legacy output, empty evidence, changed context and direct/
related-source withdrawal. Initial test-harness corrections used the existing
fixture dossier ID and split negative requests across fresh fixtures to respect
the real inference rate limit; production behavior was not changed by those fixes.
The 81-case affected server regression suite passed, including the backlog invariant:
91 distinct server cases are verified in total. The exact API lint gate passed.
Exact initial production publication is verified below. Full architecture
and human/professional acceptance remain open.


## Publication and production evidence

Core implementation `fc48651fcd73f9e0d0ef8d8149ac36b0f20add70` activated as
`git-fc48651fcd73` at 2026-09-29T10:59:54+00:00. The existing public Sites 46 use
Legal `d42bfac5fc46485037068f446e55f4b2d24917da` and Pharma
`239578eafddba919eee511ac5f276e80eae3f6b8`. Legal activated at
2026-09-29T11:00:34.147206+00:00; Pharma at 2026-09-29T11:01:14.888974+00:00.

The [frozen release receipt](product-releases/2026-09-29-1.46-source-analysis.json)
verifies 41 exact runtime module hashes, the unchanged DomainPack 1.4.0 and
0bd495bef125 schema, five running containers and nine native navigation routes.
Each product passed 45 public/access checks and 47 exact published asset hashes.
The public guide and compiled optional format are active; anonymous private
preview/generation remain denied. Labels come from the retained server contract;
compiled client checks verify its version and quotation rendering branch. All
three main checkouts were clean and aligned after fresh fetches at verification.

The local gate covered 91 distinct Core cases and 232 tests per client, lint,
types and production builds. Source parity and protected-value scans passed.
The normal native release policy ran smoke/functional checks; its integration
step remains explicitly skipped under the existing policy. The affected integration
cases above were run locally before publication. The completed Global Ask 1.24
backlog overview was archived verbatim; the 512 KiB guard was preserved.

No browser, authenticated production dossier or paid inference probe was used.
Native backup still briefly pauses API/tunnel; this is not zero-downtime evidence.
Final documentation activation is observed separately in the parent checkpoint
without republishing unchanged clients. Full architecture, live source readiness,
semantic entailment and human/professional acceptance remain OPEN.
