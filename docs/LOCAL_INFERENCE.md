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

**Remaining HL-091 boundary:** [Capability decisions](AI_CAPABILITY_PROFILES.md)
still need to drive planning and adapter selection. Cache lookup, completed-job
deduplication, report/matrix freshness and reuse have not yet adopted runtime
identity; this slice does not claim they invalidate an old model's result.
Reported context/output defaults do not measure a serialized prompt and do not
approve explanatory quality. Real tokenizer accounting and independent
per-model/task/locale evaluation remain open. An unpinned legacy client remains
protected only during its individual call. No production deployment occurred.

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
