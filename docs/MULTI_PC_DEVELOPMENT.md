# Two-computer development without replacing each other's work

| Alias | Environment | Purpose |
| --- | --- | --- |
| `HappyDucky02` | Windows development PC | Develop and test task branches |
| `HappySnowman` | Ubuntu production host | Run production; develop only in a separate worktree/clone |

The alias is stored in **clone-local Git configuration**, not guessed from a user
name or the OS hostname. The Windows hostname may differ from `HappyDucky02`.
The tracked root `AGENTS.md` tells Codex to inspect this setting at each task start.
Open Codex in the actual repository/worktree. Start a new task/session after pulling
these instructions; an already running task should explicitly read the updated file.
See [Codex project instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
and [Codex worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees).

## One-time setup on each clone

Run from the repository root (Git Bash / a shell with Git's `sh` on Windows;
the normal terminal on Ubuntu). No Python/Node installation is needed for hooks.

```sh
# Windows development clone
sh scripts/setup-git-workflow.sh HappyDucky02

# Ubuntu DEVELOPMENT clone, not the directory running production
sh scripts/setup-git-workflow.sh HappySnowman
```

The script installs the versioned `.githooks`, sets `pull.ff=only` and
`push.default=simple`, and refuses to replace another hook setup or silently
change an existing host identity. Git does **not** install hooks/config by cloning
or pulling; run setup once on HappySnowman as well. Worktrees of an initialized
clone share its alias and hook configuration; use separate clones on different PCs.

Verify:

```sh
git config --get helvetic.host
git config --get core.hooksPath
git status --short --branch
git worktree list
```

## Each task gets its own branch and working directory

First check for uncommitted changes and other running tasks. Do not stash, reset,
overwrite or switch their work. Fetch the remote before selecting a task, and
inspect remote `codex/*` branches to avoid implementing the same backlog item.

For a clean, otherwise idle DEVELOPMENT checkout:

```sh
git fetch origin
git switch -c codex/HappyDucky02/hl-094-topic-matching origin/main
```

On the other PC use e.g. `codex/HappySnowman/hl-095-topic-editor`.
For concurrent tasks on one PC, create another working directory instead of
switching the first task's branch:

```sh
git fetch origin
git worktree add -b codex/HappyDucky02/hl-095-topic-editor ../hl-095-editor origin/main
```

Use a different task slug/suffix if a branch already exists. Branch names show
ownership but are not locks or a substitute for coordinating overlapping features.

Develop, run the affected tests, review the diff and commit on the task branch.
Hooks add a trailer without changing `user.name` or `user.email`:

```text
fix(topics): preserve matching continuation

Development-Host: HappyDucky02
```

Inspect it with `git log --format=full`. Git tags remain for releases, such as
`v0.2.0`; a tag identifying a computer would not prevent history replacement.

## Publish and integrate without losing remote changes

```sh
git push -u origin HEAD
git fetch origin
git log --oneline HEAD..origin/main
git merge origin/main
# Review the combined changes and rerun affected tests if main changed.
git diff --check
git diff --stat origin/main...HEAD
git push origin HEAD
git push origin HEAD:main
```

The final command is an ordinary fast-forward push; it does not switch the current
task branch or another worktree's `main`. Existing authorization to publish tested
tasks does not need repeating. If GitHub later requires PRs, use a PR instead.
Do not automatically deploy merely because code reached `main`.

The pre-push hook freshly fetches `main` from the exact push destination and checks
that its tip is an ancestor of the proposed update. If another PC wins the race,
fetch/merge/review/test again. Do not use `--force`, `--force-with-lease`, `--no-verify`,
disable hooks, hard-reset remote changes away, or resolve all conflicts with one
side. Resolve specific conflicts while preserving both tasks' behavior. Even a
conflict-free Git merge can combine incompatible code, so tests and review matter.

Hooks also reject direct commits on `main`/detached HEAD, commits or pushes under
another host's branch prefix, non-fast-forward task updates, main deletion and
replacement/deletion of release tags. Host-owned task branch deletion is allowed
after integration. The hooks do not run tests or prove a commit was reviewed.

**Server protection is the last line of defense:** protect GitHub `main` against
force pushes and deletion, including administrators. Ordinary fast-forward pushes
can remain enabled without mandatory PR approvals. Local hooks are bypassable and
cannot provide that server guarantee by themselves, especially for a racing forced
push. A fresh-main check is not a distributed lock. Repository administrators can
still change protection settings; this workflow prevents accidents, not a hostile
administrator or intentional semantic removal of code in a new commit.

## Keep HappySnowman's production checkout out of development

After installing these files in that checkout as part of a normal, planned code
update, mark it explicitly:

```sh
sh scripts/setup-git-workflow.sh HappySnowman --production
git fetch origin
git worktree add -b codex/HappySnowman/hl-095-topic-editor ../helvetic-lens-dev-hl095 origin/main
```

Open the new directory in Codex. The production path marker blocks commits/pushes
from the marked directory but permits the sibling worktree. It does not physically
prevent file edits or deployment commands, so the agent instructions also forbid
development in that checkout. A separate development clone is equally valid.
Do not remove the marker to unblock a development task.

Development containers need a separate Compose project name **and** separate
ports, volumes, database/Redis credentials and data. A worktree alone does not
isolate those resources. Never start the default development stack beside
production without checking those collisions. Deploy separately from a reviewed
main commit/release through the existing release procedure; do not restart
containers, migrate the database or change running code during ordinary task work.

## Verification and limits

```sh
python scripts/test_git_workflow.py
# Ubuntu may call the executable python3 instead.
```

The test creates disposable local bare remotes and two real clones, installs the
actual hooks and exercises commits, pushes, stale-main rejection, merging both
tasks, host enforcement, existing-hook preservation and production/worktree
separation. It uses no GitHub credentials or application data. The Python test
dependency is not needed for normal Git usage. Production deployment and actual
HappySnowman setup must be verified on that computer; testing a second local clone
does not claim that remote machine has been configured.

On 5 September 2026, all 15 Git integration scenarios passed on HappyDucky02 using
Git for Windows, including an unavailable refresh destination, a remote update
newer than the push's advertised base, and rejection of an invalid multi-ref push
without publishing any of its refs. Ruff and shell syntax checks passed. GitHub
`main` protection was enabled and read back with force pushes/deletion disabled,
administrator enforcement enabled, and no required PR reviews. These checks do
not constitute an Ubuntu-host deployment rehearsal.
