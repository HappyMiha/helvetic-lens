# Helvetic Lens — choose a workstream

Start with **[PROJECT_MAP.md](PROJECT_MAP.md)**. Three organizational activities use two product channels: `main` for the main product and hackathon connectors, and `codex/HappyDucky02/monitoring-v2` for Monitoring v2. The frozen MVP tag remains a reference while both channels can evolve independently.

| Workstream | Entry point | Status |
|---|---|---|
| Support & Infrastructure | [Open support](docs/workstreams/SUPPORT.md) | Parked — wait for the user's explicit start |
| Legal Hackathon — 23 September 2026 | [Open main-product hackathon preparation](docs/workstreams/HACKATHON_2026.md) | Changes go to `main` → HappySnowman → helveticlens.ch; connector implementation not started |
| Helvetic Lens Monitoring v2 | [Open Monitoring v2](docs/workstreams/MONITORING_V2.md) | Dedicated v2 branch → HappyDucky02 → monitoring.helveticlens.ch; deployment setup in progress, not yet verified live |

**Monitoring v2 implementation:** use the [active backlog on the dedicated v2 branch](https://github.com/HappyMiha/helvetic-lens/blob/codex/HappyDucky02/monitoring-v2/BACKLOG_MONITORING_V2.md), with Pollen Watch first and customs rates deferred. The [main-branch snapshot](BACKLOG_MONITORING_V2.md) preserves the published plan and is not the active implementation queue.

[Frozen MVP release](https://github.com/HappyMiha/helvetic-lens/releases/tag/v1.0.0-hackathon-mvp) · [Historical v1 backlog](BACKLOG_V1_ARCHIVE.md) · [Outstanding legacy obligations](docs/monitoring-v2/LEGACY_DISPOSITION.md).

The historical backlog is not a parallel queue. Record work in its selected workstream before implementation; do not mix support activity, hackathon integrations and Monitoring v2 features.
