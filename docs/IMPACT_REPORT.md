# Actionable impact reports

Helvetic Lens keeps the deterministic legal-unit comparison as the audit record and turns its bounded material-change dossier into an `impact-report-v5` review report. A model with a currently reviewed model/task/locale capability produces a structured decision draft. The API validates its structure, reference integrity and review-state consistency before materializing exact saved citations. Those checks do not prove legal entailment or usefulness.

The report contains:

- a headline, potential materiality, summary, and reason;
- each material change with its old and new legal-unit reference and exact saved evidence;
- organization applicability and affected business areas;
- literal date/period mentions with exact source quotes, version sides and an explicit unreviewed legal meaning; no automatic absent-date claim;
- assumptions and uncertainties;
- evidence coverage and a separate evidence grade;
- zero to five structured review suggestions.

Evidence grades are `confirmed`, `supported`, `possible`, or `needs_review`. They describe the strength and completeness of the saved evidence, not the potential severity of the change. Assessed severity is `high`, `medium`, or `low`; selected-evidence output has `unknown` impact and materiality, never an invented Low rating.

Each new decision suggestion has a stable `action_key`, action type, title, concrete instruction, rationale, actual organization activity, priority, applicability condition, related change IDs, exact obligation anchor and citations. The server sets an unassigned owner and unreviewed null due date; the draft cannot assign people or calculate deadlines. Suggestions remain interpretations for human review, never confirmed duties. An empty action list is explicitly distinguished from a reviewed `no_action_now` decision.

## Validation and history

The provider cannot select arbitrary evidence URLs or pages. The API materializes those fields from the saved version and passage after validating the quoted text. The final report is validated again against the server-owned schema, and duplicate action keys fail validation.

The impact cache boundary includes the comparison, semantic-diff fingerprint, organization profile revision, editable prompt fingerprint, prompt and report schema versions, provider/model runtime fingerprint, generation settings, and output locale. Successful and failed attempts remain in AI history. If a rerun fails, the comparison continues to show the last valid report and identifies the failed latest attempt.

The output locale is persisted for DE/FR/IT/RM/EN. New review labels, deterministic change descriptions and unassigned/unknown states use that locale; source quotations remain in their original language. Independent native-language review and remaining server-authored labels remain open. Historical v2/v3/v4 reports stay readable with their original content and timestamps; explicit reassessment produces v5 instead of silently modifying history.

## Explicit response modes (HL-091)

- `selected_evidence`: the small-model adapter selects validated citation rows. The server records `assessment_status=not_assessed`, `impact=unknown`, unknown organization applicability, no actions or copied business areas, and date meaning `not_reviewed`. A successful selection request is not a successful legal-impact assessment. Absence of an assessment does not mean no action is needed.
- `generated_explanation`: the existing explanatory path produced text passing schema/citation checks. This label describes how the response was produced, **not** independent semantic quality or an approved model capability. Claim entailment and profile promotion remain open.
- `deterministic`: saved facts, clarification or a deterministic fallback; there is no model interpretation. A cached report answer retains the report's originating mode even when reuse costs zero calls.

For selected evidence, the complete deterministic comparison remains available. The compact report retains saved citations and actual before/after unit evidence. A quotation selected from only one version is labelled as that version's wording; it does not prove deletion/addition. Selection order cannot pair unrelated articles. Applicability/action questions can reuse the saved evidence without calls but are explicitly unassessed, not asserted conclusions. The Actions tab does not turn an empty selection result into a no-action recommendation.

Production mode selection is now based on the captured model/task/locale capability and observed runtime, not a successful connection or Docker label. The shipped registry contains no approved explanatory model. Unreviewed providers return selected evidence; the rich contract does not promote a model, download/swap one or silently call a cloud provider. Ask ≤3 / Impact ≤5 requests, one structured repair per completion within that ceiling, full native prompt/output budgets and exact evidence validation remain in effect. Low-level legacy test/adaptor paths remain explicitly marked `legacy_compatibility`; production clients with a capability decision never fall back to these templates after a failed draft.

## Structured decision drafts (HL-092, 6 September 2026)

The approved Impact synthesis uses `decision-draft-v1` within the existing batch/synthesis call budget. It supplies numbered organization activities and selected change/citation catalogs, including both admitted version sides even when the batch originally cited only one. At most eight selected changes enter this synthesis; each citation is a bounded exact excerpt. Native measurement includes the complete prompt, schema and repair before generation. A rich schema that does not fit is rejected, not silently truncated or allowed extra calls. Capability promotion must evaluate this actual workload and reserve an adequate output budget; synthetic transport fixtures cannot establish that a real 700-token response suffices.

