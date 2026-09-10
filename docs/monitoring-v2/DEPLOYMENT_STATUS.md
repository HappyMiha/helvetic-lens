# Monitoring deployment status — 10 September 2026

**MV2-072 is IN PROGRESS. The dedicated Cloudflare tunnel and hostname route are configured, and SMTP STARTTLS/authentication is verified. First bootstrap is underway; successful activation, public-site acceptance and automatic-update acceptance remain pending.**

## Verified implementation

- Main routing documentation was published as `4aa4981e11e946a4fc8bb49865ab7455de374295`. Its application/deployment code was not changed by this split.
- Monitoring follows `codex/HappyDucky02/monitoring-v2`, host HappyDucky02, Compose project `helvetic-lens-v2`, Docker context `desktop-linux`, and hostname `monitoring.helveticlens.ch`.
- Native Windows affected regressions: **79 passed**. Linux affected deployment/installer/configuration regressions: **92 passed**. Ruff passed.
- Native Windows installer regression checks passed, including strict configuration validation, controller provenance, ACLs, concurrent-install lock, idempotence, foreign-task rejection and the exact hidden scheduler invocation. Scheduler calls were mocked in these tests.
- API, model-manager and web images built with explicitly synthetic QA configuration. Rendered Compose has separate namespaced volumes/networks, no published host ports and explicit service memory/CPU limits. This is build/isolation evidence, not a live deployment.
- A broader application test run was stopped after the affected suites passed because first deployment still needs external setup. It is **not** a passing full-suite result. The controller retains its mandatory full API and image-build quality gates before activation; none were bypassed.

At `2026-09-10T19:56:35Z`, the authenticated main-product deployment UI showed **main** with verified activated SHA `4aa4981e11e946a4fc8bb49865ab7455de374295`, automation idle/up to date, and the latest deployment succeeded on HappySnowman (`happysnowman-cWo2eEPkrR1nfT0`). The UI displayed completion at **21:49:05 Europe/Zurich** and an API-test duration of **39m 31s**. This is the pre-Monitoring-activation baseline; compare the same authenticated UI after v2 activation. The main public readiness endpoint does not expose release identity.

## Host preparation and open acceptance

The dedicated root is `C:/Users/HappyDucky02/Documents/Codex/helvetic-lens-monitoring`. It contains a separate serving-only source clone, protected private configuration, separate generated database/encryption credentials and instance paths. Windows ACLs restrict the root to the owning user, SYSTEM and Administrators.

The user explicitly approved the separate setup. The dedicated Cloudflare tunnel **happyducky02-helvetic-monitoring-v2**, UUID `bba4be43-c30a-4c98-a3f3-c788002b2422`, has been created. Its token is stored in the protected instance configuration, and the hostname route **monitoring.helveticlens.ch → http://web:3000** has been saved. Existing main-product and Lokvetia tunnels are unchanged. A saved Cloudflare route is configuration evidence; a connected tunnel and the public application's identity still require live verification.

The user created a separate fourth Infomaniak mailbox device, **Helvetic Lens Monitoring v2 - HappyDucky02**, for **info@helveticlens.ch**. The operator stored its credential in the protected Monitoring environment and verified SMTP STARTTLS followed by successful authentication (`235`) at `2026-09-10T19:53:07+00:00`. No message was sent; registration-email delivery and a real authentication flow remain unverified. The three existing mailbox devices are unchanged, and no main-product device credential or user database was copied into Monitoring.

The native installer validated and installed controller commit `aba58b3c0f7ac8b3a530503efc579dc123340cd9`. The actual Windows task `HelveticLens-Monitoring-v2-AutoDeploy` was read back as **Disabled / Enabled=false / IgnoreNew / Limited**. Its persisted selector follows only the Monitoring branch; the controller itself remains pinned. The source clone is marked serving-only using the repository Git safeguards.

**Current action:** the installed pinned controller is bootstrapping application candidate `69a63823d6f6e04e9167077d9f89396ba2be9ab1`. At the recorded checkpoint, production configuration validation and the empty-instance guard passed; the Windows deployment task remained disabled. The operator owns completion of the mandatory quality gates, bootstrap, recovery rehearsal, public verification and subsequent automatic-update acceptance. Setup authorization, the dedicated tunnel route and SMTP authentication are complete.

Successful first-bootstrap completion, full candidate quality-gate results, actual backup/restore rehearsal, public HTTPS instance/release checks and a subsequent automatic branch update still require evidence. Keep the Windows deployment task disabled until bootstrap succeeds and the operator has completed the paused recovery rehearsal. The dedicated Cloudflare tunnel and hostname route exist; this status does not yet claim an accepted live Monitoring application or automatic deployment. SMTP authentication success does not prove email delivery.

The preview remains one Windows host. Login, Docker Desktop readiness, sleep/power and shared GPU capacity affect availability. Resource limits do not establish high availability or Pollen Watch user-test readiness. Follow the [runbook](../MONITORING_DEPLOYMENT.md); Pollen Watch remains the first product delivery and C4 customs remains deferred.
