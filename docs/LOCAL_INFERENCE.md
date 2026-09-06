# Local inference contract

Helvetic Lens has one OpenAI-compatible inference address: the private model-manager gateway at `/openai/v1`. API and AI-worker containers never call a llama.cpp child process directly. The gateway retains its address while the manager starts, warms, replaces, splits, or degrades a runner.

The clean installation selects `docker` and `apertus-1.5b-q4km`. Cloud adapters remain explicit settings and are never selected after a local error. Registry, evidence, and deterministic comparison continue without a model; queued AI work enters `waiting_for_model` without consuming retry attempts until a verified local artifact is ready.

## Runtime profiles

| Profile | Layout | Slots | Selection rule |
| --- | --- | ---: | --- |
| `dev-1070` | one CUDA runner on device 0 | 1 | one visible CUDA device |
| `dual-1080-replicated` | one independent runner per card | 2 | two cards and model + 2 GiB headroom fit on each |
| `dual-1080-split` | one layer-split runner over devices 0 and 1 | 1 | two cards, but an independent replica does not fit |
| `cpu-degraded` | one CPU runner | 1 | no CUDA device or explicit diagnostic selection |

Each child uses one llama.cpp parallel slot. The gateway assigns one owner to each runner, rotates fairly between organizations, gives interactive calls priority, and ages background calls every 15 seconds so they cannot starve. If one replicated runner exits, the remaining runner stays available and the deployment is marked degraded.

The manager reserves 2 GiB beyond the immutable model artifact for runtime, KV cache, and operational headroom. Automatic and explicit choices use the same memory plan: replicated mode must fit that plan independently on each of the first two GPUs, split mode must fit it across both, and the development profile must fit on its one visible GPU. An unsafe automatic GPU plan degrades to CPU; an unsafe explicit plan is rejected with a profile-unavailable error. The selected byte-level plan and visible VRAM are stored with the deployment inventory.

Starting is complete only after every planned llama.cpp runner passes health and a schema-constrained warm-up call returns HTTP 200. During replicated startup, one ready runner plus one starting runner keeps the aggregate state at `starting`. One ready runner plus a failed runner is `degraded`; a runner that becomes ready later cannot erase another replica's failure. Client timeouts and bounded retries remain active. Context-limit errors are returned immediately because retrying the same oversized evidence would occupy the slot without changing the result.

## Audit data

### Deployment binding — 6 September 2026

The private `GET /v1/runtime` endpoint returns a `local-runtime-binding-v1`
snapshot of the active deployment. It includes a new ID for each start, a binding
fingerprint, exact served/catalog model IDs, revision/artifact hash, configured
context window and default output length. Stopped or dead deployments return no
active binding or identity. The snapshot is independent of inference admission
and does not start a model or consume a generation call.

Startup rehashes the installed GGUF before launching; a saved download checksum
alone no longer accepts a same-size modified file. This adds disk I/O to an
explicit model start, not to every generation. Launch inputs also record the
actual template and executable hashes. The conservative tokenizer binding is the
whole GGUF hash because this runner uses its embedded tokenizer. The runtime hash
is SHA-256 over the canonical `local-runtime-manifest-v1` JSON (sorted keys,
compact separators) containing the configured pinned image reference and actual
executable digest. **The image reference is a trusted launcher assertion**, not
Docker-daemon attestation; no Docker socket access was added. This assumes an
operator-controlled immutable runtime/filesystem after launch. It does not
independently hash every system library or detect arbitrary host file edits
during a running inference. Missing readable inputs or immutable image/revision
references produce no complete capability identity, rather than a guessed one.

A client can pin a planned request with `X-Helvetic-Runtime-Binding`. The gateway
checks that binding while waiting and again when atomically reserving its actual
runner. Even restarting the same model invalidates an old pin. A mismatch or
stopped deployment returns HTTP 409 `runtime_binding_changed`; the caller must
replan instead of silently retrying on the new model. Every chat request must
name the currently served model; a wrong alias returns
`runtime_model_mismatch` without a generation call. Successful proxy responses
carry the observed binding and deployment ID in headers.

