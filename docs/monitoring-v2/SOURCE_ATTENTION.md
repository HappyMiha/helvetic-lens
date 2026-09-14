# Monitoring source attention — 15 September 2026

Complete scoped MV2-052 feature at /admin/monitoring-sources, alongside the
source operations overview. Platform administrators see an actionable list for
all nine active categories, including separate transport update/alert channels.
The public nine-direction navigation remains available to every user.

## Behavior and limits

The list derives issues from stored source metadata: disabled sections, missing
collector configuration, permission-record status, failed/missing acquisitions,
invalid clocks and renewal windows at 30 and 7 days. Partial Pollen access retains
expired/revoked channel warnings. Unknown evidence never becomes zero or healthy.
Each item links to its category in /monitoring/settings. Reload reads local
metadata; it does not collect from providers, renew rights or send messages.

Acknowledgement is personal to the current platform administrator. The API checks
the exact current issue key and fingerprint. Changes to permission/source binding,
selected source generation, severity, acquisition outcome or retry clocks require
review again. Elapsed age alone does not create repeated issues. Acknowledged
current issues remain available through the All current issues filter and are
never relabelled healthy. This is an attention inbox, not an incident history or
an email/push reminder service. Cleared issues disappear from the current list.

Only fixed issue keys, hashes and acknowledgement times are retained per user.
No source payload, endpoint query, credentials, policy text or private monitor
content enters this API or receipt storage. Source selection reads are capped at
100; exceeding the cap returns an explicit unavailable result instead of partial
success. Metadata snapshots and acknowledgements are no-store, including denied
and failed responses. POST requires session/CSRF, strict fields and a fresh role.
The shared platform-user lock serializes concurrent role/deletion changes and
receipts. Wall time is sampled after acquiring the lock, so crossing a renewal
boundary while waiting invalidates an old confirmation. A later source change
also invalidates the receipt on the next read; no source mutation is authorized.

The additive ad80517acef0 migration creates only the receipt table. User deletion
cascades to personal receipts. Downgrading to 9c7f5069bdef drops receipts; upgrading
again starts with no acknowledgements and preserves source records/operators.
Do not treat this schema rollback as a backup or recovery workflow.

The five-language interface supports pending/all filtering, acknowledgement,
connector links, unknown dates, errors and reload. It refreshes once per minute
while visible and idle. Page hiding aborts pending work and clears the list;
access denial also redacts the parent source overview. A successful POST is
followed by a fresh GET rather than optimistic health/acknowledgement changes.

## Local acceptance

- 32 API/source/account-erasure checks passed, including all nine categories,
  two transport channels, expiry windows, Pollen partial access, source generation
  replacement, recovery/retry, exact-state idempotency, foreign-admin isolation,
  role withdrawal, auth/CSRF/strict fields, no-store errors, migration round trip
  and renewal-boundary changes during lock acquisition.
- scripts/check_source_attention_postgres.py passed all three real PostgreSQL 16
  lock races: duplicate acknowledgement produces one receipt; role revocation
  and operator deletion produce platform_admin_required and no receipt. Each
  scenario observes pg_stat_activity reporting an actual lock wait. Only a new,
  named, empty localhost scratch database is permitted by this harness.
- scripts/check-source-attention-browser.mjs passed all nine categories and two
  transport channels in five locales at 390/1440px, acknowledgement/reappearance,
  stale/denied mutations, failed reads/recovery and late pagehide responses.
  All 24 full-document axe checkpoints passed reported violations and the
  prohibited-ARIA gate. Other incomplete checks remain recorded, not certified.
  Non-admin denial waits for hydrated visible content before asserting isolation.
  Browser API responses are synthetic; no live provider or user data was changed.
- Full root build with HELVETIC_LENS_CHECK_BUILD=source-attention passed, including
  frontend lint/type/guide gates. Generated isolated-build imports are excluded.
  Exact API Ruff and scoped Prettier passed; the actual backlog-integrity test
  passed (1 check) after the final backlog update. Local evidence lives in .tmp/source-attention-accepted.log,
  .tmp/source-attention-postgres.log, .tmp/source-attention-browser-accepted.log
  and test-results/accessibility/monitoring-source-attention.json. Mobile/desktop
  screenshots were inspected for readable controls and horizontal overflow.

Reviewer is the implementing single agent. Independent human/native-language,
provider and production acceptance is not claimed. MV2-052 remains IN PROGRESS:
historical publication/ingestion/processing/delivery lag charts, recovery/backfill,
queue fairness and independent operational acceptance still require evidence.
Publication and verified production activation are tracked separately.
