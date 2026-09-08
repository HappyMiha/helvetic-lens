# Selecting the current saved impact report

Implemented for HL-099 on HappyDucky02, 8 September 2026.

The document summary and comparison detail previously examined only the latest
50 Analysis records. An older successful result could disappear behind repeated
failed attempts, even when its exact model/profile/prompt/evidence cache key was
still current. The UI would then show a failed or obsolete result and encourage
unnecessary regeneration.

The reader now examines saved metadata across the complete accessible history:

1. Prefer the newest successful result with the current cache key.
2. If none exists, retain the newest successful previous result, labelled stale.
3. If none succeeded, show the newest attempt and its actual status.

Timestamp and ID define deterministic newest-first ordering, including equal-time
attempts. The latest attempt is still shown separately when it differs from the
selected report. Existing action decisions, report content, runtime/capability
freshness and historical records are not rewritten. Reads do not generate an
answer or increment reuse counters. Current-key computation keeps the existing
local-runtime metadata check; this is not a claim of zero metadata requests.

## Read and visibility contract

The selector performs three analysis queries for a nonempty result: newest-attempt
metadata, one preferred report ID, and that report body. Only the chosen Analysis
object is materialized. Empty history returns before computing runtime/cache state.
There is no arbitrary 50-attempt eligibility limit and no transfer of every old
result, plan, coverage or provenance JSON to the application process.

All selection queries explicitly require the current organization and visible
comparison/law, including in privileged database sessions. Visibility is repeated
when loading the selected body; losing access can yield no report rather than a
foreign payload. The observed latest timestamp/ID is an upper boundary, so a later
attempt waits for the next read. This is not a cross-request transaction snapshot:
corrections, deletions or deliberately backdated rows can change selection.

SQL ranks eligible metadata using current-success / previous-success / other
priority. Database sorting/filtering cost is not constant and has not been certified
on the intended host. Existing comparison, profile and action-decision reads are
separate from the three analysis queries. This does not bound action-decision
history, all law-summary bodies or the independent impact-matrix reader. Those
remain HL-099 work; no schema migration or production deployment accompanies this
change.

## Evidence and limits

The large regression seeds a valid saved report and 1,001 later failures with large
archived plan fields, requires exactly one materialized Analysis body, and checks
the actual document and comparison HTTP responses without further inference.
Additional tests cover newer obsolete successes, stale/failed fallback, equal-time
ordering, organization/comparison/law revocation and newer admissions.

The existing AI history and runtime-cache suites verify that changing prompts,
models, capability metadata or runtime availability still invalidates current reuse.
See [verification](VERIFICATION.md) for the exact completed runs. After the user
started Docker, all six PostgreSQL 16.14 scratch scenarios passed: complete current
selection, fallback, admission boundary and analysis/comparison/law visibility.
The labelled temporary container and its synthetic databases were removed; no
application data was used. These regressions do not establish intended-host
capacity, native-language or independent legal-quality acceptance.
