"""Bounded cleanup for operational records; legal evidence/history stays separate."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select

from .config import Settings
from .db import Database, utcnow
from .models import (
    ConnectorRun,
    DigestDelivery,
    IntegrationLog,
    Job,
    JobStep,
    Observation,
    OutboxMessage,
    RegulatoryDocumentVersion,
    Version,
)

TERMINAL_JOB_STATES = ("succeeded", "failed", "cancelled")


def _remove_old_files(folder: Path, cutoff: datetime, *, allowed_names: set[str] | None = None) -> int:
    if not folder.is_dir():
        return 0
    removed = 0
    cutoff_timestamp = cutoff.timestamp()
    for path in folder.iterdir():
        if not path.is_file() or (allowed_names is not None and path.name in allowed_names):
            continue
        try:
            if path.stat().st_mtime < cutoff_timestamp:
                path.unlink()
                removed += 1
        except FileNotFoundError:
            continue
    return removed


def cleanup_operational_data(
    database: Database,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> dict[str, int | str]:
    now = now or utcnow()
    log_cutoff = now - timedelta(days=settings.integration_log_retention_days)
    job_cutoff = now - timedelta(days=settings.job_history_retention_days)
    digest_cutoff = now - timedelta(days=settings.digest_delivery_retention_days)
    artifact_cutoff = now - timedelta(hours=settings.orphan_artifact_retention_hours)
    mailbox_cutoff = now - timedelta(hours=settings.auth_mail_retention_hours)

    with database.session(include_all_organizations=True) as session:
        old_log_ids = list(
            session.scalars(select(IntegrationLog.id).where(IntegrationLog.created_at < log_cutoff))
        )
        if old_log_ids:
            session.execute(delete(IntegrationLog).where(IntegrationLog.id.in_(old_log_ids)))

        connector_job_ids = select(ConnectorRun.job_id).where(ConnectorRun.job_id.is_not(None))
        old_job_ids = list(
            session.scalars(
                select(Job.id).where(
                    Job.state.in_(TERMINAL_JOB_STATES),
                    Job.updated_at < job_cutoff,
                    Job.id.not_in(connector_job_ids),
                )
            )
        )
        if old_job_ids:
            session.execute(delete(OutboxMessage).where(OutboxMessage.job_id.in_(old_job_ids)))
            session.execute(delete(JobStep).where(JobStep.job_id.in_(old_job_ids)))
            session.execute(delete(Job).where(Job.id.in_(old_job_ids)))

        old_digest_ids = list(
            session.scalars(
                select(DigestDelivery.id).where(
                    DigestDelivery.status.in_(TERMINAL_JOB_STATES + ("skipped",)),
                    DigestDelivery.created_at < digest_cutoff,
                )
            )
        )
        if old_digest_ids:
            session.execute(delete(DigestDelivery).where(DigestDelivery.id.in_(old_digest_ids)))

        referenced_artifacts = set(
            session.scalars(select(Version.artifact_key).where(Version.artifact_key != ""))
        )
        referenced_artifacts.update(
            session.scalars(select(Observation.artifact_key).where(Observation.artifact_key != ""))
        )
        referenced_artifacts.update(
            value
            for value in session.scalars(
                select(RegulatoryDocumentVersion.artifact_key).where(
                    RegulatoryDocumentVersion.artifact_key.is_not(None)
                )
            )
            if value
        )
        session.commit()

    storage = settings.storage_path
    orphan_artifacts = _remove_old_files(
        storage / "artifacts",
        artifact_cutoff,
        allowed_names=referenced_artifacts,
    )
    temporary_files = _remove_old_files(storage / "tmp", artifact_cutoff)
    auth_messages = _remove_old_files(storage / "auth-mailbox", mailbox_cutoff)
    result: dict[str, int | str] = {
        "integration_logs": len(old_log_ids),
        "terminal_jobs": len(old_job_ids),
        "digest_deliveries": len(old_digest_ids),
        "orphan_artifacts": orphan_artifacts,
        "temporary_files": temporary_files,
        "auth_messages": auth_messages,
        "completed_at": now.isoformat(),
    }
    marker_dir = storage / "operations"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker = marker_dir / "last-cleanup.json"
    temporary_marker = marker.with_suffix(".tmp")
    temporary_marker.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    os.replace(temporary_marker, marker)
    return result
