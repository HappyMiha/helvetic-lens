# Actionable impact reports

Helvetic Lens keeps the deterministic legal-unit comparison as the audit record and turns its bounded material-change dossier into a validated `impact-report-v3` review report. The model still produces a compact, citation-constrained draft. The API then verifies every citation against the saved versions and assembles the final contract deterministically.

The report contains:

- a headline, potential materiality, summary, and reason;
- each material change with its old and new legal-unit reference and exact saved evidence;
- organization applicability and affected business areas;
- effective date and deadline entries; selected-evidence mode uses `not_reviewed`, not a claim that no date exists. The legacy generated-report adapter still needs the date-extraction correction in HL-092;
- assumptions and uncertainties;
- evidence coverage and a separate evidence grade;
- zero to five structured review suggestions.

Evidence grades are `confirmed`, `supported`, `possible`, or `needs_review`. They describe the strength and completeness of the saved evidence, not the potential severity of the change. Assessed severity is `high`, `medium`, or `low`; selected-evidence output has `unknown` impact and materiality, never an invented Low rating.

Each review suggestion has a stable normalized `action_key`, action type, verb/object title, rationale, proposed owner role, affected area, priority, due basis/date, applicability condition, related change IDs, evidence grade, and citations. Suggestions are never presented as confirmed legal obligations. Identical suggestions are merged across changes; their change IDs and citations are combined. A report may contain no actions when the evidence does not justify a concrete next step.

## Validation and history

The provider cannot select arbitrary evidence URLs or pages. The API materializes those fields from the saved version and passage after validating the quoted text. The final report is validated again against the server-owned schema, and duplicate action keys fail validation.

The impact cache boundary includes the comparison, semantic-diff fingerprint, organization profile revision, editable prompt fingerprint, prompt and report schema versions, provider/model runtime fingerprint, generation settings, and output locale. Successful and failed attempts remain in AI history. If a rerun fails, the comparison continues to show the last valid report and identifies the failed latest attempt.

The output locale is persisted for DE/FR/IT/RM/EN. Mode notices and selected-evidence explanations use the selected locale; source quotations remain in their original language. Full native-language review and remaining server-authored labels remain in HL-057. Historical v2 reports stay readable with their original content and timestamps; the versioned cache requires new analysis to produce v3, rather than silently modifying history.

## Explicit response modes (HL-091)

- `selected_evidence`: the small-model adapter selects validated citation rows. The server records `assessment_status=not_assessed`, `impact=unknown`, unknown organization applicability, no actions or copied business areas, and dates `not_reviewed`. A successful selection request is not a successful legal-impact assessment. Absence of an assessment does not mean no action is needed.
- `generated_explanation`: the existing explanatory path produced text passing schema/citation checks. This label describes how the response was produced, **not** independent semantic quality or an approved model capability. Claim entailment and profile promotion remain open.
- `deterministic`: saved facts, clarification or a deterministic fallback; there is no model interpretation. A cached report answer retains the report's originating mode even when reuse costs zero calls.

For selected evidence, the complete deterministic comparison remains available. The compact report retains saved citations and actual before/after unit evidence. A quotation selected from only one version is labelled as that version's wording; it does not prove deletion/addition. Selection order cannot pair unrelated articles. Applicability/action questions can reuse the saved evidence without calls but are explicitly unassessed, not asserted conclusions. The Actions tab does not turn an empty selection result into a no-action recommendation.

The response-mode slice does not yet replace Docker-based adapter selection. Approved per-model/task/locale capabilities, immutable runtime identity, evaluation references and promotion remain HL-091 work. It does not auto-download/swap a model or silently call a cloud provider. Ask ≤3 / Impact ≤5 requests, one structured repair and exact evidence validation remain in effect.
