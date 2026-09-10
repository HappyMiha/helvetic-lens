# Helvetic Lens: working on two computers

Read `docs/MULTI_PC_DEVELOPMENT.md` before Git mutations. These rules apply to
humans and Codex tasks on both computers; nested AGENTS.md instructions still apply.

- At task start inspect the OS, `git config --get helvetic.host`, branch, worktree,
  status and remotes. HappyDucky02 is the Windows development PC; HappySnowman is
  the Ubuntu production host. These are explicit aliases, not inferred usernames.
  Configure an unconfigured clone with `sh scripts/setup-git-workflow.sh <alias>`.
  Do not change an existing alias just to pass a hook.
- Fetch origin before starting a new task. Use a unique branch
  `codex/<alias>/<task-id-or-short-slug>` based on current `origin/main`.
  Concurrent tasks on the SAME PC also need different branches AND worktrees.
  Never switch another running task's checkout or discard its uncommitted work.
- Do not develop in the checkout serving production. On HappySnowman mark that
  checkout using the setup script's `--production` flag and create a sibling
  development worktree or separate clone. Development services must not reuse
  production ports, volumes, databases, secrets, or Compose project names.
- Commit on the task branch, test the actual changes, then push that branch.
  Installed hooks append `Development-Host: <alias>` without changing Git authors.
  Check other remote task branches before choosing a backlog item; branch names
  are coordination hints, not locks. Prefer independent tasks/files.
- Before integrating into main: fetch origin again, inspect incoming commits and
  merge `origin/main` into the task branch if needed. Preserve both tasks' intent,
  review the combined diff, and rerun affected tests after every integration.
  Push only a fast-forward update containing the latest remote main, or use a PR
  if server rules require it. A racing push rejection means fetch/merge/test again.
  Never use force-push, force-with-lease, hard reset, blanket ours/theirs conflict
  resolution, or bypass hooks to make a push succeed.
- Existing user authorization for routine tested commits/pushes persists; do not
  request confirmation again solely because there is another computer. Publishing
  code is not permission to restart/deploy production or run database migrations.
- Report the host alias, task branch, tests and pushed commit. A clean Git merge
  does not prove semantic compatibility; inspect overlapping behavior explicitly.

Hooks are local safeguards and must be installed per clone. They are not a server
security boundary. Keep them enabled; do not replace unrelated existing hooks.

## Single active product backlog

- Read `BACKLOG_MONITORING_V2.md` before selecting implementation work. It is the sole current backlog for all new features, fixes and acceptance work.
- Customs rates (C4), Swiss Customs, CURRENCY and MV2-026/027/061 are DEFERRED possible future scope. Do not start their discovery, licensing, implementation or acceptance work without a new explicit user scope decision recorded in the backlog; they do not block v2.0. Shared numeric rules for active cases remain required.
- First delivery is Pollen Watch: MV2-001 → MV2-069 → MV2-070 → MV2-030 → MV2-031 → MV2-071. The explicit C5 slices are independent of parent tasks for all sources/templates; partial C5 acceptance does not complete those parents. Do not substitute mock forecast for verified official forecast or wait for full-v2 business/pilot gates to start this scoped delivery.
- Use an MV2 task ID and its dependencies, source-readiness gates and acceptance criteria. Add any necessary new task or explicit subtask to that backlog before implementing it; do not silently expand scope.
- `BACKLOG_V1_ARCHIVE.md` is historical, not a parallel queue. Remaining HL acceptance is inherited through `docs/monitoring-v2/LEGACY_DISPOSITION.md`; mapping an item does not complete it.
- Preserve the frozen `v1.0.0-hackathon-mvp` tag, legacy evidence and compatibility. Planned v2 templates or source documentation must not be presented as implemented/live coverage.
- Update task status and requirement evidence after verification. Source-access, native-language, independent evaluation, hardware and pilot gates require their stated evidence; mocks or local static checks do not satisfy them.
