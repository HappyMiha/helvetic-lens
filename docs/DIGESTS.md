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
an explicit command but respects the quiet hours below. Existing queued jobs/periods
are not rewritten by schedule edits, and unsubscribe still prevents delivery.

Migration `ff72eb61754d` adds nullable `digest_preferences.schedule_json`; existing
preferences, opted-in status, due instants and delivery history are preserved.
The migration does not opt anyone in or enqueue mail. It must be applied through
the normal deployment process; development publication does not run it on prod.

Checks: `test_digest_schedule.py`, digest preview/resume/delivery regressions,
PostgreSQL scratch suites `digest-local-schedule` and `digest-schedule-migration`,
and five-language mobile/desktop browser flows. Topic inclusion, expanded filters,
organization policy and notification-noise measurement remain open.


## Optional recipient quiet hours (HL-079, 6 September 2026)

The same saved schedule accepts `quiet_start` and `quiet_end` as distinct HH:MM
values, in the chosen timezone. Both null disables the policy; one missing/null
side of a new pair, equal endpoints or invalid clocks are rejected. Existing
clients omitting these fields preserve saved quiet hours. Updating only quiet
hours does not postpone the next scheduled period. No new migration is needed.

Intervals include the start and exclude the end, and may cross midnight. The
worker checks actual local time before delivery preparation and again immediately
before handing the message to SMTP. Both scheduled and explicit **Send now** jobs
obey this rule. A delay releases the durable job and sets its transactional outbox
wake-up time to the next allowed UTC minute; it does not sleep in a worker, create
another digest or consume a failure attempt. Early duplicate broker messages do
not reclaim quiet-delayed work. Completed preparation remains checkpointed; on
resume the recipient, opt-in, current access and selected evidence are checked
again. No inference is triggered by delivery.

DST tests cover missing local endpoints and both occurrences of repeated hours.
The policy is evaluated at each real instant: a clock rollback may re-enter quiet
hours after an earlier allowed interval. Already accepted SMTP messages cannot be
recalled. A changed or removed policy is checked at the existing job's planned
wake-up, not by eagerly rescheduling every pending job; a longer new quiet period
can defer it again. Queue delays remain possible. This is personal email-digest
policy, not a quiet-hours guarantee for all future notification channels.

The five-language form provides both time fields and an explicit clear action.
History distinguishes queued quiet-hour waits from failures. Tests include UTC/DST
boundaries, old-client API preservation, atomic invalid saves, no early dispatch,
one resumed send, unsubscribe and a boundary crossed while rendering. Scratch
PostgreSQL suites: `digest-quiet-resume`, `digest-quiet-unsubscribe`,
`digest-quiet-boundary`, `digest-quiet-save`. Topic inclusion and broader filters,
organization limits, immediate notification eligibility and user-measured noise
remain open under HL-079.
