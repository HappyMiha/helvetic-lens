# Reviewed AI explanation profiles

The capability contract separates **how a model is connected** from **what a
specific deployment has been reviewed to do**. `docker`, `custom` and `infomaniak`
are transport choices, not quality evidence. A model returning valid JSON does
not establish that its explanations, applicability claims or suggested actions
are useful or correct.

## Implementation boundary — 6 September 2026

HL-091 now has a strict, versioned registry reader, independent-review artifact
integrity checker, provider-independent decision resolver and read-only CLI.
The shipped registry is deliberately empty. **This slice does not yet change
Impact/Ask runtime routing, the planner, settings, cache or history.** Those still
need the coordinated integration described below. The resolver's
`generated_explanation` decision is a permission for a verified scope, not an
assertion that the current application has used that mode.

The local manager now exposes [observed launch inputs and deployment binding](LOCAL_INFERENCE.md#deployment-binding--6-september-2026).
Its gateway enforces pins during admission and inference; Marvin's local client
already uses them. This prevents per-request model substitution and supplies the
identity needed by the future Impact/Ask integration. It does not approve a
model or migrate the analysis pipeline automatically.

The existing GTX 1070 structured-output benchmark is not an explanatory quality
review. Neither it nor a successful HTTP/JSON response promotes Apertus 1.5B,
Apertus 8B or a cloud model. HL-093 independent evaluation and target-hardware
acceptance remain open. No new model has been downloaded or started.

## Registry and evidence contract

The trusted deployment registry is
`services/api/helvetic_lens/ai-capability-profiles.json`, schema
`ai-capability-registry-v1`. It contains profiles with unique IDs, integer
revisions and `candidate`, `approved` or `revoked` status. Earlier revisions
belong in Git and immutable result history, not duplicate IDs whose order could
change which approval wins.

Each profile binds the exact observed runtime identity:

- model ID and immutable 40- or 64-digit hexadecimal model revision;
- model-artifact, tokenizer, chat-template and runtime-manifest SHA-256 digests;
- the hardware profile on which the declared budget was evaluated.

Floating `main`, `latest` or marketing version labels cannot be immutable
revisions. A caller must obtain this identity from the serving runtime and
verified artifacts; editable UI labels or request fields are not attestation.
An unavailable identity leaves the decision in `selected_evidence` mode.

Every approved grant is for exactly one task (`ask` or `impact_report`) and one
product locale (`de-CH`, `fr-CH`, `it-CH`, `rm-CH`, `en-CH`). There is no implicit
English fallback, transfer between tasks, search for a more permissive profile,
model swap or cloud fallback. The caller must explicitly select a profile.

Each grant records tested input, output and safety token budgets. Their sum must
fit the recorded context window; booleans and numeric strings are rejected as
token counts. These are **declared evaluated limits**, not token measurements
of a current request. The later runtime integration must count the complete
serialized prompt with the bound tokenizer, including chat-template overhead,
before comparing it to those limits. Character estimates cannot certify a fit.

Each approved grant references a relative JSON evaluation record plus its
SHA-256. The `ai-explanation-review-v1` record repeats the exact profile revision,
runtime identity, task, locale and budget, and records:

- dataset and result digests and the evaluator's immutable Git revision;
- named reviewer, timezone-aware review date and review reference;
- explicit boolean `independent_review: true` and a `pass` outcome.

These fields are review attestations, not cryptographic signatures. Integrity
checking cannot prove that a reviewer is independent or their judgment is right.
Promotion requires inspecting the linked evidence and applying the independently
reviewed HL-093 protocol; this contract does not invent or waive its thresholds.
Someone able to edit the trusted registry and review files controls that trust
boundary. Do not expose approval writes to an ordinary model-settings endpoint.

The loader verifies all approved grants before returning any registry. It fails
on absent files, checksum mismatch, a changed model/budget/scope, unknown fields,
duplicate scopes or IDs and incomplete approval records. Artifact paths must stay
inside the chosen evidence root after canonical resolution. Files are bounded at
one MiB and are never fetched over the network. Revoked/candidate profiles cannot
grant permission and do not require their former evidence files to remain
available just to express that denial.

## Read-only check

From the repository root, using the API Python environment:

```sh
python scripts/check_ai_capabilities.py
python scripts/check_ai_capabilities.py --require-approved
python scripts/check_ai_capabilities.py --registry path/to/registry.json --evidence-root path/to/evidence
```

The first command verifies integrity, including an honestly empty registry. The
second also exits unsuccessfully when no approved profile exists: a green
integrity result is not readiness. The JSON report always distinguishes approval
availability from semantic verification and runtime enablement. It reports counts
and a bounded error code without echoing artifact contents. The checker does not
write files, change settings, contact models or publish messages.

The resolver returns mode, reason, selected profile/revision, task/locale, allowed
budget, evaluation reference and a deterministic fingerprint. Identity, profile
status/revision, review checksum, budget or scope changes change that fingerprint.
The caller must use the registry returned by the verified loader; constructing a
model object directly is an explicitly trusted in-process operation, not a
substitute for checking evidence.

## Remaining runtime integration

Before enabling this policy in the product:

1. Obtain actual immutable runner identity, including tokenizer/template/image
   digests and active context settings; handle disappearance or a model switch
   between planning and inference. Unknown remote identities stay limited.
2. Resolve the explicitly selected trusted profile for the routed task/locale.
   Keep transport-specific authentication and wire-format handling separate.
3. Carry the same resolved decision and token budget through planning, structured
   response adaptation, synthesis, final response mode and saved provenance.
   Do not let a client object choose another mode based on its provider string.
4. Bind decision fingerprints to cache/history freshness. Supersede old results
   without deleting them; retain deterministic/offline results and truthful
   limited-mode labels in all five locales.
5. Test changed/revoked identities during execution, measured prompt limits,
   cancellation, one repair and existing Ask ≤3 / Impact ≤5 request ceilings.
   Independently evaluate each actual promoted task/locale deployment under
   HL-093 before claiming explanatory quality.

The contract tests use synthetic review files and synthetic immutable identities.
They prove gate behavior and read-only handling, not legal usefulness or model
performance.
