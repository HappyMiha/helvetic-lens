# Helvetic Lens project map

One agent develops complete features on **main**, following [the development cycle](docs/DEVELOPMENT.md).
The only active site is **helveticlens.ch on HappySnowman**, including Monitoring features.

| Activity | Queue | State |
|---|---|---|
| Monitoring v2 | [Active backlog](BACKLOG_MONITORING_V2.md) | Pollen, River / Lake and Basel Air code released on the main site; applicable acceptance remains open |
| Legal Hackathon 2026 | [Hackathon](docs/workstreams/HACKATHON_2026.md) | Main product; preserve the frozen MVP reference |
| Support and infrastructure | [Support](docs/workstreams/SUPPORT.md) | Parked pending the user's explicit start |

| Instance | Code | Website |
|---|---|---|
| Main product and Monitoring features (HappySnowman) | main | helveticlens.ch |

The user retired `monitoring.helveticlens.ch` on 12 September 2026. Do not restart
its HappyDucky02 deployment, Windows task, `helvetic-lens-v2` Docker project, tunnel
or hostname. Retained private data and deployment evidence must not be deleted or
transferred as part of routine development.

The active Monitoring backlog is the file on main. Older integration/task branches
and host aliases are historical, not development routes. Customs/C4 remain deferred.
Keep scoped task acceptance distinct from broader shared-contract and human pilot gates.

The [Monitoring Centre](docs/monitoring-v2/MONITORING_CENTRE.md) at `/monitoring`
provides the shared entry point for saved Pollen, River/Lake and Air monitors and
nine honestly gated scenario choices. Its code verification and release boundary
are recorded separately; the broader MV2-017/018 tasks remain in progress.

See [deployment evidence](docs/monitoring-v2/DEPLOYMENT_STATUS.md) for exact active
commits and selector migration. A push is not proof of a successful release.
Preserve the [frozen MVP tag](https://github.com/HappyMiha/helvetic-lens/releases/tag/v1.0.0-hackathon-mvp)
and [legacy obligations](docs/monitoring-v2/LEGACY_DISPOSITION.md).
