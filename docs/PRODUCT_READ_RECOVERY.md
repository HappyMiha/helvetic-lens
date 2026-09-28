# Evidence read recovery — release 1.28

Status: VERIFYING production. Scope recorded before implementation on 28 September 2026.
This is a bounded contribution to MV2-002 and MV2-020, not completion of either
parent or the Dynamic Dossier / Visual Language specifications.

## User outcome and dependencies

A failed saved-evidence read has a clear retry action. Previously displayed
evidence cannot reappear because an earlier analysis or action request finishes.
Navigation, account/workspace changes and request cancellation cannot substitute
one dossier's result for another. Both Pharma and Legal receive the same read
lifecycle improvement. Existing source/version APIs, native resource cache,
durable jobs, session/CSRF and dossier rights remain authoritative.

Native comparison and single-version Ask readers must gate retained evidence on
their current read result. Preserve ordinary background revalidation, all four
companion tabs, material classification, identity confirmation, exact citations,
saved results and durable job recovery. Terminal analysis now refreshes the
comparison through the existing server reader, which checks current profile and
runtime identity; job output alone must not replace that reader. This deliberately
adds one targeted comparison read at completion, without a page reload or broad
cache invalidation. Source access is unchanged and no connector is needed.

Both product clients must cancel superseded reads, ignore obsolete callbacks,
clear failed read content, retain a visible error until successful retry, expose
actual retry progress, and clear transient resource state on session changes.
Saved history/text readers retain their pinned cursor/revision and explicit
restart controls. Do not change publication, provider routing or storage.

## Acceptance required before scoped DONE

- Deferred-response tests cover success, failure after success, repeated failure,
  retry, ignored aborts, navigation/unmount/session changes and current ownership.
- Native snapshot and comparison failures render no retained evidence or research
  controls; retry is accessible in all five locales and stays busy until settled.
- Late analysis/action/Ask responses cannot mutate another comparison/account or
  clear a comparison read error. Profile/runtime filtering still comes from the
  existing native read. Successful refresh preserves the workspace's task state.
- Both clients pass their existing test/lint/type gates and final Sites builds;
  native frontend gates/build and affected native API regression tests pass.
- English evidence, immediate main pushes, exact Sites artifacts/deployments,
  native immutable release proof and public HTTP checks are recorded separately.

No private production records, paid provider calls, new accounts/keys, browser
testing, screenshots, or human language/visual/professional acceptance are part
of this background cycle. Nine Monitoring directions, Apache-2.0, legacy Legal
aliases and all deferred tasks remain unchanged.

## Local acceptance — 28 September 2026

Native frontend gates pass 426 cases, catalogue/value audits and strict types.
Both clients pass 162 cases each, lint and strict types. All three production
builds pass. Native API regression passes 75 cases (6 smoke, 69 integration),
including new profile/runtime/locale recovery fixtures, durable cancellation and
retry, saved history, identity and the backlog invariant. Exact API Ruff passes.

The native read cache keeps ordinary stale-while-revalidate behavior. Comparison
and snapshot errors gate the entire evidence/research surface and offer a
five-locale retry. Read-owned job state, keyed view lifetimes and authority epochs
fence callbacks after navigation, account/workspace or locale changes. Analysis
queue/cancel/completion and review writes invalidate only affected resources;
the comparison reader chooses current or explicitly stale historical reports.
Completion notification requires a fresh, matching, non-stale successful report.
Ask failures hide retained history/jobs until their scoped read succeeds.

Both clients use one cancellable resource reader per URL/mount. Superseded
responses remain ignored even when a transport disregards AbortSignal. Session
changes clear contents immediately; failed refreshes clear content and retain
errors throughout retries. Saved-history/text controls use actual request state
and preserve revision/cursor selection. Eight deferred-request cases per client
and fourteen new native SSR/lifecycle cases verify these boundaries.

No database, API payload, provider setting or source permission changed. The
native completion flow intentionally trades one scoped re-read for authoritative
profile/runtime freshness. Server markup, synthetic fixtures and transport
contracts are verified; browser interaction and human acceptance are unclaimed.
Exact source/artifact hashes and production activation remain required below.
