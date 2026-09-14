# Monitoring email preferences in one place

Whole-feature scope, 14 September 2026 — MV2-022/018.

Users select a saved private monitor in the Monitoring Centre and manage its
native email preferences there. All nine directions remain visible; only the
selected editor loads private settings. The eight separate email-policy domains
reuse their existing consent, schedule, quiet-hour, preview and CAS commands.
Pollen uses its existing versioned configuration and lifecycle: explicit pause
before changing a live schedule, save without activation, and separate explicit
resume/consent. Source coverage, monitoring status and email consent remain distinct.

Dependencies: existing owner-private inventory, native settings/preview APIs,
membership checks and final-send consent revalidation. No new consent store,
delivery engine or source permission is introduced. Legal digests retain their
own settings. This feature does not complete broader event/type priority controls,
cross-monitor delivery aggregation or human/live acceptance.

Acceptance before publication:

- Every direction opens the exact selected monitor's settings from the centre;
  opening/closing/filtering/list pagination causes no writes or email.
- Explicit save persists native settings; consent starts unchecked, off needs no
  consent, and source/verification restrictions remain visible. Preview sends nothing.
- Pollen schedule editing preserves station/rules, requires draft/paused state,
  handles current revisions, and does not implicitly resume or consent.
- A second monitor, locale/account/workspace/role change, pagehide, access failure
  or closed panel cannot retain another selection's settings or late write response.
- Test actual built UI at mobile/desktop in five locales, failures/retry, viewer
  mode and consent boundaries; run affected native API regressions, root build,
  formatting and the backlog invariant. Record exact publication separately from
  activation and source/human acceptance.

## Implementation and verification — 14 September 2026

The shared `/monitoring/email` page is linked from the Monitoring Centre and
Digests. It lists the current owner's monitors with direction filtering and
bounded continuation pages. Exactly one native editor is mounted at a time;
closing, changing selection/filter, pagehide or changing session/locale removes
that editor. Read-only users retain the existing native permission boundaries.
No new backend write route, source request or email consent is introduced.

Pollen edits retain the exact station, rules and timezone. Its saved schedule and
consent are visible separately, with explicit pause/save/resume and native
unsubscribe/mute controls. Resume is disabled while the schedule is unsaved.
Source readiness is rechecked by the existing lifecycle API. Other directions
reuse their existing schedule, quiet-hour, consent and due-item preview forms.
Tender now aborts pending work when its editor closes and clears stale settings
on a failed write/preview; invalid local quiet hours can be corrected in place.

- **61 native API regressions passed in 137.23 seconds**, covering Pollen
  configuration/lifecycle/delivery, private inventory, Tender HTTP operations
  and the backlog invariant. Existing fake mailers never contact SMTP.
- Root isolated `monitoring-email-centre` build passed, including type checking
  and contextual-guide coverage. The initial build correctly required a new
  page guide; it was added. The exact API Ruff gate, changed frontend formatting
  and whitespace checks passed. Generated Next directory settings were removed.
- **97 built-browser/axe checkpoints passed**: all nine editors in five locales
  at 390/1440px, native consent/off and quiet-hour saves, Pollen pause/save/resume,
  unsaved-schedule protection, filter/preview, inventory pagination, version
  conflict, quiet-hour correction, late response, viewer and access removal.
  The first expanded pagination run had a test-harness expectation of nine
  initial rows; the fixture uses two per page. The expectation was corrected
  and the final expanded suite passed.
- Existing Tender journeys passed **36 browser/axe checkpoints**, including
  profile/save/start, follow/review, email and private/source boundaries. The
  existing Monitoring Centre passed **8 checkpoints**, covering five locales,
  mobile/viewer, filters, pagination and no mutations. Mobile and desktop
  screenshots of the new editor were visually inspected.

Browser checks use synthetic APIs and accounts. They do not prove real source
coverage or SMTP delivery. Axe incomplete findings remain retained; independent
accessibility/language review and human acceptance are not certified. Run
`npm run check:monitoring-email-centre:browser` against a build with the same
`HELVETIC_LENS_CHECK_BUILD=monitoring-email-centre` selector to reproduce.

Fresh authenticated deployment evidence records `660edacc8e7a` activated and
`c66e77fc7721` Deploying. This newer email-centre feature is not yet verified
activated. Broader MV2-022 priority/event controls, cross-monitor aggregation,
source rights and human acceptance remain open.
