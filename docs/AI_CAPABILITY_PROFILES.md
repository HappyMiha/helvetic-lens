# Reviewed AI explanation profiles

The capability contract separates **how a model is connected** from **what a
specific deployment has been reviewed to do**. `docker`, `custom` and `infomaniak`
are transport choices, not quality evidence. A model returning valid JSON does
not establish that its explanations, applicability claims or suggested actions
are useful or correct.

## Implementation boundary — 6 September 2026

Production comparison Ask/Impact now resolve the selected profile against the
observed runtime, routed task and language. An exact approved scope with a
working native count protocol enables explanatory batch output. Impact uses a
bounded synthesis; a single supported Ask batch needs no extra synthesis call.
Unselected/unknown/revoked profiles, invalid review files, identity mismatch,
unreviewed tasks/languages or missing measurement support stay in explicitly
labelled **selected evidence** mode. This includes cloud/custom endpoints whose
immutable serving identity cannot be observed by the current integration.
Choosing a provider or model name never supplies an approval.

The shipped registry is deliberately empty. **No real model/task/language is
promoted by this implementation.** Synthetic approvals exercise the execution
path only. Independent HL-093 explanatory evaluation on each exact model,
hardware and task/language remains required; existing GTX 1070 JSON/transport
benchmarks do not establish useful legal explanations or target-server capacity.

The adapter decision controls newly generated output. Deterministic no-change
and clarification responses need no inference. Reusing a current, same-language
impact report also needs no new Ask call: it retains the source report's response
mode, citations and report ID, while the trace does not invent an Ask approval.
Changing/revoking its profile makes the report stale and unavailable for current
report reuse. Historical records are never relabelled or deleted.

## Execution, budgets and freshness

The existing [deployment binding](LOCAL_INFERENCE.md#deployment-binding--6-september-2026)
and [complete prompt guard](LOCAL_INFERENCE.md#complete-prompt-token-guard--6-september-2026)
remain in force. The same captured capability decision accompanies planning,
measured numbered-evidence selection, generation, synthesis, transport retry and
one constrained JSON/citation repair. Output reserve is the smaller of configured
and reviewed output limits. Native counts include the full wire prompt, schema,
instructions and template; character estimates remain preliminary estimates.

A reviewed request must fit both native and evaluated limits: input and output
must fit their individual reviewed limits, and input + output + the larger safety
reserve must fit the smaller of reviewed and actual per-slot context. No measured
count is rewritten to manufacture a fit. Numbered batch evidence is reduced in
whole changes/windows using the existing bounded allocator. Every approved
completion, including synthesis and repair, gets a count-only preflight; the
existing gateway independently counts again under its inference lease. Synthesis
or repair that cannot fit fails explicitly rather than silently dropping evidence
or retrying unchanged input. Counting does not consume generation calls, but its
network waits remain within the operation deadline. Ask ≤3 / Impact ≤5 provider
generation-attempt ceilings are unchanged.

The verified registry, selected profile and runtime identity form a versioned
policy fingerprint. It participates in API cache keys, current-report selection,
comparison/law/matrix freshness and completed/queued job reuse. Registry review
integrity and the captured fingerprint are rechecked before/after counting,
before each generation attempt, after the reply and before accepting a new
result. Mid-operation changes fail as `capability_changed` and remain recorded in
history. The registry is a trusted operator-managed file, not a transactional
revocation service; an update after a completed operation makes that result stale
on the next current-data read. Unrelated registry edits also invalidate reuse
conservatively. An unchanged fully identified restart can still reuse results.

Plans expose the selected decision and effective output/reviewed token limits.
History retains the captured decision, review reference/fingerprint, actual
measured budget checks and allocation/partial coverage. Worker execution resolves
its current approval rather than trusting the profile present when it was queued;
reconciled job keys cannot make a result from another policy current. Failed
attempts and earlier conclusions remain inspectable without live inference.

This policy covers the public comparison Ask/Impact service paths. Relation
assessments and Marvin remain separate tasks; raw connection tests/benchmarks do
not publish capability-approved legal conclusions. Low-level deterministic test
doubles keep their existing adapters. No automatic model download, model switch,
cloud fallback or promotion is performed.

## Selecting and installing profiles

Organization integration settings expose an optional **Explanation profile**
selector with five-language help, task/language scope and reviewed/candidate/
withdrawn status. The existing admin/viewer access rules apply. A saved profile
missing from the server is visibly retained until the user changes it; a failed
registry verification cannot produce a selectable approval. Metadata does not
expose review-file paths or reviewer details. The API accepts a profile ID, never
approval records or filesystem settings.

Operators install the trusted registry and its independently reviewed artifacts.
The defaults are the shipped `ai-capability-profiles.json` and its API package
directory. Server-only `AI_CAPABILITY_REGISTRY` / `AI_CAPABILITY_EVIDENCE_ROOT`
can select read-only mounted paths; these paths must exist inside **both API and
worker** environments. Validate them with the read-only CLI below before a
reviewed deployment. `APERTUS_EXPLANATION_PROFILE` supplies an optional environment
default; a saved organization setting overrides it. Selecting a profile is not
attestation and does not change the model actually running.

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

Every approved grant is for exactly one task (`ask`, `impact_report`, or
`interest_brief`) and one
product locale (`de-CH`, `fr-CH`, `it-CH`, `rm-CH`, `en-CH`). There is no implicit
English fallback, transfer between tasks, search for a more permissive profile,
model swap or cloud fallback. The caller must explicitly select a profile.

Each grant records tested input, output and safety token budgets. Their sum must
fit the recorded context window; booleans and numeric strings are rejected as
token counts. These are **declared evaluated limits**, not token measurements
of a current request. The runtime integration counts the complete
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

## Remaining acceptance work

- Independently evaluate and review actual task/language/deployment profiles under
  HL-093 before installing any approved grant. Hashes prove integrity, not review
  independence or semantic quality. Evaluate usefulness, grounded explanations,
  dates, applicability and non-duplicated actions; correct JSON is not sufficient.
- Establish target GTX 1070 / dual GTX 1080 context, latency and capacity evidence.
  No promotion or 100-user readiness follows from synthetic HTTP/native tests.
- Character-based candidate preparation and conservative measured halving are
  not optimal relevance/packing. Synthesis/repair may still exceed a reviewed
  budget and stop visibly; this implementation does not silently truncate them.
- Remote observed-identity attestation and relation-assessment quality policy
  remain separate work. The current cloud bonus stays in selected-evidence mode
  for comparison Ask/Impact when its serving identity is unavailable.
- Five-language UI checks are automated; native-language/domain and real-user
  acceptance remain independent work, including Romansh copy review.
