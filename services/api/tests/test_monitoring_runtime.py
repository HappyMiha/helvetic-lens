"""Complete-feature diagnostics in isolated databases with synthetic source input.

These fixtures do not approve an official source, production rollout or email.
"""

from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select
from test_monitoring_subjects import db as db
from test_pollen_thresholds import NOW, SERIES, sample

from helvetic_lens import monitoring_runtime as runtime
from helvetic_lens import monitoring_subjects as subjects
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import Job, MonitoringSubject, OrganizationMembership, OutboxMessage
from helvetic_lens.monitoring_live_models import (
    MonitoringDelivery,
    MonitoringReview,
    MonitoringRuntime,
    MonitoringSourceSample,
)
from helvetic_lens.pollen_sources import sample_channel_hash
from helvetic_lens.pollen_thresholds import _hash


def policy(**overrides):
    return Settings(_env_file=None, app_environment="test", deployment_instance="monitoring-v2", monitoring_rollout={
        "enabled": True, "grants": [{"workspace_id": "org-a", "template_id": "pollen-watch",
                                     "template_version": 1, "mode": "enabled"}]}, pollen_source_policy={
        "channels": [{"version": "synthetic-policy-v1", "review_sha256": "e" * 64,
            "source_id": SERIES.source_id, "method_version": SERIES.method_version, "period": SERIES.period,
            "stations": ["PBS"], "allergens": ["grasses"], "status": "approved",
            "valid_from": NOW - timedelta(days=1), "valid_until": NOW + timedelta(days=30),
            "freshness_seconds": 10800, "poll_seconds": 1200, "retention_days": 30}]}, **overrides)


def seed(db, key="complete-feature", user_id="owner"):
    with db.session() as session:
        subject = subjects.create_draft(session, user_id=user_id, request_key=key, configuration={
            "station_id": "PBS", "selections": [{"allergen": "grasses", "rules": [{"period": "observation_hourly",
                "threshold": {"trigger_at_or_above": "10", "reset_at_or_below": "5"}}]}],
            "delivery": {"email": "immediate"}})
        session.commit()
        return subject["id"]


def input_sample(db, value, hour=0, **overrides):
    point = sample(value, hour, **overrides)
    with db.session() as session:
        session.add(MonitoringSourceSample(channel_hash=sample_channel_hash(point.series), series_hash=_hash(point.series.model_dump()), valid_at=point.valid_at,
            revision=point.source_revision, content_hash=_hash(point.model_dump()), sample_json=point.model_dump(mode="json")))
        session.commit()


def command(db, subject_id, action="start", version=0, hour=0, key=None, consent=False, settings=None):
    with db.session() as session:
        result = runtime.command(session, settings=settings or policy(), user_id="owner", subject_id=subject_id,
            action=action, expected_revision=1, expected_version=version, request_key=key or f"{action}-{version}",
            now=NOW + timedelta(hours=hour), email_consent=consent)
        session.commit()
        return result


def refresh(db, subject_id, run_id, hour):
    with db.session() as session:
        result = runtime.refresh_from_cache(session, settings=policy(), user_id="owner", subject_id=subject_id,
            run_id=run_id, now=NOW + timedelta(hours=hour))
        session.commit()
        return result


def test_explicit_start_is_atomic_idempotent_and_never_invents_initial_crossing(db):
    subject_id = seed(db)
    input_sample(db, "20")
    started = command(db, subject_id, consent=True)
    assert started["status"] == "active" and started["runtime"]["health"] == "ready"
    assert command(db, subject_id, consent=True) == started
    with db.session() as session:
        entries = runtime.history(session, user_id="owner", subject_id=subject_id)["items"]
        assert len(entries) == 1 and entries[0]["kind"] == "initial" and entries[0]["material_id"] is None
        assert session.scalar(select(func.count()).select_from(Job)) == 1
        assert session.scalar(select(func.count()).select_from(OutboxMessage)) == 1
        assert session.scalar(select(func.count()).select_from(MonitoringDelivery)) == 0
    with pytest.raises(DomainError) as conflict:
        command(db, subject_id, consent=False)
    assert conflict.value.code == "subject_request_conflict"


