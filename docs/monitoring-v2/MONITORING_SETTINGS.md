# Monitoring settings — implementation acceptance

Requested 14 September 2026. Scope: MV2-018 and MV2-025; contributes to
MV2-024. These parent tasks remain IN PROGRESS. C4 remains deferred.

The settings section must expose all nine native monitoring editors, including
configuration, lifecycle, sharing where supported and personal email preferences.
Reuse their existing validation and ownership rules rather than maintaining a
second configuration format. Each category also exposes its source connector.

Platform administrators can replace or explicitly clear supported credentials,
select existing reviewed permission records and change native collector options.
IPI accepts its supported API username/password; Commute has two independent
feed keys; Road has its API key. Public connectors do not ask for unused website
passwords. Saved secrets use authenticated encryption and are never returned.
An optimistic revision prevents overwriting another administrator's changes.

API requests and scheduled collectors use a fresh, consistent saved configuration
without restarting the deployment. Saving source settings never grants source
rights, creates email consent or hides a monitoring section. Access checks are
explicit, bounded, fixed-origin operations with redacted outcomes; a connection
check is distinct from schema, permission, freshness and coverage acceptance.

Required evidence: encrypted persistence/clear/conflict behavior, role and CSRF
boundaries, runtime adoption across API and workers, probe failure handling and
credential redaction, native editor navigation, frontend build, API lint and
affected regressions. Actual release and external-source acceptance are separate.

## Implemented behavior

`/monitoring/settings?category=<domain>` is linked in desktop/mobile Monitoring
navigation. All nine categories mount the existing native editor inside one shell;
configuration, lifecycle, sharing, source status, saved evidence and email controls
retain their native contracts. Source failures remain visible in those editors.
Public source access checks do not invent credentials for unsupported website login.
IPI uses its native API account, Commute has independent trip/alert keys and Road
uses the native SOAP API key. Administrative source permissions are selected from
existing records, not created or approved by a settings save. Public Pollen policy,
decoder and reviewed transport redirect origins are inspectable deployment settings.

The additive migration seeds nine version-zero configuration rows. Updates use a
database compare-and-swap revision. Credential payloads bind their encrypted content
to the category, and an explicit empty value overrides a deployment credential.
IPI account changes invalidate the associated token cache. Corrupt credentials fail
closed for source use while leaving administration reachable for explicit repair.
Secrets are absent from API responses, diagnostic results and audit payloads.

The existing request-local service settings context resolves source overrides;
native routers preserve unchanged deployment flags. Scheduled collectors resolve
fresh concrete snapshots. Native source guards reject a changed configuration
revision during acquisition. Existing grants and leases remain authoritative.
No serving checkout, environment file or production credential was changed.

Access checks use fixed native HTTPS endpoints, explicit request objects without
ambient cookies/auth, bounded reads/timeouts and a database cooldown of one minute
per category. Redirects never receive credentials. Result persistence requires the
same revision that was checked. Public checks establish HTTP access only; IPI checks
token authentication only. They admit no source observations and send no email.

## Verification

- Initial HTTP/encryption/native batch regression and backlog bundle: 15 passed.
- Expanded acquisition/source operations bundle: 162 passed; two test expectations
  needed adjustment for the existing Tender composite result and the newly required
  persisted-config read before Road's disabled decision. The affected settings/Road
  rerun then passed all 58 tests, retaining cleanup and disposal assertions.
- The expanded bundle includes the reported Aste migration preservation regression,
  now passing with the previously pushed SQLite repair.
- Final publication bundle: 30 passed, including native HTTP credential adoption,
  actual periodic worker entry points, existing named permission selection, IPI
  token invalidation after password rotation, prior model-provider credential
  persistence/clearing and the updated backlog integrity check.
- Root build passed with `HELVETIC_LENS_CHECK_BUILD=connector-settings`; exact API
  Ruff gate passed. Compiled browser checks passed 93 full-document axe checkpoints:
  nine categories × five locales × two widths, credential save/clearing, conflict,
  and viewer boundaries. Mobile and desktop captures were visually inspected.
- Tests use synthetic credentials and source responses; no live account access or
  full source coverage is claimed. Native editor behavior is reused, not replaced.
  Browser source gaps are deliberate fixtures, not claims of production readiness.

Exact activation and independent human language/accessibility acceptance remain
unverified. MV2-018/025 and their broader acceptance gates remain IN PROGRESS.