An inference reservation prevents manager-driven stop/replacement until the
request finishes, fails or is cancelled. Such lifecycle attempts return HTTP 409
`model_busy`; cancel/wait for the request before stopping the model. This does
not prevent an external OS/process failure. Admission removes cancelled,
timed-out and invalidated waiters, and always releases its slot, so abandoned
requests cannot become permanent queue winners. Late callbacks from an earlier
runner cannot rewrite the state of a replacement deployment.

Marvin's `ModelManagerClient.complete_profile` now reads the selected profile and
runtime snapshot, matches model ID/revision/artifact/alias, sends the binding and
rejects an absent/mismatched response binding. It adds one small read-only runtime
request, no extra model call, automatic download/swap or cloud fallback. Deploy
API and model-manager code together when an operator next updates the system;
the new client intentionally does not silently downgrade against an older
manager lacking this contract. This change was not deployed to production.

### Analysis execution binding — 6 September 2026

Every new local Impact/Ask inference trace now resolves the active snapshot from
the same configured gateway before sending document evidence. A shared async
lock performs one probe for concurrent batches. The trace retains that snapshot
across batches, synthesis, transport retries and the existing one JSON repair;
it never switches deployments mid-analysis. An unavailable or inconsistent
snapshot fails before a generation POST. A stopped/replaced deployment or an
absent/mismatched successful-response pin fails without a binding-change retry.
Other provider transports are unchanged; no automatic cloud fallback was added.

The probe appears separately in integration logs and does not consume a model
call. It uses the remaining analysis deadline. A cancelled probe releases its
lock; another waiting batch may resolve a snapshot when no generation has yet
been accepted. Separate traces keep separate bindings. A standalone `complete`
call without a trace pins just that call and its transport retries; callers
orchestrating multiple calls must use `begin_trace`/`end_trace` for the full run.
The existing Impact, Ask and relation-analysis services already do so.

History records the whitelisted launch snapshot, including captured hardware,
with `runtime_binding_state` and `runtime_identity_fingerprint`. Completed plan
metadata records the execution pin and identity fingerprint too. Saving a result
does not probe current inventory or label old output as if a replacement model
produced it. Missing metadata stays unknown. A failed response cannot become a
successful answer merely because HTTP returned 200. Existing structured-output
validation and citation checks remain required after the transport check.

The stable identity fingerprint includes immutable model/artifact/tokenizer/
template/runtime/hardware identity, served alias and launch context/output
defaults. Restarting the same inputs changes the execution pin but not this
identity fingerprint; an incomplete immutable identity has no reusable identity
fingerprint. Runtime snapshots are not independent hardware or image attestation.

### Runtime-aware cache and history — 6 September 2026

Impact and Ask keys now include the observed local runtime identity alongside
the existing evidence, settings, profile, prompts, language and question inputs.
With complete immutable identity, identical restarts reuse the saved answer
without generation. If immutable inputs are incomplete, reuse is scoped to the
exact deployment pin and stops at a restart. Revision, artifact, tokenizer,
template, runtime manifest, hardware profile, alias or launch context/output
changes invalidate the relevant cache scope. Old local keys without this
observation are not silently upgraded; records and citations remain unchanged.

One operation uses a single runtime observation for cache selection and any
subsequent inference. The observation has a two-second wall-clock deadline,
does not send document text and does not spend a generation call. Inference
retains that same execution pin. Runtime state is local to the operation,
client and organization; cancellation/exit restores its contexts. Comparison,
law list/detail and matrix endpoints perform one observation per request, not
per displayed document. No cross-process TTL cache is claimed. Freshness is as
of that observation, not a promise that a model cannot be changed after an HTTP
response or cached-result selection. Gateway checks still protect actual calls.

