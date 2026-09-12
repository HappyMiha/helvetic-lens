# Monitoring v2

[Project map](../../PROJECT_MAP.md) · [Active backlog on main](../../BACKLOG_MONITORING_V2.md)

One agent develops complete features on main, following [the development cycle](../DEVELOPMENT.md).
Pollen Watch is implemented. The next selected complete direction is River / Lake Watch,
MV2-032/033; human pilot and broader acceptance gates remain evidence-based.
Customs/C4 remain deferred and grants remain parked.

Both helveticlens.ch and monitoring.helveticlens.ch use main code while retaining separate
deployments, databases, volumes, secrets, source approvals and public identities.
Never develop in serving checkouts. Historical task/integration branches are no longer
publication routes. Preserve the frozen MVP tag and existing private monitors.

See [deployment evidence](../monitoring-v2/DEPLOYMENT_STATUS.md) for actual active releases
and the operational selector migration. A successful push does not prove activation.
