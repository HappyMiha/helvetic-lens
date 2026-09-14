# Account deletion and shared monitor ownership

MV2-053 scoped implementation, 14 September 2026. The parent privacy task remains
IN PROGRESS; this document is implementation evidence, not independent privacy
certification or proof that a release has activated.

## User workflow

Monitoring settings links to **Account and privacy** at `/account`. Any signed-in
member, including a viewer, can review their own deletion scope. The preview
lists all nine monitor categories, personal record counts, private document
versions and workspace dispositions. No source access or inference is needed.
Current owned configurations can be downloaded from Monitoring settings first.

Deletion requires the current password, an unchecked account confirmation and,
when applicable, a second unchecked confirmation for the listed sole-member
private workspaces. A preview expires after 15 minutes and is bound to the user,
session, current workspace, password hash and exact selected record identities.
Changed scope, revoked membership, invalid proof or invalid password does not
erase data. The UI discards the preview after a failure and asks for a fresh review.
Successful deletion clears authentication cookies and performs a full navigation
to the signed-out page, discarding private browser application state.

The last active workspace administrator must arrange a successor. The last active
platform administrator must promote another active administrator. An apparently
sole-member workspace that retains a former colleague's private data cannot be
erased as the departing user's private workspace. A retained cross-workspace
reference to private evidence blocks erasure rather than destroying the evidence
used by that colleague. These conditions have explicit explanations in the preview.

Shared Tender, IP and Auction monitors must be handed over before their owner
can leave through deletion. In the native editor, **Access and responsibility**
contains the owner-only handover form. The owner selects another active workspace
administrator and explicitly confirms. Handover updates owner and responsible
person together, records the previous/new owner in history, pauses active
monitoring, requests cancellation of pending jobs and revokes email consent.
Authenticated SIMAP document grants are revoked; source credentials, access rights
and notification consent are not transferred. The successor reviews these and
resumes separately. Private monitors must first be explicitly shared if handover
is desired. Former-workspace ownership requires restoring membership through its
administrator; that workspace's private identity is not disclosed in the preview.

## Data and concurrency contract

The account erasure transaction removes the account, sessions and tokens, owned
personal monitor state across all nine categories, conversation state, private
preferences and queued private work. Explicitly confirmed private workspaces also
lose their private corpus and dependent records. Legacy/native document pairs
count once in the preview. SQL foreign keys stay enabled; the executor refuses
unknown schema tables, oversized inventories and retained restrictive references.
Selection is bounded to 10,000 inventory records and 100,000 dependent records;
oversized accounts need an operator-managed process rather than partial deletion.

Shared official corpus, colleagues' private data, shared decisions and platform
connector settings survive. Retained decision/audit actor references become null;
denormalized actor labels and account-bound security hashes are removed. Shared
free-text decision notes remain workspace records, as disclosed in the preview.
Historic notification recipients matching the removed account are cleared.

Database locks and a rebuilt inventory serialize erasure with role changes,
ownership handover and other account erasures. A late assistant response cannot
restore a deleted conversation, and an in-flight job cannot restore its removed
parent/job state. Late request auditing rechecks live user/workspace references
instead of reintroducing foreign keys to erased accounts. The API applies session,
CSRF, current-role, password, rate-limit and no-store protections. The deletion
subject always comes from the session, never a body-provided user identifier.

## Retention and recovery limits

Online database erasure is transactional. Physical files become eligible for the
existing orphan cleanup only after their configured file-age grace period; the
maintenance job runs every 24 hours. Files still referenced by retained official
or private records remain. Cleanup failure or a stopped maintenance worker delays
physical removal. Source-retained authenticated documents follow their existing
retention records. Development mail files also follow their own retention.
The UI does not promise immediate removal of backups, delivered messages,
externally downloaded exports or source-retained documents.

Migration `9c7f5069bdef` makes four retained actor references nullable with
`ON DELETE SET NULL` and adds handover history fields. Upgrade preserves existing
decisions. Downgrade refuses after null retained actors or recorded handovers;
it never fabricates people or discards shared decisions to satisfy an old schema.
Use compatible code/schema after an erasure, rather than forcing this downgrade.

Existing `deploy/restore.sh` restores the database and document archive together.
It has no independent erasure ledger/replay mechanism: restoring an older backup
can restore accounts and data deleted after that backup. Before exposing such a
recovery to users or starting collectors/delivery, operators must reconcile all
intervening account erasures and ownership changes in the isolated restored copy,
reapply required removals and validate remaining references. A historical backup
is not proof that an erased account may be reactivated. Backup expiry, independent
review and a rehearsed automatic erasure-aware recovery remain broader retention
and recovery gates under MV2-053/055/056; this feature does not certify them.

## Verification

- The final affected API/migration/auth/backlog matrix passed **58 tests** in
  120.18 seconds. Focused API tests cover physical erasure of all nine monitor kinds, retained
  native decisions, source corpus, private document dates, shared files, sessions,
  proof/password/CSRF/current role, changed scope and in-flight assistant/job work.
  Migration checks upgrade real populated native decision fixtures and exercise
  irreversible downgrade refusal.
- `scripts/check_account_erasure_postgres.py` ran against a new isolated PostgreSQL
  16 database: concurrent workspace and platform-admin erasure, an observed lock
  wait with changed membership, and competing incoming handovers for all three
  business domains passed. The synthetic container was removed afterwards.
- `scripts/check-account-deletion-browser.mjs` passed 15 compiled-page workflow
  and full-document axe checkpoints across five locales and 390/1440px widths,
  including two confirmations, incorrect password, changed/revoked access,
  success navigation and cancelled late preview. No real account was deleted.
- `scripts/check-business-monitor-browser.mjs` passed 99 compiled-page workflow
  and full-document axe checkpoints: all three business directions, five locales,
  two widths, sharing, owner-only explicit handover, previous/new owner history,
  peer/viewer behavior, conflicts, withdrawal and late responses.
- The root build, TypeScript and exact API Ruff gate passed. Browser accessibility
  reports retain incomplete checks for review; automated results are not full
  accessibility certification. Synthetic fixtures do not prove production source
  access, real delivery, human acceptance or activation.

The exact feature commit and production activation must be verified separately.
