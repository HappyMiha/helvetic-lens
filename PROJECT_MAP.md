# Helvetic Lens — project map

**Start here when choosing what to work on.** Helvetic Lens has three organizational activities and **two code and deployment channels**. The frozen MVP remains a release reference; the main product continues to evolve.

## Two product channels

| Product | Integration branch | Deployment host | Website | Update route |
|---|---|---|---|---|
| **Main product, including hackathon connectors** | `main` | **HappySnowman** | **helveticlens.ch** | Existing automatic deployment from `main` |
| **Monitoring v2** | `codex/HappyDucky02/monitoring-v2` | **HappyDucky02** | **monitoring.helveticlens.ch** | Independent automatic deployment from the dedicated v2 branch; setup in progress, live operation not yet verified |

Hackathon connector improvements belong to the main product and follow its existing release route. Monitoring v2 has a separate application instance, deployment trigger and data. Funding/support does not create a third application branch or website.

## Frozen reference — Hackathon MVP

[Release v1.0.0-hackathon-mvp](https://github.com/HappyMiha/helvetic-lens/releases/tag/v1.0.0-hackathon-mvp) is the shared reference for demonstrations, support discussions and future development. Preserve its tag, source, artifacts and evidence. A frozen release does not by itself establish which version a live site currently serves.

## Choose one workstream

| Workstream | Status now | Purpose | Open this page |
|---|---|---|---|
| **01 — Support & Infrastructure** | **PARKED — wait for the user's explicit start** | Organize future requests for development compute, servers and infrastructure support | [Support & Infrastructure](docs/workstreams/SUPPORT.md) |
| **02 — Legal Hackathon 2026** | **MAIN PRODUCT — connector implementation not started** | Prepare organizer-resource integrations for 23 September 2026 and deliver them through `main` | [Legal Hackathon](docs/workstreams/HACKATHON_2026.md) |
| **03 — Monitoring v2** | **BACKLOG READY — separate deployment setup in progress** | Build the next product version on its dedicated branch, starting with Pollen Watch | [Monitoring v2](docs/workstreams/MONITORING_V2.md) |

## Keep the work separate

- Start each task with one workstream name. Suggested task titles: `HL / Support — …`, `HL / Hackathon — …`, or `HL / Monitoring v2 — …`.
- Record work under its own entry page and backlog. Grant preparation is not a v2 feature; hackathon provider integration is not automatically part of Pollen Watch.
- Monitoring v2 implementation follows the [active backlog on the v2 branch](BACKLOG_MONITORING_V2.md). The [copy on main](https://github.com/HappyMiha/helvetic-lens/blob/main/BACKLOG_MONITORING_V2.md) preserves the published plan as a reference. The original 71 task definitions, C4 deferral and Pollen Watch first-delivery sequence are preserved. The active backlog adds [MV2-072](BACKLOG_MONITORING_V2.md#mv2-072) for this independent deployment: 72 tasks in total, 63 required and 9 deferred.
- Use a separate task branch/worktree for each implementation task, based on its product channel. Integrate hackathon work into `main`; integrate Monitoring v2 work into `codex/HappyDucky02/monitoring-v2`. Follow [the two-computer workflow](docs/MULTI_PC_DEVELOPMENT.md). Never develop in either site's serving checkout.
- Share a fix or connector deliberately: record the source task/commit, identify the receiving workstream and verify compatibility there. Do not merge an entire experimental workstream into the MVP as an incidental step.
- Preserve [the historical backlog](BACKLOG_V1_ARCHIVE.md). It is reference material, not a fourth active queue.

## Current focus

Support work is parked. Hackathon preparation has its own entry page within the main-product channel; no connectors are being implemented by this organization change. Monitoring v2 deployment setup is in progress for **HappyDucky02 → monitoring.helveticlens.ch**, using **`codex/HappyDucky02/monitoring-v2`**. DNS routing, isolation and branch-triggered deployment require verification before the site can be described as live. The existing `main` deployment on HappySnowman remains active; freezing the MVP tag does not freeze `main`.
