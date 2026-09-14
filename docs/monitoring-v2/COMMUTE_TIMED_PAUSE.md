# Visible Commute notification pause — MV2-018/039

Scope: complete the visible calendar-day pause journey in Commute settings and
the shared Monitoring Centre. The persisted `paused_on` mechanism already
suppresses today's signals and delivery. Previously the Centre showed only
`active`, while settings offered Continue today without showing the end time.

Use existing owner/organization, lifecycle, source and delivery contracts.
The pause ends at the next Europe/Zurich calendar midnight, which may be 23 or
25 elapsed hours after the start of a DST transition day. The saved weekdays,
journey windows and source availability then apply; midnight is not a promised
notification or successful source observation. Source checks may continue.
Permanent pause and archive never receive a timed-resume promise.

Acceptance:

- Both readers show the current notification pause and exact Zurich end time.
  Five-language copy distinguishes it from source checking and permanent pause.
- Continue today removes it through the existing versioned command; reload
  preserves a current pause, and expiry requires no database write or scheduler
  job. Stale/future pause dates and nonactive monitors do not imply a pause now.
- Midnight expiry, DST short/long days and year rollover are verified. An open
  notice updates at expiry; revisiting the page rechecks private state.
- Section disablement, membership loss and owner isolation remain effective;
  no source activation, duplicate notification or mutation occurs from a read.
- Tests cover actual API/persistence and the built settings/Centre journeys,
  including mobile, keyboard and five locales.

MV2-018/039 retain broader IN PROGRESS acceptance. Shared business ownership,
live transport access and human acceptance are not established by this feature.

## Verification — 14 September 2026

- Combined pause, lifecycle/persistence, Centre, deterministic rules, delivery,
  Today and mandatory backlog suite: **127 passed** in 104.09 seconds. Synthetic
  accounts/sources only; the existing Starlette/httpx deprecation warning remains.
- Exact `ruff check services/api deploy/release_manager.py`: passed. New UI/copy
  formatting and the root production build `commute-pause` passed, including
  translation, navigation, resources, reports, help, lint and TypeScript gates.
- Built Centre browser: **8 full-document axe checkpoints** passed, plus the
  existing inventory/filter/deep-link/revocation journey. New pause checks cover
  all five locales at 390px, exact time/link, expiry while open, disabled-section
  redaction and revoked access. No source collection or mutation occurs.
- Built Commute browser: **25 full-document axe checkpoints** passed, including
  the full existing configuration, preview/start, review/reopen, pause/edit,
  email-consent/preview, archive/delete, mobile and viewer workflow. New checks
  exercise pause notice persistence, Continue today removing it, exact expiry
  and the notice in all five languages on desktop/mobile.
- The initial new API revocation assertion expected 403; authoritative session
  revocation returns 401, and the corrected full run passed. The initial build
  flagged the hard-coded timezone label; the shared constant passed the gate.
  A browser-test race after email save was repaired by awaiting the remounted
  collapsed settings before reopening; the complete rerun passed.

The migration-free additive reader derives `notification_pause_until` from the
existing active monitor and stored date. It adds no queries, jobs, source values,
consent or mutations. Expiry does not transfer review state or send mail. The
client notice also stops claiming a current pause when its deadline passes.
Archive/permanent pause have no automatic restart. Source switches and all nine
navigation entries remain enabled as configured.

The feature is published by the commit introducing this evidence. Actual main
site activation and human acceptance remain separate; a successful push alone
does not close either parent task. No retired deployment was touched.
