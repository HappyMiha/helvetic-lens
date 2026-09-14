# Selected Monitoring evidence downloads

Status: **IMPLEMENTED AND VERIFIED LOCALLY; production activation pending**. This is the
selected-evidence feature scoped under MV2-055, not completion of the broader
retention, restoration, source-rights or human acceptance requirements.

## User workflow

The nine native readers offer a private JSON download beside their evidence
controls. Tender publication versions, selected IP changes and selected auction
changes additionally pass an explicit historical revision. The current-settings
download and existing Pollen/IP exports remain available separately.

Prepare reads the exact native record and shows its evidence sequence, settings
revision and expiry. Download rebuilds the same packet using current membership,
session, monitor visibility and source permissions. A changed packet, expired
preview, revoked access or missing retained evidence produces an unavailable
result; the selected version is never replaced silently with today's head.

The client checks the exact UTF-8 JSON bytes against the server hash and preview,
validates the record/workspace/locale, then checks the current browser identity
before creating the download. It cancels pending work on unmount, page hiding,
workspace/context changes or explicit cancellation. Copies in downloaded files
are outside server-side account erasure.

## Retained evidence and source boundaries

The versioned manifest names the selection, configuration revision, private
scope, locale, preparation time, byte size and payload SHA-256. The outer file
also has a SHA-256 verified by the browser. Native evidence preserves its actual
schema and before/after semantics. Private reviews and evidence-bound business
decisions/comments are separate from source facts. Actor IDs may be null after
account erasure; no current-person lookup invents a historical identity.

Only normalized native projections are included. ASTRA raw payloads, transport
feed bytes, authenticated SIMAP originals and connector credentials are excluded.
Road source/topology rights, retained proof hashes, expiry and allowed derived
fields still apply. MeteoAlarm attribution and redistribution metadata remain in
the packet. IPI and auction snapshots require explicit export permission for both
selected and previous source states. These private copies grant no additional
redistribution rights. Missing source rights remain a source acceptance gate.

Air/River did not retain configuration digests; their calculated download hash
is explicitly marked as not a retained historical hash. Legacy auction decisions
record source/material sequence but not a profile revision; this absence is
explicit. IP exports require the historical rule assessment and retain its
evaluation hash and calibration IDs. A damaged newer Commute snapshot cannot
block a still-permitted older selected version.

## Authorization and boundedness

Preview confirmation is stateless, domain-separated and HMAC-bound to the user,
session, workspace, exact selection, locale, content hash and five-minute expiry.
Password changes also invalidate it. The browser supplies no user ID or source
body. Final download locks the monitor before organization/account membership,
rechecks the real session after lock waiting and uses the native source locks.
Elapsed-time expiry/retention is checked again after packet assembly. Lock
conflicts return a retry error, never a partial packet.

Both POST endpoints require session authentication and CSRF. Viewers retain
authorized read access; source credentials remain administrative/private. Error
and success responses use `Cache-Control: no-store`. Requests are rate bounded.
Packets are limited to 2,000,000 bytes, with at most 1,000 native actions and 1,000
work actions. Overflow is explicit rather than silent truncation. No packet,
source artifact, model response, job or outgoing message is created in storage.

## Acceptance evidence

- 54 API/native cases passed in `.tmp/evidence-export-binding.log`: all nine
  adapters, manifests and exact bytes, real session/CSRF endpoints, historical
  states, private decisions, shared/viewer/private boundaries, between-request
  membership/source revocation, invalid configuration, password/session changes,
  expiry and source/topology retention gaps.
- Five isolated PostgreSQL cases passed through
  `scripts/check_evidence_export_postgres.py`: three business histories with
  decisions and viewer visibility, plus observed scope and source revocation
  lock races. Waits were verified in `pg_stat_activity`; generic retry/deadlock
  outcomes do not satisfy the race assertions.
- Exact API Ruff gate, script lint, web formatting, TypeScript and the complete
  root build passed. Build output: `.next-check-evidence-export`.

- Three additional real HTTP checks passed: expiry during lock waiting and
  packet assembly (both explicitly return preview-expired without file bytes),
  and an authenticated viewer downloading owned permitted evidence. Together
  with the preceding suite this gives 57 passing API/native cases. Logs:
  .tmp/evidence-export-final-negatives.log (two expiry cases passed), and
  .tmp/evidence-export-viewer-final.log (viewer fixture scope corrected and passed).
- scripts/check-evidence-file-browser.mjs passed 129 actual JSON downloads and
  129 full-document axe checkpoints: nine real native reader pages, five locales
  at 390/1440px, nine viewer reads, plus the three business historical readers
  in every locale/width. The download bytes, filename, selected IDs/revisions,
  SHA-256, Unicode, large integer/decimal bytes and separate private comments
  were checked from real filesystem downloads. Invalid previews, expiry, altered
  hashes/bytes/manifests, revoked access, changed browser identity, cancellation,
  late responses, pagehide and Today changes produced no product JSON file.
  Browser API/source responses are synthetic; authorization/ingestion evidence
  comes from the real API and PostgreSQL checks above. Native source URLs are
  localized in browser fixtures. Managed Chrome's unrelated extension update
  files are excluded from the product-download assertion.
- The browser run identified and resolved heading-order and duplicate-landmark
  findings when several readers share the download control. It is a named action
  group that preserves each native page's heading hierarchy. Full root build
  passed after these changes (.tmp/evidence-export-build-final2.log).
- Full browser evidence: test-results/accessibility/monitoring-evidence-file.json,
  test-results/evidence-file-requests.json, and evidence-file-<domain>-<width>.png.
  Mobile Pollen and desktop warning screenshots were visually inspected. Other
  axe incomplete checks remain recorded; no blanket accessibility certification
  or real-user acceptance is claimed.

Reproduce the browser check after the root build with
HELVETIC_LENS_CHECK_BUILD=evidence-export and
node scripts/check-evidence-file-browser.mjs. Its three business seed contracts
are prepared by scripts/prepare_business_item_browser.py in disposable SQLite;
personal reader fixtures are in scripts/evidence-personal-browser-fixtures.mjs.
No production collection, account, source approval or deployment job is changed.

The feature is ready for normal main publication. MV2-055 remains IN PROGRESS:
telemetry compaction, complete retention/restore rehearsal, source readiness,
verified production activation and human acceptance remain separate open gates.