Unavailable observation leaves saved reports unconfirmed and their history
readable. Dedicated AI-history and job-detail reads do not probe the model.
Direct service callers that need current local freshness use
`runtime_cache_scope`; without one, reads cannot assert a bound report is current.
The UI's stale-report guidance covers both changed and unconfirmed settings,
and cached-answer guidance says no new answer was generated, rather than
incorrectly claiming there was no metadata request at all. Existing custom and
Infomaniak transport keys are unchanged.

Completed background jobs validate their actual saved result's organization,
comparison and cache key before reuse. A model may change while work waits in
the queue: the worker resolves its actual runtime when it starts, and that
result cannot subsequently masquerade under the earlier enqueue key. When an
old completed job cannot be reused, its ID, steps and result remain inspectable;
its logical idempotency key moves to `superseded:<job-id>`, with the original key
retained in correlation metadata. A new job can then own the requested key.
Pending work still deduplicates. Requested cache scope is retained in job
payloads; the executed scope is retained in result plans and provenance.
The worker's existing readiness inventory read is separate from this snapshot.

Ask retries append a new history record instead of resetting a failed record
to pending and deleting its error/provenance. Valid successful reuse increments
use counters and never relabels the original model or generation date. Both
completed Ask and Impact jobs identify reused results as cached.

**Remaining HL-091 boundary:** [Capability decisions](AI_CAPABILITY_PROFILES.md)
still need to drive planning, adapter selection and approval-aware freshness.
Reported context/output defaults alone do not measure a serialized prompt and do not
approve explanatory quality. The request guard below measures the bound prompt;
planner allocation against reviewed per-model/task/locale limits and independent
evaluation remain open. Relation-assessment cache policy
is separate from these comparison Ask/Impact keys. An unpinned legacy client
remains protected only during its individual call. No production deployment,
100-user throughput or target-hardware latency is claimed.

### Complete prompt token guard — 6 September 2026

Every chat request through the private model-manager gateway now passes a
non-generating preflight **after admission and under the same deployment lease
as generation**. It reads the reserved runner's `/props` for actual per-slot
context and posts the **unchanged full chat body** to
`/v1/chat/completions/input_tokens`. Thus messages, citation instructions, repair
text, schema/template options and the model's chat rendering are not reduced to
an evidence-character estimate. The tokenizer counts the rendered prompt; a
schema used only as a decoding grammar is not incorrectly counted as prompt text.

The gateway requires:

```text
measured input + positive requested output reserve + 128 safety tokens
    <= min(actual runner slot context, configured launch context)
```

Omitted output limits reserve the manager launch default (700). Conflicting
`max_tokens`, `max_completion_tokens` and `n_predict` limits, unlimited/non-integer
values and multiple responses are rejected. Each managed process has one slot;
unexpected multi-slot properties fail closed instead of confusing total and
per-slot context. Both metadata calls share a ten-second wall-clock deadline.
No request is truncated, model switched, context expanded or fallback provider
contacted. Tokenizer failure/absence/malformed output returns a specific 422
before generation. An oversized prompt returns `context_length_exceeded` without
entering decoding. API clients do not retry these unchanged failures. Each
transport retry and structured repair is checked again on the pinned runtime.

The private `/openai/v1/chat/completions/input_tokens` route permits count-only
planning/diagnostics and returns `fits: false` for oversized inputs; it never
generates text. It uses the same admission/model-alias/pin/lease protections.
This route does not itself select passages or approve a capability profile.

`X-Helvetic-Token-Budget` contains the versioned measurement, output/safety/context
reserves, canonical full-request hash and deployment identity. Ask/Impact validate
received metadata against their payload and execution pin, retain it in history
and the completed plan, and expose it in existing integration-log response
headers. Preflight counts are separate from model-reported usage and do not add
generation calls. Failed oversized attempts retain the measurement too. For
compatibility, an older gateway without this metadata is **unmeasured**, not
silently assigned an estimate; only the updated gateway enforces this guard.
Historical records and successful caches are not relabelled as newly measured.

