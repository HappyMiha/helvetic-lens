# Independent matching evaluation (HL-093)

This offline tool evaluates whether an event is relevant to a specific saved monitoring plan. It separates reference integrity, reviewer declarations, prediction coverage and precision/recall. It does **not** evaluate legal entailment, useful explanations/actions, language fluency, website ingestion coverage or hardware capacity, and cannot approve an explanatory model profile.

The runnable [synthetic walkthrough](../demo/semantic-matching-example/README.md) intentionally fails readiness. There is no checked-in independently labelled gold set. Code tests use synthetic declarations to exercise both passing/failing calculations; these must never be promoted as human evidence.

The walkthrough's hashed JSON/text files use scoped `-text` Git attributes so a Windows checkout cannot change their bytes through line-ending conversion. New frozen packages need the same byte-preservation rule; rehash deliberately when the underlying evidence changes.

## Collect and freeze the dataset

1. Select at least 200 interest/event pairs from saved public sources, with actual user-relevant monitoring plans and realistic negatives. Include federal laws, Parliament and courts; separate news where applicable. Keep source provenance and source content intact. Do not include confidential organization text in a public evaluation package.
2. Store the exact model/scorer input as JSON and the relevant saved source text as UTF-8 files. Each case records locale, source type, family, split, feature tags, source URLs and SHA-256 references. The input includes the actual plan, event, work, expression/identifiers and source-pack stream definitions. Reviewers must judge the pair against that specific plan, including exclusions and scope, rather than judging topical similarity in isolation.
3. Assign related amendments, translations, versions and near-duplicate sources to one family **before tuning**. Separate development from held-out families. The validator rejects a family, exact source hash or exact input hash present in both splits. It cannot discover semantic near-duplicates automatically: family assignment still needs independent review.
4. Freeze the manifest and archive its hash. Changed source/input bytes require a new manifest, labels and prediction run. Never edit a held-out case after seeing a miss merely to improve the score. The tool does not fetch source URLs or prove they are authoritative; curators/reviewers must verify provenance.

`schemas` exports current JSON authoring contracts for `Dataset`, `Labels`, `Predictions` and `MatchingInput`. Package references are relative, resolved within the root, checksum-verified and bounded to eight MiB per file and 128 MiB of unique input/source artifacts. The manifest, labels and predictions each have a separate eight MiB file limit. Invalid JSON, duplicate keys, nonfinite values, path traversal, escaped symlinks and changed bytes are rejected. Original source quotes are not normalized or translated for gold-citation validation.

## Independent labelling and adjudication

Keep labels outside the scorer's inputs. Each case needs two distinct independent reviewers fluent in its locale. A reviewer entry contains a stable ID, declared independence, fluent locales and a domain-review reference. Dataset authors cannot count as independent reviewers. Every vote includes the relevance decision, rationale and verbatim supporting source quotations. Negative decisions also need an explained comparison with the plan/source; lack of a keyword alone is not a human relevance judgment.

Preserve conflicting votes. A third, distinct reviewer must adjudicate a disagreement with a rationale and source citations. Until then, the case is pending, never silently majority-voted or treated as negative. Agreement cannot be overridden by adding an adjudication record; correct/review the frozen labels in a new revision instead. Missing votes, unqualified locales, self-review and unresolved disagreement remain visible in pending counts.

Freeze labels before the evaluated run. Labels name the exact dataset hash; the evaluation result names both labels and prediction file hashes. The timestamp ordering check verifies declared chronology, not the authenticity of those dates. Reviewer IDs/independence/qualifications and source authority are **attestations**, not verified human identity or signatures. Inspect the actual review records during acceptance. The tool deliberately emits `independence_is_attestation_not_verified_identity=true`.

## Run the actual scorer or a separately frozen candidate

`baseline` invokes production `normalize_plan` and `score_event` on every case in the requested partition. It does not read gold labels, optimize thresholds or shortlist cases by similarity. Official references, metadata values, synonyms, exclusions, languages, jurisdictions, document/event kinds, source-pack streams and importance filters use the same code as monitoring preview/live matching.

