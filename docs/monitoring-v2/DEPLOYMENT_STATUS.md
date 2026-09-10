# Monitoring deployment status — 10 September 2026

**The isolated Monitoring site is live. MV2-072 remains IN PROGRESS: first bootstrap, public HTTPS identity and actual backup/restore passed; automatic-update acceptance remains pending. MV2-073 is VERIFYING and its progress interface is published in Git, awaiting deployment.**

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
