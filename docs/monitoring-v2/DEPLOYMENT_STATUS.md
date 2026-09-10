# Monitoring deployment status — 10 September 2026

**MV2-072 is in progress; the public site and automatic updates have not been accepted.**

## Verified implementation

- Main routing documentation was published as `4aa4981e11e946a4fc8bb49865ab7455de374295`. Its application/deployment code was not changed by this split.
- Monitoring follows `codex/HappyDucky02/monitoring-v2`, host HappyDucky02, Compose project `helvetic-lens-v2`, Docker context `desktop-linux`, and hostname `monitoring.helveticlens.ch`.
- Native Windows affected regressions: **79 passed**. Linux affected deployment/installer/configuration regressions: **92 passed**. Ruff passed.
- Native Windows installer regression checks passed, including strict configuration validation, controller provenance, ACLs, concurrent-install lock, idempotence, foreign-task rejection and the exact hidden scheduler invocation. Scheduler calls were mocked in these tests.
- API, model-manager and web images built with explicitly synthetic QA configuration. Rendered Compose has separate namespaced volumes/networks, no published host ports and explicit service memory/CPU limits. This is build/isolation evidence, not a live deployment.
- A broader application test run was stopped after the affected suites passed because first deployment still needs external setup. It is **not** a passing full-suite result. The controller retains its mandatory full API and image-build quality gates before activation; none were bypassed.

## Host preparation and open acceptance

The dedicated root is `C:/Users/HappyDucky02/Documents/Codex/helvetic-lens-monitoring`. It contains a separate serving-only source clone, protected private configuration, separate generated database/encryption credentials and instance paths. Windows ACLs restrict the root to the owning user, SYSTEM and Administrators.

SMTP configuration is pending. No shared main-product credentials or user database were copied. The Cloudflare creation form has the proposed name `happyducky02-helvetic-monitoring-v2`; no new tunnel token or route exists yet. Existing main/Lokvetia tunnels are unchanged.

Controller/scheduler installation, first bootstrap, full candidate quality gates, actual backup/restore rehearsal, public HTTPS instance/release checks and a subsequent automatic branch update still require live evidence. An installed scheduler will remain disabled until first bootstrap succeeds.

The preview remains one Windows host. Login, Docker Desktop readiness, sleep/power and shared GPU capacity affect availability. Resource limits do not establish high availability or Pollen Watch user-test readiness. Follow the [runbook](../MONITORING_DEPLOYMENT.md); Pollen Watch remains the first product delivery and C4 customs remains deferred.
