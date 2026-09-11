# Complete Pollen Watch feature — engineering candidate

User scope decision, 2026-09-11: take the entire remaining Pollen block as one
feature. This supersedes further publication of individual draft controls or
technical backlog slices. Worktree `mv2-031-pollen-complete`, branch
`codex/HappyDucky02/mv2-031-pollen-complete`, base `eaafb6a`.

## Outcome and release boundary

Complete Personal → Pollen Watch → configure → preview → explicit Start → initial
official state → Today/material change → explanation/evidence/history → Review or
Not relevant → later material reopening, with pause/resume/archive/delete/export
and independently consented notifications. Reuse the existing private draft UI,
versioned numeric rules and durable job system. Observations and forecast remain
different series. Unknown, stale and unavailable never mean zero or resolved.

MV2-069 source contracts, MV2-070 C01–C08, MV2-030 connector, MV2-031 journey and
MV2-071 readiness are one engineering work package. Their acceptance dependencies
remain intact: implementation can proceed together, but downstream acceptance
does not bypass upstream source or independent human gates. No intermediate
commits/releases for this implementation document, a component or a timer.

## Implementation and acceptance checklist

- [x] Server-owned, versioned channel admission; bounded official downloads,
  immutable artifact hashes, strict CSV/GRIB identities and correction handling;
  shared fetches with bounded retry, freshness and operational health.
- [x] Durable private lifecycle with explicit idempotent Start, initial state,
  configuration revisions, resume without replay floods, owner/membership checks
  at API, execution, evidence and delivery boundaries.
- [x] Separate live state and evidence from existing `draft_rehearsal` rows.
  Exact numeric hysteresis/rapid rules, approved period-specific category scales,
  correction/out-of-order/restart behavior and revisioned review/reopening.
- [x] Today/current state, measured versus forecast times, why/prior/current,
  source attribution and private history. Five-language mobile/keyboard flows;
  no medical advice or requirement for an LLM.
- [x] Transactional delivery intent, explicit email consent independent of saved
  draft preferences, in-app deduplication, quiet hours/DST/digest, unsubscribe,
  current permission/rights/review checks and no recovery notification flood.
- [x] Additive migration, isolated rollback/restore/restart and targeted legacy checks;
  retention/deletion/export, rollout-off recovery without private data loss.
- [x] Integrated feature checks, fixes, English evidence and backlog consistency.
  The candidate is prepared for one feature commit/task push and reviewed
  fast-forward Monitoring integration through the existing automatic deployment.
- [ ] Actual release identity, permitted official birch/grass forecast proof,
  period/method category approval, operating source gates, independent language,
  accessibility and human workflow review before final user-readiness/DONE.

Checked implementation items record existing code and isolated evidence. They do not claim approved operation, independent acceptance or an activated release.

## Evidence boundaries

Retained 2026-09-11 source captures are dated evidence, never live fallback data.
Synthetic tests must stay isolated and explicitly labelled. Source admission is
operator-controlled, never accepted from a browser payload. A source gate may be
open while its implementation is tested; tests cannot manufacture source rights,
seasonal coverage or a human review. No production migration, activation, message
or invitation is performed by a local rehearsal. Existing authorized automatic
deployment remains the release mechanism; do not restart it while it is running.

## CORE-20 implementation trace

| Criteria | Implementation and inspectable evidence | Remaining acceptance |
| --- | --- | --- |
| CORE-01, 02 | Station-guided creation, server-owned coverage preview, separately gated Start; source and live HTTP tests | Approved source operation and unassisted creation |
| CORE-03, 04, 12 | Immutable current/previous/baseline, detected/valid/issued/fetched times; runtime and five-language browser checks | Independent timestamp comprehension |
| CORE-05, 15 | Exact Decimal threshold/hysteresis/rapid rules, separately approved category scales, no inferred extra rules | Approved category scales and seasonal evidence |
| CORE-06, 07, 20 | Material reason on card; one expansion opens prior/current, rule, source hashes and history | Independent explanation comprehension |
| CORE-08 | Shared fetch leases, private input/material uniqueness, owner-scoped logical signal deduplication in Today and email | Declared pilot workload measurement |
| CORE-09, 10, 16 | Reviewed, not relevant, continue, action required; immutable reviews and later reopening; duplicate monitors retain their own histories | Independent review/reopening exercise |
| CORE-11 | Failed refresh warning with still-fresh cache; original time retained; quiet recovery baseline | Operational outage/recovery observation |
| CORE-13, 14 | Deterministic facts/rules, no AI prerequisite or generated pollen value; revisioned export | Independent evidence review |
| CORE-17, 18 | Existing organization/session, subject, durable job and Today contracts; isolated source parsers/decoder | Broader template extensibility remains parent scope |
| CORE-19 | Pollen joins existing mixed Today page and refresh control; browser navigation | Independent mixed legal/Pollen review |

