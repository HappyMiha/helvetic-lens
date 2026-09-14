# Explicit workspace sharing of business monitors

Whole-feature scope, 14 September 2026 — MV2-004/018 and the monitor-level
responsibility contribution to MV2-013/021. Implement across continuations;
publish only after the complete API, native UI and private/shared regressions pass.

Tender, IP and Auction monitors start private. Their creator can explicitly move
one into workspace scope after reviewing the exposure of its profile and permitted
evidence/history. Workspace administrators then manage it and record native
decisions; viewers can read permitted evidence but cannot change shared decisions,
configuration or assignments. The six personal/environmental directions keep
their current private ownership. No bulk sharing, implicit migration or new
source permission is part of this operation.

Each shared monitor has an explicitly assigned responsible workspace administrator
or an unassigned state. Assignment changes retain an append-only actor/time history.
Deactivating or removing the responsible member preserves the monitor and unresolved
work; another administrator can reassign it. The original creator remains the
stable creation/idempotency identity. Changing responsibility does not transfer
personal email preferences or authorize messages to the new responsible person.
Physical account deletion and per-development assignment/comments are distinct
remaining parent requirements; do not claim them completed by this feature.

Scope transitions require the current monitor version, pause collection and revoke
old email consent/work without deleting its history. They never automatically
start/resume collection. Returning a monitor to private scope is limited to its
creator and removes colleagues' access on the next request, including old links.
Every mutation retains current membership, role, version and source-rights checks.

The same visibility predicate must reach native monitor lists/detail/configuration,
Today and Inbox queues/counts, notification links, shared inventory, decisions,
history, exports and reminders. Source-side restrictions remain independent:
authenticated SIMAP originals and their derived private evidence cannot gain team
access merely because their monitor is shared. Either an explicit reviewed source
audience allows the use, or that evidence remains unavailable to colleagues.
Email settings/preview and addresses remain accessible only to their original
private owner; the shared email centre must not list another person's email settings.

Acceptance before publication:

- Real additive migration preserves all private defaults/history and has a tested
  downgrade. No existing monitor becomes shared automatically.
- Owner opt-in, colleague admin/viewer access, outsider/other-workspace denial,
  stale versions, scope withdrawal and member deactivation/reassignment are tested
  for all three domains. Personal locations and other private monitors stay hidden.
- Responsible-member changes and scope history survive reload; collection uses a
  currently authorized responsible actor and stops honestly when none is available.
- Native source gates, old/new evidence, decisions/reopening, review queues/counts,
  exports, reminders and email revocation remain consistent under shared access.
- Five-language native UI exposes the scope, responsible member and exact effects
  of sharing, pausing, restoring private access and reassignment. Account/workspace/
  role changes and late responses cannot retain another private editor or grant.
- Run affected API/privacy/concurrency/migration checks (including PostgreSQL),
  exact API Ruff gate, root build, built-browser/axe journeys and backlog invariant.
  Record code publication separately from production activation/source/human gates.

## Completed code verification — 14 September 2026

The complete scoped feature is ready for publication. The three native sections
now expose Access and responsibility in all five product languages. Owners
explicitly confirm workspace sharing; colleagues can take responsibility, while
viewers only read. Access history and the administrator selector use bounded
pagination. The Monitoring Centre marks workspace profiles; its email page
explicitly requests personal-only inventory. Existing nine-direction navigation
and separate source readiness remain available.

Native collection, evidence, decisions, Today/Inbox/notification projections,
reminders and IP exports use the current audience. Collection can continue under
an active responsible colleague after the original creator is deactivated. Native
email settings, previews and durable email jobs remain owner-only. Scope or
responsibility changes pause active collection, append an off policy revision,
suppress pending email and cancel pending monitor work. No automatic resume,
source grant, external bid, export transmission or real email is performed.
Authenticated SIMAP files and document-derived versions remain unavailable to
colleagues; public tender originals retain their existing source checks.

Verification (synthetic accounts and source grants, no real mail):

- 25 repository/migration regressions passed in 19.29 seconds.
- 139 native API, repository, source-document, workflow, reminder and delivery
  checks passed in 228.62 seconds.
- 51 sharing HTTP, native Today/inventory and IP export checks passed in 109.57
  seconds. The HTTP matrix covers three domains, peer admins, viewers, other
  workspaces, explicit confirmation, CSRF, stale versions, pagination and withdrawal.
- After extending durable-job privacy, 48 affected API/collector/notification/
  Today/backlog checks passed in 61.11 seconds. Email-job detail and cancellation
  remain owner-only even when collection-job status is shared.
- Four additional real-source-fixture workflows passed in 8.13 seconds: collection
  with an inactive creator, responsible-account loss, retained unresolved work,
  native shared decisions, and peer IP export with current source revocation.
- PostgreSQL 17 scratch rehearsal passed additive upgrade/downgrade preservation,
  native metadata parity, competing CAS writes and actual observed lock waits
  followed by access withdrawal for all three domains. Only the explicitly named
  empty localhost test database was used; its container was removed after checks.
- Final explicit document-audience/delivery boundary and backlog invariant: 37
  checks passed in 44.41 seconds.
- Exact API Ruff gate and the complete root build passed. Build selector:
  `HELVETIC_LENS_CHECK_BUILD=business-sharing`.
- New built-browser suite: 69 full-document axe checkpoints for three domains,
  five locales and mobile/desktop, explicit confirmation, assignment, personal
  email exclusion, viewer access, history paging, conflicts, old links and
  pagehide/late-response handling. Existing Tender suite: 36 checkpoints;
  existing all-nine email-centre suite: 97 checkpoints, all passed.
- Four extra visual checkpoints and 390/1440 px screenshots were inspected.
  Unresolved axe manual checks remain in their JSON; this is not independent
  human accessibility or linguistic certification.

Reproduction: `npm run check:business-monitor:browser` against the matching
isolated build; `scripts/check_business_monitor_postgres.py --database-url ...`
accepts only an empty localhost `helvetic_business_scope_check` database. API
suites are `test_business_monitor_sharing.py`, `test_business_monitor_api.py` and
`test_business_monitor_native.py`, together with the affected native regressions.
Local logs are `.tmp/business-sharing-*.log`; browser evidence is retained under
`test-results/accessibility/business-monitor-access.json` and
`business-monitor-visual.json`. No source payloads or credentials enter Git.

MV2-004/013 remain IN PROGRESS: this is explicit business-monitor sharing and
monitor responsibility, not completion of physical account deletion,
per-development owner/comments or independent pilot acceptance. Exact production
activation remains unverified until the automatic main-site release records it.
No existing production monitor has been shared automatically.