The model must produce separate per-change explanations, applicability status/conditions, official-status interpretation, a decision about next steps, specific actions and uncertainties. The server validates every nested reference; change claims cannot cite a different legal unit and must cite both supplied sides. Organization numbers must refer to actual profile business areas. An exact anchor quote is required for each action. URL/title guesses, invented activity numbers, provider owners/dates, inconsistent review states and unknown fields are rejected. One repair receives the same catalogs and validation error; a second failure stays failed in history. There is no template substitute pretending that the rich review succeeded.

`decision_review` records interpreted/legacy/unreviewed basis, available and explained change counts, partial scope and merged-action count. `material_changes[].explanation_basis` distinguishes an actual interpretation from a server rendering of saved before/after wording. Interpreted changes are prioritised in the bounded report display; all deterministic changes remain in the unchanged comparison. Explanation counts do not imply semantic correctness or complete document review.

`official_status` distinguishes proposal, enacted, repealed, mixed and unknown, with its own citations and an explicit model-interpretation label. It is not an authoritative enactment check. `action_review` distinguishes `review_actions`, `no_action_now` and `not_reviewed`. A global no-action decision requires citations, known organizational applicability, explanation of all material changes and non-partial evidence; excerpt clipping also prevents that decision. Empty results, unknown scope or a skipped change cannot pass as no action needed.

Action identity hashes the exact saved version/passage, normalized obligation quote, actual activity and action type, excluding the generated title and wording. Paraphrases sharing that identity merge citations/change IDs and retain the highest suggested priority. Distinct activities/types/anchors remain separate. This is bounded anchor-based deduplication, not a semantic matcher for different overlapping quotes, old/new equivalent obligations or unrelated obligations sharing a generic phrase. Those cases require independent fixtures and further HL-092/093 work.

The comparison summary, action state and historical viewer share five-language decision notices. Source disclosures use existing in-place citation navigation; legacy reports receive a warning without modification. Ask can reuse current applicability conditions and action rationale/conditions with the interpretation warning and report ID, without another model call. Date meaning remains unreviewed; this slice neither computes deadlines nor treats a literal date as a legal obligation.

Remaining gates: actual legal date types and scope exceptions, reviewed absence/not-applicable states, relative anchors, full semantic deduplication, independently adjudicated proposal/applicability/action quality, fluent-language review, and evaluation/promotion on the real target model and GPU hardware. Exact quotes and schema validity alone do not pass those gates. No database migration or automatic reassessment is required.

## Date mentions and review state (HL-092)

Report v4 scans the **full text of selected saved material passages**, not a model's preview or generated prose. The deterministic `date-mentions-v1` scanner recognizes full month names in DE/FR/IT/RM/EN, ISO dates, numeric dates with a four-digit year, and common numeric periods. It creates no extra provider requests. This is not a review of unchanged passages or every date in either complete document.

`important_dates` contains at most eight literal `mention` values with a saved `version_side`, `change_id`, and exact quote around the mention, even beyond a passage's shortened preview. Calendar tokens use `kind=other`; period tokens use `kind=relative_period`. Their `status=uncertain`, `evidence_grade=needs_review` and null `date` mean that **no applicable calendar date has been established**. Numeric order, invalid source dates, relative periods and proposed dates are preserved verbatim; the scanner does not calculate or repair them. It cannot distinguish publication, entry into force, historical references, conditions or scope exceptions.

The separate `date_review` records the scanner version, selected-material scope, distinct passages scanned, detected/displayed mentions and display-limit flag. It always has `legal_meaning_status=not_reviewed`. Zero pattern matches never becomes `not_found`, nor proof that no deadline exists. Unsupported abbreviations, dates written as words, OCR damage and unselected passages can contain additional dates. Both version sides and repeated occurrences are retained; duplicate dossier rows are scanned once.

The comparison and history show the same compact, five-language date section. Exact source context is collapsed initially and existing citation controls retain their in-place evidence navigation. Counts and omitted mentions are visible. Legacy entries display their original recorded status with a historical warning; they are not recomputed on read. Actions without an established due basis use `not_reviewed`, not `not_found`.

Legal date extraction, reviewed absence/not-applicable states, anchored period calculation and independent domain/language review remain HL-092 work. These literal candidates support manual review; they are not accepted legal deadlines or evidence that the AI understood them.
