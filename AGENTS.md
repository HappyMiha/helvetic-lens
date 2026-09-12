# Helvetic Lens development

The user's instruction of 12 September 2026 replaces the previous multi-computer,
host-alias, task-branch and separate Monitoring integration workflow.

- Work as one agent in the development checkout on `main`. Do not create task
  branches, parallel agents or development worktrees. Read `docs/DEVELOPMENT.md`,
  `PROJECT_MAP.md` and the relevant backlog; nested AGENTS.md instructions apply.
- Fetch origin, inspect status and update safely before starting. Preserve
  unfinished changes. If upstream changes arrive, integrate deliberately, review
  the combined behavior and repeat affected checks. Never force-push, reset away
  work, bypass hooks or replace the frozen `v1.0.0-hackathon-mvp` tag.
- Deliver complete user-facing features across as many continuations as needed.
  Implement the whole outcome, run required checks, fix failures, update English
  acceptance evidence, then commit and immediately push `main` to `origin/main`.
  Do not publish unfinished technical substeps merely at a continuation boundary.
- Run the exact API lint gate `ruff check services/api deploy/release_manager.py`
  for API changes, affected tests, and relevant frontend lint/type/build checks.
  Tests must prove behavior, privacy and failure handling, not mirror code.
- Routine tested commits, pushes and normal automatic deployments are already
  authorized. Continue the next ready feature while a previous deployment runs;
  never duplicate, interrupt or restart active checks or deployment jobs.
- The only active product site is `helveticlens.ch` on HappySnowman. The user
  retired `monitoring.helveticlens.ch` on 12 September 2026. Do not recreate or
  restart the HappyDucky02 Monitoring deployment, its Windows task, Docker project
  `helvetic-lens-v2`, tunnel or hostname. Verify releases only on the main site.
- Serving checkouts are deployment-managed: never develop there. Preserve private
  data, volumes, credentials and source approvals; retirement is not authorization
  to delete or transfer them. Historical deployment instructions are not active.
  Read-only Python diagnostics near serving code must use `-B` or
  `PYTHONDONTWRITEBYTECODE=1` to preserve immutable release directories.
- Keep local Git safeguards enabled and preserve unrelated hooks. Historical
  remote branches, worktrees and deployment evidence are not active workflow;
  do not mass-delete them or disturb another existing checkout.
- `BACKLOG_MONITORING_V2.md` on main is the sole active Monitoring backlog.
  Before implementing a direction, record its MV2 scope, dependencies, source
  readiness and acceptance criteria. A scoped shared-contract implementation
  does not complete its broader parent task. The user has authorized the next
  complete direction after Pollen while outstanding pilot/release gates continue.
- Keep private ownership, membership, consent, source rights, quality and review
  gates. Never invent source coverage or interpret unavailable data as safe.
  DONE requires all stated evidence; unverified release or human acceptance stays
  IN PROGRESS/VERIFYING. Report pushed code separately from verified activation.
- Update both backlog index and task detail. Before publishing backlog edits,
  run `services/api/tests/test_monitoring_progress.py::test_actual_backlog_has_complete_unique_sections_and_preserves_customs_deferral`.
- Support/grants remain parked. Customs/C4 and MV2-026/027/061 remain DEFERRED.
  Preserve legacy obligations, historical evidence and the frozen MVP tag.
