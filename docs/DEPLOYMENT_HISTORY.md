# Deployment history

The Deployment page (`/deployments`) is available to platform administrators. It
shows actual host release-manager attempts, not Git pushes or assumptions based
on the current branch. The latest known active release remains separate from
the requested revision and the history of attempts.

## What an administrator can inspect

- A chronological list with newer/older pages and outcome filters. Runs have
  exact start dates/times in Europe/Zurich, target commits and outcome badges.
- Expand a run in place for its previous, requested and verified activated commit,
  recorded host/environment, start/end time, duration, phases and phase errors.
  Mobile layouts stack the information without a sideways page scroll. Controls
  have 44-pixel minimum targets and details/release notes work with a keyboard.
- Failed attempts show sanitized failure excerpts and the failing phase;
  rollback status and backup restoration remain visible. No failed attempt is
  presented as a successfully activated release. Diagnostic truncation is explicit.
- Successful attempts show release notes captured from the exact commit range
  before execution. These are labelled **saved commit summaries**, not invented
  product notes or repository-authored release notes. The existing 50-commit
  collection is retained, with an explicit possible-truncation warning and a
  link to the full exact GitHub comparison when both SHAs and the repository are
  known. Moving `main` later cannot change the saved summary.
- Legacy attempts without notes/host/activation metadata show that information
  as not recorded. For failed/running attempts notes describe **intended** changes.
  They are never described as proof those changes reached production.

Latest history and expanded details refresh every ten seconds while their
resources are mounted, visible and online. Older pages are not polled. A failed
detail read can be retried without starting deployment or reloading the page;
the latest button resets the cursor and invalidates the target history cache.

## Host journal

The standalone Linux `deploy/release_manager.py` now writes `history.sqlite3`
under the existing deployment state directory. It uses Python's standard library,
so it can record an application/database deployment failure even when the API or
PostgreSQL is down. The API mounts that state directory through the existing
read-only arrangement and opens the SQLite file with `mode=ro`.

Each run has one row, updated while running and immutable after its terminal
outcome. Phase transitions are checkpointed, not just the final status. SQLite
transactions protect initialization/import and updates. A host-lock-protected
restart marks the preceding unfinished run `interrupted`, preserving its unknown
finish time and recording the time interruption was observed. It does not invent
success, a verified activation or the time the old process actually stopped.
Rejected ancestry checks preserve the requested revision and rejection phase.

The old `status.json` and rolling `history.json` remain for compatibility.
`HELVETIC_LENS_DEPLOY_HISTORY_LIMIT` applies only to that old snapshot, not to the
permanent journal. On first journal initialization, all still-available legacy
records are imported. The UI can also page/read these legacy JSON files before
the updated host manager has first run. **Previously discarded history cannot
be reconstructed.** Manual deployments outside the release manager are not
automatically discoverable; run tracked deployments through the existing manager.

No new production installation or deployment was performed while developing this
feature. The updated manager takes effect through the existing separately
authorized release/install procedure. Retain the state directory in operational
backups; the journal is not a replacement for database or evidence backups.

## Read API and safety

`GET /api/admin/deployments/history` accepts `status`, `cursor` and `limit` (1–50).
The journal query reads only one page plus a continuation sentinel. It uses
start-time/ID ordering, a captured row-ID ceiling and cursors bound to the filter
and journal identity. New attempts do not leak into an older traversal. The list
reads compact summaries, not all diagnostic payloads. No full-history count is
needed. The legacy mode explicitly reports uncertain retention.

`GET /api/admin/deployments/history/{run_id}` reads one exact stored attempt.
Fields are allowlisted; the API does not use supplied IDs or stored log names to
read arbitrary host files, execute commands or expose environment dictionaries.
Known host secrets are removed before journaling, with additional bearer,
credential-assignment and URL-password redaction in the writer and reader.
Malformed/unreadable/oversized records return a retryable error, not an empty
successful history. Original host log files are not exposed through this API;
the displayed diagnostics are bounded recorded failure excerpts.

Existing platform-admin authorization protects both routes. Organization admins
alone cannot inspect platform deployment history. Normal local anonymous-dev
mode retains its existing platform permissions; this is not a new public endpoint.

## Verification and limits

- 27 API/access/production-configuration tests passed on isolated SQLite data.
  New tests cover 135 equal-time attempts, continuation past the old limit,
  concurrent new rows, filters/cursor identity, exact notes, quoted-secret
  redaction, malformed dates/records, legacy fallback and 401/403/admin access.
- 14 Linux tests exercised the real writer and release pipeline with external
  commands replaced: 81 records survive a three-entry legacy window, checkpoints
  and terminal records are durable, and success, test failure, health failure,
  failed rollback, interruption and rejected history gates remain distinct.
  The container had no network or deployment data and was removed after each run.
- Production Next.js build passes. Ten browser journeys cover all five locales
  at 390/1440 pixels, exact retry, notes, real pointer access, filters/pagination
  and non-admin access. Full-document axe checks retain incomplete results;
  they are not an independent accessibility certification or native translation review.

No production rollout, production-log recovery or target-host operational rehearsal
is claimed. This feature does not change release approval policy or authorize an
automatic production deployment merely because code was pushed.
