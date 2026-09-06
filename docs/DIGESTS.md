# Personal digests

Helvetic Lens digests are a delivery view over the persisted organization impact inbox. They do not run another model, create legal events, or maintain a parallel source of truth.

## User flow

Each signed-in user can open **Digests**, choose daily or weekly delivery, filter by impact severity and official source, and opt into email. The current web digest remains available when email is disabled. Preferences belong to the user inside the active organization, so the same account can choose different settings after switching organizations.

**Send now** creates the same durable job as the scheduler and is limited to three requests per hour. The page shows the latest 20 delivery attempts and a preview built only from saved impact leads. Opening the page, sending a message, skipping an empty period, or failing delivery never changes impact-inbox read, dismissed, or muted state.

Every email contains links back to the saved comparison or relation evidence. A signed direct unsubscribe URL disables only that user's email digest for that organization; the web digest and all monitoring history stay available.

## Delivery contract

- Celery Beat checks due preferences every minute and enqueues idempotent `digest_delivery` jobs on the maintenance queue.
- A scheduled period has one delivery record and one job idempotency key. Worker retries use the durable job lease and retry policy.
- Summaries include at most 50 regulatory events and five monitored-law effects per event. Dismissed and muted items are excluded.
- Empty periods and installations without email transport are recorded as `skipped`, not as successful email.
- SMTP credentials stay in server settings. Delivery records contain the bounded summary, status, timestamps, and a short error; integration logs do not receive document bodies or mail credentials.
- Terminal delivery records are retained for `DIGEST_DELIVERY_RETENTION_DAYS` (180 by default) and then removed by the operational cleanup task. Legal evidence, impact history, and user read state are not deleted.

Development mode writes inspectable messages to the private application data volume. A shared deployment uses the existing SMTP settings. Transactional content and the web flow support `de-CH`, `fr-CH`, `it-CH`, `rm-CH`, and `en-CH`, using the recipient's saved locale.


## Optional local delivery clock (HL-079)

The existing daily/weekly preference now accepts `schedule: {timezone, time}`.
`timezone` is a validated IANA name (default `Europe/Zurich`); `time` is strict
`HH:MM` or null. Host-specific names such as `localtime` are rejected. Null or an
omitted schedule preserves legacy elapsed 24-hour/7-day behavior. Omitting the
schedule in an older client request preserves an already configured clock; an
explicit null `time` turns that clock off. Saving a changed timezone alone while
the clock is off does not postpone the existing due date.

Enabling or changing an explicit clock schedules the first attempt on the next
local day (daily) or seven local dates later (weekly), at that time. Weekly cadence
therefore uses the weekday of configuration; a separate weekday picker remains
future work. Subsequent due dates advance from the previous scheduled instant,
not when a delayed worker finishes. Instants remain stored in UTC. Across a DST
gap the selected nonexistent time advances to the first valid minute; an ambiguous
repeated time uses the first occurrence once. A completely skipped civil date is
also handled. The UI shows the saved next instant in its timezone, falling back
to an explicitly labelled UTC display if the browser lacks that timezone.

Beat checks every minute and retains the existing bounded due selection, locks,
unique period and durable-job keys. This is a scheduled attempt, not a delivery
SLA: stopped workers, backlog or SMTP failures can delay email. **Send now** stays
an explicit immediate command. Existing queued jobs/periods are not rewritten by
schedule edits, and unsubscribe still prevents delivery. Quiet-hours enforcement
at final dispatch is not implemented here; it remains part of HL-078/079.

Migration `ff72eb61754d` adds nullable `digest_preferences.schedule_json`; existing
preferences, opted-in status, due instants and delivery history are preserved.
The migration does not opt anyone in or enqueue mail. It must be applied through
the normal deployment process; development publication does not run it on prod.

Checks: `test_digest_schedule.py`, digest preview/resume/delivery regressions,
PostgreSQL scratch suites `digest-local-schedule` and `digest-schedule-migration`,
and five-language mobile/desktop browser flows. Topic inclusion, expanded filters,
quiet hours, organization policy and notification-noise measurement remain open.
