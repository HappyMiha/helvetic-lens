# Synthetic matching walkthrough — not a gold set

These six tiny cases demonstrate package authoring and the actual offline topic scorer. They are invented, not saved Swiss publications. Declared locale fields exercise language filtering; the English fixture vocabulary is not a translation or language-quality test. The `example.invalid` addresses must never be fetched.

Four cases are development inputs and two are held out. Every source/input is hash-bound. `labels.json` deliberately contains no reviewers or labels: no independent human review occurred. Do not populate it with generated reviewer names or mark this package as public-source evidence to obtain a green result.

From the repository root, using the project's Python environment:

```text
python scripts/evaluate_semantic_matching.py schemas --output test-results/matching-schemas.json
python scripts/evaluate_semantic_matching.py baseline --dataset demo/semantic-matching-example/dataset.json --root demo/semantic-matching-example --split held_out --output test-results/matching-example-predictions.json
python scripts/evaluate_semantic_matching.py evaluate --dataset demo/semantic-matching-example/dataset.json --root demo/semantic-matching-example --labels demo/semantic-matching-example/labels.json --predictions test-results/matching-example-predictions.json --output test-results/matching-example-evaluation.json
```

Use new filenames for a later run; commands refuse to overwrite evidence. The baseline should produce two operationally successful predictions, one match and one non-match, and exit 0. Evaluation must exit **1** with pending reviews, zero scored pairs, null precision/recall, insufficient coverage and `explanation_capability_approved=false`. An uncommitted code tree is an additional readiness blocker. Exit 2 indicates invalid input or an existing output filename.

No database URL, provider credential, network request, model call, application write or automatic model approval is involved. This is a workflow example, not the independent 200-pair/30-report evidence required by HL-093. See [the protocol](../../docs/SEMANTIC_MATCHING_EVALUATION.md).
