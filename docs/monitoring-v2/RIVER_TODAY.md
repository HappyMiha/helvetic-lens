# River / Lake changes in Today — scoped MV2-033/019/021

Scope recorded before implementation, 14 September 2026: complete the missing
River Today and Impact Inbox journey using retained River changes and existing
exact evidence/review endpoints. Include latest change per development across the
owner's monitors, all/unreviewed filters, bounded stable pagination and an honest
unreviewed count. Paused and old-configuration evidence is explicitly historical;
archived monitors stay in their own history. No fresh measurement, all-clear,
source coverage or alert is inferred from a retained change. Empty results mean
no retained matching changes, not safe water conditions.

Dependencies: existing River lifecycle, source evidence, strict review version
checks and exact reader. This feature needs no external keys or source calls.
Five-language cards show source time/unit/quality, optional previous sample,
official danger versus personal threshold, detection time, correction/recovery,
review state and exact evidence link. Review and Not relevant use the existing
owner/role/CSRF/revision gate. Viewing a link changes no review state or consent.

Acceptance: owner/workspace isolation and fresh membership checks; no-store;
latest revision selected before review filtering; no invented baseline; equal-time
pagination and concurrent replacement; no acquisition/email writes on GET;
review conflicts refresh the reader; failures/access loss clear private cards;
page-return/focus refresh, five locales/mobile/keyboard, and existing Today/Inbox
remain usable. Run required Ruff, affected API tests, root build and browser/axe
checks, then update evidence and immediately commit/push main. Parent tasks and
production/human acceptance remain distinct; C4 stays deferred.

## Delivered behavior and verification — 14 September 2026

The main Today page and `/impact` now include River cards. Inbox starts with the
Unreviewed filter; both readers use the same retained changes, River-only count
and review endpoint. The API authenticates the current member, restricts both
monitor and event organization plus owner, then selects the latest change per
development **before** applying the unreviewed filter. A reviewed latest revision
cannot uncover an old unreviewed predecessor. Pages default to 30 and cap at 50;
immutable creation time/UUID ordering handles ties. The cursor checks private
ownership and the immutable time, including a subsequently replaced/reviewed
anchor. Archive removes a monitor from this queue, preserving its exact history.

GET performs only local SELECTs; it does not collect, mark read, activate a
monitor, change consent or enqueue mail. Cards distinguish retained recent/stale/
future samples, old configuration, paused monitors, official station danger,
personal thresholds, source units/datum/quality and detection versus source time.
No previous sample is invented. This is latest retained history, not a claim of
current source coverage or safe conditions. Raw source content and credentials
are absent. The existing exact evidence endpoint provides the full stored record.

Reviewed/Not relevant calls the existing versioned review action. A conflict
clears old cards and reloads current changes; another failure clears private
cards and allows retry. Viewer actions are absent. Principal/workspace/role or
page-return changes remount the private reader; focus and minute refresh recheck
read access. Existing Today and legal Inbox filters remain separate and the
contextual guides explain the distinction.

Verification on the introducing feature commit:

- **53 API tests passed** across the new River Today, River lifecycle/source and
  River email suites. Coverage includes ownership/workspace isolation, archived
  and paused histories, stale/future evidence, latest-before-filter, 53 equal-time
  changes and replaced cursor anchor, metadata SELECT-only reads, fresh membership,
  no-store, CSRF, viewer denial, exact links and review/new-revision conflicts.
- Root `HELVETIC_LENS_CHECK_BUILD=river-today npm run build` passed, including
  lint/type/translation/navigation/help gates. Required API Ruff and changed new
  frontend/copy/guide formatting checks passed.
- `scripts/check-river-today-browser.mjs` passed the built Today and Inbox journey
  with synthetic API data: five locales, mobile geometry, two-page navigation,
  exact links, keyboard reload, saved review, conflict, read/review failure,
  viewer restrictions and page-return/access redaction. **Eight full-document
  axe checkpoints** report zero violations and pass the prohibited-ARIA gate.
  Incomplete/manual audit checks are not an accessibility certification.
- The existing `scripts/check-interest-feed-browser.mjs` regression passed ten
  journeys (five locales at 390/1440px), including legal evidence/permalinks,
  scope/date precision, private reading states, pagination and failure recovery.
  The required final backlog consistency/customs-deferral test passed.

Reviewer: the implementing single agent; no independent native-language, live
source or human acceptance is claimed. Latest-per-development selection is local
to each monitor; this feature does not provide cross-monitor signal merging or a
global all-domain unread count. Shared business assignments/decisions and broader
MV2-019/021 acceptance remain open. MV2-033 remains VERIFYING. Push and actual
production activation are recorded separately. All nine sections remain enabled
and visible; C4 and grants stay deferred.
