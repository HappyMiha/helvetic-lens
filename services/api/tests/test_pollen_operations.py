"""Isolated retention, scheduler fairness, cancellation and recovery checks."""

import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from test_monitoring_runtime import NOW, command, input_sample, policy, seed
from test_monitoring_subjects import db as db

from helvetic_lens import jobs
from helvetic_lens.monitoring_live_models import (
    MonitoringRuntime,
    MonitoringSourceArtifact,
    MonitoringSourceSample,
)
from helvetic_lens.pollen_collector import record_artifact
from helvetic_lens.pollen_jobs import enqueue_due, refresh
from helvetic_lens.pollen_retention import cleanup


def test_public_retention_expiry_preserves_private_snapshot(db, tmp_path):
    from helvetic_lens import monitoring_runtime
    body = b"synthetic-cache-bytes"
    digest = hashlib.sha256(body).hexdigest()
    subject_id = seed(db)
    input_sample(db, "0", artifact_hashes=(digest,))
    command(db, subject_id)
    with db.session() as session:
        record_artifact(session, digest=digest, source_id="synthetic", identity="synthetic", body=body, fetched=NOW,
                        retention_days=1, storage_root=tmp_path)
        session.scalar(select(MonitoringSourceSample)).retention_until = NOW + timedelta(days=1)
        session.commit()
    settings = policy(data_dir=tmp_path)
    assert cleanup(db, settings, now=NOW + timedelta(hours=23)) == {"artifacts": 0, "samples": 0}
    assert cleanup(db, settings, now=NOW + timedelta(days=1)) == {"artifacts": 1, "samples": 1}
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(MonitoringSourceArtifact)) == 0
        assert monitoring_runtime.history(session, user_id="owner", subject_id=subject_id)["items"][0]["current"]["value"] == "0"
    assert not (tmp_path / "monitoring-public-artifacts" / digest[:2] / digest).exists()


def test_renewed_shared_artifact_survives_old_cleanup_deadline(db, tmp_path):
    body = b"synthetic-renewal"
    digest = hashlib.sha256(body).hexdigest()
    with db.session() as session:
        for offset in (0, 1):
            record_artifact(session, digest=digest, source_id="synthetic", identity="synthetic", body=body,
                fetched=NOW + timedelta(days=offset), retention_days=1, storage_root=tmp_path)
        session.commit()
    assert cleanup(db, policy(data_dir=tmp_path), now=NOW + timedelta(days=1))["artifacts"] == 0


def test_denied_scheduler_advances_due_time_and_cancellation_prevents_fetch(db):
    subject_id = seed(db)
    started = command(db, subject_id)
    settings = policy().model_copy(update={"pollen_source_policy": policy().pollen_source_policy.model_copy(update={"channels": ()})})
    assert enqueue_due(db, settings, now=NOW + timedelta(hours=1)) == {"enqueued": 0}
    with db.session() as session:
        runtime = session.get(MonitoringRuntime, subject_id)
        assert runtime.next_poll_at.replace(tzinfo=NOW.tzinfo) == NOW + timedelta(hours=1, minutes=20)
    def cancelled():
        raise jobs.JobCancelled()
    with pytest.raises(jobs.JobCancelled):
        refresh(db, policy(), subject_id=subject_id, run_id=started["runtime"]["run_id"], checkpoint=cancelled)


def test_failed_refresh_is_visible_even_with_fresh_cached_value_and_recovers_quietly(db, monkeypatch):
    from test_pollen_thresholds import SERIES

    from helvetic_lens import monitoring_runtime, pollen_jobs

    subject_id = seed(db)
    input_sample(db, "0")
    started = command(db, subject_id)
    class Clock:
        @staticmethod
        def now(_zone):
            return NOW + timedelta(hours=1)
    monkeypatch.setattr(pollen_jobs, "datetime", Clock)
    monkeypatch.setattr(pollen_jobs, "OBSERVATION_SOURCE", SERIES.source_id)
    monkeypatch.setattr(pollen_jobs, "HOURLY_METHOD", SERIES.method_version)
    monkeypatch.setattr(pollen_jobs, "collect_hourly", lambda *args, **kwargs: {"status": "official_source_unavailable"})
    result = refresh(db, policy(), subject_id=subject_id, run_id=started["runtime"]["run_id"])
    assert result["status"] == "source_unavailable"
    with db.session() as session:
        view = monitoring_runtime.state(session, settings=policy(), user_id="owner", subject_id=subject_id, now=Clock.now(None))
        assert view["runtime"]["health"] == "source_unavailable"
        assert view["current"][0]["sample"]["value"] == "0"
    input_sample(db, "20", 1)
    monkeypatch.setattr(pollen_jobs, "collect_hourly", lambda *args, **kwargs: {"status": "cached_or_collecting", "source_error": None})
    assert refresh(db, policy(), subject_id=subject_id, run_id=started["runtime"]["run_id"])["status"] == "ready"
    with db.session() as session:
        assert monitoring_runtime.history(session, user_id="owner", subject_id=subject_id, material_only=True)["items"] == []
