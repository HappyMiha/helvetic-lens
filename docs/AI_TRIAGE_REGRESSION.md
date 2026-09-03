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

The platform now records and aggregates deterministic-overview latency, provider queue/inference latency, calls/tokens, cache reuse, citation acceptance, limited/failed results, and action accept/dismiss outcomes as described in [the operational metrics contract](AI_TRIAGE_METRICS.md). The final release validator binds those metrics to a clean Git revision, the strict capacity report, its dual-GTX-1080 model profile, and five independent moderated sessions. Missing, substituted, or mismatched evidence fails closed.

The five-locale moderation template is `demo/ai-triage-usability-review.template.json`. Copy it outside the repository for each review round; do not replace the blank template with invented or self-reviewed results. Use a different fluent participant for each locale. Each participant starts on the material-change comparison without opening **All exact changes**, opens one exact citation, and records an action decision in the UI. The moderator records the participant's concrete description of the main material change, possible organizational relevance, evidence reference, next review step, and reviewed action within a timezone-bounded session. Boolean checkboxes alone are insufficient. Validate a completed copy with `python scripts/check_ai_triage_usability.py path/to/results.json --results`. Duplicate participants, blank observations, invalid timestamps, false/missing outcomes, over-120-second insight, or dependence on **All exact changes** fails the gate.

Run the moderated sessions on the clean target build before the final capacity run so their saved action decisions appear in the platform metrics captured by that run. Then set `capacity_report_sha256` in the completed usability file to the SHA-256 of the unmodified capacity JSON and run:

```powershell
python scripts/check_ai_triage_release.py `
  --capacity-report reports/capacity-result.json `
  --usability-results path/to/ai-triage-usability-results.json `
  --output reports/ai-triage-release.json
```

The combined command exits zero only when the strict capacity gate passed on the public HTTPS target from a clean 40-character Git revision; the usability file names that exact report, commit, host, and measured dual-GTX-1080 profile; all five independent sessions pass against corpus `hl064.v1`; deterministic insight has at least ten samples and remains below one second p95; local queue/inference and validation each have at least twenty samples; provider calls remain within the three/five-call budgets; no measured AI record failed; citation validation accepted every measured result; and at least five saved action decisions produced measurable accept/dismiss rates. Keep raw participant results outside Git. A checked-in release record should contain only the validator's aggregate output.
