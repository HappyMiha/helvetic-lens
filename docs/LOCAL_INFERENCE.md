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

Starting is complete only after llama.cpp health succeeds and a schema-constrained warm-up call returns HTTP 200. Client timeouts and bounded retries remain active. Context-limit errors are returned immediately because retrying the same oversized evidence would occupy the slot without changing the result.

## Audit data

Every saved Impact and Ask record carries backend, model ID, immutable revision, artifact SHA-256, quantization, pinned runtime image, hardware profile and devices, configured/runtime context, generation settings, aggregate gateway queue wait, inference duration, token usage when returned, individual attempts, and structured validation/repair events.

The repeatable benchmark is `scripts/benchmark_local_inference.py`. Its checked-in GTX 1070 result is in `docs/benchmarks/dev-1070-apertus-1.5b-q4km.json`. It records 20 schema-constrained calls, a concurrent pair, load time, throughput, peak GPU/runner memory, stable prompt size, slots, citation/schema validity, timeouts, and OOMs. The same command must be run on the two-GTX-1080 host; only a report whose `concurrent_pair.profile_matched` is true may promote the 8B Q4 candidate.
