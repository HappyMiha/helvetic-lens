# Explicit batch review of native Monitoring evidence

Status: implemented and locally verified release candidate. Scope: MV2-021 acceptance criterion 2,
with native review history and privacy under MV2-013. All nine active directions
participate; customs and grants remain deferred. Existing readers, native review
commands and the authenticated notification queue are dependencies.

## Acceptance contract before implementation

1. Select at most twenty visible notifications on one queue page. Opening,
   selection and preview perform no review, source collection or outgoing message.
2. Preview the selected native evidence and its exact identity. The user explicitly
   applies the displayed actions. Personal directions use Reviewed; Tender and
   Auctions require an explicit native decision for each record, without a default
   bid/no-bid. IP preserves its native review choices. Assignment and comments are
   retained; no source state, mute, consent or external action is inferred.
3. Bind the apply operation to every previewed native version, source/profile and
   locale. Recheck rights, membership and write role. Reject the entire bounded
   batch when any selected record changed or became unavailable; do not mark a
   newly arrived version reviewed. Duplicate target records are rejected.
4. Use existing native review commands and histories in one transaction. No
   independent bulk-review truth or replacement source record is introduced.
   A lost response must require a fresh preview rather than blind automatic retry.
5. Clear selection/preview after page, direction, identity, workspace, role or
   locale changes, page hiding and access failures. Late responses cannot restore
   stale evidence. Report successful application before refreshing native counts.
6. Cover real native fixtures in all nine directions; stale source/configuration,
   changed decision, source withdrawal, cross-user/workspace/viewer denial,
   atomic rollback and concurrency. Exercise the built UI on mobile/desktop in
   all five locales, keyboard, invalid selection, failure/retry and late response.
   Run exact API lint, affected native tests, root build and backlog invariant.

Publication and verified production activation are distinct. Broader Inbox
aggregation, full parent-task acceptance and independent human/source review
remain open until their own requirements are proved.

## Implementation and local evidence

Every native notification carries a typed target instead of reconstructing IDs
from URLs. The queue offers selection to authenticated administrators, limited
to twenty current-page records. Preview uses the nine native rights-aware readers
and returns exact literal source fields, units and a binding to the complete read,
record and locale. The original-evidence reference rechecks the same binding.
It cannot silently navigate to a newer version after the preview was displayed.

Explicit apply locks monitors/items in stable order, validates every binding and
choice, then invokes the existing native commands in one transaction. Native
review histories and business responsibility are preserved. Pollen retains its
existing same-signal review propagation across the same owner's duplicate monitors;
this does not mark a newer material signal reviewed. No independent batch state,
model call, source collection or external submission is introduced. HTTP success
is returned only after commit. A repeated old request receives a conflict.

The five-language panel clears private previews and selection on context changes,
pagehide, visibility loss and request failure. Failures explicitly explain that
a lost response does not prove nothing was saved. The success message precedes
normal Today/count refresh. Source fields are escaped, business decisions have
no default choice, and source state/mute/email consent remain separate.

- The final combined native/API/notification/backlog suite passed **34 tests in
  54.99 seconds**. It exercises all nine real native workflows, actual HTTP
  persistence/replay, CSRF, private/workspace/viewer boundaries, three business
  source updates and withdrawal, invalid selections and rollback after a later
  native action fails. HTTP acceptance caught a missing outer commit, which was
  corrected before publication; no assertion was weakened.
- An isolated PostgreSQL 17 rehearsal passed opposite-order, two-user batches:
  exactly one complete two-item winner, one conflict, a single actor's two audit
  records and no deadlock. The labelled disposable database/container was removed
  after verifying its exact identity. No serving database or volume was touched.
- The isolated root `batch-review` build and exact API Ruff gate passed.
  Generated Next directory settings were reviewed and restored.
- The final compiled browser suite passed **186 full-document axe checkpoints**
  across nine directions, five locales and 390/1440px widths, explicit decisions,
  source conflict/denial, wrong context, twenty-item limit, real Space/Enter
  keyboard interaction, viewer mode and late pagehide response. The harness waits
  for authenticated hydration and uses a complete native Enter event. Desktop
  and mobile previews were captured and visually inspected. A final 21-test
  notification/native HTTP/backlog run passed after tightening target-field
  reads and synchronizing the parent task's index and detail.

Browser fixtures are synthetic and grant no live source coverage. Axe incomplete
checks remain in the report; independent screen-reader/language/user acceptance
is not claimed. Reproduce with `npm run check:monitoring-batch:browser` against
the same build selector and `scripts/check_monitoring_batch_postgres.py` against
an empty loopback-only `helvetic_lens_batch_check` database. Broader parent tasks
remain IN PROGRESS, and a push is not verified production activation.
