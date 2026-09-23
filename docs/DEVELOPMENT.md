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

From 23 September 2026 the owner's [test-suite policy](TESTING.md) makes smoke
and functional checks the standard automatic release gate. Run affected
integration tests before publishing their feature; use the full profile for
broad release regression. Existing cases remain available in the separate
integration/full suites. The exact-SHA, reason-bearing emergency invocation is
the only test bypass and is recorded as skipped. It never becomes the next
automatic invocation's policy. Bootstrap still uses the full suite.

SQLite migrations require a connection without pending application writes when
foreign-key enforcement is enabled. Commit or roll back fixture/application data
before handing the connection to Alembic. The migration runner temporarily gates
enforcement only around its own atomic schema work, checks referential integrity,
and restores enforcement before returning the connection. It never commits a
caller's pending writes. This prevents SQLite batch table replacement from
cascading into retained child records; PostgreSQL uses its existing migration path.

All nine active Monitoring sections must remain enabled in production and
directly visible in desktop and mobile navigation for every user. Source
credentials, reviewed permissions and freshness remain separate readiness
checks inside each section. Do not hide a section because its source is not
ready. This records the owner's 13 September 2026 visibility instruction;
it does not reactivate deferred C4/customs.

For an isolated local web check, set `HELVETIC_LENS_CHECK_BUILD` to a short name
containing lowercase letters, digits and hyphens. Next writes to the ignored
`apps/web/.next-check-<name>` directory; use the same value when serving that
build. This allows useful independent checks without replacing an active check's
default `.next` output. It does not authorize duplicating or stopping an active
check. Next may update generated type imports and TypeScript includes for the
temporary directory; remove only those generated changes after the check. Normal
builds and deployments leave the variable unset.

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
