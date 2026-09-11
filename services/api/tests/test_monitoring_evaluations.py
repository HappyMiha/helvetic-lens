"""Atomic private rehearsal evidence on SQLite and optional isolated PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier

import pytest
from alembic.config import Config
from sqlalchemy import event, func, select, update
from sqlalchemy.exc import IntegrityError
from test_monitoring_subjects import db as db
from test_pollen_numeric import binding as numeric_binding
from test_pollen_thresholds import NOW, sample

from alembic import command
from helvetic_lens import monitoring_evaluations as ledger
from helvetic_lens import monitoring_subjects as subjects
from helvetic_lens.config import DomainError
from helvetic_lens.models import (
    MonitoringEvaluationEntry,
    MonitoringEvaluationStream,
    MonitoringSubject,
    MonitoringSubjectRevision,
    OrganizationMembership,
    OutboxMessage,
    User,
)
from helvetic_lens.pollen_numeric import NumericBinding


def seed(db):
    configured = numeric_binding()
    configuration = {"station_id": configured.series.station_id,
                     "selections": [{"allergen": configured.series.allergen,
                                     "rules": [configured.rule.model_dump(mode="json")]}]}
    with db.session() as session:
        subject = subjects.create_draft(session, user_id="owner", request_key="numeric", configuration=configuration)
        session.commit()
    return NumericBinding(**{**configured.model_dump(), "organization_id": "org-a", "owner_id": "owner",
                             "subject_id": subject["id"]})


def evaluate(session, binding, sequence=0, value="0", hour=2, key="first"):
    return ledger.evaluate_draft(session, user_id="owner", binding=binding, current=sample(value, hour),
        baseline=sample("0", hour - 2), as_of=NOW + timedelta(hours=hour), expected_sequence=sequence, request_key=key)


def saved(db, binding, **kwargs):
    with db.session() as session:
        entry = evaluate(session, binding, **kwargs)
        session.commit()
        return entry


def counts(session):
    return tuple(session.scalar(select(func.count()).select_from(model))
                 for model in (MonitoringEvaluationStream, MonitoringEvaluationEntry, OutboxMessage))


def test_restart_exact_retry_and_source_replay_keep_one_material_update(db):
    binding = seed(db)
    initial = saved(db, binding)
    crossed = saved(db, binding, sequence=1, value="10", hour=3, key="crossing")
    assert crossed["decision"]["reasons"] == ["threshold_triggered", "rapid_triggered"]
    assert crossed["material_id"] and crossed["evidence_kind"] == "draft_rehearsal"
    db.migrate()
    assert saved(db, binding) == initial  # Old request returns old immutable entry, not latest state.
    assert saved(db, binding, sequence=1, value="10", hour=3, key="crossing") == crossed
    replay = saved(db, binding, sequence=2, value="10", hour=3, key="source-replay")
    assert replay["material_id"] is None
    with db.session() as session:
        checkpoint = ledger.get_checkpoint(session, user_id="owner", binding=binding)
        assert checkpoint["sequence"] == 3 and checkpoint["state"]["threshold"]["active"]
        assert counts(session) == (1, 3, 0)
        material = list(session.scalars(select(MonitoringEvaluationEntry).where(
            MonitoringEvaluationEntry.material_id.is_not(None))))
        assert len(material) == 1


def test_conflicting_request_or_stale_checkpoint_does_not_append(db):
    binding = seed(db)
    saved(db, binding)
    with db.session() as session:
        for kwargs, code in (({"value": "1"}, "evaluation_request_conflict"),
                             ({"key": "stale"}, "evaluation_sequence_conflict")):
            with pytest.raises(DomainError) as conflict:
                evaluate(session, binding, **kwargs)
            assert conflict.value.code == code
        assert counts(session) == (1, 1, 0)
        assert ledger.get_checkpoint(session, user_id="owner", binding=binding)["sequence"] == 1


def test_rollback_and_failure_between_checkpoint_and_entry_are_atomic(db):
    binding = seed(db)
    with db.session() as session:
        evaluate(session, binding)
        session.rollback()
    with db.session() as session:
        assert counts(session) == (0, 0, 0)
    saved(db, binding)

    def fail_entry(_mapper, _connection, _target):
        raise RuntimeError("injected evidence write failure")

    event.listen(MonitoringEvaluationEntry, "before_insert", fail_entry)
    try:
        with db.session() as session:
            with pytest.raises(RuntimeError, match="injected"):
                evaluate(session, binding, sequence=1, value="10", hour=3, key="failed")
            session.commit()  # Savepoint already reverted the checkpoint update.
    finally:
        event.remove(MonitoringEvaluationEntry, "before_insert", fail_entry)
    with db.session() as session:
        assert ledger.get_checkpoint(session, user_id="owner", binding=binding)["sequence"] == 1
        assert counts(session) == (1, 1, 0)
        evaluate(session, binding, sequence=1, value="10", hour=3, key="rolled-back")
        session.rollback()
    assert saved(db, binding, sequence=1, value="10", hour=3, key="retry")["material_id"]


def test_historical_input_is_evidence_without_rolling_back_current_state_and_pages_are_bounded(db):
    binding = seed(db)
    saved(db, binding)
    saved(db, binding, sequence=1, value="10", hour=3, key="cross")
    with db.session() as session:
        before = ledger.get_checkpoint(session, user_id="owner", binding=binding)["state"]
        old = ledger.evaluate_draft(session, user_id="owner", binding=binding, current=sample("0", 1),
            as_of=NOW + timedelta(hours=3), baseline=None, expected_sequence=2, request_key="old")
        session.commit()
        assert old["decision"]["disposition"] == "history_required" and old["material_id"] is None
        assert old["request"]["as_of"] == (NOW + timedelta(hours=3)).isoformat()
        assert old["request"]["current"] == sample("0", 1).model_dump(mode="json")
        assert ledger.get_checkpoint(session, user_id="owner", binding=binding)["state"] == before
        page = ledger.evaluation_history(session, user_id="owner", binding=binding, limit=1)
        assert page["items"][0]["sequence"] == page["next_before_sequence"] == 3
        rest = ledger.evaluation_history(session, user_id="owner", binding=binding,
                                        before_sequence=page["next_before_sequence"])
        assert [row["sequence"] for row in rest["items"]] == [2, 1] and rest["next_before_sequence"] is None
        for kwargs in ({"limit": 0}, {"limit": True}, {"before_sequence": 0}):
            with pytest.raises(DomainError):
                ledger.evaluation_history(session, user_id="owner", binding=binding, **kwargs)


def test_owner_workspace_and_revocation_are_rechecked(db):
    binding = seed(db)
    saved(db, binding)
    with db.session() as session:
        for read in (ledger.get_checkpoint, ledger.evaluation_history):
            with pytest.raises(DomainError) as denied:
                read(session, user_id="peer", binding=binding)
            assert denied.value.status == 404
        forged = NumericBinding(**{**binding.model_dump(), "owner_id": "peer"})
        with pytest.raises(DomainError) as denied:
            ledger.get_checkpoint(session, user_id="peer", binding=forged)
        assert denied.value.status == 404
    with db.organization_context("org-b"), db.session() as session:
        assert list(session.scalars(select(MonitoringEvaluationStream))) == []
        assert list(session.scalars(select(MonitoringEvaluationEntry))) == []
        with pytest.raises(DomainError) as denied:
            ledger.get_checkpoint(session, user_id="owner", binding=binding)
        assert denied.value.status == 404
        with pytest.raises(DomainError) as denied:
            evaluate(session, binding)
        assert denied.value.status == 404
    with db.session() as session:
        ledger.get_checkpoint(session, user_id="owner", binding=binding)
        with db.engine.begin() as connection:
            connection.execute(update(OrganizationMembership).where(
                OrganizationMembership.user_id == "owner", OrganizationMembership.organization_id == "org-a",
            ).values(role="viewer"))
        assert ledger.get_checkpoint(session, user_id="owner", binding=binding)["sequence"] == 1
        with pytest.raises(DomainError) as denied:
            evaluate(session, binding)
        assert denied.value.status == 403
        with db.engine.begin() as connection:
            connection.execute(update(User).where(User.id == "owner").values(active=False))
        with pytest.raises(DomainError) as denied:
            ledger.evaluation_history(session, user_id="owner", binding=binding)
        assert denied.value.status == 403


@pytest.mark.parametrize("field,value", [("station_id", "PZH"), ("allergen", "ragweed")])
def test_binding_must_match_saved_configuration(db, field, value):
    binding = seed(db)
    forged = NumericBinding(**{**binding.model_dump(), "series": {**binding.series.model_dump(), field: value}})
    with db.session() as session, pytest.raises(DomainError) as denied:
        evaluate(session, forged)
    assert denied.value.status == 422


def test_changed_rule_and_revision_cannot_reuse_checkpoint_but_history_remains_readable(db):
    binding = seed(db)
    saved(db, binding)
    forged = NumericBinding(**{**binding.model_dump(), "rule": {
        **binding.rule.model_dump(), "threshold": {"trigger_at_or_above": "50", "reset_at_or_below": "5"}}})
    with db.session() as session:
        with pytest.raises(DomainError):
            evaluate(session, forged)
        config = subjects.get_subject(session, user_id="owner", subject_id=binding.subject_id)["configuration"]
        subjects.revise_draft(session, user_id="owner", subject_id=binding.subject_id,
                              expected_revision=1, configuration=config)
        session.commit()
        with pytest.raises(DomainError) as denied:
            evaluate(session, binding)
        assert denied.value.code == "evaluation_configuration_conflict"
        assert ledger.evaluation_history(session, user_id="owner", binding=binding)["items"][0]["sequence"] == 1
    revised = NumericBinding(**{**binding.model_dump(), "configuration_revision": 2})
    assert saved(db, revised)["sequence"] == 1


@pytest.mark.parametrize("status", ["active", "paused", "archived"])
def test_non_draft_cannot_be_evaluated(db, status):
    binding = seed(db)
    with db.session() as session:
        session.execute(update(MonitoringSubject).where(MonitoringSubject.id == binding.subject_id).values(status=status))
        session.commit()
        with pytest.raises(DomainError) as denied:
            evaluate(session, binding)
        assert denied.value.code == "evaluation_configuration_conflict"
        assert counts(session) == (0, 0, 0)


@pytest.mark.parametrize("same_request", [True, False])
@pytest.mark.parametrize("existing_checkpoint", [True, False])
def test_concurrent_writers_replay_or_conflict_without_lost_state(db, same_request, existing_checkpoint):
    binding = seed(db)
    if existing_checkpoint:
        saved(db, binding, key="baseline")
    sequence = 1 if existing_checkpoint else 0
    barrier = Barrier(2)

    def attempt(key):
        with db.session() as session:
            barrier.wait(timeout=10)
            try:
                result = evaluate(session, binding, key=key, sequence=sequence, value="10", hour=3)
                session.commit()
                return result["id"]
            except DomainError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(attempt, "first"), pool.submit(attempt, "first" if same_request else "second")
        results = [first.result(timeout=20), second.result(timeout=20)]
    if same_request:
        assert results[0] == results[1] and results[0] != "evaluation_sequence_conflict"
    else:
        assert results.count("evaluation_sequence_conflict") == 1
    with db.session() as session:
        assert counts(session) == (1, sequence + 1, 0)
        material_count = session.scalar(select(func.count()).select_from(MonitoringEvaluationEntry).where(
            MonitoringEvaluationEntry.material_id.is_not(None)))
        assert material_count == int(existing_checkpoint)


def test_cross_scope_foreign_keys_and_subject_deletion(db):
    binding = seed(db)
    saved(db, binding)
    with db.session() as session:
        stream = session.scalar(select(MonitoringEvaluationStream))
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(MonitoringEvaluationStream(organization_id="org-b", subject_id=binding.subject_id,
                configuration_revision=1, binding_hash="c" * 64, binding_json={}, sequence=1, state_json={}))
            session.flush()
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(MonitoringEvaluationEntry(organization_id="org-b", stream_id=stream.id, sequence=2,
                request_key="forged", request_hash="a" * 64, decision_json={}, request_json={}))
            session.flush()
        subjects.delete_draft(session, user_id="owner", subject_id=binding.subject_id, expected_revision=1)
        session.commit()
        assert counts(session) == (0, 0, 0)


def test_additive_upgrade_preserves_drafts_and_prior_configuration(db):
    binding = seed(db)
    migration = Config()
    migration.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    with db.engine.begin() as connection:
        migration.attributes["connection"] = connection
        command.downgrade(migration, "f0627ab1d43e")
        before = {model.__tablename__: connection.execute(select(model.__table__)).all()
                  for model in (MonitoringSubject, MonitoringSubjectRevision)}
        command.upgrade(migration, "head")
        for model in (MonitoringSubject, MonitoringSubjectRevision):
            assert connection.execute(select(model.__table__)).all() == before[model.__tablename__]
    assert saved(db, binding)["sequence"] == 1