## Verification ledger

All API/browser fixtures are isolated and synthetic except explicitly retained
source bytes. No test sends real email, invites participants or sets production
source policy. Publication and actual activation remain distinct from these checks.

- Production frontend build, including i18n, shell, resources, reports, help,
  types and Next compilation passed after the final four-state/source-warning UI.
- Browser journey previously passed 47 full-document axe checkpoints including
  five runtime locales, mobile width, lost Start response with the same key,
  no implicit consent, evidence, review/reopening, pause/resume, source/membership
  withdrawal and Today navigation. The final four-state/source-warning rerun also
  passed all 47 checkpoints.
  Automation does not establish native-language or screen-reader acceptance.
- Isolated PostgreSQL 17 passed 64 runtime/delivery/operations/source/forecast/
  subject checks, then 14 stale paused-editor and last-moment delivery checks.
  Final staged-schema PostgreSQL passed 61 cases, including simultaneous duplicate
  delivery, peer isolation, four review states and source-failure recovery.
- Actual pg_dump/pg_restore rehearsal restored private current state, immutable
  evidence, review, run identity and consent after deletion; repeated migration
  succeeded. Final schema rehearsal also passed with the fourth review state and
  a 458,774-byte snapshot. This used a disposable database, never a serving volume.
- Canonical decoder and offline HTTP replay matched retained 2026-09-11 ragweed
  artifacts at 15 stations exactly. Modified density hash returned generic 422.
  See canonical decoder/RPC JSON evidence. Birch/grass and rights remain open.
- Merged production, tunnel and Monitoring Compose validated with synthetic env.
  Native decoder has no exposed port, secrets or database mount. First automatic
  cold-build activation and rollback remain unverified.
- The real web Docker image passed after fixing the preceding station feature's
  missing build-only source-proof fixture. The test remains mandatory and the
  final runtime stage still contains only the standalone application/assets.
- Final standard-path run passed **346 Pollen/Monitoring tests** in 183.41 seconds,
  including the actual final migration and mandatory index/detail consistency.
  Final PostgreSQL standard-path checks passed **6 tests**: prior-schema identity
  preservation through downgrade/upgrade, stale runtime conflict and concurrent
  cross-monitor signal/delivery isolation. These cover the last model/code changes.
- Final staged-schema SQLite passed 34 runtime/delivery/operations/live-HTTP/dedup
  cases. This includes private job list/detail/cancel/retry protection from a peer
  in the same workspace. Final Ruff passes API, tests and the native HTTP server.
- The broader Windows API run finished with **2303 passed, 25 skipped, 2 failed**
  in 3260.57 seconds. It loaded the earlier feature model before the last schema
  additions, so it is not a final all-green result. The failures were the unchanged
  vague-question latency test (1.558 seconds against <1 second) and the unchanged
  release-journal success test (`WinError 5` replacing temporary `status.json`).
  An isolated unchanged rerun of the latency case plus all release-history tests
  passed **9/9** in 4.54 seconds. No assertion, timing bound, skip or deployment
  gate was weakened. These environment-sensitive observations remain recorded;
  the deployment's full API gate must still pass on the actual candidate.

## C5 completion boundary

C01 creation/Start, C02 observation/forecast, C03 rule explanation, C04 Today and
deduplication, C05 review/reopening, C06 delivery, C07 lifecycle/history and C08
export/deletion are implemented in one feature worktree. MV2-069/070/030/031/071
remain IN PROGRESS. The pilot packet is [POLLEN_PILOT_RUNBOOK.md](POLLEN_PILOT_RUNBOOK.md).
Its decision stays HOLD until official-source, independent human, operational and
actual-release evidence is recorded. Successful local checks do not close them.
