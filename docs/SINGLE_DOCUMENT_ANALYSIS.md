# Whole-document analysis without redundant passes

## Scope before implementation — 9 October 2026

Scoped MV2-020/021/023 repair, prompted by a 3,055-character original that was fully
read and analysed once but marked incomplete because a mandatory extra document
review failed. Dependencies: retained originals, source/citation authority, stamped
reading context, document reconciliation and both client mission readers. Source
readiness: existing retained material and normal authorized research only.

Complete originals that fit one analysis batch should receive one complete analysis.
Preserve exceptions, contrary evidence, source context and internal references.
Retain multi-batch reconciliation only when it has unresolved work to perform;
never convert missing/invalid analysis into completion. Reuse already checked small
originals without fabricating a model call or overwriting historical evidence.
Keep current hashes, question scope, permission and duplicate-analysis guards.

Separate processing failures/pending work from substantive unanswered questions in
new and saved readings. Do not hide unresolved research questions or falsely label
incomplete analysis complete. Preserve the compact saved-reading endpoint.

Acceptance: one small original takes no redundant review call; missing/failed
analysis and unresolved cross-reference targets remain explicit; large originals
still reach late evidence and reconcile; changed rights/hash/question invalidate
completion. Both clients show technical status apart from evidence gaps. Run affected
Core tests and exact Ruff/backlog gate, client tests/lint/typecheck/build, push main,
verify normal Core and both existing Sites releases. Active research is never duplicated.

## Implemented and locally verified

- A complete single-capture public original with a current, validated analysis now
  finishes without a second model call. Its distinct `single-document-analysis/v1`
  receipt preserves exact findings, context anchors and limitations; no fictional
  document-review execution is written. The ordinary worker can recover the obsolete
  mandatory-review failure using that saved analysis.
- Missing analysis, extraction failures, unread pages, separate analysis batches
  and unresolved internal references retain their checks. Changed questions,
  source hashes, interpretations and access invalidate the old receipt; merely
  opening a saved reading cannot stamp changed evidence as current analysis.
- Technical document work is exposed as `processing_issues`, separate from genuine
  answer limitations. Precisely identified legacy generated technical limitations
  are separated when reading old checkpoints; historical conclusions are not
  promoted. Obsolete document-incomplete stop messages disappear when current
  document checks succeed. Failed branch history is not rewritten as a successful run.
- Saved-reading projections reuse their existing authorized source map and classify
  only the complete original being checked, avoiding another full-source load per
  document. Opening research still does not enqueue or execute model work.
- New focused coverage: 22 cases, including actual worker recovery without model or
  fetch calls, duplicate reuse, citation conditions, withdrawn sources and stale
  reading receipts. Read-map reuse and processing separation were also verified.
- All 109 affected regression cases passed, including 420-page late evidence,
  multi-part reconciliation, failure isolation, duplicate provenance, model
  transport and the required backlog guard. The exact API Ruff gate passed.
- Both clients 1.107.0: 557 tests each, lint, strict typecheck and exact Sites
  production builds passed. The mounted regression keeps real gaps and unfinished
  processing separate, avoids repeated progress entries, and correctly labels text
  that has already been read. No authenticated visual-browser acceptance is claimed.
- Publication and live activation are recorded separately from these local checks.
