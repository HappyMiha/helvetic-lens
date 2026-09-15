# Independent business matching evaluation

Status: MV2-051 IN PROGRESS. The offline reporting workflow covers B2 Tender,
B7 Trademark and B8 Auction candidate relevance. It does not measure legal
conflict accuracy or authorize a model, source connection or deployment.

## Prepare a private package

Use a directory outside the repository for real review material. Do not commit
source documents, credentials, personal profiles, human labels or captured model
outputs. The command makes no network, model or database calls. Only an explicit
new output filename is written; existing reports are never replaced.

From the development checkout, export the five versioned JSON authoring schemas:

```powershell
services/api/.venv/Scripts/python.exe -B scripts/evaluate_business_matching.py schemas --output C:/private-review/business-schemas.json
```

On other platforms use the API environment's Python executable. The destination
directory must already exist. Schemas describe contracts; they contain no gold
answers, reviewer identities or source permission grants.

Prepare these files according to the exported schemas:

| File | Purpose |
|---|---|
| `dataset.json` | Frozen case IDs, publication families, business case, language, development/held-out split, release-critical designation, input and source references |
| `labels.json` | Dataset hash, freeze time, independent gold reviewers, two votes per pair, exact source-field quotes and distinct adjudication when votes disagree |
| `predictions.json` | Exact dataset, input and configuration hashes; system/commit identity; captured full outputs; decisions, failures, abstentions and cited fields |
| `audits.json` | Exact dataset and predictions hashes; output review time; separate reviewers of complete captured outputs; per-output hashes and factual verdicts |
| Referenced artifacts | Inputs, normalized source snapshots, source permission records, configuration/runtime manifests and full outputs |

An artifact reference contains a relative forward-slash path and SHA-256 of its
exact bytes. Absolute paths, drives, traversal, escaped symlinks, changed hashes,
duplicate JSON keys and nonfinite JSON numbers are rejected. Individual files
are limited to 8 MiB. Unique artifact reads and repeated artifact processing each
have a 128 MiB limit. There are at most 2,000 pairs, ten sources per pair, 256
fields per source and 50 reported output citations per pair. If a corpus is too
large, curate a bounded review package without silently dropping failed rows.

Inputs are JSON. Preserve the exact profile, source edition, normalization and
effective clock used by the captured matcher in that input. Configuration and
implementation manifests are JSON artifacts; include the complete non-secret
configuration and runtime/model/implementation identity used for the run. Their
hashes must match the prediction manifest. A supplied hash does not independently
prove that the stated system produced the output.

Source snapshots are flat JSON maps of stable field IDs to exact text. For
example, `{"title":"Exact retained title","deadline":"Exact retained wording"}`.
The captured source edition and permission reference must establish the origin
of these fields; the evaluator neither downloads nor reconstructs originals.
A citation names `source_id`, `field` and an exact quotation of at least eight
characters. It must occur in that particular permitted field, not elsewhere in
the document. Preserve Unicode and wording when preparing the snapshot.

Each source references a separate `mv2.evaluation-permission.v1` JSON artifact:

```json
{
  "schema_version": "mv2.evaluation-permission.v1",
  "snapshot_sha256": "<64 lowercase hexadecimal characters>",
  "permitted_fields": ["title", "deadline"],
  "evaluation_allowed": true,
  "reference": "<actual reviewed permission and retained evidence reference>",
  "reviewed_at": "2026-09-01T00:00:00Z",
  "valid_until": "2026-10-01T00:00:00Z"
}
```

This is an authoring example, not a permission or a valid ready-made record.
Use actual permissions and dates. Permission must cover the exact snapshot and
the whole period from frozen labels through the run and final output audit.
An expired or denied permission blocks readiness and does not count as a valid
output citation. Current revocation and the authenticity of the permission
still require external verification; the offline command cannot query them.

## Freeze, capture and review

1. Curate permitted pairs and separate related publications into families. Freeze
   development and held-out splits before tuning. A family, input or source cannot
   cross splits; canonical JSON checks also catch formatting-only duplicates and
   leakage. Duplicate input/source pairs cannot increase sample counts.
2. Have at least two qualified, language-fluent independent people label each
   pair. Dataset authors and system-dependent reviewers cannot count. Keep both
   initial votes; disagreements require a distinct adjudicator. Reviewers declare
   their business-domain scope, language competence and evidence reference.