def test_crossing_review_reset_reopen_and_restart_keep_immutable_evidence(db):
    subject_id = seed(db)
    input_sample(db, "0")
    started = command(db, subject_id, consent=True)
    run_id = started["runtime"]["run_id"]
    for hour, value in enumerate(["10", "11", "7", "5", "10"], 1):
        input_sample(db, value, hour)
        refresh(db, subject_id, run_id, hour)
        refresh(db, subject_id, run_id, hour)  # Broker duplicate does not add evidence/delivery.
        if hour == 1:
            with db.session() as session:
                first = runtime.history(session, user_id="owner", subject_id=subject_id, material_only=True)["items"][0]
                runtime.review(session, user_id="owner", subject_id=subject_id, entry_id=first["id"],
                               decision="reviewed", expected_version=0)
                session.commit()
    db.migrate()
    with db.session() as session:
        changes = runtime.history(session, user_id="owner", subject_id=subject_id, material_only=True)["items"]
        assert [row["reasons"] for row in changes] == [["threshold_triggered"], ["threshold_reset"], ["threshold_triggered"]]
        assert changes[-1]["review"] == {"version": 1, "decision": "reviewed"}
        assert changes[0]["review"] is None and changes[0]["previous"]["value"] == "5"
        assert session.scalar(select(func.count()).select_from(MonitoringDelivery)) == 3
        assert session.scalar(select(func.count()).select_from(MonitoringReview)) == 1


def test_missing_stale_and_recovery_preserve_state_without_alert_flood(db):
    subject_id = seed(db)
    input_sample(db, "10")
    run_id = command(db, subject_id)["runtime"]["run_id"]
    input_sample(db, None, 1, quality="missing")
    refresh(db, subject_id, run_id, 1)
    refresh(db, subject_id, run_id, 5)
    input_sample(db, "0", 6)
    refresh(db, subject_id, run_id, 6)
    with db.session() as session:
        rows = runtime.history(session, user_id="owner", subject_id=subject_id)["items"]
        assert rows[0]["kind"] == "recovered"
        assert all(row["material_id"] is None for row in rows)
        assert any(row["current"]["value"] is None for row in rows)


def test_pause_resume_rebaselines_without_erasing_review_or_replaying_backlog(db):
    subject_id = seed(db)
    input_sample(db, "0")
    started = command(db, subject_id, consent=True)
    paused = command(db, subject_id, "pause", version=1)
    assert paused["status"] == "paused" and not paused["runtime"]["email_consent"]
    input_sample(db, "30", 1)
    assert refresh(db, subject_id, started["runtime"]["run_id"], 1)["status"] == "inactive"
    resumed = command(db, subject_id, "resume", version=2, hour=1)
    assert resumed["runtime"]["run_id"] != started["runtime"]["run_id"]
    assert not resumed["runtime"]["email_consent"]
    with db.session() as session:
        rows = runtime.history(session, user_id="owner", subject_id=subject_id)["items"]
        assert len(rows) == 2 and all(row["kind"] == "initial" and not row["material_id"] for row in rows)


def test_default_off_source_gate_and_cross_owner_access_fail_without_jobs(db):
    subject_id = seed(db)
    for settings in (Settings(_env_file=None), policy().model_copy(update={"pollen_source_policy": policy().pollen_source_policy.model_copy(update={"channels": ()})})):
        with pytest.raises(DomainError):
            command(db, subject_id, settings=settings)
    with db.session() as session:
        assert session.get(MonitoringSubject, subject_id).status == "draft"
        assert session.scalar(select(func.count()).select_from(Job)) == 0
        assert session.scalar(select(func.count()).select_from(MonitoringRuntime)) == 0
        with pytest.raises(DomainError) as denied:
            runtime.state(session, settings=policy(), user_id="peer", subject_id=subject_id, now=NOW)
        assert denied.value.status == 404
        with pytest.raises(DomainError):
            runtime.history(session, user_id="peer", subject_id=subject_id)


