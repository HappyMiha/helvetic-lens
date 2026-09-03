# AI-triage regression gate

HL-064 uses the labelled corpus in `demo/ai-triage-regression.json` as a stable acceptance input. It contains German, French, Italian, Romansh, and English cases for:

- a version attached to the wrong law;
- real PDF line-wrap noise;
- one inserted provision followed by renumbering;
- an unchanged section moved elsewhere;
- one true obligation/deadline change;
- an official repeal/replacement relation with its metadata evidence;
- a generated complete rewrite with 1,401 passages on each side.

The fixture stores intended outcomes rather than model prose. The deterministic gate fails if identity protection weakens, exact coverage becomes incomplete, formatting or movement becomes material, the insertion expands into many material changes, a real deadline is hidden, official relation provenance is incomplete, or any supported locale disappears from the corpus.

Run the fast development gate with:

```powershell
npm run test:ai-triage
```

Run the complete large-document gate before changing alignment, semantic grouping, or inference planning:

```powershell
npm run test:ai-triage:full
```

The quick mode evaluates 220 passages per side for the rewrite case. Full mode evaluates all 1,401 passages per side and still requires every old and new unit to be present in the complete exact diff. On 3 September 2026, full mode completed locally in 7.6 seconds and produced 1,500 material change records: 1,302 aligned substantive changes plus 99 additions and 99 removals. It produced no moved, renumbered, formatting-only, or uncertain records for that deliberately unrelated rewrite.

`npm run test:ai-triage:acceptance` exercises the API and analysis boundary. Its 1,401-passage comparison asserts a three-call Ask ceiling and five-call Impact ceiling. It also verifies zero-call clarification in under one second, identical-answer cache reuse, prompt-revision invalidation, exact quotation lookup in persisted passages, rejection of invented citations, preservation of the last valid report after a failed rerun, unique action keys, and a valid zero-action/zero-call formatting-only result.

The platform now records and aggregates deterministic-overview latency, provider queue/inference latency, calls/tokens, cache reuse, citation acceptance, limited/failed results, and action accept/dismiss outcomes as described in [the operational metrics contract](AI_TRIAGE_METRICS.md). A measured target-host baseline, human action-specificity review, and moderated two-minute usability remain separate acceptance checks.
