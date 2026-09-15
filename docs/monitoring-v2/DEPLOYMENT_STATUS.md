# Monitoring deployment status — 15 September 2026

## Verified query-budget repair and settings activation — 15 September 2026

The authenticated main-site journal confirms **Succeeded** for requested and
verified activated commit `e0af3fc848b6bcfc2f17413856e01d53eb0c97e3` on
HappySnowman production. Run `66c4f009-fdb7-4779-a1af-d5f0c2a2dcae` started at
08:06:02 and finished at 10:02:35 Europe/Zurich. The complete API test gate passed
in **113m 26s**, following successful API lint. Image build, writer quiescence,
backup `20260915T080033Z`, release start, restoration of `apertus-8b-q4km`, public
health verification and release publication all succeeded.

This release includes `769795b525f11f90d4c67795164d671256cbb46a`, repairing the
Inbox/matrix failures in the owner's supplied deployment log, and the earlier
bounded-history query repair. Its pinned release notes also include the
nine-category settings and encrypted connector access, configuration drafts and
downloads, selected evidence downloads, private account erasure and handover,
source attention/history, Tender XLSX, recurring Road closures and independent
business evaluation tooling. Activation does not establish live source rights,
human acceptance or the separate capacity/inference/recovery gates.

The same fresh journal shows `336a9db47ed3` Deploying, started at 10:04:02. That
subsequent candidate includes worker isolation and handoff fairness; neither is
claimed activated here. No active deployment, check or serving checkout was
restarted or modified. The unfinished synthetic capacity workload remains local
development and is not part of this verified release.

## Queue handoff verification — 15 September 2026

The authenticated main-site journal, refreshed during handoff-fairness checks,
still shows candidate `e0af3fc848b6` Deploying, started at 08:06:02 Europe/Zurich,
and production `d961ebd54998c124458b7185f0258c9d9197dd0f`. The 06:12:02 retry of
`60d87fcdb481` is Failed. Candidate e0af3fc contains the Inbox/matrix query-budget
repair below; the newer worker isolation and queue-handoff changes are subsequent
code. No successful activation of those changes has been recorded. No running
deployment, test process or serving checkout was restarted or modified.

## Inbox and matrix query-budget repair — 15 September 2026

The owner's latest deployment excerpt identifies `api_tests` failures in
`test_context_queries_do_not_grow_between_one_and_fifty_event_pages` (17/17
queries against the old 16-query ceiling) and
`test_matrix_large_history_loads_only_selected_comparison_and_result` (10 against
9). A subsequent authenticated journal read matched this exact excerpt to run
`ca332a6a-0cba-4d3a-8866-0f42fe7a1751`, candidate `60d87fcdb481`, started at
04:06:02 and failed at 05:56:47 Europe/Zurich on 15 September. Both assertions
reproduced on main.
The adjacent 51-document matrix boundary also reproduced (14 against 13).

Each failure was the same fixed connector-configuration read introduced by the
monitoring settings workflow. HTTP requests now load four configuration tables,
once each. The query-budget helper explicitly requires exactly those four reads
and rejects repeated, missing or combined/subquery configuration reads. Remaining
page queries keep their original limits: 13 for Inbox, independent of a one- or
fifty-event page; six for one matrix batch; ten for 51 matrix documents; four for
each paginated document-history page. No page budget, runtime query, cache,
timeout or release gate was relaxed or disabled.

The full Inbox-context, matrix-selection and document-history suites passed:
**31 passed in 111.31 seconds**, `.tmp/request-query-fixed.log`. The preceding
reproduction run failed all three stale assertions as expected,
`.tmp/request-query-reproduce.log`. Checks retain no heavy archive hydration,
current selected-report eligibility, tenant boundaries, full tied-date history
ordering, unchanged model calls and no source fetches. A repository scan of other
fixed SQL budgets confirmed that the remaining discovered checks operate on
internal readers, outside HTTP setup; their limits are unchanged.

Exact API lint passed. This is a complete repair of the identified release-gate
regressions, not proof of full-suite success or activation. No active deployment
was interrupted or restarted, and no serving checkout or production data changed.
The same journal shows a new attempt for `60d87fcdb481` started at 06:12:02 and
still Deploying. It does not include this subsequent repair. Verified production
remains `d961ebd54998`; the older `6f8b91244a95` attempt is now Failed.

## Fresh main-site observation — 15 September 2026

A newly loaded authenticated journal shows 7fd0c80a2686 Failed and
6f8b91244a95 Deploying, started at 02:14:02 Europe/Zurich. Verified production
still remains d961ebd54998. This is a newer observation than the earlier entry
below. The new business evaluation workflow is a subsequent candidate; no active
release check was duplicated, interrupted or restarted. The collapsed journal
does not establish the failed candidate's gate/error, and the current candidate
is not yet a verified activation.

Earlier observation:

A newly loaded authenticated journal shows 6f1361883b55 Failed and
7fd0c80a2686 Deploying, started at 00:24:02 Europe/Zurich. Verified production
remains d961ebd54998. The new candidate includes d00e3f5, the tested history-query
and diagnostic-lock repair described below, and selected evidence downloads.
Neither is yet verified activated. The source-attention feature is a subsequent
complete candidate; no active deployment has been interrupted or duplicated.


## Connector request setup and diagnostic lock gate repair — 14 September 2026

A fresh authenticated main-site journal read shows `82eefcfd4119` Failed and
`6f1361883b55` Deploying, started at 22:34:02 Europe/Zurich. Verified production
remains `d961ebd54998`. The user's new API failure excerpt concerns document
history query counts and a whole-reader stopwatch assertion, not the earlier
Aste child-record migration failure. No active release gate was restarted.

All three history-page variants reproduced the stale query-count assertion
locally. The connector settings feature adds one bounded configuration query to
HTTP request setup. The test now requires exactly one read of each of the four
configuration tables and retains the separate four-query history budget, full
equal-time traversal, no historical body hydration and no source/model calls.
The history implementation and pagination limits are unchanged.