def test_revocation_blocks_worker_recheck_and_command_rollback_leaves_draft(db):
    subject_id = seed(db)
    with db.session() as session:
        runtime.command(session, settings=policy(), user_id="owner", subject_id=subject_id, action="start",
            expected_revision=1, expected_version=0, request_key="rolled-back", now=NOW)
        session.rollback()
    with db.session() as session:
        assert session.get(MonitoringSubject, subject_id).status == "draft"
        assert session.get(MonitoringRuntime, subject_id) is None
    started = command(db, subject_id)
    with db.session() as session:
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.organization_id == "org-a",
                                                           OrganizationMembership.user_id == "owner"))
        session.commit()
    with pytest.raises(DomainError):
        refresh(db, subject_id, started["runtime"]["run_id"], 1)


def test_paused_edit_retains_history_export_and_delete_cascades(db):
    import json

    from helvetic_lens.monitoring_live_models import (
        MonitoringCommand,
        MonitoringLiveEntry,
        MonitoringLiveStream,
    )
    subject_id = seed(db)
    input_sample(db, "0")
    started = command(db, subject_id, consent=True)
    input_sample(db, "10", 1)
    refresh(db, subject_id, started["runtime"]["run_id"], 1)
    command(db, subject_id, "pause", version=1, hour=1)
    with db.session() as session:
        entry = runtime.history(session, user_id="owner", subject_id=subject_id)["items"][0]
        for version, decision in enumerate(["reviewed", "continue", "not_relevant"]):
            runtime.review(session, user_id="owner", subject_id=subject_id, entry_id=entry["id"], decision=decision, expected_version=version)
        config = subjects.get_subject(session, user_id="owner", subject_id=subject_id)["configuration"]
        config["selections"][0]["rules"][0]["threshold"]["trigger_at_or_above"] = "12"
        edited = runtime.revise_paused(session, user_id="owner", subject_id=subject_id, expected_revision=1, configuration=config, now=NOW)
        assert edited["status"] == "paused" and edited["revision"] == 2 and edited["runtime_version"] == 3
        assert session.get(MonitoringRuntime, subject_id).current_stream_ids == []
        session.commit()
    exported = [json.loads(line) for line in runtime.export_records(db, settings=policy(), user_id="owner", organization_id="org-a", subject_id=subject_id)]
    assert exported[-1] == {"type": "complete", "complete": True}
    assert len([row for row in exported if row["type"] == "configuration"]) == 2
    assert [row["record"]["decision"] for row in exported if row["type"] == "review"] == ["not_relevant", "continue", "reviewed"]
    with db.session() as session:
        runtime.remove(session, user_id="owner", subject_id=subject_id, expected_revision=2, expected_version=3)
        session.commit()
    with db.session() as session:
        for model in (MonitoringSubject, MonitoringLiveStream, MonitoringLiveEntry, MonitoringDelivery, MonitoringReview, MonitoringRuntime, MonitoringCommand):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.scalar(select(func.count()).select_from(MonitoringSourceSample)) == 2
        assert all(job.cancel_requested for job in session.scalars(select(Job)))


def test_today_review_reopens_and_stale_state_is_computed_at_read(db):
    subject_id = seed(db)
    input_sample(db, "0")
    started = command(db, subject_id)
    input_sample(db, "10", 1)
    refresh(db, subject_id, started["runtime"]["run_id"], 1)
    with db.session() as session:
        items = runtime.today(session, settings=policy(), user_id="owner", now=NOW + timedelta(hours=1))["items"]
        assert len(items) == 1 and items[0]["subject_id"] == subject_id
        assert runtime.today(session, settings=policy(), user_id="peer", now=NOW)["items"] == []
        runtime.review(session, user_id="owner", subject_id=subject_id, entry_id=items[0]["id"], decision="reviewed", expected_version=0)
        assert runtime.today(session, settings=policy(), user_id="owner", now=NOW)["items"] == []
        session.commit()
    input_sample(db, "0", 2)
    refresh(db, subject_id, started["runtime"]["run_id"], 2)
    with db.session() as session:
        items = runtime.today(session, settings=policy(), user_id="owner", now=NOW + timedelta(hours=2))["items"]
        assert len(items) == 1 and items[0]["reasons"] == ["threshold_reset"]
        stale = runtime.state(session, settings=policy(), user_id="owner", subject_id=subject_id, now=NOW + timedelta(days=1))
        assert stale["runtime"]["health"] == "unavailable" and stale["current"][0]["availability"] == "stale"


