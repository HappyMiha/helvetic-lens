# Today review counts

## Implementation scope — 14 September 2026

MV2-019/014/021 contribution: one owner-private review summary for all nine
active Monitoring directions and the existing legal interest feed. C4 and grants
remain deferred. Cross-domain event grouping and shared business ownership remain
separate open requirements of the parent tasks.

Acceptance:

- Count eligible unreviewed Today cards through the existing domain readers,
  including continuation pages and sparse pages after permission filtering.
  Pollen/Air/River cards with an existing decision are not unread; Tender uses
  its pending latest-version queue; other directions retain their native
  current-version, source-rights, mute/pause and Today time-window rules.
- Legal counts use the existing personal unread interest feed. The summary is
  global to Today, independent of the legal-only period/page filters below it.
  Counts are review units, not a claim to deduplicate one real-world incident
  across independent source workflows. Auction deadline reminders are separate
  from unread material changes and must not be counted a second time.
- Use a consistent database read transaction, no collection, model call,
  mutation, notification or permission grant. Preserve tenant and membership
  checks and no-store responses. Only scalar counts leave the API.
- Never show a truncated page count as a total. Bound scanning; if a complete
  count cannot be computed, return an explicit unavailable result and no global
  numeric total. A zero describes readable saved cards, never source coverage,
  safety or absence of real-world changes.
- Show all ten queues with five-language labels, section links, loading/error/
  incomplete states and an accessible refresh action. Clear private results on
  identity changes; review actions invalidate the summary.
- Verify native domain parity, multiple/sparse pages, review/reopen, rights,
  ownership and membership, bounded scans and no side effects. Run affected API
  tests, exact API lint, root web checks and built-browser journeys before
  committing and pushing this complete feature.

## Delivered behavior

`GET /api/monitoring-centre/today-counts` returns ten scalar queue results and a
global total only when every queue was completely evaluated. Air cards and counts
share an extracted reader; the other directions retain their native readers.
River and Tender reuse their existing permission/owner-aware SQL totals. Other
queues follow up to 20 bounded native pages, including empty continuation pages.
A shared 15-second budget is checked between pages/queues; this is not a hard
request timeout and does not interrupt a native page already executing. Exhaustion
or an unavailable section yields a null count and suppresses the numeric total.
This endpoint is limited to 12 requests per authenticated rate-limit scope/minute.

The request opens a PostgreSQL repeatable-read, read-only transaction or an
explicit SQLite read transaction. Current membership, review and stored rights
are evaluated within that database snapshot. External boundary-file selection is
still rechecked by the native Hazard reader; no frozen external-source snapshot
is claimed. Results are not cached and include their evaluation time. Monitoring
Centre denial/error responses now also receive no-store headers.

Today displays all ten section links even when counts fail. Successful native
review/configuration changes emit a payload-free invalidation signal; the mounted
private summary clears its old result and refreshes. Account/workspace/role
changes and page hiding discard the private component and abort old requests.
Legal-only period and reading filters do not alter this global summary.

## Verification

- The affected API suite passed 57 tests, covering native queues in all nine
  directions, legal personal read state/topic validity, 52 Air and 53 River review
  units beyond the first page, current heads, review/reopen, owner/workspace/
  membership isolation, source revocation and geometry unavailability.
- Sparse-page continuation, repeated cursors and exhausted budgets return no
  invented total. Native count projections issued only SELECT statements and
  left ORM new/dirty/deleted sets empty. No model, collection or real mail was used.
- Root isolated production build and exact API Ruff gate passed. Browser evidence
  contains 22 full-document axe checkpoints across five locales: populated,
  incomplete, empty and failed results, actual River review refreshing 55 to 54,
  keyboard refresh and stale private-response suppression on account/page return.
  Desktop/mobile screenshots were inspected. Synthetic API/source evidence does
  not certify live data or human translation/accessibility acceptance.
- A final 14-test contract/backlog run passed in 24.14 seconds. An independent
  SQLite WAL writer committed a new River change while the preceding Air count
  was being evaluated: the first request retained its original total, and the
  following request included the change. This tests database snapshot behavior;
  the PostgreSQL production transaction still requires live release verification.

Source readiness, exact production activation, independent human acceptance and
large-workspace capacity remain separate requirements. Wider cross-domain card
grouping and shared business ownership remain open. No production release or
parent-task completion is claimed by these code checks.