Implementation uses the pinned llama.cpp revision
[`b96806d96061049a5b574269b049bf6241d63d46`](https://github.com/ggml-org/llama.cpp/blob/b96806d96061049a5b574269b049bf6241d63d46/tools/server/server-context.cpp#L4967).
Its count handler applies the same chat parser as generation and tokenizes with
special-token insertion/parsing enabled. The [documented API](https://github.com/ggml-org/llama.cpp/blob/b96806d96061049a5b574269b049bf6241d63d46/tools/server/README.md#post-v1chatcompletionsinput_tokens-token-counting)
is available in the already pinned Docker image; no tokenizer dependency or
runtime image update is needed.

`scripts/check_local_prompt_tokens.py` starts its own CPU-only loopback child in
a disposable, network-disabled container. Mount the existing GGUF, template,
script and current `services/model-manager` package read-only, set `PYTHONPATH`
to that package's parent, and pass `--model` and `--template`. It checks five
synthetic language prompts and a JSON repair prompt against actual completion
`usage.prompt_tokens`, then counts oversized input without generation. The
6 September run used Apertus 1.5B Q4_K_M, build `b10752-b96806d96`, context 1024;
all six counts matched (49, 50, 51, 56, 51, 55); oversized input counted 1837.
This validates the protocol for that fixture/runtime/template, not every model,
semantic quality, dynamic/custom templates, GPU performance or 100-user capacity.

**Still open:** use exact preflight results in capability-aware evidence planning,
carry reviewed task/language budgets and approval-decision freshness through the
entire analysis, and provide explanatory evaluation. Current character-based
evidence planning may still choose an input the final guard rejects; it is never
called a measured token allocation. Ask/Impact generation call caps remain 3/5.
No deployment or model promotion is authorized by this code change.

Every saved Impact and Ask record carries backend, model ID, immutable revision, artifact SHA-256, quantization, pinned runtime image, hardware profile and devices, configured/runtime context, generation settings, aggregate gateway queue wait, inference duration, token usage when returned, individual attempts, and structured validation/repair events.

The repeatable benchmark is `scripts/benchmark_local_inference.py`. Its checked-in GTX 1070 result is in `docs/benchmarks/dev-1070-apertus-1.5b-q4km.json`. It records 20 schema-constrained calls, a concurrent pair, load time, throughput, peak GPU/runner memory, stable prompt size, slots, citation/schema validity, timeouts, and OOMs.

The v2 promotion gate fails closed: it writes the diagnostic report and exits nonzero unless all 20 representative calls and both concurrent calls succeed, the requested runtime profile and GPU inventory match, the manager exposes the expected slot count, and the concurrent responses prove the expected number of distinct runner slots. Selecting a dual-GPU profile implicitly requires two visible CUDA devices, even when the device-count argument is omitted.

Run the target replicated acceptance check from the repository root on the two-GTX-1080 server:

```powershell
python scripts/benchmark_local_inference.py --base-url http://127.0.0.1:12436 --required-profile dual-1080-replicated --required-cuda-devices 2 --require-gpu-substring "GTX 1080" --output docs/benchmarks/target-dual-1080-replicated.json
```

If inventory legitimately selects the smaller one-runner fallback because an independent replica does not fit, record that separately:

```powershell
python scripts/benchmark_local_inference.py --base-url http://127.0.0.1:12436 --required-profile dual-1080-split --required-cuda-devices 2 --require-gpu-substring "GTX 1080" --output docs/benchmarks/target-dual-1080-split.json
```

The split report proves one layer-split runner over both visible cards. It does not satisfy the replicated-mode acceptance criterion and cannot by itself promote the 8B Q4 candidate.
