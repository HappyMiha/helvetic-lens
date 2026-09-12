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

## Active deployment

Deploy and verify only **helveticlens.ch on HappySnowman**, including Monitoring
features, from main. Never develop in serving checkouts.

The user retired the separate monitoring.helveticlens.ch site on 12 September
2026. Do not recreate or restart its HappyDucky02 deployment, Windows scheduled
task, Docker project `helvetic-lens-v2`, tunnel or hostname. Older controller,
selector and retry instructions are historical evidence, not work to resume.
Preserve retained databases, volumes, credentials, consent and source approvals;
retirement does not authorize deleting or transferring private data.
See `monitoring-v2/DEPLOYMENT_STATUS.md` for verified main-site releases.
