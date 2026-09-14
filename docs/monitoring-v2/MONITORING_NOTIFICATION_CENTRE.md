# Monitoring notification centre

## Whole-feature scope — 14 September 2026

MV2-022/019/020 contribution: the header notification centre must expose the
owner's unreviewed saved Today changes in all nine active Monitoring directions,
alongside the existing legal notifications. It currently exposes legal events
only. Reuse the published global review summary and native source/review readers;
do not create another independent unread flag or imply a source permission.

Acceptance:

1. The centre offers all nine directions and the legal feed, including loading,
   empty, unavailable and error states. Queue navigation and counts work in five
   languages on desktop/mobile and with keyboard focus.
2. Each domain queue uses native current-head, review, source-rights, ownership,
   pause/mute and Today-window eligibility, exactly as the shared Today counts.
   Pagination is bounded and continues across sparse filtered pages; a revoked
   cursor or changed account cannot expose another user's or workspace's records.
3. Open change links identify the saved evidence version. Opening a notification
   is not a review or a source request. Existing explicit domain review actions
   update both Today and the centre; an old version cannot review a new one.
4. Pollen currently links only to its monitor. Add a permission-checked exact-entry
   reader and a pinned entry panel so a link remains meaningful after later
   samples arrive. Preserve current monitoring state separately from old evidence.
5. Source outages do not become an all-clear. Disabled/unavailable counts are not
   zero and do not hide navigation. Reads do not collect, send, grant, activate or
   generate. Preserve existing legal brief/reading controls and digest links.
6. Verify native all-domain parity, exact Pollen evidence under update/revocation,
   private scoped cursors and failure handling, existing legal regressions, the
   exact API lint gate, root web build and populated five-language browser checks.

Broader MV2-022 shared email/noise preferences, recap-policy acceptance and live
source/user acceptance remain open. C4/customs and grants remain deferred. This
feature has passed local code acceptance; source coverage and activation are not claimed.

## Implementation and acceptance evidence

The authenticated header opens all nine Monitoring queues and the existing legal
feed. Counts and pages share the native review projection; a section stays visible
when its queue is unavailable. Pages carry an organization/user/domain-scoped
cursor and native source/ownership checks run again on every request. Reading
does not collect data, change a review, send mail or grant source access.

Pollen notification and Today links now identify the exact saved entry. The
selected monitor shows its retained evidence separately from current state,
including later-entry/configuration indicators. Source permission is rechecked
on read; withdrawn evidence is redacted and raw downloads remain permission-gated.
An explicit review targets that entry and the existing optimistic review version.
Changing monitors clears the stale entry locator. Account, workspace, role and
page lifecycle changes clear private notification state.

Local checks on 14 September 2026:

- 48 affected API checks passed in 86.22 seconds, including all-nine native queue
  parity, paged counts, read-only snapshot behavior, private scoped cursors,
  Pollen version retention/revocation and subject API regression.
- The final 13 subject HTTP/backlog checks passed in 31.86 seconds, including
  anonymous no-store rejection and cross-owner exact-entry route protection.
- The exact API Ruff gate and root isolated `monitoring-notifications` build
  passed. Generated Next check-directory changes were removed after verification.
- 65 populated built-browser/axe checkpoints passed for all nine queues and pinned
  Pollen across five locales, sparse pages, explicit review, source redaction,
  failure/unavailable/empty states and viewer scope.
- Existing legal notifications passed 80 axe checkpoints and 20 desktop/mobile,
  viewer/admin journeys. Today counts passed all 22 browser/axe checkpoints.
- All three draft-locator tests passed. Browser evidence uses synthetic APIs and
  disposable local Chrome sessions; no production source calls or messages occur.

The browser driver waits for authenticated rendering and finite dialog animations;
number expectations use Chrome's own ICU rather than Node's different Romansh
locale support. Axe reported no violations; other incomplete checks are retained
in local JSON and are not a claim of certified accessibility. Independent language
review, real-user acceptance, source readiness, exact deployment and broader
MV2-022 email/noise policy acceptance remain open.
