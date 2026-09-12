"""Bounded cleanup of public source cache, separate from private review history."""

import re
from datetime import UTC, datetime

from sqlalchemy import delete, select

from .monitoring_live_models import MonitoringSourceArtifact, MonitoringSourceSample


def cleanup(database, settings, *, now=None):
    if settings.deployment_instance not in {"main", "monitoring-v2"}:
        return {"artifacts": 0, "samples": 0}
    now = now or datetime.now(UTC)
    deleted = 0
    with database.session() as session:
        # Collector retention renewal locks the same metadata row before writing
        # bytes, so it cannot return an already-removed cached artifact.
        rows = list(session.scalars(select(MonitoringSourceArtifact).where(
            MonitoringSourceArtifact.retention_until <= now).order_by(MonitoringSourceArtifact.retention_until).limit(100).with_for_update()))
        root = (settings.data_dir / "monitoring-public-artifacts").resolve()
        for row in rows:
            if not re.fullmatch(r"[a-f0-9]{64}", row.sha256):
                continue
            path = root / row.sha256[:2] / row.sha256
            if not path.resolve().is_relative_to(root):
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue  # Retry cleanup later; unavailable files never bypass expiry.
            session.delete(row)
            deleted += 1
        ids = list(session.scalars(select(MonitoringSourceSample.id).where(
            MonitoringSourceSample.retention_until <= now).order_by(MonitoringSourceSample.retention_until).limit(1000)))
        if ids:
            session.execute(delete(MonitoringSourceSample).where(MonitoringSourceSample.id.in_(ids)))
        session.commit()
    return {"artifacts": deleted, "samples": len(ids)}
