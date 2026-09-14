# Monitoring deployment status — 14 September 2026

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