The diagnostic lock test measures the actual database protection at each INSERT:
250 ms lock timeout, plus 500 ms PostgreSQL statement timeout. It requires the
real lock-conflict error while the other transaction remains active, one attempt
per diagnostic writer, the unchanged saved answer, restored pooled connection
settings and later successful telemetry. This replaces the whole-reader two-second
stopwatch, which also measured unrelated runtime validation and host scheduling.
It does not increase any database timeout or remove a release test.

Local history/metadata/diagnostic checks passed: **29 passed, 1 PostgreSQL-only
skip**. The combined run also passed 29 checks for the separate, unpublished
evidence-download work. The exact API Ruff gate and backlog integrity check passed.
All **five affected PostgreSQL cases passed** in an isolated disposable PostgreSQL
16 container: both held-lock cases and all three history-page variants. Publication
of this tested repair remains distinct from its production activation.

## Verified Aste repair activation — 14 September 2026

A fresh authenticated main-site journal read confirms **Succeeded** for requested
and verified activated commit `d961ebd54998c124458b7185f0258c9d9197dd0f` on
HappySnowman production. The run started at 19:10:03 and finished at 20:51:57
Europe/Zurich. API lint and the complete API test gate passed (API tests took
98m 28s), followed by image build, backup `20260914T184956Z`, release start,
model-runtime restoration, public health verification and release publication.

This release includes SQLite retained-child repair `9a0a9e6`, native evidence
search and batch review. The Aste failure reported for `f07b164` and subsequently
`9e631d9` is superseded by this verified activation; no test was disabled.

The next immutable candidate `82eefcfd411929970442c42e63d77f31fb426472` started at
20:52:03 and is recorded as Deploying. It includes nine-category settings,
encrypted connector controls, configuration drafts and owned settings download.
Those newer features are not yet verified activated. No active deployment was
restarted, interrupted or duplicated. Earlier observations below remain history.

## Owned settings download candidate — 14 September 2026

All nine categories now offer owned current-configuration JSON downloads in
`/monitoring/settings`, with revision numbers, saved email preferences, scoped
pagination, payload integrity and final ownership/content verification. See
[workflow and checks](MONITORING_CONFIGURATION_EXPORT.md). Publication of this
feature does not establish live source coverage or a verified production release.
The preceding natural-language draft feature was pushed as
`5a51903df8d5de1ada2abb4d245ff8ea67910057`. The active automatic deployment has not
been restarted or duplicated; its exact activated commit is tracked separately.
A fresh authenticated journal refresh still reports `c66e77fc7721` as production
and `d961ebd54998` as Deploying. This settings-export candidate is not verified
activated; the d961 candidate includes the earlier Aste migration repair.

## Native configuration draft candidate — 14 September 2026

All nine native editors now expose explicit natural-language configuration drafts
with manual fallback and separately reviewed model capability. Loading a proposal
does not save or activate a monitor. See [scope and local checks](MONITORING_CONFIGURATION_DRAFTS.md).
The preceding settings feature was pushed as `96bede19d244204d6f3126087fafda2d38a321b4`.

A fresh authenticated main-site journal read still reports production
`c66e77fc7721fbbd4ff11a522d4cc7183cc81523` and `d961ebd54998` Deploying, started
14 September at 19:10:03 Europe/Zurich. This candidate includes Aste migration
repair `9a0a9e6`; the recorded Aste failures concern older immutable candidates.
Neither the settings feature nor this draft feature is verified activated.
No active deployment or quality gate was restarted or duplicated.

## Nine-category settings candidate — 14 September 2026

`/monitoring/settings` brings native editors and appropriate source credential
controls into nine categories. Encrypted, revisioned platform settings are adopted
by new requests and scheduled collectors; explicit bounded access checks do not
grant rights or coverage. See [implementation and checks](MONITORING_SETTINGS.md).
This feature is a main-branch candidate, not a verified production activation.

Fresh authenticated main-site inspection confirmed `d961ebd54998` deploying,
started **14 September 2026, 19:10:03 Europe/Zurich**. Production remains
`c66e77fc7721fbbd4ff11a522d4cc7183cc81523`. The preceding `9e631d93c13c` failed
at **19:09:27**, with the same Aste preservation test (1 failed, 4466 passed,
14 skipped); it predates repair `9a0a9e6`. The running d961 candidate includes
that repair. No running check or deployment was interrupted or restarted.

## Nine-direction native batch review candidate — 14 September 2026

The notification queues now offer explicit selection, evidence preview and atomic
native decisions for up to twenty records. Changed versions or access reject the
whole batch; business actions have no default bid decision and send no external
submission. [The acceptance record](MONITORING_BATCH_REVIEW.md) includes 34 API
checks, PostgreSQL concurrent opposite-order batches, the root build, exact Ruff
gate and 186 compiled-browser/axe checkpoints in five locales and two widths.

The SQLite repair `9a0a9e6` and native evidence search `60776ad` are already pushed
to origin/main. The owner's repeated Aste failure log identifies the earlier
`f07b164` attempt, which predates that repair. No newer activation is claimed from
that historical failure. This batch feature remains a candidate until its own
exact main-site release is verified; the active automatic deployment is not
interrupted or duplicated. Source rights and human acceptance remain separate.

## Native evidence-search feature candidate — 14 September 2026

All nine native Monitoring readers now offer bounded word matching in selected
saved evidence, exact literal extracts with available units, and authenticated
references bound to the same record. The interface is available in five locales
under the existing enabled sections. It performs no model calls, collection,
monitor changes or email delivery. See [scope and verification](MONITORING_EVIDENCE_ASK.md).

Local acceptance includes 25 feature API checks after the migration repair,
26 citation/backlog checks, a further seven elapsed-request/backlog checks, the
root build, exact API Ruff gate and 81 built-browser accessibility/workflow
checkpoints. Generative conclusions, natural-language drafts, independent human
review and source/live acceptance remain open; MV2-023 remains IN PROGRESS.

