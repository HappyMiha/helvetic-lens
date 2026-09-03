import os
from datetime import timedelta

from conftest import add_law
from sqlalchemy import select

from helvetic_lens import jobs
from helvetic_lens.db import utcnow
from helvetic_lens.maintenance import cleanup_operational_data
from helvetic_lens.models import (
    DigestDelivery,
    DigestPreference,
    IntegrationLog,
    Job,
    JobStep,
    OutboxMessage,
    User,
    Version,
)


def test_cleanup_bounds_operational_data_without_deleting_evidence_or_active_work(harness):
    client, _, service, _ = harness
    law = add_law(client)
    now = utcnow()
    old = now - timedelta(days=120)
    digest_old = now - timedelta(days=service.settings.digest_delivery_retention_days + 1)

    with service.db.session() as session:
        old_log = IntegrationLog(
            provider="test",
            operation="expired",
            method="GET",
            url="https://example.ch/old",
            status="success",
            duration_ms=1,
        )
        current_log = IntegrationLog(
            provider="test",
            operation="current",
            method="GET",
            url="https://example.ch/current",
            status="success",
            duration_ms=1,
        )
        session.add_all([old_log, current_log])
        session.flush()
        old_log.created_at = old

        expired_job, _ = jobs.enqueue(
            session,
            job_type="scan",
            target_type="scan",
            target_id="expired",
            queue="ingest",
            idempotency_key="expired-maintenance-job",
            steps=[("Expired step", {"large": "detail"})],
        )
        expired_job.state = "succeeded"
        expired_job.updated_at = old
        expired_job.finished_at = old
        active_job, _ = jobs.enqueue(
            session,
            job_type="scan",
            target_type="scan",
            target_id="active",
            queue="ingest",
            idempotency_key="active-maintenance-job",
        )
        active_job.updated_at = old

        user = User(
            email="retention@example.ch",
            password_hash="not-used",
            name="Retention test",
        )
        session.add(user)
        session.flush()
        preference = DigestPreference(user_id=user.id)
        session.add(preference)
        session.flush()
        expired_digest = DigestDelivery(
            user_id=user.id,
            preference_id=preference.id,
            frequency="weekly",
            period_start=old - timedelta(days=7),
            period_end=old,
            status="succeeded",
        )
        current_digest = DigestDelivery(
            user_id=user.id,
            preference_id=preference.id,
            frequency="weekly",
            period_start=now - timedelta(days=7),
            period_end=now,
            status="succeeded",
        )
        session.add_all([expired_digest, current_digest])
        session.flush()
        expired_digest.created_at = digest_old
        session.commit()
        old_log_id = old_log.id
        current_log_id = current_log.id
        expired_job_id = expired_job.id
        active_job_id = active_job.id
        expired_digest_id = expired_digest.id
        current_digest_id = current_digest.id

        version = session.get(Version, law["current_version_id"])
        referenced_artifact = service.settings.storage_path / "artifacts" / version.artifact_key

    artifact_dir = service.settings.storage_path / "artifacts"
    orphan_artifact = artifact_dir / "unreferenced.bin"
    recent_orphan = artifact_dir / "recent-unreferenced.bin"
    orphan_artifact.write_bytes(b"expired")
    recent_orphan.write_bytes(b"recent")
    old_timestamp = old.timestamp()
    os.utime(orphan_artifact, (old_timestamp, old_timestamp))
    os.utime(referenced_artifact, (old_timestamp, old_timestamp))
    mailbox = service.settings.storage_path / "auth-mailbox"
    mailbox.mkdir()
    expired_message = mailbox / "expired.eml"
    expired_message.write_text("expired", encoding="utf-8")
    os.utime(expired_message, (old_timestamp, old_timestamp))

    result = cleanup_operational_data(service.db, service.settings, now=now)

    assert result == {
        "integration_logs": 1,
        "terminal_jobs": 1,
        "digest_deliveries": 1,
        "orphan_artifacts": 1,
        "temporary_files": 0,
        "auth_messages": 1,
        "completed_at": now.isoformat(),
    }
    assert referenced_artifact.exists()
    assert recent_orphan.exists()
    assert not orphan_artifact.exists() and not expired_message.exists()
    assert (service.settings.storage_path / "operations" / "last-cleanup.json").is_file()

    with service.db.session() as session:
        assert session.get(IntegrationLog, old_log_id) is None
        assert session.get(IntegrationLog, current_log_id) is not None
        assert session.get(Job, expired_job_id) is None
        assert session.get(Job, active_job_id) is not None
        assert session.get(DigestDelivery, expired_digest_id) is None
        assert session.get(DigestDelivery, current_digest_id) is not None
        assert session.scalar(select(JobStep).where(JobStep.job_id == expired_job_id)) is None
        assert session.scalar(select(OutboxMessage).where(OutboxMessage.job_id == expired_job_id)) is None
