# Owned Monitoring configuration downloads

Scope: MV2-053 private configuration export, with the existing MV2-004 ownership
and native nine-category settings contracts. This does not complete account
deletion, historical evidence exports, retention, independent security review or
the broader Monitoring release gate.

## User workflow

Open `/monitoring/settings`. Choose **Download all nine categories** or
**Download this category**. The browser collects current owned monitor settings,
shows the count, checks the collected records again and prepares one JSON file.
Viewers can export their own settings. Archived monitors are included. A business
monitor explicitly shared by its owner is included in that owner's export; a
colleague's shared monitor is not included.

The file contains the current configuration, saved configuration revision number,
lifecycle/visibility state and saved email preferences. Pollen preserves recorded
consent and mute state; Commute also preserves its paused date. Saved email
preferences are not a claim that delivery is currently authorized or operational.
No monitor is changed, started, collected or emailed by exporting.

The page explains that the download can contain private locations and interests.
Connector credentials, source documents, source observations, previous
configuration revisions, review decisions and colleagues' monitors are excluded.
This is an inspectable settings export, not an import format, database backup or
historical evidence archive. There is no new source access or model dependency.

## Integrity and consistency

`helvetic-lens-monitoring-configuration-v1` includes the authenticated owner and
workspace, selected category, collection/completion times, item count and explicit
inclusions/exclusions. Each record includes `canonical_json` and its SHA-256 over
the exact UTF-8 string. This retains decimal spelling and Unicode independently
of a downstream JSON parser. The browser verifies those bytes before accepting a
record and derives displayed/exported fields from the verified payload.

The export reads and rechecks individual current records; it does not claim a
single transactional database snapshot. Creation after the initial server cutoff
is excluded. A concurrent change to a collected configuration, saved email
policy, lifecycle state or ownership fails final verification. A removed record
also fails verification. Records removed before they are read are absent; the
manifest does not claim to reconstruct their former state. Source polling alone
does not invalidate the settings binding.

The UI aborts on cancellation, unmount, category/identity/locale changes, pagehide
and native monitor-change signals. Failed pages, changed scope, repeated records
or cursors, failed integrity checks and rejected verification produce no completed
download. The in-memory export is never persisted on the server. Browser object
URLs are revoked after the download handoff and on cancellation/unmount.

## API boundaries

- `GET /api/monitoring-centre/configuration/export`: optional category, 1–50
  records per page. The opaque continuation includes owner/workspace/filter,
  creation cutoff and stable category/UUID position, expiring after 15 minutes.
  It never bypasses the current owner and membership query.
- `POST /api/monitoring-centre/configuration/export/verify`: at most 1000
  `{domain,id,sha256}` bindings per request, protected by the existing session and
  CSRF middleware. An empty export still checks membership. The browser batches
  larger verification sets and checks the returned authenticated scope.
- Source/feature readiness does not deny access to the user's existing settings.
  Reads check membership again before returning; no source reader is invoked.
- Responses are `no-store`. Existing administrative audit contains action/status
  metadata, not configuration content. No credentials store, source document or
  integration logger is attached.
- Per-record payloads are bounded to 256 KiB, browser collection to 10,000 records
  and 64 MiB of compact item JSON. Limits fail explicitly; they never truncate a
  successful file. The UI offers a category export for a smaller collection.

## Verification and limits — 14 September 2026

The feature API and shared configuration/backlog regression passed **62 tests**.
They cover all nine native model mappings, archived and disabled-source settings,
saved email policies and Pollen consent, SHA-256 payloads, stable multi-category
pagination, later creation, shared/private ownership, workspace changes, current
viewer access, CSRF, cursor limits, missing policy rows, changed/deleted records,
deactivation and revocation during response assembly. No collection or delivery
jobs are created by the workflow. The exact API Ruff gate passes.

The isolated root build passes. The committed browser protocol
`scripts/check-monitoring-export-browser.mjs` downloads and parses actual JSON
files from the compiled application. It checks all-category export in five
locales at 390/1440 pixels, each of nine category selections, scope mismatch,
corrupted payload hash, later-page failure, rejected verification, cancelled late
response and empty export: **25 full-document axe/workflow checkpoints**. Early
protocol fixes wait for Chrome to finish writing the download and distinguish
existing shell assistant requests from export actions. The final UI uses the
existing visible button component with wrapping labels and 44-pixel targets.

Fixtures are synthetic user configurations and API responses. This protocol is
not evidence of live source rights, production activation, target-host capacity,
independent language review or a completed privacy/account-deletion gate.
