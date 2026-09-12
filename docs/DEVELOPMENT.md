# Development: one agent, main

Effective 12 September 2026, all product development uses one agent and the
development checkout on `main`. This replaces host aliases, task branches,
parallel worktrees and cross-computer coordination. `BACKLOG_MONITORING_V2.md`
on main is the active Monitoring queue, not a published snapshot.

## Feature cycle

1. Fetch origin, inspect the checkout and safely update main. Preserve unfinished work.
2. Select the next ready complete feature and record scope and acceptance in its backlog.
3. Implement the whole outcome. Keep an accurate local continuation checkpoint.
4. Run required quality gates once the feature is ready; fix failures and retest affected behavior.
5. Update English acceptance evidence, review the complete diff, commit and immediately push main.
6. Observe automatic deployment and public release identity. Continue the next feature while
   those checks run. Do not duplicate or interrupt an active deployment.

If remote main moves, fetch, integrate carefully and retest affected behavior before
retrying. Never force-push or bypass hooks. Keep the frozen MVP tag immutable.
Code publication does not prove activation or human acceptance.

## Local safeguards

Run `sh scripts/setup-git-workflow.sh` in the development checkout. Hooks permit
commits on main, fast-forward publication to origin/main and creation of new tags.
They reject history replacement, main deletion and release-tag replacement/deletion.
No host alias or commit trailer is required. Existing unrelated hooks are preserved.
Use `--production` only to mark a serving checkout against accidental development.
Historical branches and worktrees remain history; this policy does not delete them.

## Deployment isolation

Both helveticlens.ch and monitoring.helveticlens.ch consume main, but remain separate
instances with separate data, source approvals, credentials, volumes and Compose
projects. Never develop in serving checkouts. An independent Monitoring instance
must still use its isolated project and pinned, reviewed deployment controller.
See `monitoring-v2/DEPLOYMENT_STATUS.md` for the selector migration and verified releases.