The prerequisite SQLite repair was pushed to origin/main as `9a0a9e6`.
At the latest authenticated journal observation, production is still `c66e77f`
and the older `9e631d9` candidate is Deploying. This newer feature is a tested
release candidate, not a verified production activation. Normal automatic
deployment remains responsible for the complete release gates.

## SQLite retained-child migration repair — 14 September 2026

The authenticated main-site journal records `f07b1641a351` as Failed, finished
at 17:31:50 Europe/Zurich. Its API gate reported **1 failed, 4441 passed,
14 skipped** in 5455.62 seconds. The failing assertion was
`test_aste_collection.py::test_native_migration_preserves_private_decisions`.
Production remains `c66e77fc7721fbbd4ff11a522d4cc7183cc81523`; the next immutable
candidate `9e631d93c13c` started at 17:32:02 and is Deploying. No active check or
deployment was interrupted, restarted or duplicated. These observations supersede
the earlier in-progress entry for `f07b164` below.

The failure reproduced locally: SQLite's parent-table replacement during the
business-scope downgrade fired `ON DELETE CASCADE` into retained native auction
decisions. The repair wraps online SQLite migrations on enforced connections in
an owned schema savepoint with foreign keys temporarily off, verifies all foreign
keys before success, rolls failed schema work back, and restores enforcement.
Pending caller writes are refused without commit or rollback. A populated Commute
migration fixture now persists its old-version draft before upgrading, matching
the real upgrade boundary. Existing migration definitions and the PostgreSQL
migration path are unchanged; no test assertion or release gate was removed.

Local verification: the original failing migration plus lifecycle/guard checks
passed (8 tests); the expanded actual upgrade/downgrade and lifecycle matrix
passed **48 tests in 177.94 seconds**. Four guard cases exercise retained children,
schema/data rollback, orphan rejection and preservation of pending caller writes.
The nine-direction evidence feature passed its 25 checks on the repaired migration
path. The exact API Ruff gate passed. This is a tested repair candidate; publication
does not establish successful activation of this newer code.

## Individual business responsibility and decision notes candidate — 14 September 2026

The complete Tender/IP/Auction item-work feature adds individual assignment,
plain-text comments, atomic native decision/owner/comment writes, paginated
evidence-bound audit and native assignment filters. See
[scope and verification](BUSINESS_ITEM_WORK.md). Existing monitors remain in
their current private/shared scope; no source permission or personal email
consent is inferred. No new runtime flag hides this feature.

Published to origin/main as `026ec818ada898152197dcb2cc4b77baa463d984` after its
local API, PostgreSQL race and browser checks. The fresh authenticated production
journal confirms `c66e77fc7721fbbd4ff11a522d4cc7183cc81523` as both production and
verified activation. That automatic release succeeded at **15:59:46 Europe/Zurich**
on 14 September, including its full API gate (**88 minutes 26 seconds**), build,
backup, startup, model-runtime restoration, public health and publication checks.

The next automatic candidate `f07b1641a351deddb5b7a73e47f52e99ec2fa4f3` started
at 16:00:05 and is still Deploying. The newer item-work commit `026ec81` is pushed
but not verified activated. No running checks or deployment were restarted or
duplicated. Broader MV2-013/MV2-021 and human/source acceptance remain open.

## Business workspace sharing candidate — 14 September 2026

The complete three-domain sharing/responsibility feature and its native privacy,
PostgreSQL, browser and regression evidence are recorded in
[Business monitor sharing](BUSINESS_MONITOR_SHARING.md). This is a main-branch
release candidate; a push does not establish production activation. All existing
monitors remain private unless their creator explicitly shares them.

The fresh authenticated deployment-page Refresh still reports `660edacc8e7a`
as production/verified activation and the automatic `c66e77fc7721` attempt as
Deploying. No active release checks were restarted or duplicated. Source grants,
personal email consent and independent human acceptance remain separate.

## Verified automatic activation and email-centre candidate — 14 September 2026

Authenticated Refresh on the main site's deployment page now records
`660edacc8e7afa5306b50fc97999bbc1616fd5f0` as both production and the verified
activated commit. The automatic run succeeded at **14:27:46 Europe/Zurich**;
its API test gate passed in **85 minutes 30 seconds**, followed by image build,
backup, start, public health and publication checks. This release includes the
Tender dispatcher-clock repair `4434cf9` and Trademark permission-fixture repair
`eed7fde`; the earlier failures are historical, not the current release result.

The next automatic run for `c66e77fc7721fbbd4ff11a522d4cc7183cc81523` started at
14:28:02 and still reports Deploying. No active run was restarted or duplicated.
The new shared email-preference feature is described in
[its acceptance evidence](MONITORING_EMAIL_CENTRE.md); publication and activation
of that newer feature remain distinct. Source rights and real-user acceptance
are not implied by successful deployment checks.

## Nine-direction first-run candidate — 14 September 2026

The post-registration guide now saves a personal Monitoring starting choice and
opens any of the nine native setup screens, with later continuation, optional
company guidance and explicit source/Start/email boundaries. Local acceptance:
31 API checks, an isolated PostgreSQL 17 migration/concurrency rehearsal, root
build, 35 new browser/axe checkpoints and 40 legal onboarding regressions passed.
See [implementation and limits](MONITORING_FIRST_RUN.md).

Authenticated Refresh still shows production `1188f18190e0` and `660edacc8e7a`
Deploying. The previous notification-centre feature was pushed as
`d21d0d96aa7db2a831986446ff1d79d4eb43b48c`; its activation and this newer feature's
activation are not verified. The running deployment was not restarted or
duplicated. Source and real-user acceptance remain independent gates.

## All-direction notification centre candidate — 14 September 2026

