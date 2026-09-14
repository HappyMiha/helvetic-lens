# Monitoring source history — 15 September 2026

Complete scoped MV2-052 feature at `/admin/monitoring-sources`: platform
administrators can inspect all nine active categories and both Commute channels
over 24 hours, 7 days or 30 days. Main navigation and native visibility persist.

## Sampling and meaning

The existing maintenance queue samples local source-operation metadata every
five minutes, loading current connector settings. It makes no provider/model/mail
call. Tasks expire after five minutes if not started. A unique channel/slot key
makes retries idempotent; concurrent insertion cannot overwrite an observation.
Only whitelisted counts, status enums, timestamps and a hashed source binding
are stored. No private monitor, credentials, URLs, policy text, source payload or
raw error enters history. GET requests never create samples or collect sources.

Operational retention is 30 days. Cleanup removes at most 4000 older samples per
tick and catches up after interruption. It never compacts native source evidence,
delivered revisions or private decisions. The normal rolling bound is 8641 slots
per channel including the current slot, ten channels. A stopped or failed sampler
leaves gaps; historical operation is not reconstructed. This bound does not prove
target-host capacity or uptime. A missing interval is not a healthy observation.

At most 720 hourly intervals cover the selected hour window through the current
partial hour. Each includes recorded/expected/missing counts, all observed
acquisition/permission/collector states, disabled-section counts and binding
changes. Recovery within an hour cannot hide an earlier failure or revocation.
The last state is supplementary; no continuous source identity across replacement
is assumed. Source history is an operational record, not source-rights evidence.

Publication age, latest acquisition age and oldest acquisition age are measured
separately at each sample. They are not differences between unrelated provider
and receipt timestamps and do not measure ingestion transit, processing or
delivery latency. Hourly min/max and known-value counts preserve unknowns. Future
clocks remain unknown, never zero. Missing intervals are not interpolated. A
permission record or successful acquisition does not establish source coverage.

## Interface, access and migration

Five-language source/period/metric selectors drive the chart. Missing samples
have separate markers. A labelled numerical table shows 24 hours per page with
all observed states, ranges and binding changes. Dates use Europe/Zurich; ranges
are hour windows rather than civil calendar days. Chart bounds align with time
labels at both widths. Unknown/empty/error states are explicit. Refresh reads
stored history. A visible, idle reader refreshes every five minutes. Selection
changes, page hiding and access loss abort requests and clear results; late
responses cannot restore hidden data. Role denial also redacts the parent overview.

The no-store GET checks the current platform-admin role and accepts only ten
known channels and 1/7/30-day windows. Denials/errors are also no-store. No public
export, provider action or outgoing notification is introduced.

Migration `be91628bdef1`, after `ad80517acef0`, creates
`monitoring_operational_samples`. This is separate from Pollen's existing
`monitoring_source_samples`. Downgrade discards only operational samples; tested
downgrade/upgrade preserves native source data and personal acknowledgement
receipts. This schema check is not a production backup/rollback rehearsal.

## Verification

- Final history/operations/attention API suite: **45 passed** in
  `.tmp/source-history-final.log`. Includes real HTTP auth/no-store/selection,
  real Celery invocation with current settings, ten channels, retries, recovery,
  future clocks/gaps, all periods, brief permission/collector changes, bounded
  4000-row cleanup and migration round trip preserving native data/receipts.
- `scripts/check_source_history_postgres.py` observed a real unique-key lock wait
  on an empty disposable PostgreSQL 16 database. Once the first transaction
  committed ten samples, the concurrent retry inserted zero and preserved all
  original fields. An initial run exposed unreliable psycopg `rowcount`; actual
  `RETURNING` rows now determine insert/delete counts. Final evidence:
  `.tmp/source-history-postgres-final.log`.
- The complete root build passed with the isolated `source-history` directory.
  Exact API Ruff and scoped formatting checks pass; generated Next imports are
  excluded. Actual backlog integrity passed (1 check) after recording final evidence.
- `scripts/check-source-history-browser.mjs` covers nine categories/two transport
  channels, five locales at 390/1440px, metrics, 30-day table pagination,
  unknown/gaps, empty/error recovery, denied access and a delayed pagehide reply.
  **24 full-document axe checkpoints** pass reported violations and the
  prohibited-ARIA gate; incomplete checks remain recorded, not certified.
  The fixture waits for a fresh session response before checking hydrated denial.
  API data is synthetic; no live provider or user data was changed.
- Report: `test-results/accessibility/monitoring-source-history.json`. Desktop
  and mobile screenshots were inspected; SVG letterboxing initially misaligned
  the time labels and was corrected before final verification.

Reviewer: the implementing single agent. Independent human/native-language,
provider, target-hardware and production acceptance is not claimed. MV2-052 stays
IN PROGRESS: paired ingestion/processing/delivery latency, recovery/backfill,
queue fairness and broader operational requirements remain. Publication does not
prove activation. History begins when the sampler runs on the activated release;
earlier intervals are gaps, not reconstructed measurements.
