# Monitoring Centre — MV2-017/018 scoped feature

Scope recorded 12 September 2026 before implementation. Deliver a complete
entry point at `/monitoring` on the main product: nine Personal/Business choices,
an owner-private paginated inventory of existing Pollen, River/Lake and Air
monitors, source health and exact links to their existing lifecycle editors.
Keep Topics and watched documents accessible without duplicating them.

Dependencies: use the existing C5/C6/C7 configuration, ownership, membership,
source-policy, freshness and lifecycle contracts. No new source integration or
permission is implied. C1/C2/C3/B2/B7/B8 remain unavailable with specific reasons;
C4 is absent. Transport source preflight remains unfinished local work.

Acceptance for this feature:

- Nine choices have honest availability and coverage; blocked choices cannot
  activate. Existing domain forms keep explicit preview/start and source gates.
- Inventory is bounded, paginated across all three domains, filterable by domain
  and lifecycle, including archived records. No owner/workspace leakage.
- Current, waiting, stale/partial, source unavailable, not approved and disabled
  are distinct from lifecycle state. Show last check and scheduled next check
  honestly; neither is labelled as a successful source observation.
- Exact monitor links reopen existing editors/history. No duplicate lifecycle
  store or alternative mutation route. Legacy links resolve to existing pages.
- Five languages, mobile/keyboard accessibility, reload/filter/error handling,
  membership revocation, runtime kill switches and pagination are verified.

The full MV2-017/018 parent tasks remain IN PROGRESS: shared business subjects,
commute-today timed pause and the other six domain journeys are not implemented.
Deployment identity and human acceptance are separate from code verification.

## Delivered behavior

The desktop and mobile Monitoring navigation now opens the centre. Saved
monitors come first, with a keyboard-accessible jump to the nine choices.
Thirty records load per page; the API caps pages at fifty. A stable cross-domain
keyset handles creation-time ties and concurrent insertions. Filters apply to
the complete inventory, not just the currently displayed page.

All reads require an active member and match both the owner and organization.
Responses are not cached. The component remounts on principal/workspace/role
changes, aborts obsolete reads, clears records on failed reads and refreshes on
return and every minute. A refresh restarts pagination to recheck access.
Disabled domains retain only owner-private configuration metadata with no
source values or activation link. Pollen shadow grants are labelled preview-only;
exact workspace revocation takes precedence over the public rollout grant.

Pollen uses its existing source-policy reader; River and Air recompute freshness
using their existing contracts. Forecast validity is never labelled as an
observation. Check attempts and scheduled checks are explicitly separate from
usable observation times; paused and archived monitors have no next check.
Pollen hash links and Air query links reuse the existing readers. River now
supports an exact monitor query link, including a record outside its first list
page. Thresholds and lifecycle commands remain in those original readers.

## Verification — 12 September 2026

- `ruff check services/api deploy/release_manager.py`: passed.
- `test_monitoring_centre.py`: **17 passed**. Real authenticated HTTP and SQLite
  tests cover nine choices, 65 tied records across three domains, concurrent
  insertion, filtering, same-workspace foreign owners, foreign workspaces,
  private cursors, revoked membership, viewer write denial, kill switches,
  freshness expiry, source-policy rechecks, shadow grants, anonymous denial and
  forecast/observation separation. No collection or activation is performed by
  the centre. Samples and accounts are synthetic.
- Required backlog integrity test: **1 passed**. Both index and detail retain
  IN PROGRESS for these broader parent tasks; customs deferral is preserved.
- Existing `test_air_watch.py`, `test_river_watch.py`,
  `test_monitoring_subject_api.py`, `test_monitoring_runtime.py`: **73 passed**.
  The existing Starlette/httpx deprecation warning remains; no test failed.
- Full `npm run build`: passed, including i18n, shell, resource, report, guide,
  TypeScript and production Next.js build checks.
- `node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON --experimental-strip-types
  scripts/check-monitoring-centre-browser.mjs`: passed against the finished
  production build and synthetic intercepted APIs. Covers pagination, filtering,
  empty state, exact River detail, access loss and retry, disabled choices,
  legacy destinations, keyboard focus and five locale/mobile viewer journeys.
  **8 complete-document axe checkpoints** had no violations or unresolved
  prohibited-ARIA findings. Desktop layout was visually inspected.
- Existing `scripts/check-river-browser.mjs`: complete preview/save/start/review/
  history/pause/edit/resume/archive journey passed, with **7** additional axe
  checkpoints, five languages and viewer coverage.

The browser checks do not modify production or establish live source coverage.
Other axe incomplete checks remain in the local JSON reports for human review;
these checks do not certify accessibility. Product interface copy is available
in five languages; the shared contextual page-guide system remains explicitly
English-only. Human language review and the broader pilot remain open.

## Release boundary

Implemented on main from `6940013d8e288bcc0350652e2e9064604fb986c2`.
Before publication the main site's `/api/ready` returned `ready`, instance main,
release `git-6940013d8e28`. Centre activation is pending automatic deployment;
the feature commit is the commit introducing this evidence document. Only
`helveticlens.ch` is active. No retired Monitoring deployment was restarted.
