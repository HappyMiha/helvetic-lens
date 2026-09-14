# Business item responsibility and decision comments

## Scope recorded before implementation — 14 September 2026

This complete feature contributes to MV2-013 and MV2-021: a workspace can assign
an individual Tender dossier, IP candidate or Auction item, retain comments on
the evidence reviewed, and record a native decision with its owner and comment
in one transaction. Monitor collection responsibility remains separate.

Dependencies: the native three-domain evidence/decision workflows and explicit
business monitor sharing are implemented on main (`f07b164`). This feature uses
those existing source contracts and grants; it does not acquire new sources,
infer permission, enable personal email or send external submissions. Tests use
permitted synthetic sources. Live source readiness and independent human
acceptance remain open. C4/customs and grants remain deferred.

## Required user outcome and acceptance

1. Each native item detail has a five-language, keyboard-accessible responsibility,
   comment and decision panel. An administrator can assign an active workspace
   administrator (or leave the item unassigned), comment without marking it
   reviewed, or save a native decision together with assignment and comment.
   Private monitors only permit assignment to their creator. Viewers can read
   within their permitted audience but cannot mutate or enumerate assignees.
2. Every action appends actor, responsible user, timestamp, native item version
   and evidence binding. New source/profile revisions never silently review new
   evidence or rewrite earlier comments. Old decisions remain visibly historical.
   Existing native decision entry points retain these audit snapshots too.
3. Concurrent assignment, decision, source revision, source revocation, membership
   change or scope withdrawal cannot overwrite a colleague or leak evidence.
   Comments and assignment updates preserve native following/reminder/review
   state. Combined decision/assignment/comment writes are atomic and failed
   writes leave no orphan audit. Deactivated assignees remain identifiable as
   unavailable and unresolved work can be reassigned.
4. History is bounded and paginated. Current source rights and the particular
   historical evidence audience are rechecked on reads: authenticated SIMAP
   document-derived comments cannot leak to a colleague through an older entry.
   Source-unavailable content is withheld honestly. No original document text is
   copied into the audit binding. Comments are plain text with a strict limit.
5. Assigned-to-me/unassigned filters in the native three-domain review lists make
   unfinished work findable without crossing organizations or personal audiences.
   Old links and the existing regulatory Matrix continue working.
6. Required verification: real native repository/API/privacy/reopening tests,
   PostgreSQL migration and concurrent-write rehearsal, exact API lint, web
   build and browser journeys across all three domains, five locales and mobile/
   desktop. Browser checks cover conflict/revocation, late responses, assignment,
   comment-only and combined native decisions. No real email is sent.

## Implemented outcome

Open an individual record in Tender Watch, IP Watch or Ticino auctions, then
expand **Responsibility and decision notes**. Save responsibility/comment alone,
or choose the native decision and save all three together. The native lists have
**All assignments / Assigned to me / Unassigned** filters. Existing item links
and native quick decisions still work. Comments are plain text, limited to
4,000 characters, and never send an external message, bid or legal instruction.

`assigned_user_id` belongs to each native item, independently of the monitor's
collector responsibility. Additive migration `7a5d3e479fbc` preserves existing
items as unassigned and adds `business_item_work_events`. History stores exact
native sequence/revision/profile/fingerprint references, actor, assigned person,
comment, decision and timestamp. It stores no source document body. Existing
decisions are not retroactively given invented comments, owners or timestamps.

The new GET/POST `/api/monitoring-centre/business/{domain}/{monitor}/items/{item}/work`
uses existing authentication, CSRF, tenant scope and enabled native routes. Reads
are no-store, pages are bounded to 50, and writes share the native item version
and parent locks. Private items can be assigned only to their creator; shared
items accept active administrator members. Inactive members remain identified
in readable history. Notes never change reviewed sequence, following or reminders;
native decisions keep their own source/decision guards and append audit inside
the same savepoint. Failed audits roll back owner and decision together.

Current evidence must be permitted before content or assignee details are shown.
Each historical entry independently rechecks its original evidence audience.
An authenticated SIMAP document comment stays hidden from a colleague even after
the current dossier returns to a public version. PostgreSQL transaction locks
also serialize public-source restriction insertion with reads/decisions when no
restriction row exists yet. Auction unfollow remains possible after source loss
and when the new work-history capacity has been reached.

## Verification and release boundary

Recorded local evidence includes the real three-domain API/CSRF/role journeys,
62 affected API/native/document tests, retained native repository/workflow
regressions, and explicit reopening/private-document history checks. The earlier
test fixture's two Tender title edits were corrected to the actual `project-info`
shape; all four targeted reopening/history cases then passed. No production
behavior was relaxed to make those fixtures pass.

The isolated root `npm run build` and exact
`ruff check services/api deploy/release_manager.py` passed. The browser suite
passed 75 full-document axe checkpoints across all three domains, five locales
and two viewport sizes, including comment-only versus combined decisions,
viewer/member-list privacy, paginated history, conflicts, unavailable sources,
withdrawn access, native assignment filters and late responses after pagehide.
Private assignment uses the authenticated creator directly and never needs to
enumerate colleagues, including when the creator is beyond a member-list page.
The existing Tender browser suite passed 36 checkpoints. Four additional visual
checkpoints and 390/1440 screenshots were inspected: readable, wrapped controls
and history with no horizontal overflow. Axe incomplete findings remain in the
reports; this is not independent human accessibility or translation certification.

Browser contracts come from real synthetic native workflows in disposable SQLite
(`scripts/prepare_business_item_browser.py`); the browser intercepts API requests
and sends no real mail or source requests. `scripts/check_business_item_postgres.py`
accepts only an empty localhost `helvetic_business_item_check` database. Its
populated downgrade/upgrade and metadata checks, competing native decisions and
observed lock-wait scope withdrawal passed on PostgreSQL 17. The final rehearsal
also observed a native decision waiting for a public source withdrawal to commit:
the decision then failed, with no changed item version, assignee or audit event.
All 45 final item-work/source-rights/delivery tests passed after this hardening.
Both disposable PostgreSQL containers were verified by exact ID and removed;
no serving checkout, production data or running deployment was modified.

Reproducible checks:

```text
python -B scripts/prepare_business_item_browser.py
# Build and browser use the same isolated HELVETIC_LENS_CHECK_BUILD selector.
npm run build
npm run check:business-item:browser
python -B scripts/check_business_item_postgres.py --database-url <empty-localhost-scratch-url>
ruff check services/api deploy/release_manager.py
```

Local terminal logs: `.tmp/business-item-final-api.log` (62),
`.tmp/business-item-rights.log` (45), `.tmp/business-item-source.log` (4),
`.tmp/business-item-postgres-final.log`, `.tmp/business-item-build.log`,
`.tmp/business-item-browser-final.log`, `.tmp/business-item-visual.log` and
`.tmp/business-item-tender-browser.log`. Browser reports retain all axe findings
in `test-results/accessibility/business-item-work.json`; inspected screenshots
are `test-results/business-item-work-390.png` and `business-item-work-1440.png`.

New source credentials/permissions, exact production activation, physical account
deletion, broader shared/personal review states and cross-domain Inbox/batch
assignment remain outside this feature's verified result. MV2-013 and MV2-021
remain IN PROGRESS; all nine directions remain visible and C4 stays deferred.
