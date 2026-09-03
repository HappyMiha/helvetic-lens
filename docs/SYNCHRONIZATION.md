# Official source synchronization

Helvetic Lens runs official Swiss source connectors continuously while fetching and storing public evidence once for the whole deployment. The same saved work is then exposed to every organization that watches it.

## Runtime path

```text
Celery Beat (15-second admission tick)
  -> PostgreSQL schedule row lock
  -> durable connector_sync job + transactional outbox
  -> Redis ingest queue
  -> CPU worker runs one bounded connector page
  -> shared work/version/event deduplication
  -> idempotent organization watch/feed fan-out
```

PostgreSQL is the source of truth. Redis may redeliver a message, and Beat may restart, without creating another active job for the same stream. A failed worker retry keeps the first start boundary so already committed events are still included in the final fan-out.

## Default streams

| Authority             | Streams                                         | Default cadence                                  |
| --------------------- | ----------------------------------------------- | ------------------------------------------------ |
| Fedlex                | `rss-de`, `rss-fr`, `rss-it`                    | 15 minutes plus deterministic jitter             |
| Fedlex                | `reconcile-cc`, `reconcile-oc`, `reconcile-fga` | daily bounded keyset reconciliation              |
| Swiss Parliament      | `notices`, `recent`, `active`, `catalogue`      | every 30 minutes, hourly, every 6 hours, daily   |
| Federal Supreme Court | `latest`, `reconcile`                           | hourly overlap and daily two-year reconciliation |
| Federal Criminal Court | `latest`                                        | hourly overlap over 50 decisions                 |

These are admission intervals, not promises that an upstream authority has published new material. Each connector retains its own overlap, source request pacing, cursor and partial-item checkpoint.

## Administration

Open **Source sync** as a platform administrator. The page shows the last successful run, current cursor or watermark, next run, duration, new/changed/failed/fan-out counts, freshness lag, partial coverage, connector health, ingest pressure and free artifact space.

An administrator can:

- change an interval from one minute to 30 days;
- set deterministic jitter up to half the interval;
- restrict automatic runs to a Europe/Zurich time window, including an overnight window;
- pause or resume a stream without losing its cursor or saved corpus;
- choose **Sync now**, which reuses an already active run rather than duplicating it.

The API surface is `GET /api/admin/connectors`, `PUT /api/admin/connectors/{connector}/{stream}`, and `POST /api/admin/connectors/{connector}/{stream}/sync`. Existing provider-specific sync endpoints also submit the same durable work. Mutations require platform-admin access.

## Backpressure and recovery

Admission pauses when active connector jobs reach `CONNECTOR_MAX_ACTIVE_JOBS`, pending ingest outbox records reach `CONNECTOR_MAX_QUEUE_DEPTH`, or the shared artifact volume falls below `CONNECTOR_MIN_FREE_MEGABYTES`. Registry and evidence reads remain available while synchronization is deferred.

Connector jobs use the normal durable lease and retry policy. Item-level failures remain attached to the connector page and its last safe checkpoint. Pausing a schedule stops future automatic admission; it does not cancel a run already executing. To recover, correct the source or capacity problem, keep the schedule enabled, and use **Sync now** or let the next due tick continue from the stored state.
