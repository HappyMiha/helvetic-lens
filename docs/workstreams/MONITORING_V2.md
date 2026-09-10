# 03 — Helvetic Lens Monitoring v2

[Back to the project map](../../PROJECT_MAP.md)

**Status: backlog ready; feature implementation has not started. Separate deployment setup is in progress and has not yet been verified live.**

## Where development is tracked

Use **[BACKLOG_MONITORING_V2.md on the dedicated v2 branch](../../BACKLOG_MONITORING_V2.md)** as the single implementation backlog for this workstream. The [main-branch copy](https://github.com/HappyMiha/helvetic-lens/blob/main/BACKLOG_MONITORING_V2.md) is a published planning snapshot. This entry page provides navigation and deployment context; it is not another implementation queue.

- First complete delivery: **Pollen Watch**, ready for testing with real users.
- Sequence: **MV2-001 → MV2-069 → MV2-070 → MV2-030 → MV2-031 → MV2-071**.
- Current scope: 9 active scenarios, 63 required tasks and 9 deferred tasks. [MV2-072](../../BACKLOG_MONITORING_V2.md#mv2-072) adds the independent deployment to the original 71 tasks; it is IN PROGRESS and adds no product scenario.
- Customs rates (C4) remain a possible future feature, excluded from current development and release acceptance.

## Deployment target recorded from the user

| Setting | Target | Current state |
|---|---|---|
| Host | **HappyDucky02** | Selected by the user |
| Site | **monitoring.helveticlens.ch** | Routing and public availability not yet verified |
| Integration branch | **`codex/HappyDucky02/monitoring-v2`** | Dedicated Monitoring v2 channel |
| Product channel | Monitoring v2 preview/pilot | Independent from `main` → HappySnowman → helveticlens.ch |
| Automatic deployment | Dedicated v2 configuration and trigger watching only the v2 branch | Setup in progress; bootstrap, update and rollback verification required |

[MV2-072](../../BACKLOG_MONITORING_V2.md#mv2-072) records the authorized infrastructure work and its acceptance criteria. It must deliver an isolated, reviewable setup with its own application directory, deployment selector/trigger, Compose project, ports, data volumes/database, queues, secrets, backups and domain/tunnel route. Account for shared CPU/RAM/GPU capacity on HappyDucky02. A second hostname alone does not isolate the application or its data.

The existing deployment manager has shared defaults and requires an isolation review before a second instance is installed. Do not reuse an existing deployment command unchanged or point this subdomain at the current MVP backend. A single-host preview is not a claim of high availability.

## Boundaries

- Start v2 implementation task branches/worktrees from the current dedicated v2 branch and integrate back into it. Do not merge the v2 branch into `main` as part of routine delivery.
- No automatic promotion of v2 code, schema migrations or user data into the main-product/hackathon environment. Its existing `main` automatic deployment remains active.
- No dependency on grant approval to begin the scoped Pollen Watch work; actual pilot capacity still requires verification.
- Any reusable hackathon result enters through an explicit v2 task and verification, not an implicit whole-branch merge.

**Current step:** complete MV2-072 on the active v2 branch for HappyDucky02 and monitoring.helveticlens.ch, including proof of isolation and branch-triggered updates. Pollen Watch remains the first complete product scenario, followed through the stated delivery sequence.
