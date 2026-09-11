# MV2-072: rolling-window fixture repair, 11 September 2026

Host: HappyDucky02. Task branch: `codex/HappyDucky02/mv2-072-digest-clock`,
isolated worktree based on Monitoring `bbce3e2`. Parent remains IN PROGRESS.

Automatic candidate `9034523` failed its API gate with **50 failed, 2067 passed,
12 skipped** in 75m16s. Its retained controller log
`20260911T082211Z-903452397c18.log` lists 49 digest/brief failures and the old
backlog consistency failure (already fixed by `2d07c09`). The abbreviated status
error contained only the last failures; investigation used the full log.

The shared `test_topic_matching.add_event` fixture supplied detection time
`2026-09-04T08:00:00Z`. After 11 September at 08:00 UTC, the actual weekly digest
correctly excluded that event. Topic, offline brief, recipient-language and reuse
tests therefore had no event to assert against. The existing pagination case
`test_topic_selection_pages_scope_deduplication_and_empty_continuation` failed
independently before the repair (`scanned=0`, expected 50).

The fixture now supplies detection time five minutes before its creation, before
matches, assessments and their evidence fingerprints are generated. Its historical
official publication date is retained: detection and publication are distinct.
The change is restricted to synthetic test data; application period, privacy,
withdrawal, language, source evidence and digest delivery rules are unchanged.
Mail/provider interactions in these tests remain intercepted synthetic transports.

**81 focused regressions passed** in 2m47s, including all 49 previously failing
digest/brief cases. Verification covers the existing affected digest topics, saved briefs, offline
delivery, failed review/reuse cases, shared topic matching and digest period
boundaries. No test is removed, skipped or loosened. The mandatory actual-backlog
consistency check and targeted Ruff passed. Full automatic release of the repair
remains separate; do not infer it from focused checks or a push.

At the recorded 10:00 UTC checkpoint, the controller is testing `bd4fcc5` and the
public site still serves ready release `8d5e94b`. That active full run is left
alone; this repair and other ready development proceed independently. Monitoring
publication does not update main or the frozen hackathon tag.
