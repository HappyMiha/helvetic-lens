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

This deterministic result is only the first HL-064 gate. Provider-call budgets, cache invalidation, citation rejection, durable last-valid reports, action quality, operational measurements, and moderated two-minute usability remain separate acceptance checks.

