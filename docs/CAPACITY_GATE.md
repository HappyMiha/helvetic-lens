# Recovery and 100-user capacity gate

This gate turns the public-beta capacity claim into a repeatable target-host measurement. Run it only on a dedicated copy of the single-server deployment: it creates synthetic organizations and accounts, submits real scans, connector work and local AI jobs, and deliberately restarts the API, workers, Redis, scheduler and model manager.

The gate is strict. A run does not pass without 100 seeded accounts, 10–20 concurrent readers, 20 accepted and completed AI jobs, concurrent scans, connector work, service recovery, a passing target-host inference benchmark, and a verified backup/restore timing record. Development hardware may produce a useful report, but it does not satisfy the two-GTX-1080 release gate.

## What is bounded

- Every API/worker process has a PostgreSQL pool of 4 connections plus at most 2 overflow connections by default. Production refuses a per-process total above 16.
- The CPU worker remains at concurrency 2 and the AI worker at concurrency 1. The model gateway owns each runner slot and prefers a waiting organization that does not already own a slot. If no other organization waits, one organization may use all idle slots.
- The resource sampler records host RAM/swap when `psutil` is available, Docker CPU/RAM/network/block I/O, host disk use and `nvidia-smi` GPU utilization/VRAM/temperature. Platform status adds queue depth and age, retries, connector timing, model slots and admission wait state, API latency, database/Redis latency, retention and backup age.
- Reports and manifests contain synthetic email addresses and IDs, but never the capacity password, cookies, CSRF values, provider credentials, prompts or document bodies.

## 1. Prepare the isolated target stack

Use the production deployment procedure and a separate database, Redis volume, evidence volume, model volume, hostname and backup directory. Keep public registration closed. Build and start the exact release being measured, download/verify the chosen Apertus model in **Platform administration → Local models**, and wait until its state is **Ready**.

Run the local inference benchmark first:

Keep the model manager private. Copy the benchmark into its container, run it against loopback there, and copy only the result out:

```sh
mkdir -p reports
docker compose --env-file .env.production -f compose.production.yaml \
  cp scripts/benchmark_local_inference.py model-manager:/tmp/benchmark_local_inference.py
docker compose --env-file .env.production -f compose.production.yaml exec model-manager \
  python /tmp/benchmark_local_inference.py \
  --base-url http://127.0.0.1:8090 \
  --output /tmp/target-inference.json
docker compose --env-file .env.production -f compose.production.yaml \
  cp model-manager:/tmp/target-inference.json reports/target-inference.json
```

The report records the actual model/revision/quantization, hardware profile, load time, context, throughput, schema/citation validity, queue wait, stable slots, RAM/VRAM, timeouts and OOMs. A smaller verified Apertus profile is acceptable when the desired 8B profile does not pass; the report, rather than the desired model name, controls the shipped default.

## 2. Seed 100 synthetic accounts

Choose a new prefix for every measurement. Reusing the same prefix is idempotent, which is useful when setup is interrupted. The seeder requires an explicit dedicated-environment acknowledgement and takes its password only from the process environment.

```sh
export HELVETIC_LENS_CAPACITY_ACK=dedicated-capacity-environment
export CAPACITY_GATE_PASSWORD='use-a-new-test-only-password'

docker compose --env-file .env.production -f compose.production.yaml exec \
  -e HELVETIC_LENS_CAPACITY_ACK -e CAPACITY_GATE_PASSWORD api \
  python -m helvetic_lens.capacity_seed \
  --prefix hl-capacity-20260903 \
  --output /data/capacity/manifest.json

mkdir -p reports
docker compose --env-file .env.production -f compose.production.yaml \
  cp api:/data/capacity/manifest.json reports/capacity-manifest.json
```

The default synthetic watch URL deliberately cannot be fetched, so it exercises honest scan failure and retry handling without depending on a third party. To require successful scans, host the supplied synthetic HTML on a controlled public HTTPS fixture and add `--source-url-template https://fixture.example/capacity.html`. Private/container addresses remain blocked by the production SSRF policy.

The manifest represents ten organizations with ten accounts each. The first two accounts in each organization are organization administrators; the rest are read-only viewers. The first account is the isolated stack's platform administrator. Each organization receives the same small synthetic before/after comparison, stored as private organization evidence, with two deadline changes and one added duty.

## 3. Record backup and restore duration