The header centre now exposes nine private native Monitoring review queues plus
legal notifications, with exact retained Pollen evidence links. Local acceptance
passed: 48 affected API checks, 13 final HTTP/backlog checks, the exact API lint
gate, root isolated build, 65 new browser/axe checkpoints, 80 legal regression
checkpoints and 22 Today checkpoints. See
[implementation and limits](MONITORING_NOTIFICATION_CENTRE.md).

A fresh authenticated Refresh during final acceptance still showed production
`1188f18190e0` and automatic candidate `660edacc8e7a` Deploying. It includes the
already-pushed Tender clock repair `4434cf9` and Trademark fixture repair
`eed7fde`. No production run was interrupted or retried. The new notification
feature is not yet verified activated; source access and human acceptance remain
independent. The retired Monitoring deployment was not touched.

## Shared Today review counts publication candidate — 14 September 2026

All nine Monitoring directions and the legal feed now contribute to a private
Today review-count overview, with native source/review eligibility, complete
pagination, null totals for incomplete scans, five-language section links and
automatic refresh after successful review actions. The affected API suite passed
57 checks; the final contract/snapshot/backlog run passed 14 checks. The root
isolated build and 22 built-browser/axe checkpoints passed. See
[scope, evidence and limits](TODAY_COUNTS.md).

The feature was pushed as `dcfbb1fb86337565541e43392f35193b6851cfe2` to main.
Authenticated Refresh then confirmed production still at `1188f18190e0` and a
new automatic attempt for `660edacc8e7a`, started at 13:00:03 local, Deploying.
The preceding `4434cf94da05` attempt finished Failed at 12:58:59: 4,293 passed,
14 skipped and one Trademark export fixture failure after 4,932.50 seconds.
The Tender dispatcher regression is absent from that failure summary. The sole
remaining reported failure is already repaired by `eed7fde`, which is included
in the running `660edac` candidate. No duplicate fix or deployment retry was made.

These records do not verify activation of `660edac` or the newer Today counts.
No active deployment/test run was interrupted or duplicated. The retired
Monitoring deployment was not touched; source access, real-user acceptance and
larger workspace capacity remain independent gates.

## Monitoring companion guidance publication candidate — 14 September 2026

Marvin now identifies all nine Monitoring sections and their centre, with a
shared five-language screen guide, direct centre navigation and an offline help
action. Exact route-only conversations do not read private records or start
monitoring. See [scope and checks](MARVIN_MONITORING_GUIDANCE.md).
The final 44 affected API/backlog checks, root build and 55 built-browser/axe
checkpoints passed; prior private history/context checks passed as well.

After authenticated Refresh, production still reports `1188f18190e0` and
`4434cf94da05` remains Deploying. No active test/deployment was restarted or
duplicated. The current candidate and newer source features are not yet verified
activated. All nine sections stay enabled and visible; C4/grants remain deferred.

## Trademark export fixture diagnosis — 14 September 2026

Native Hazard commit `2799a7a579a172f24efcb65a630c7996c7f4a2f1` was pushed to
origin/main; the checkout is synchronized. A fresh authenticated release read
found `11ef1765d8f3` failed at 11:34:21 local after 4,271 passed and two failures:
the known Tender clock test and the Trademark export permission test.
The automatic attempt for `4434cf94da05` started at 11:36:02 and is Deploying.
It contains the Tender fix; it has not been restarted or duplicated.

The Trademark failure was reproduced locally. The fixture created two active
source channels, one permitted for matching/display only and one permitted for
export. Both produce candidates in the second portfolio; choosing `items[0]`
made the test depend on random UUID ordering and could select the denied source.
The repair binds the candidate to its actual stored permission, exercises both
source orders, confirms denied-source export remains forbidden, then revokes
the allowed permission and checks that both preview and download are rejected.
Production export permissions and runtime behavior are unchanged.

Validation: all 28 affected Trademark export, workflow and API tests passed
in 50.63 seconds. The exact API Ruff gate and diff whitespace check passed.
This repair is a publication candidate; production activation is not yet verified.

## Native Swiss wind/thunderstorm publication candidate — 14 September 2026

