# Actionable impact reports

Helvetic Lens keeps the deterministic legal-unit comparison as the audit record and turns its bounded material-change dossier into a validated `impact-report-v2` review report. The model still produces a compact, citation-constrained draft. The API then verifies every citation against the saved versions and assembles the final contract deterministically.

The report contains:

- a headline, potential materiality, summary, and reason;
- each material change with its old and new legal-unit reference and exact saved evidence;
- organization applicability and affected business areas;
- effective date and deadline entries, explicitly marked `not_found` when the evidence does not establish them;
- assumptions and uncertainties;
- evidence coverage and a separate evidence grade;
- zero to five structured review suggestions.

Evidence grades are `confirmed`, `supported`, `possible`, or `needs_review`. They describe the strength and completeness of the saved evidence, not the potential severity of the change. Severity remains `high`, `medium`, or `low`.

Each review suggestion has a stable normalized `action_key`, action type, verb/object title, rationale, proposed owner role, affected area, priority, due basis/date, applicability condition, related change IDs, evidence grade, and citations. Suggestions are never presented as confirmed legal obligations. Identical suggestions are merged across changes; their change IDs and citations are combined. A report may contain no actions when the evidence does not justify a concrete next step.

## Validation and history

The provider cannot select arbitrary evidence URLs or pages. The API materializes those fields from the saved version and passage after validating the quoted text. The final report is validated again against the server-owned schema, and duplicate action keys fail validation.

The impact cache boundary includes the comparison, semantic-diff fingerprint, organization profile revision, editable prompt fingerprint, prompt and report schema versions, provider/model runtime fingerprint, generation settings, and output locale. Successful and failed attempts remain in AI history. If a rerun fails, the comparison continues to show the last valid report and identifies the failed latest attempt.

The current output locale is English until the five-language work in `HL-057` supplies locale negotiation and translated report prompts. Historical `impact` fields remain readable while clients adopt `materiality` and the richer report fields.
