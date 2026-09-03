# Personal digests

Helvetic Lens digests are a delivery view over the persisted organization impact inbox. They do not run another model, create legal events, or maintain a parallel source of truth.

## User flow

Each signed-in user can open **Digests**, choose daily or weekly delivery, filter by impact severity and official source, and opt into email. The current web digest remains available when email is disabled. Preferences belong to the user inside the active organization, so the same account can choose different settings after switching organizations.

**Send now** creates the same durable job as the scheduler and is limited to three requests per hour. The page shows the latest 20 delivery attempts and a preview built only from saved impact leads. Opening the page, sending a message, skipping an empty period, or failing delivery never changes impact-inbox read, dismissed, or muted state.

Every email contains links back to the saved comparison or relation evidence. A signed direct unsubscribe URL disables only that user's email digest for that organization; the web digest and all monitoring history stay available.

## Delivery contract

- Celery Beat checks due preferences hourly and enqueues idempotent `digest_delivery` jobs on the maintenance queue.
- A scheduled period has one delivery record and one job idempotency key. Worker retries use the durable job lease and retry policy.
- Summaries include at most 50 regulatory events and five monitored-law effects per event. Dismissed and muted items are excluded.
- Empty periods and installations without email transport are recorded as `skipped`, not as successful email.
- SMTP credentials stay in server settings. Delivery records contain the bounded summary, status, timestamps, and a short error; integration logs do not receive document bodies or mail credentials.
- Terminal delivery records are retained for `DIGEST_DELIVERY_RETENTION_DAYS` (180 by default) and then removed by the operational cleanup task. Legal evidence, impact history, and user read state are not deleted.

Development mode writes inspectable messages to the private application data volume. A shared deployment uses the existing SMTP settings. Transactional content and the web flow support `de-CH`, `fr-CH`, `it-CH`, `rm-CH`, and `en-CH`, using the recipient's saved locale.
