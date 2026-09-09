# Basel-Stadt pilot and first relevant material

The user selected Basel-Stadt explicitly on 9 September 2026 (HL-080/HL-073).
The implemented package is **German legislation in the official OGD dataset
100354**, including the municipal entries published there. It is labelled a
pilot. This is a bounded source contract, not a claim of complete cantonal news,
legal advice, or readiness for a broad public launch.

## First-use journey

Open `/onboarding` → **Open the Basel-Stadt guide**, or open
`/onboarding/basel-stadt` directly. The Sources page also links the guide.

1. Read the scope and attribution, then explicitly enable Basel-Stadt for the
   organization. Federal starter activation does not activate the cantonal pack.
2. Explicitly request the two starter laws if the shared corpus is empty. This
   uses the existing durable ingestion queue; it needs a running worker and an
   available publisher. Opening the page does not write anything.
3. Choose privacy or building/planning, or edit the German concepts and exclusions.
   Preview uses the existing deterministic topic scorer, with no AI call. Source
   titles remain German; product controls are available in DE/FR/IT/RM/EN.
4. Inspect matching terms and open the exact saved evidence in a separate tab,
   keeping the form available. The original publisher version is linked too.
5. Save the shared monitoring topic explicitly. Retry keeps its idempotency key;
   changing the draft clears the old preview and key. Already matching rules link
   to existing topics. Notification preferences are a separate explicit action
   on `/digests`; topic creation does not subscribe the user to email.

An invited viewer can preview already admitted evidence. An organization
administrator enables the package, requests collection and saves shared topics.
The existing generic onboarding/evidence viewer records personal first-action
milestones through its existing visibility and permission checks. A recorded
display is not proof of comprehension or independent usability success.

## Why this source

- [The canton's collection description](https://www.bs.ch/jsd/zentraler-rechtsdienst/zentraler-rechtsdienst-zrd/gesetzessammlung)
  identifies cantonal and Basel, Riehen and Bettingen municipal legislation and
  states that the electronic **Kantonsblatt is authoritative**.
- [Official dataset 100354](https://data.bs.ch/explore/dataset/100354/), published
  by Zentraler Rechtsdienst / Open Data Basel-Stadt, supplies stable law IDs,
  version IDs, SG numbers, source-stated validity dates, exact publisher version
  links and a German HTML representation. Its metadata declares daily updates
  and CC BY 4.0; attribution and dataset/publisher links are retained.
- [Dataset API](https://data.bs.ch/api/explore/v2.1/catalog/datasets/100354)
  offers bounded keyset queries, avoiding a fragile interactive-portal scraper.
  This supports the selected canton's actual privacy and planning use cases with
  reopenable source text and explicit maintenance checks.
- Dataset 100355 was examined but is not ingested. Its detection/change timestamp
  must not be interpreted as the date on which law changed.

## Exact contract and limits

| Stream | Default cadence | Scope |
| --- | --- | --- |
| `starter-de` | Daily; explicit first-use requests globally throttled to once per hour | Current dataset entries for SG 153.260 (information/data protection) and 730.100 (building/planning) |
| `latest-de` | Hourly, up to 180 seconds jitter | 50 newest numeric version IDs over three bounded pages; these are not necessarily the newest legal changes |
| `catalogue-de` | Every 15 minutes, up to 60 seconds jitter | At most 20 records per job, descending version IDs, restarting after the available dataset is traversed |

All three streams use the shared connector runner, immutable evidence store,
receipt deduplication, checkpoints, health/status, durable jobs and organization
subscriptions. No private collector is created per organization. The initial
catalogue may take several days: the inspected source had 11,006 version/taxonomy
rows; this is neither a unique-law count nor a completeness guarantee. Queue
pressure, failures and the upstream daily cadence can add delay. The fast starter
path does not wait for the historical cycle.

The retained artifact is the exact UTF-8 value of the publisher's
`gesetzestext_html` field. The record fingerprint, exact record-query URL and
publisher-version link accompany it; the whole dataset/API response is not
represented as the saved artifact. Missing HTML remains metadata-only. Corrections
create another immutable fingerprinted version; identical taxonomy placements and
overlapping streams do not create another text version. Dates come only from
source fields. An old version's `not_current` badge does not repeal the work.
Absence is not used to infer deletion, repeal or a quiet period.

**Excluded:** court decisions, parliamentary business, full Kantonsblatt coverage,
annex contents, OCR, documents absent from the dataset and non-German source
translations. Municipal entries are included only to the extent present in this
dataset, not as a claim of complete coverage of each municipality. No other canton
is advertised as implemented.

The preview examines at most the 500 most recently admitted organization events
and displays at most 10 matches. It is not full-text search over every historical
law: relevance uses titles, identifiers and metadata via the existing scorer.
An empty preview can mean pending collection, sample limits or unsuitable terms.
The guide explains recovery and never equates that result with no relevant law.
Package `active` means subscription/backfill state; successful connector pages and
`available` contract evidence do not mean complete historical or live coverage.

## Verification and release boundary

Reproducible checks:

```sh
PYTHONPATH=services/api python -m pytest services/api/tests/test_basel_stadt.py -q
PYTHONPATH=services/api python scripts/check_basel_stadt_live.py --output .tmp/basel-live.json
python scripts/check_basel_stadt_postgres.py --database-url '<empty local hl080_basel_regression database URL>'
npm run build
npm run check:basel:browser
```

- Live acceptance on 9 September 2026, 05:52 UTC: two starter laws ingested through
  the actual durable job/fanout path, found by privacy/building concepts and
  reopened through organization-scoped evidence APIs; topic saved without AI and
  repeat collection deduplicated. Two discovery pages and one actual ingestion
  page passed for each of the other streams. The bounded report is
  [basel-stadt-live-2026-09-09.json](evidence/basel-stadt-live-2026-09-09.json).
- Synthetic backend cases cover page/cycle recovery, overlap, correction history,
  schema and host drift, missing HTML, source dates, exact artifact bytes, duplicate
  topic detection, tenant isolation, CSRF/viewer boundaries and collection throttling.
- Disposable PostgreSQL acceptance additionally checks competing first-use
  requests from two service instances: one queued request and one throttled result.
- Production-build browser test covers 20 journeys (five locales × 390/1440 px ×
  administrator/viewer), passive entry, explicit activation/collection, errors,
  empty/repeated previews, saved-evidence destinations, duplicate handling and
  idempotent save retry. Forty axe checkpoints inspect all reported violation
  severities; other incomplete checks are retained, not accessibility certification.

Native-language review, a real new user's unaided completion measurement,
production worker/source-outage observation and deployment remain separate field
acceptance. Automated tests do not substitute for these. No production database,
container or deployment was changed by this implementation. Existing operator
source-status and schedule controls remain the maintenance surface; an operational
owner still needs to be assigned before an external organizational pilot.