def test_revoked_source_withholds_history_and_raw_export_requires_separate_permission(db, tmp_path):
    import hashlib

    from helvetic_lens.monitoring_live_models import MonitoringSourceArtifact
    from helvetic_lens.pollen_collector import _retain
    body = b"isolated synthetic public source"
    digest = hashlib.sha256(body).hexdigest()
    subject_id = seed(db)
    input_sample(db, "0", artifact_hashes=(digest,))
    command(db, subject_id)
    settings = policy(data_dir=tmp_path)
    _retain(tmp_path, digest, body)
    with db.session() as session:
        entry = runtime.history(session, user_id="owner", subject_id=subject_id)["items"][0]
        session.add(MonitoringSourceArtifact(sha256=digest, source_id=SERIES.source_id, identity="synthetic-test", byte_count=len(body), fetched_at=NOW, retention_until=NOW + timedelta(days=1), attribution="Synthetic test"))
        session.commit()
        args = dict(settings=settings, user_id="owner", subject_id=subject_id, entry_id=entry["id"], artifact_hash=digest, now=NOW)
        with pytest.raises(DomainError):
            runtime.artifact_path(session, **args)
        settings.pollen_source_policy = settings.pollen_source_policy.model_copy(update={"channels": (
            settings.pollen_source_policy.channels[0].model_copy(update={"raw_export_allowed": True}),)})
        assert runtime.artifact_path(session, **args).read_bytes() == body
        settings.pollen_source_policy = settings.pollen_source_policy.model_copy(update={"channels": (
            settings.pollen_source_policy.channels[0].model_copy(update={"status": "revoked"}),)})
        redacted = runtime.history(session, user_id="owner", subject_id=subject_id, settings=settings, now=NOW)["items"][0]
        assert redacted["current"]["value"] is None and redacted["source_withheld"]
        with pytest.raises(DomainError):
            runtime.artifact_path(session, **args)


def test_stale_paused_editor_cannot_revise_after_another_session_resumes(db):
    subject_id = seed(db)
    command(db, subject_id)
    command(db, subject_id, "pause", version=1)
    with db.session() as stale:
        current = subjects.get_subject(stale, user_id="owner", subject_id=subject_id)
        assert current["status"] == "paused"
        command(db, subject_id, "resume", version=2)
        with pytest.raises(DomainError) as conflict:
            runtime.revise_paused(stale, user_id="owner", subject_id=subject_id, expected_revision=1,
                configuration=current["configuration"], now=NOW)
        assert conflict.value.code == "subject_revision_conflict"


def test_source_readmission_rebaselines_even_when_operator_reuses_policy_version(db):
    subject_id = seed(db)
    input_sample(db, "0")
    run_id = command(db, subject_id, consent=True)["runtime"]["run_id"]
    unavailable = policy().model_copy(update={"pollen_source_policy": policy().pollen_source_policy.model_copy(update={"channels": ()})})
    with db.session() as session:
        assert runtime.refresh_from_cache(session, settings=unavailable, user_id="owner", subject_id=subject_id,
            run_id=run_id, now=NOW + timedelta(minutes=20))["status"] == "source_not_approved"
        session.commit()
    input_sample(db, "30", 1)
    assert refresh(db, subject_id, run_id, 1)["material_changes"] == 0
    with db.session() as session:
        rows = runtime.history(session, user_id="owner", subject_id=subject_id)["items"]
        assert rows[0]["kind"] == "recovered" and rows[0]["material_id"] is None
        assert session.scalar(select(func.count()).select_from(MonitoringDelivery)) == 0


def test_stale_runtime_identity_map_cannot_overwrite_another_command(db):
    subject_id = seed(db)
    command(db, subject_id)
    with db.session() as stale:
        cached = stale.get(MonitoringRuntime, subject_id)
        assert cached.version == 1
        command(db, subject_id, "mute", version=1)
        with pytest.raises(DomainError) as conflict:
            runtime.command(stale, settings=policy(), user_id="owner", subject_id=subject_id,
                action="pause", expected_revision=1, expected_version=1, request_key="stale-pause", now=NOW)
        assert conflict.value.code == "monitoring_version_conflict"
    with db.session() as session:
        assert session.get(MonitoringRuntime, subject_id).version == 2
        assert session.get(MonitoringRuntime, subject_id).muted
        assert session.get(MonitoringSubject, subject_id).status == "active"