Each case uses a new memory-only SQLite database for required source-pack/identifier lookups. Application settings, database URLs, organization subscriptions and working data are never loaded. This verifies the **pair scorer**, not live admission/queue fairness, source completeness or the performance of a mature PostgreSQL corpus. Timings include isolated database/schema setup and are not production latency or human time-to-insight.

The baseline records Git revision, dirty-tree state, a digest of the current API Python implementation/CLI and a configuration digest containing rule/evaluation/input-contract revisions. Dataset input hashes bind the per-case plan and source definitions. External predictions must supply equivalent run identity and exact case/input bindings. Unknown cases, wrong splits, duplicated predictions, mismatched inputs and invalid decisions are rejected. Error/abstained predictions remain explicit; missing predictions stay missing. Never convert an exception to a successful non-match.

## Read the evaluation honestly

Every metric exposes numerator and denominator. Precision is true positives divided by all positive predictions among adjudicated cases. Recall is recovered positives divided by all adjudicated positives; error, abstention and missing predictions on a positive count as misses. Unknown negative predictions are not true negatives. Unreviewed gold cases are excluded from these fractions but remain in total/pending counts and prevent readiness. Empty denominators produce `null`, never 0% or 100%.

Outputs include false-positive/false-negative IDs, per-case outcomes, retained disagreements/adjudication and disagreement numerator/denominator. Locale/source/feature strata expose counts and metrics; absent known strata remain zero-count/unmeasured instead of disappearing. Independent reviewers can inspect important misses without hiding them behind one aggregate number. Stratum-level scores do not automatically authorize a model or a language.

The provisional **matching-only** readiness calculation requires:

- public-source provenance and all frozen dataset labels resolved, with at least 200 reviewed pairs;
- at least 50 held-out pairs, at least five per locale and both positives and negatives in each of DE/FR/IT/RM/EN;
- at least five held-out examples each from federal legislation, Parliament and courts;
- held-out negative, paraphrase, German compound, cross-language reference, scope-exception and high-value feature coverage;
- a held-out run tied to a clean implementation revision, with a successful prediction for every selected case;
- precision at least 0.85 and recall at least 0.90, with actual denominators.

These provisional sample minima make incomplete evidence visible; they are not a statistical confidence guarantee. Feature tags and family/source definitions require reviewer scrutiny. The result separately lists readiness blockers and target failures. Even when both lists are empty, `explanation_capability_approved` stays false and the unmeasured report/action/language/human/hardware gates remain explicit. Do not paste a matching score into an explanation-profile approval.

CLI exit codes: 0 means baseline completed or matching-only targets/readiness met; 1 means valid artifacts with operational gaps or unmet/unmeasured matching targets; 2 means invalid package/output. Output files are created exclusively, never overwritten. Diagnostic errors omit source/model input values. Archive each manifest, source set, labels, predictions, report and code revision; the evaluator does not secretly mutate them.

## Existing title benchmark and remaining work

`benchmark_relation_candidates.py` remains an unreviewed title/reference regression. It no longer claims a measured `evidence_policy_compliance=1.0`: that field is null, and the result explicitly says independent review was not performed. Missing denominators are unmeasured. A smoke-test gap can recommend a semantic trial, but never enables pgvector; its deprecated `pgvector_enabled` output is always false. Its CLI exit code now follows `semantic_trial_recommended`.

Still required for HL-093: the actual independently curated/adjudicated 200-pair package, real frozen baseline failures and subsequent held-out evaluations, plus at least 30 comparison/Ask/report scenarios and separate human assessments of entailment, critical unsupported claims, material omissions, action usefulness and language quality. This matching tool cannot provide those missing observations. Target hardware, real users and multilingual domain reviewers remain separate acceptance evidence, not claims inferred from passing code tests.
