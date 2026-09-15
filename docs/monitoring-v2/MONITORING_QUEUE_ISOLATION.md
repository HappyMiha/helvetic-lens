# Monitoring worker isolation

## Outcome

Monitoring scheduling, source work, private event projection and consented email
delivery have dedicated Celery consumers. Legal ingestion/parsing and local AI
keep their existing workers. A long document download, model download or parsing
job therefore cannot occupy the slots assigned to Monitoring orchestration.

The nine active directions retain their existing source, ownership, freshness,
model capability and consent gates. C4 remains deferred. There is no new broker,
database, GPU allocation, source credential or external delivery during validation.

## Evidence motivating the change

At commit e0af3fc, all periodic tasks routed to maintenance. The production CPU
worker consumed interactive, ingest, parse_diff and maintenance with concurrency
two. A controlled real Celery experiment occupied both ingestion slots and queued
a control probe. It did not start during the 1.015-second observed occupation;
after release it started about 1000ms later. The experiment used a memory broker
and synthetic task bodies, with no application jobs or production access.

This demonstrates the shared-slot scheduling dependency. It is not a Redis
throughput result, a production latency measurement or the target-host capacity
gate. No new capacity envelope is inferred from it.

## Routing and resource budget

| Consumer | Queue | Concurrency | Work |
|---|---|---|---|
| control | monitoring_control | 1 | Durable dispatch/recovery and native due-work scheduling |
| sources | monitoring_sources | 2 | Pollen/River/Air refreshes and current Hazard/Road/Commute source acquisition |
| bulk | monitoring_bulk | 1 | Tender refreshes, IPI/Auction acquisition and static timetable archives |
| projection | monitoring_projection | 1 | Commute/Road/Hazard private projections, IP/Auction projection and auction deadline activation |
| delivery | monitoring_delivery | 1 | Native consented email jobs for all nine directions |
| cpu | existing CPU queues | 2 | Legacy interactive work, legal ingestion/parsing and retention |
| existing worker-ai service | existing AI queues | 1 | Existing interactive/background model work |

The six CPU consumer parents share the existing worker-cpu container lifecycle.
The five new consumers each use a database pool of two and zero overflow.
Their six execution processes therefore budget twelve pooled database connections
in addition to the inherited API, scheduler, CPU, AI and backup budget. Collector
paths can instantiate short-lived database engines; actual total connection,
CPU and RAM use must still be measured on the target host. No per-process or
global database limit is increased.

Pollen, River, Air and Tender refreshes retain their existing acquisition plus
evaluation boundary. They do not become network-free projection jobs merely
because they have a dedicated route. Business feeds/static archives have their
own bulk consumer. Operational sources still share a bounded source worker;
the full workload gate must measure fairness and source-to-event
readiness there. Independent queues do not eliminate shared CPU/database limits.

Pollen retention and Tender document cleanup are separate periodic maintenance
tasks at their prior scheduling intervals. Their scheduling tasks enqueue due
refresh/delivery work without doing the cleanup in the control slot.
All replaceable periodic wakeups expire after their schedule interval. Durable
outbox jobs do not inherit this expiry; their native recovery and consent rules
still govern retries.

## Durable upgrade and recovery

New jobs record their canonical queue in the same transaction as the existing
outbox. Pending or recovered pre-upgrade jobs are rerouted at dispatch under the
existing job-then-outbox locks. Job IDs, payloads, idempotency keys, requested
priorities, delivery consent and attempt semantics are preserved. A broker failure
keeps the same retryable outbox row. AI dispatch fairness is unchanged.

Already published legacy broker messages remain consumable by the legacy CPU
worker. They are not cancelled or duplicated to accelerate migration. Full
isolation takes effect for newly dispatched work while old messages drain.

The production controller is separately pinned and does not self-update from
main. Adding independent container names would therefore make the initial
upgrade's rollback unsafe. Instead, a supervisor starts all six CPU consumers
inside the existing worker-cpu service. The unchanged controller and capacity
runner already stop/restart this service, including the entire group.

Any consumer exit fails the group, stops its peers and lets the existing container
restart policy recover all consumers together. SIGTERM/SIGINT starts a shared
120-second warm-stop deadline. Remaining process groups, including orphaned
prefork children, are then killed and reaped. Compose allows 150 seconds before
its own forced termination. No new controller installation is required.

The container healthcheck requires a live Celery ping from each of the six
named consumers. A live supervisor alone does not count as healthy. A missing
consumer or broker makes the existing Compose wait/recovery gate fail.
The capacity recovery runner also waits for this check after restarting
worker-cpu. Downgrading to code that predates these queue names still requires
the corresponding verified database restore; this feature does not certify
code-only downgrade or the broader MV2-056 migration/rollback gate.

## Validation and acceptance boundary

15 September 2026:

- The broad routing/native delivery/connector/deployment regression run passed
  358 tests in 425.78s. This covered delivery workflows for all nine directions.
- After preserving the existing container lifecycle, 117 worker, routing,
  deployment, recovery and rendering checks passed in 91.82s.
- Final operational/bulk separation and affected Tender regression checks passed
  33 tests in 38.49s. Real Linux subprocess checks covered graceful stop,
  ignored SIGTERM and unexpected consumer exit; in every case all six parents
  and all six child processes stopped. New consumer database pool limits and
  the inherited CPU pool were checked from the actual child environment.
- Actual Celery consumers with a memory broker progressed control, projection
  and delivery while all legacy ingestion, operational source and bulk source
  slots were occupied. Their tasks were synthetic, without production data,
  source traffic, Redis or SMTP. The subprocess test isolates Celery's global
  test-worker state from the rest of the API suite.
- Readiness required six exact live consumer replies, redacted broker failures
  and retried until ready during the capacity runner's worker-cpu recovery step.
  Production and development Compose render with the existing service names;
  the required API lint gate passed.

These are overlapping validation checkpoints, not additive test counts. The
first two runs each skipped the existing PostgreSQL-only AI dispatch race on
the SQLite suite; the final 33-test run had no skips. The warning was the
existing Starlette/httpx deprecation. Linux shutdown checks used isolated
offline containers with a read-only fixture and bounded temporary storage;
their containers were removed after execution.

Reproducible checks:
[queue/worker progress](../../services/api/tests/test_monitoring_queues.py),
[supervisor readiness and Linux shutdown](../../services/api/tests/test_worker_supervisor.py),
and [Linux process fixture](../../services/api/tests/worker_supervisor_probe.py).
On Windows, select a cached Linux Python image through
HL_SUPERVISOR_TEST_IMAGE; on Linux these tests use local isolated subprocesses.

Production activation and the full MV2-054 target-hardware workload remain open:
100 accounts, 300 reads, 10–20 readers, 20 AI jobs and recovery; inherited larger
legal/assistant scenarios; plus 1000 active subjects, nine templates and one
million observations with their original latency budgets.
