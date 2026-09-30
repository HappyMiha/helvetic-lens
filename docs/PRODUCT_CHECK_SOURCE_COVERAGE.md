# What each scheduled check actually read — 1.78

Scope recorded before implementation, 30 September 2026. VERIFYING production activation.
MV2-002/012/020/024 and target C20–C24 remain OPEN beyond this bounded outcome.

## Outcome and existing behavior

The scheduled result already distinguishes findings, changed evidence, unchanged
captures and failed work. It does not identify which returned pages failed or
which previously captured pages were not checked. A recurring query is not a
subscription to every previously found URL. Page watches are separately consented
and read retained corpus versions; they are not silently enabled by web research.

Show one expandable source list in the existing scheduled result. Bind read and
analysis attempts to actual worker receipts, with start/finish dates. Distinguish
first capture, changed capture, unchanged captured material, failed/interrupted
reading, read but unanalysed evidence, and not checked. Never infer access-barrier
causes from a generic failure, or call incomplete reading proof of no change.
Show up to twelve recent distinct earlier captures for this exact scheduled
question, pinned before work, explicitly labeling any bounded/truncated lookback.
Those missing from this search stay visibly not checked, without fetching them.

## Reuse and dependencies

Extend existing InvestigationBranch checkpoints and InvestigationSource capture
metadata. Reuse scheduled consent, worker leases/fences, current source exclusions,
source visibility, existing response/export and the 1.77 result reader. No new
source database, scheduler, migration, query, fetch, model call or subscription.
Persist source IDs and actual receipt linkage; do not reconstruct old failed
attempts as new historical facts. Legacy runs explicitly lack a source receipt.
Keep private/team/workspace boundaries and current source rights; hide excluded,
removed or scope-changed source details. Historical successful baselines must not
be replaced by failed/unchanged reads. Do not confuse capture change with factual
or legal change. No modification of frozen evaluation or provider settings.

## Readiness and acceptance

Existing local fictional worker fixtures and saved public captures suffice. No
paid/live/private research, browser/preview/DOM/screenshots or messages to people.

- Both products: explicit consent -> first capture -> unchanged -> changed ->
  earlier source absent from search; exact query and existing provider call counts.
- Multi-source partial read, failed extraction, empty/failed search, exclusion,
  interrupted work and retries retain honest source-specific outcomes/timestamps.
- Queued/running/stopped work cannot imply completed coverage; legacy records
  explicitly lack receipts. Later runs cannot alter a pinned earlier source list.
- Current source/question/access changes redact derived details in response and
  export; no provider errors or private note becomes source metadata.
- Shared accessible reader keeps overview concise; safe escaped text and links,
  retained evidence navigation, legacy contract behavior, mobile wrapping.
- Affected Core tests, exact API lint and backlog guard; both complete client
  suites/lint/types/build. Source/privacy/parity review, main push, normal Core
  deployment and exact existing public Sites activation with access checks.

This does not complete unified historical coverage for native feed/page scans,
normalized SourceHealth, all-source subscriptions or professional live acceptance.

## Local acceptance

84 distinct Core cases passed: 14 new source-coverage behavior cases, 45 existing
scheduled outcome/consent/access/backlog cases and 25 native worker/page-watch
regressions. The first new pass had 13 passes and one fixture failure: the
interruption fixture used an absent job_id instead of the investigation ID.
After repair, its actual explicit retry completed without repeating search, keeping
two reading attempts. Final affected runs: 46 passed in 113.84 seconds, then
25 worker/page cases in 52.46 seconds; earlier new-case passes do not overlap.
Exact API lint and backlog consistency passed. Each client passed all 437 tests,
lint, typecheck and the required production build. The existing Starlette/httpx
warning and Vinext route-classification notice are unchanged.

Existing branch receipts now bind source URL/ID to actual reading and analysis
attempts. Captures retain comparison state and the last analysed baseline; only
successful analysis writes an actual analysis-completion timestamp. Old records
without that timestamp remain unknown. A seeded lookback scans at most 60 prior
captures and pins at most twelve distinct permitted source IDs; truncation and
subsequent withdrawal are explicit. No previously absent URL is fetched merely
because it appears in this list. Older runs have no invented per-source receipt.

Both 1.78.0 readers use one expandable list, safe original links, retained-capture
navigation, honest incomplete states and a limited-lookback explanation. No
browser, live/private/paid research or human professional evaluation was used.
Exact source/privacy/parity and deployment evidence follow separately.
