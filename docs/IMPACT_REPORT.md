# Actionable impact reports

Helvetic Lens keeps the deterministic legal-unit comparison as the audit record and turns its bounded material-change dossier into a validated `impact-report-v4` review report. The model still produces a compact, citation-constrained draft. The API then verifies every citation against the saved versions and assembles the final contract deterministically.

The report contains:

- a headline, potential materiality, summary, and reason;
- each material change with its old and new legal-unit reference and exact saved evidence;
- organization applicability and affected business areas;
- literal date/period mentions with exact source quotes, version sides and an explicit unreviewed legal meaning; no automatic absent-date claim;
- assumptions and uncertainties;
- evidence coverage and a separate evidence grade;
- zero to five structured review suggestions.

Evidence grades are `confirmed`, `supported`, `possible`, or `needs_review`. They describe the strength and completeness of the saved evidence, not the potential severity of the change. Assessed severity is `high`, `medium`, or `low`; selected-evidence output has `unknown` impact and materiality, never an invented Low rating.

Each review suggestion has a stable normalized `action_key`, action type, verb/object title, rationale, proposed owner role, affected area, priority, due basis/date, applicability condition, related change IDs, evidence grade, and citations. Suggestions are never presented as confirmed legal obligations. Identical suggestions are merged across changes; their change IDs and citations are combined. A report may contain no actions when the evidence does not justify a concrete next step.

## Validation and history

The provider cannot select arbitrary evidence URLs or pages. The API materializes those fields from the saved version and passage after validating the quoted text. The final report is validated again against the server-owned schema, and duplicate action keys fail validation.

The impact cache boundary includes the comparison, semantic-diff fingerprint, organization profile revision, editable prompt fingerprint, prompt and report schema versions, provider/model runtime fingerprint, generation settings, and output locale. Successful and failed attempts remain in AI history. If a rerun fails, the comparison continues to show the last valid report and identifies the failed latest attempt.

The output locale is persisted for DE/FR/IT/RM/EN. Mode notices and selected-evidence explanations use the selected locale; source quotations remain in their original language. Full native-language review and remaining server-authored labels remain in HL-057. Historical v2/v3 reports stay readable with their original content and timestamps; the versioned cache requires new analysis to produce v4, rather than silently modifying history.

## Explicit response modes (HL-091)

- `selected_evidence`: the small-model adapter selects validated citation rows. The server records `assessment_status=not_assessed`, `impact=unknown`, unknown organization applicability, no actions or copied business areas, and date meaning `not_reviewed`. A successful selection request is not a successful legal-impact assessment. Absence of an assessment does not mean no action is needed.
- `generated_explanation`: the existing explanatory path produced text passing schema/citation checks. This label describes how the response was produced, **not** independent semantic quality or an approved model capability. Claim entailment and profile promotion remain open.
- `deterministic`: saved facts, clarification or a deterministic fallback; there is no model interpretation. A cached report answer retains the report's originating mode even when reuse costs zero calls.

For selected evidence, the complete deterministic comparison remains available. The compact report retains saved citations and actual before/after unit evidence. A quotation selected from only one version is labelled as that version's wording; it does not prove deletion/addition. Selection order cannot pair unrelated articles. Applicability/action questions can reuse the saved evidence without calls but are explicitly unassessed, not asserted conclusions. The Actions tab does not turn an empty selection result into a no-action recommendation.

The response-mode slice does not yet replace Docker-based adapter selection. Approved per-model/task/locale capabilities, immutable runtime identity, evaluation references and promotion remain HL-091 work. It does not auto-download/swap a model or silently call a cloud provider. Ask ≤3 / Impact ≤5 requests, one structured repair and exact evidence validation remain in effect.

## Date mentions and review state (HL-092)

Report v4 scans the **full text of selected saved material passages**, not a model's preview or generated prose. The deterministic `date-mentions-v1` scanner recognizes full month names in DE/FR/IT/RM/EN, ISO dates, numeric dates with a four-digit year, and common numeric periods. It creates no extra provider requests. This is not a review of unchanged passages or every date in either complete document.

`important_dates` contains at most eight literal `mention` values with a saved `version_side`, `change_id`, and exact quote around the mention, even beyond a passage's shortened preview. Calendar tokens use `kind=other`; period tokens use `kind=relative_period`. Their `status=uncertain`, `evidence_grade=needs_review` and null `date` mean that **no applicable calendar date has been established**. Numeric order, invalid source dates, relative periods and proposed dates are preserved verbatim; the scanner does not calculate or repair them. It cannot distinguish publication, entry into force, historical references, conditions or scope exceptions.

The separate `date_review` records the scanner version, selected-material scope, distinct passages scanned, detected/displayed mentions and display-limit flag. It always has `legal_meaning_status=not_reviewed`. Zero pattern matches never becomes `not_found`, nor proof that no deadline exists. Unsupported abbreviations, dates written as words, OCR damage and unselected passages can contain additional dates. Both version sides and repeated occurrences are retained; duplicate dossier rows are scanned once.

The comparison and history show the same compact, five-language date section. Exact source context is collapsed initially and existing citation controls retain their in-place evidence navigation. Counts and omitted mentions are visible. Legacy entries display their original recorded status with a historical warning; they are not recomputed on read. Actions without an established due basis use `not_reviewed`, not `not_found`.

Legal date extraction, reviewed absence/not-applicable states, anchored period calculation and independent domain/language review remain HL-092 work. These literal candidates support manual review; they are not accepted legal deadlines or evidence that the AI understood them.