3. Freeze `labels.json` before running the system. Capture all outcomes from the
   selected split, including abstentions and failures. Preserve each complete raw
   response or error artifact, not a curated excerpt. Record exact configuration,
   implementation, input and output hashes. The evaluator consumes these captures;
   it does not call the live matcher or model.
4. Separate output auditors inspect the full response, its declared relevance
   decision and all referenced evidence. Auditors must be independent of the
   system, dataset authors and all gold voters/adjudicators. They record whether
   the decision matches the output, whether all output citations are represented,
   and counts of invented facts and deadlines. Two audits must agree or a distinct
   auditor must adjudicate. An exact quote proves a reference, not entailment.
5. Save `audits.json` after the run, bound to the exact predictions file and every
   reviewed output hash. A later edit to the run requires a new bound audit.

The package records reviewer attestations, not verified identities. The release
reviewer must establish real independence, source rights, faithful captures and
absence of training/held-out contamination. Do not relabel synthetic examples as
human evidence. Test fixtures in the repository establish software behavior only.

## Generate and read a report

```powershell
services/api/.venv/Scripts/python.exe -B scripts/evaluate_business_matching.py evaluate --root C:/private-review/run-001 --dataset C:/private-review/run-001/dataset.json --labels C:/private-review/run-001/labels.json --predictions C:/private-review/run-001/predictions.json --audits C:/private-review/run-001/audits.json --output C:/private-review/run-001/report.json
```

Exit codes: **0** means declared package targets met; **1** means a valid report
contains unmet or unmeasured requirements; **2** means an invalid/unreadable
package or occupied output filename. Errors omit private input values. Reports
contain case IDs, decisions, counts and hashes, not source quotations or response
bodies. Treat IDs, decisions and the report itself as private review data.
The successful file-write receipt includes its SHA-256. Re-evaluating identical
bytes yields an identical report; no wall clock or random ID is injected.

The report requires at least 200 resolved pairs and 50 in each business category.
It measures the selected split only. The additional conservative reporting policy
requires at least 50 scored held-out pairs, positive and negative examples for
every business/language combination, and release-critical cases in every business
category. Missing strata are explicitly unmeasured. Development results and dirty
implementation captures cannot satisfy readiness.

Precision must reach 85% and recall 90% **in each business case**. A high overall
mean cannot hide a weak category. False positives, false negatives, missing rows
and unknown outputs remain visible. Failed/abstained/missing positive predictions
remain in the recall denominator. A zero denominator is `null`, never 100%.
Reports include per-business/per-language metrics and negative-example slices.

All successful outputs require valid citations and resolved independent output
audits. Any invented fact or deadline, mismatched decision or incomplete citation
inventory blocks the package, including non-critical rows. This is stronger than
the release-critical minimum and prevents curating away unsupported outputs.
Unresolved labels, rights or output audits cannot silently disappear from the
readiness decision. Original disagreement records remain in the hash-bound files;
the report lists their case IDs without copying private reviewer prose.

`package_targets_met` describes accounting over supplied evidence.
`capability_approved` is always false. This command cannot write an AI capability
registry or production settings. Score calibration, legal accuracy, target-machine
capacity, reviewer/source/run authenticity, deployment and human pilot acceptance
remain separately unmeasured. Existing deterministic monitoring remains available.

## Verification and remaining acceptance

The new business evaluator and existing HL-093/Tender experiment regression
suite passed **101 tests in 34.28 seconds** on 15 September 2026. Evidence:
`.tmp/business-eval-final.log`. Coverage includes a complete 210-pair synthetic
accounting package, category-level failure hidden by a high overall mean, absent
and failed outputs, zero denominators, reviewer independence/scope/disagreements,
source/field/permission binding, stale hashes, split leakage, reformatted duplicate
pairs, bounded repeated reads, no network or file writes during evaluation,
reproducible CLI reports, schema export, private error redaction and refusal to
overwrite earlier reports. Initial tests caught shared mutable citation data in
the synthetic fixture; separate copies fixed it before the passing run.

`ruff check services/api deploy/release_manager.py` and the separate evaluator
script lint passed. Existing evaluation contracts and runtime behavior are
unchanged. No frontend, database schema, collector, capability registry, source
permission or production setting is modified by this feature.
The final backlog consistency/customs-deferral check passed (one test, 0.18s;
`.tmp/business-eval-backlog.log`).

No independent 200-pair corpus, actual model quality measurement or production
activation is claimed. The synthetic declared-permission branch in one test
exercises accounting, not real source rights or human identities. Real labels,
audits and captures must be supplied through the documented procedure and
independently verified. MV2-051 remains IN PROGRESS.
