# Connected-page check history — 1.79

Scope recorded before code, 30 September 2026. VERIFYING production activation.
MV2-002/011/020/024 and broader C20–C24/live professional acceptance remain OPEN.

## Whole outcome

The existing Source coverage reader shows latest DocumentWatch health, while native
ScanItem retains each check, versions, comparison references, stages and events.
Connect these existing records into an expandable, paginated history per linked
page: what was checked, unchanged/changed/failed/skipped/interrupted, whether
analysis completed, the retained versions and related dossier research with a
current quoted finding when available. Read source text through the existing
revision-aware document reader and research through its existing record.

Do not interpret a missing research trigger as no change. Page acquisition and
analysis have separate states and consent. First attachment can create a baseline
without a ScanItem; explain absence of history instead of fabricating a check.
Show actual stage-event dates only. Scan completion is not a per-page completion
stamp, and a cancelled item without a terminal event has an unknown finish time.
Historical comparisons remain labeled; synthetic/imported captures never prove a
successful live-source check. Captured-text changes are not verified factual changes.

## Dependencies and implementation

Reuse Scan/ScanItem/Version/Comparison, linked DocumentWatch, native acquisition,
MonitoringResearchTrigger, investigation/source visibility and quoted finding
projection. Add a read-only dossier/document check-history route alongside existing
version routes. Use bounded scalar metadata reads and ten-record pages with a
fixed saved-time cutoff; later retries/corrections can still update retained rows.
No source body is loaded to list history. No schema, duplicate database, scheduler,
provider call, fetch, model request, subscription or automatic consent.

Require current dossier/organization/product access, current linked watch and corpus
rights. Excluded/unlinked/withdrawn sources and versions cannot leak their derived
metadata or findings. Member-team dossiers cannot expose workspace page history.
Pausing a watch preserves otherwise authorized saved history. Related research must
belong to this dossier and exact saved version/revision; current quotations and
paired-version access remain required. Never forward raw provider/source errors.

Both products use the same reader. Load history only on request, clear it on
access/session/dossier changes, keep errors actionable and preserve the main concise
view. Existing clients/servers remain compatible. Keep Brandbook and nine sections.

## Source readiness and acceptance

Existing local fictional native acquisition fixtures suffice; no live/private/paid
research, browser/preview/DOM/screenshots, new keys or frozen evaluation.

- Legal and Pharma: connect source -> actual unchanged scan -> changed scan ->
  retained earlier/later versions -> explicitly consented research and cited finding;
  failed source preserves prior success and has its own visible history record.
- Acquisition success versus failed/deferred/unconfigured analysis; skipped,
  interrupted, queued and synthetic checks; absent timestamps remain unknown.
- Bounded pagination, stable cutoff and no new fetch/model calls from reader/export.
- Current exclusion, unlink, corpus/version withdrawal, paused watch, private-team,
  tenant/product/viewer and session boundaries; no raw error bodies or private data.
- Actual shared UI rendering/navigation, safe untrusted text, source failure and
  retry behavior, legacy compatibility; full client tests/lint/types/build.
- Affected Core tests, exact API lint and backlog guard; source/privacy/parity review,
  tested main push, normal Core activation, exact existing public Sites publication
  and verified deployment/access. No repeated unchanged client publication.


## Local acceptance

66 distinct Core checks passed: 22 new history cases and 44 affected native
history, page-research, source-health and backlog checks. Both products exercise
actual attachment, unchanged and changed acquisition, consented durable research,
current quotations, paired saved-text reads, failed acquisition and unchanged
recovery. Native analysis succeeds or fails independently of capture; historical
baseline comparison does not masquerade as a fresh page change. Synthetic/imported
versions, correction revisions, current corpus/link/exclusion/team/tenant/product
and session boundaries stay explicit. Metadata-only pagination retains its cutoff
without fetching or calling a model. Timestamps are actual per-item events.

Each client passed all 442 tests, types and production build. A test-only unused
import was removed; lint and all five new reader cases then passed again in both.
Actual React reconciliation covers on-demand fetch, pagination, version/revision
navigation, research navigation, source failure, retry and session invalidation.
Reader markup safely escapes supplied text. No browser or visual acceptance was
performed. Native analysis fixture configuration was corrected to use the current
organization environment; source quotations are checked against actual stored text.
These fixture corrections do not change production configuration.

The analysis label describes the status retained on that native check. A deferred
background analysis may complete later without updating its ScanItem; this reader
does not invent a subsequent completion. Related dossier research has its own
current investigation status and separately consented provenance. Broader unified
feed history and normalized SourceHealth remain OPEN. No schema, acquisition,
provider, scheduling, consent or notification changes were made.