The complete native Hazard source-to-private-workflow feature passed 360 affected
API/source-operation tests, 34 final guards, the root build and 60 browser checks.
The normal enabled collector initializes the reviewed public channel and pinned
geography only for a fresh configuration; explicit permissions and existing or
revoked source/catalogue decisions are preserved. A real empty Swiss feed poll
and native Basel readiness were verified in an isolated local database.
See [scope and evidence](HAZARD_WATCH.md#native-source-activation-and-complete-vertical-workflow-14-september-2026).

This candidate includes the already-pushed Tender dispatcher clock fix `4434cf9`.
Exact production activation is not yet verified. The last inspected active
attempt was `11ef1765d8f3`; no active check/deployment was duplicated or restarted.
The retired Monitoring deployment was not touched. Broader C1 hazard coverage
and real-warning/human acceptance remain open.

## Diagnosed release-test failure and confirmed navigation — 14 September 2026

After reloading the authenticated main-site Deployments page, all nine
Monitoring links are visible, including warnings, commute, roads, tenders, IP
and auctions. The current active release remains `99da831d934a`.
Attempt `ec4874618b1e` failed at `api_tests` after 75m 13s:
3,968 passed, 14 skipped, one failure in
`test_new_date_and_trip_ids_recheck_source_rules_and_keep_old_proof[arrival-insufficient_time]`.
The following attempt `79c7a0abf02b` is already deploying; it has not been
interrupted or duplicated. Auction acquisition `ce8f954` was pushed to main.

The recorded failure was reproduced locally as clock-dependent synthetic ZIP
metadata causing a new archive hash on an unchanged replay. The fixture fix
passed all 141 affected static/renewal/collector checks and retains the real
source-conflict guard. See [regression evidence](TRANSPORT_WATCH.md).
Production activation of the fix and newer features remains unverified.

## Native auction collection publication candidate — 14 September 2026

The main-site ready endpoint still reports `git-99da831d934a`, instance `main`,
database/Redis healthy. The complete native Auction acquisition→private review/
reminder feature and five-language source-status panel passed affected server,
root build and browser checks; see [acceptance evidence](AUCTION_WATCH.md#native-collection-and-visible-source-status--14-september-2026).
Activation is not yet verified. All nine sections and implemented native source
switches remain enabled; actual access approvals and coverage remain independent.
No deployment was restarted, duplicated or interrupted; the retired Monitoring
host was not touched.

## Trademark deadline publication candidate — 14 September 2026

The public main-site ready endpoint was last verified at `git-99da831d934a`,
instance `main`, database/Redis true, after native acquisition publication
`fe5978d`. This confirms Auction reminders and consented email activation.
Later Trademark review/export/acquisition activation is not yet confirmed.
The [complete deadline feature](TRADEMARK_WATCH.md#reviewed-deadline-feature--14-september-2026)
passes private workflow/export, five-language browser and isolated build gates.
All nine sections remain enabled and visible; approved rules/calendars and source
access remain independent. No deployment was restarted, duplicated or interrupted,
and the retired Monitoring host was not touched.

## Native IPI acquisition publication candidate — 14 September 2026

The public main-site `/api/ready` still reports `git-3b48a00c92d6`, instance
`main`, database/Redis true. Native IPI acquisition now passes its private
candidate/review integration, source-status browser journey and root build;
see [native acquisition evidence](TRADEMARK_WATCH.md#native-acquisition-implementation-and-verification).
Its activation is not yet verified. All nine sections and implemented production
collector switches remain enabled. Actual IPI credentials, source approval,
catalogue capacity/coverage and human acceptance remain separate. No deployment
was restarted or duplicated and the retired Monitoring host was not touched.

## Auction tracking and Inbox activated; counsel export follow-up — 14 September 2026

The public main-site `/api/ready` reports `git-3b48a00c92d6`, instance `main`,
status ready and database/Redis true. This verifies activation of private Auction
tracking, the Centre configuration copy and Auction Today/Inbox. Later Auction
reminders/email and Trademark review commits are published; activation remains
unverified. The new explicit Trademark counsel-packet export passed 54 combined
server tests, one focused prior-permission check and 42 browser checkpoints;
its activation is likewise unverified. All nine sections remain enabled and
visible. Source access, approved legal deadline rules and human acceptance remain
separate. No deployment was restarted or duplicated and the retired host was
not touched. See [counsel packet evidence](TRADEMARK_WATCH.md#counsel-packet-feature--14-september-2026).

## Trademark private review follow-up — 14 September 2026

The main-site `/api/ready` still reports `git-f8a4304e658a`, instance `main`,
status ready and database/Redis true. The complete private Trademark candidate,
review, register-change and Today/Inbox feature passed 103 combined server tests,
two focused follow-up checks and 32 browser checkpoints. Its activation is not
verified. No deployment was restarted or duplicated; the retired Monitoring host
was not touched. All nine sections remain enabled and visible; real source access
and acceptance stay separate. See [the feature evidence](TRADEMARK_WATCH.md#private-register-review-journey--14-september-2026).

## All-nine navigation activated — 14 September 2026

A fresh public main-site `/api/ready` reports `git-f8a4304e658a`, instance
`main`, status ready and database/Redis true. This verifies activation of the
all-nine desktop/mobile navigation commit and the ninth Auction profile section.
The later private Auction tracking, Centre readiness copy and Today/Inbox commits
are published on main; their activation is not yet verified. The reminders/email
follow-up passed 122 server checks, 14 browser checkpoints and the root build;
its activation is not yet verified. No deployment, controller or
check process was restarted or duplicated. Source credentials, reviewed rights,
current observations and user email consent remain separate from section access.

## Integrated directions activated — 14 September 2026

The public main-site `/api/ready` now reports `git-4859c58a8b25`, instance `main`,
status ready and database/Redis true. This verifies activation of the integrated
directions commit. The subsequent Auction profile (`395458d`) and all-nine direct
navigation (`f8a4304`) commits are published on main; their activation is not yet
verified. The private Auction tracking follow-up has passed its local checks;
see [scope and evidence](AUCTION_WATCH.md#private-source-backed-tracking--14-september-2026).
No deployment was restarted or duplicated. Source credentials, rights, current
observations and human acceptance remain separate from code activation.

## Nine-section visibility checkpoint — 13 September 2026

Both `4859c58a8b255b40e30a6c2ae00d363e72f0d9dc` (integrated directions) and
`395458d350591371e3ce767ac06551e48ca0cf22` (ninth Auction section) are published
on origin/main. The authenticated main-site deployment page was inspected:
automation reports **deploying 4859c58a8b25**, started at 20:46:02 UTC, while
production still reports **80825246c7d5**. This proves automatic pickup, not
activation of either new commit. No deployment was restarted or duplicated.

The follow-up navigation feature makes all nine sections directly visible in
desktop and mobile menus, in addition to the Centre. All implemented production
feature/collector defaults remain enabled. Current source access, rights and
freshness are separate checks inside each section; missing inputs do not become
invented live coverage. See [navigation evidence](MONITORING_CENTRE.md#all-nine-sections-in-navigation--13-september-2026).

## Integrated publication candidate — 13 September 2026

**Published:** integrated main commit `4859c58a8b255b40e30a6c2ae00d363e72f0d9dc`
was successfully pushed to origin/main. The subsequent public readiness check
still reported `git-80825246c7d5`, with database/Redis true. Publication is proved;
activation of the integrated commit is not yet verified. The next Auction profile
release makes the ninth Centre section navigable; its live source remains
unconfigured. No controller/check process was restarted or duplicated.

The owner's latest instruction authorizes publishing all implemented monitoring
directions now and continuing development afterward. All implemented feature and
collector switches default to enabled in production Compose. Missing credentials,
permissions and source evidence remain visible readiness constraints; no access
or successful collection is fabricated. See the [exact scope and verification](evidence/2026-09-13-integrated-publication.md).
Activation remains unverified. Earlier disabled defaults and uncommitted-state
statements below are historical.

## Current checkpoint — 12 September, 19:45 UTC

The active main site's `/api/ready` reports `ready`, database/Redis checks true,
instance `main`, and **git-0772edd2c381**, matching pushed main commit
`0772edd2c3813bce7e98ff6365b2c08a139f3385` (private Monitoring centre and scenario
chooser). Code activation is verified; authenticated user journeys and human
acceptance remain separate. Only `helveticlens.ch` on HappySnowman is active;
the retired Monitoring deployment was neither contacted nor restarted.

Tender Watch remains uncommitted local development. Its isolated source rehearsal
and local tests do not imply deployment, source enablement or completed B2
acceptance. Both new tender/public-source switches default to false and no
production configuration was changed.

## Prior main-only checkpoint — 12 September, 16:21 UTC

The user's latest instruction retires the separate `monitoring.helveticlens.ch`
site. **Only `helveticlens.ch` on HappySnowman remains an active deployment target**,
including Monitoring features. Do not recreate or restart the retired HappyDucky02
Windows task, Docker project `helvetic-lens-v2`, tunnel, hostname or deployment.
Do not resume historical retry/controller instructions below. Retained data,
credentials, consent and source approvals must be preserved.

The main site's `/api/ready` reports `ready`, instance `main`, release
**git-113e914e39d6**, matching pushed Air Quality feature
`113e914e39d636646b515ac781a3a1ce40812521`. This confirms code activation;
authenticated feature/source and human acceptance remain separate. This check
made no operational changes and did not audit or alter the retired host's shutdown.

The retired site's previous Air attempt failed on one SQLite test-fixture startup
error after 2380 passes. Targeted Windows (47) and Linux (12) checks passed;
the underlying cause remains unresolved. It is historical
diagnostic evidence, not a reason to restart the retired deployment.

## Historical two-site checkpoint — 12 September, 13:49 UTC

Both public readiness endpoints independently confirm River / Lake release
**87c563db935bec92e809eb4c3d8d9f8f13c292c2**: Monitoring exposes its full SHA and
main exposes `git-87c563db935b`. Monitoring's ordinary deployment
`f03d9108-fa1e-4213-be3d-908fdf43ac19` completed at **13:42:57 UTC**. The complete
API gate passed, followed by image builds, writer quiescence, a pre-release backup,
activation and public health verification. The previous outage notes are historical.

The main-only operational cutover is complete. The active selector is
`monitoring-instance.main.json`, with branch `main` and every other isolated
instance field preserved. The reviewed pinned controller is `87c563d`; installation
passed ValidateOnly and used the existing deployment lock. The old selector and
controller backup remain rollback evidence. Both sites share code while their
Compose projects, databases, credentials, approvals and private data stay separate.
No manual or duplicate deployment was started.

The next complete Air Quality Basel feature has passed local implementation checks
and is being prepared for a single main commit. Its exact activation is **pending**;
do not confuse River's published identity with the Air feature. See
[Air Quality Watch](AIR_QUALITY_WATCH.md) and [River / Lake Watch](RIVER_LAKE_WATCH.md).
MV2-032/033 retain VERIFYING for applicable post-release acceptance; no completed
human pilot or whole-v2 acceptance is claimed.

## Historical outage checkpoint

**OUTAGE: complete Pollen candidate `0ec41a9` passed its full API gate and builds, but failed decoder health and then database rollback. Public readiness returns Cloudflare 1033; the stored previous SHA does not establish a currently serving site. MV2-072 remains IN PROGRESS and MV2-073 remains VERIFYING.**

## Recovery checkpoint — 12 September

The 00:10 UTC attempt passed **2328 API tests, 12 skipped**, then failed
`start_release` at 01:36 UTC. Docker health exec could not find `python`; the
micromamba entrypoint's PATH does not apply to Docker health probes. Restore of
pre-release snapshot `20260912T013436Z` then failed because the newer delivery FK
depends on the old users primary key. Application services were already stopped.
An automatic retry started at 01:52 UTC and was still in its API gate when the
incident was inspected. It has not been restarted or duplicated by this task.

The dedicated recovery feature corrects the interpreter path and provides
transactional older-schema restoration. Isolated Docker reproduction, SQL-failure
preservation and 80 affected release/deployment/backlog tests pass. All five
members of the exact production snapshot were independently checksum-verified;
its metadata identifies `git-6d7a5997b480c7da8fd78ec7938bf12d50c05737` and the
database archive is 51,479,280 bytes. No production restore or restart has been
performed manually. See [the concrete recovery boundary](POLLEN_RELEASE_RECOVERY.md).

Target-branch publication of this repair is held until the partial production
database is recovered under explicit authorization; a successful startup against
that partial state must not become a trusted new baseline.

## Current checkpoint — 11 September

**22:34 UTC update:** Public readiness still serves
`6d7a5997b480c7da8fd78ec7938bf12d50c05737`. The subsequent named-station candidate
failed at `build_images` at 22:31:16 UTC; the service is in `retry_wait`. Its web
builder omitted `docs/monitoring-v2/evidence/mv2-069-source-proof.json`, required
by the station contract test. The complete Pollen feature worktree fixes this by
copying that exact fixture into the build stage. A real isolated web Docker build
now passes, without removing the test or changing the running controller. The
feature is not yet published or activated. No source, email or human gate closes
because a build passes. See [complete-feature evidence](POLLEN_COMPLETE_FEATURE.md).

**20:08 UTC update:** The controller is deploying the completed backup/restore
feature `6d7a5997b480c7da8fd78ec7938bf12d50c05737`, with no error step. Public
readiness continues to serve `72bc48945a08fc98140559d6d837f2cfbe6b3dfe`. Development
of the next complete named-station/channel-guidance feature proceeded independently;
its local checks have passed. Neither newer feature is recorded as activated yet.

**19:31 UTC update:** The controller reports automatic release
`72bc48945a08fc98140559d6d837f2cfbe6b3dfe` succeeded with no error step, and public
readiness independently serves that exact SHA. Saved-state recovery and delivery
preferences are therefore activated components. The next private backup/restore
feature has passed its local build, API and browser gates and is being published
once as a complete feature under the user's revised cadence. Its activation is
not yet verified. No source, live Start, email-consent or human acceptance gate is
completed by the earlier automatic release.

**17:00 UTC update:** Automatic release `fc62f43b621d0cb2a613c272473263d6b7e4bb78`
was activated at `2026-09-11T16:35:06Z`, with every gate successful and **2261 API
tests passed, 12 skipped**. Public readiness independently confirms the same SHA.
This includes the private reader and new-draft creator. The controller is now
running API tests for `5e318b0`; independent delivery-preference development
continues without restarting that run. Draft rollout/source/user acceptance
remains separate from successful component activation.

**15:27 UTC update:** Automatic release `40e7283bc4b7d61b56c6fc2b212c7f35cec3b315`
was activated at `2026-09-11T15:08:19Z`, with all gates successful and **2261 API
tests passed, 12 skipped**. Public readiness independently confirms that SHA.
This includes the numeric coordinator and additive private evaluation ledger.
The controller now tests `fc62f43`; frontend iterations continue without restarting
that run. This is actual component release evidence, not source/user acceptance.

**13:49 UTC update:** Automatic release `1144a4742dce6666f6530261e5f08c467b6cc995`
was activated at `2026-09-11T13:42:41Z`; all automatic gates succeeded. Its full
API suite passed **2225 tests, 12 skipped**. Independent public readiness confirms
that exact SHA. The next automatic run targets `40e7283` and continues separately
from frontend implementation. Source-backed Start remains unavailable; this
accepts the rapid-comparison component's release, not the complete Pollen Watch.

**12:21 UTC update:** Automatic release `030ab2960b08a079605013f402c14ef0db1eb9c4`
completed every gate at `2026-09-11T12:21:06Z`, including public health and release
publication. Its full API suite passed **2180 tests, 12 skipped**. Independent
public readiness now reports `ready` with that exact SHA. The transient 1033
during container startup cleared when the new tunnel became healthy. The old-date
digest-fixture repair is therefore included in an accepted real release, together
with private draft API and C02a threshold code. Source-backed Start remains off.
The controller subsequently picked up `1144a47`; its tests run independently.
Remaining account/email/protected progress acceptance keeps MV2-072/073 open.
The earlier checkpoints below remain historical evidence.

Automatic application release `8d5e94b786885609cf4413f17a640ac6a8097792`
completed every release step at `2026-09-11T07:04:38Z`. Public readiness still
independently reports `ready` and that exact SHA at the 10:00 UTC checkpoint.
This verifies an actual automatic update, beyond scheduler pickup. It does not
complete the remaining account/email or protected progress-page checks.

Candidate `c2ab0d6` failed the strict backlog index/detail consistency test; its
cause was fixed in `2d07c09`. Later candidate `9034523` still contained that old
error and failed 49 additional digest/brief cases (50 failed, 2067 passed,
12 skipped). The full retained release log identifies a shared synthetic event
dated `2026-09-04T08:00:00Z`; it left the seven-day digest period during the next
run. A focused paging case reproduces the failure. The independent MV2-072
fixture repair anchors that synthetic detection time five minutes before the
test clock, before any match/assessment fingerprints are created. Application
period filters, eligibility, evidence checks and release gates are unchanged.
All 81 focused regressions passed, including the 49 affected digest/brief cases;
the mandatory backlog consistency test and Ruff also passed. See the
[repair evidence](evidence/MV2-072-digest-clock.md); its automatic release remains pending.

At that checkpoint the controller is testing `bd4fcc5`; latest published Monitoring is `bbce3e2`.
Those are distinct from the currently serving SHA. Development continues in
isolated task worktrees while that run proceeds; it is not restarted or duplicated.
The sections below retain the dated bootstrap/controller history, not current
claims that the first automatic update is still running.

## Verified first release

- Application: `69a63823d6f6e04e9167077d9f89396ba2be9ab1`; controller: `aba58b3c0f7ac8b3a530503efc579dc123340cd9`.
- Host HappyDucky02; branch `codex/HappyDucky02/monitoring-v2`; Compose project `helvetic-lens-v2`; Docker context `desktop-linux`.
- Every bootstrap gate passed. The full API suite reported **2023 passed, 12 skipped, 1 warning** in 82m 32s. Image build, empty-instance guard, startup, initial backup, public health and release publication succeeded. No gate was bypassed.
- At `2026-09-10T21:20:54Z`, an independent HTTPS request to `monitoring.helveticlens.ch/api/ready` returned 200, `status=ready`, `instance=monitoring-v2`, and `release=git-69a63823d6f6e04e9167077d9f89396ba2be9ab1`. Login returned 200; the deployment API returned 401 without authentication.
- The dedicated Cloudflare connector is healthy. Tunnel **happyducky02-helvetic-monitoring-v2**, UUID `bba4be43-c30a-4c98-a3f3-c788002b2422`, routes **monitoring.helveticlens.ch → http://web:3000**. The earlier 1033 error occurred before the connector started.

## Recovery and isolation evidence

With the Windows task paused, a rehearsal created a uniquely named database table and document, captured backup `20260910T212131Z`, mutated both probes, then restored that exact backup. Database contents and document bytes matched the saved versions. The probes were removed, clean backup `20260910T212146Z` was captured, and the same full application SHA restarted with verified public readiness and login.

This proves actual database/document restoration and a restart of the prior revision. It does not claim an intentionally failed candidate was exercised on the live site; release-transaction failure and rollback behavior are covered by the existing regression suites. The rehearsal affected only this instance.

All **30 unrelated running containers** retained their identities/start times through bootstrap and recovery. The refreshed authenticated main-product deployment page still showed verified activated SHA **`4aa4981e11e946a4fc8bb49865ab7455de374295`** on HappySnowman (`happysnowman-cWo2eEPkrR1nfT0`), matching the pre-activation baseline. Public main readiness alone does not expose a release identity.

The dedicated root is `C:/Users/HappyDucky02/Documents/Codex/helvetic-lens-monitoring`, with its own serving-only source clone, immutable releases, controller, state, data/queue volumes, backups, database/encryption credentials and protected private configuration. Windows ACLs restrict the root to its owning user, SYSTEM and Administrators. Runtime services have scoped CPU/memory limits and no published host ports.

## SMTP and account access

The user created the fourth Infomaniak mailbox device **Helvetic Lens Monitoring v2 - HappyDucky02** for **info@helveticlens.ch**. Its credential is protected locally. SMTP STARTTLS followed by authentication returned `235` at `2026-09-10T19:53:07+00:00`. Existing mailbox devices are unchanged. No main-product user database was copied into Monitoring. Registration-email delivery and a real user authentication flow remain unverified; SMTP authentication alone is not delivery evidence.

## Controller upgraded; first automatic update running

The installed controller is pinned to **`dc93efcb5e16db3ac74c45fa1adfa290d8045338`**; `self_update` is false. Its installed SHA-256 is `644ee91a94355a529fee931b29fb932052d7baf9a93aaf1b919cdb912357a7bd`. The paused upgrade succeeded and the task **HelveticLens-Monitoring-v2-AutoDeploy** was enabled at **2026-09-10T21:48:00Z**, retaining **IgnoreNew / Limited**, current-user interactive execution and the two-minute/logon triggers.

The first upgrade attempt was rejected before files or tasks changed because Windows returned the task principal as the local short name. The installer compared only its SID and qualified name. The reviewed fix resolves the principal through Windows to a SID and compares that exact identity; unknown/different owners and mismatched actions/descriptions remain rejected. Native installer regressions cover SID, qualified and short names, foreign/unresolved principals, immutable controller extraction, ACLs, configuration preservation, paused-task preservation and the exact hidden invocation. Scheduler registration is mocked in the suite. The actual paused task also passed a read-only ownership check with the repaired function.

A subsequent paused upgrade passed ownership validation but stopped before controller replacement when Windows refused to reapply the already correct directory ACL (`SeSecurityPrivilege`). The installer now preserves an ACL only after checking the exact owning SID, protected DACL and both explicit user/SYSTEM FullControl entries with the required flags. ACL drift still reaches the protection operation; no extra privilege or broader access is requested. Native first/repeated file and directory checks and synthetic drift regressions verify this behavior.

No manual poll or task start was issued. The enabled task picked up application **`dc93efcb5e16db3ac74c45fa1adfa290d8045338`** at **2026-09-10T21:48:10Z**, run `183a4e02-c5c2-4a80-9cbf-504c1ce8ae11`. Checkout, configuration validation and API lint passed; the full API suite is running. The prior accepted `69a63823d6f6e04e9167077d9f89396ba2be9ab1` remains the current site during these gates. The first bootstrap's 82-minute API run is a duration reference, not a completion prediction or permission to skip checks.

The captured progress snapshot reports available latest data at the new SHA (73 tasks, 64 required) and available deployed data at the prior SHA (72 tasks, 63 required). Both have zero recorded DONE tasks; this is valid backlog data. The new progress interface is still awaiting application deployment. Scheduler execution proves automatic pickup; it does not yet prove acceptance of the new release.

**Next action:** verify the completed automatic release, public SHA, protected deployment page and exact before/after progress snapshots. A later accepted automatic revision must refresh the deployed snapshot. Real user registration and email delivery remain pending. Keep MV2-072 IN PROGRESS and MV2-073 VERIFYING until their remaining live acceptance passes.

## Earlier validation and limits

Earlier affected regressions passed: **79 native Windows** and **92 Linux** tests plus Ruff, synthetic image builds and rendered Compose isolation checks. A preliminary broader run was stopped while external setup was incomplete; it was not a full-suite pass. The completed first-bootstrap result above supersedes that preliminary checkpoint.

The preview remains one Windows host: login, Docker Desktop readiness, sleep/power and shared GPU capacity affect availability. This setup does not establish high availability or implement Pollen Watch. Follow the [runbook](../MONITORING_DEPLOYMENT.md); Pollen Watch remains first, support remains parked and C4 customs remains deferred.

## Release-blocking Tender dispatcher clock regression — 14 September 2026

The authenticated main-site deployment journal was refreshed: attempt
9b34ecb96842 (08:50:02–10:10:16 local UI time) failed after 4,210 passed,
14 skipped and one failing private Tender SMTP-dispatch test. The actual active
attempt 11ef1765d8f3, started 10:12:02, is running api_tests; it was not restarted,
duplicated or interrupted. Production remains 1188f18190e0. All nine Monitoring
navigation links are visible on the authenticated main site.

The same test fails locally on current main. Its synthetic consent and event use
12 September 06:00 UTC while real dispatcher delivery uses the wall clock. The
48-hour expiry therefore correctly suppresses the event from 14 September onward.
Repair scope: make the dispatcher test's delivery clock explicit; prove current,
exactly-48-hour and just-expired outcomes through the actual durable dispatcher
and fake SMTP. Preserve production expiry, privacy, consent and all release gates.
Run the affected Tender API/delivery suite and exact API lint before publication.
This is a verification repair for the complete Tender feature, not a waiver of
source or human acceptance. No real email or source access approval is involved.

Verification completed: the full affected Tender API/delivery suite passed
**33 tests**, including actual dispatcher sends at age zero and exactly 48 hours,
and suppression one second beyond 48 hours. The persisted job outcome is asserted
as sent/no_eligible_changes, as well as fake SMTP calls. Exact API lint passed.
The production delivery implementation and its expiry guard are unchanged. This
fix will be picked up by a subsequent normal deployment; activation remains open.
