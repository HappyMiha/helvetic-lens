# First-run choice across all nine Monitoring directions

Whole-feature scope recorded 14 September 2026, before implementation. MV2-002
and MV2-017, with the existing personal-workspace boundary from MV2-004.
Registration already permits an empty company name, but its getting-started
destination offers only legal topics, documents and exploration. A new person
must be able to choose a Monitoring direction and enter its existing configuration
journey, return later to that choice, and distinguish an intention from a running
monitor or verified first value.

Acceptance:

1. All nine active directions appear in the first-run guide, grouped by personal
   and business use, in all five languages. Pollen appears first. C4 stays absent.
2. Choosing a direction persists only that authenticated person's choice in the
   current workspace, then opens its existing configuration screen. Save failure
   keeps the guide and supports retry. No monitor, source job, email consent,
   evidence milestone, bid or shared company setting is created by the choice.
3. Reload/login, defer/resume and workspace switching retain/isolate the selection;
   returning to a legal choice clears it. Viewer selection does not grant write
   access. Old responses cannot navigate or populate a changed user/workspace.
4. The guide offers a clear continuation link and explains source checks, preview,
   explicit Start and separate email consent. Unavailable sources do not hide a
   direction or count as success. Legacy recorded progress remains available and
   is distinguished from Monitoring setup. Existing first-value metrics stay open.
5. An additive database migration preserves existing onboarding/watch data and
   legacy intent values. Verify API roles, CSRF, idempotence and isolation, actual
   migration behavior, five-language mobile/desktop navigation and existing legal
   onboarding regressions. Required API lint and root build precede publication.

Source readiness is inherited from the native sections. No new source access is
needed to choose a direction, and no source coverage is claimed by this feature.
Independent language/user acceptance and measured time-to-first-value remain open.

## Implemented behavior and local acceptance

The guide shows six everyday and three business choices, with Pollen first.
Registration explains the existing optional company field. Choosing a template
uses the personal onboarding endpoint, saves an explicit template, then opens
the native section. The original legal intent remains `explore` for compatibility;
the additional nullable column records the precise Monitoring selection. Repeating
the choice is idempotent; defer retains it, and choosing a legal path clears it.
The guide links back to the saved setup and distinguishes legal milestones from
Monitoring/source acceptance. Viewer selection grants no configuration permission.

Role/account/workspace changes remount the guide; pending writes are aborted on
unmount/pagehide, and stale responses cannot navigate a different session. This
does not undo a choice already committed by the server. Reopening reads its actual
saved state. No source/monitor activation or delivery consent is inferred.

Verification on 14 September 2026:

- The first affected API run found a missing Cache-Control header on personal
  onboarding responses. The outer response middleware now applies private
  no-store to onboarding reads, writes and denial/error responses.
- Corrected affected API acceptance: **31 passed, 2 skipped in 75.92 seconds**.
  It covers all nine choices, repeat/defer/resume, legal return, invalid and forged
  inputs, viewer CSRF, membership/workspace isolation, login persistence, passive
  reads, no source/model/job/mail/milestone side effects and migration preservation.
- An empty isolated **PostgreSQL 17** rehearsal passed simultaneous duplicate
  first choices, real downgrade/upgrade with retained legacy state, direct database
  C4 rejection and the all-nine personal-intent journey. Its runner refuses remote
  hosts, other database names and nonempty databases. SQLite skips do not count
  as PostgreSQL evidence; this separate execution supplies the relevant evidence.
- The exact API Ruff gate, root isolated `monitoring-first-run` build and changed
  frontend formatting checks passed. Generated Next build-directory changes were
  inspected and removed.
- **35 built-browser/axe checkpoints** passed, including five registrations with
  an empty company, **90** native direction handoffs across five locales and
  mobile/desktop, saved return links, failure/retry, viewer scope and an aborted
  late response. **40** existing onboarding axe checkpoints and 20 legal journeys
  passed. The rendered screenshot was inspected. These are synthetic accounts
  and APIs, with no real source requests or email. Axe incomplete findings remain
  recorded; independent accessibility/language review is not certified.

Reproduction: run the affected pytest modules `test_monitoring_first_run`,
`test_personal_onboarding`, `test_onboarding_milestones`, the backlog invariant,
the root build, `npm run check:monitoring-first-run:browser`, and
`scripts/check_monitoring_first_run_postgres.py --database-url <empty-local-test-db>`
against the required `helvetic_first_run_check` database. Use the same isolated
build selector for build and browser checks.

Publication and exact activation remain distinct. Fresh authenticated release
Refresh still reports `1188f18190e0` active and `660edacc8e7a` Deploying. No
production run was interrupted/retried. Broader MV2-002/017 first-value measurement,
source readiness, shared business ownership and human acceptance remain open.
