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