Follow the destructive restore rehearsal in [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) on this isolated stack. Measure the one-shot backup and the full verified restore, then create a local file such as `reports/backup-restore.json`:

```json
{
  "schema_version": "1",
  "target_host": "capacity-server",
  "backup_id": "20260903T155446Z",
  "backup_seconds": 42.7,
  "restore_seconds": 58.4,
  "verified": true,
  "verification": [
    "database probe restored",
    "evidence artifact restored",
    "login and comparison opened"
  ]
}
```

Set `verified` only after the restored database and evidence artifact match the pre-backup probes and login, registry, comparison and local-model inventory all work. The capacity runner embeds this record but never performs a destructive database restore itself.

## 4. Run the complete gate

The host running this command needs Python 3.11+, `httpx`, Docker access and preferably `psutil`. The API's virtual environment already contains `httpx`. Use the externally reachable HTTPS origin as `--base-url`; do not add `/api`.

```sh
export HELVETIC_LENS_RECOVERY_ACK=dedicated-capacity-environment
export CAPACITY_GATE_PASSWORD='use-a-new-test-only-password'

services/api/.venv/bin/python scripts/run_capacity_gate.py \
  --base-url https://capacity.example.ch \
  --manifest reports/capacity-manifest.json \
  --output reports/capacity-result.json \
  --inference-report reports/target-inference.json \
  --backup-report reports/backup-restore.json \
  --compose-project-directory . \
  --compose-file compose.production.yaml \
  --compose-env-file .env.production \
  --recovery
```

The Windows interpreter path is `services\api\.venv\Scripts\python.exe`; the remaining arguments are identical.

The scenario logs in only the 30 accounts it needs, while proving that 100 exist in the manifest. Twenty clients concurrently read registry filters, saved evidence and comparisons. A bounded five-request command burst admits five scans, one bounded Fedlex catalogue sync, and one Impact analysis plus one material-change question for each of ten organizations. The runner then restarts scheduler, API, Redis, CPU worker, AI worker and model manager, reactivates the previously running local model, waits for durable jobs to terminate, and captures the final platform state.

The command exits zero only if all criteria pass:

- registry/evidence/comparison read p95 is below 500 ms;
- scan/connector/AI validation and enqueue p95 is below 1 second;
- unexpected HTTP errors are below 1%, excluding deliberate `422` and `429` outcomes;
- at least 20 AI jobs were accepted and later succeeded;
- every service recovered, all submitted jobs left the queue before the timeout, and no successful job carries an error code;
- every measured API response has an `X-Request-ID`;
- the target inference benchmark detected both target CUDA devices, passed without OOM, and completed at least 20 schema-valid calls;
- the target-host backup/restore record is verified.

Use `--no-wait-for-jobs`, `--skip-connector` or omit `--recovery` only for diagnostics. Such a report remains useful but intentionally fails the complete gate. Generated `reports/` are ignored by Git; check in a redacted accepted target-host report under `docs/benchmarks/` when the dual-GTX-1080 run is complete.

After retaining the accepted report, remove a test run by its exact prefix. This command refuses to run without both safeguards and deletes only organizations whose slug starts with that prefix and users on the reserved `capacity.invalid` domain:

```sh
export HELVETIC_LENS_CAPACITY_DELETE_ACK=delete-synthetic-capacity-data
docker compose --env-file .env.production -f compose.production.yaml exec \
  -e HELVETIC_LENS_CAPACITY_DELETE_ACK api \
  python -m helvetic_lens.capacity_cleanup \
  --prefix hl-capacity-20260903 --execute
```

## Reading failures

- High read p95 with low database query time usually points to API CPU saturation or an expensive registry/comparison serialization path.
- High enqueue p95 with low read p95 points to connection-pool pressure, lock contention or synchronous validation doing too much work.
- Rising swap or worker memory means the shipped worker concurrency/document limits are too high for the host.
- GPU OOM, one available slot or an inference profile mismatch means the desired model topology cannot ship. Select the split or smaller verified profile and rerun both benchmarks.
- A queue timeout with zero model admission slots is a model outage, not a completed analysis. Inspect the request ID in Integration logs and the model manager log.
- A failed scan against the default `.invalid` URL is expected evidence that source failure remains explicit. Use a controlled public fixture when successful scan recovery is part of the target run.

Do not increase concurrency or database connections merely to make one metric green. First identify the measured bottleneck, update the documented capacity envelope, and rerun the complete scenario.
