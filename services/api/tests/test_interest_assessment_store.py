"""Real transactions: coalescing, immutable successes and stale-worker fences."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from alembic.config import Config
from sqlalchemy import func, inspect, select
from test_interest_assessment import Model, dossier, draft_for, run
from test_interest_feed import seed

from alembic import command
from helvetic_lens.config import DomainError
from helvetic_lens.interest_assessment_store import AssessmentStore
from helvetic_lens.models import (
    InterestAssessmentAttempt,
    InterestAssessmentBinding,
    InterestEventAssessment,
    Organization,
)


def setup(harness):
    _, events = seed(harness)
    service = harness[2]
    value = dossier(organization_id=service.organization_id, event_id=events[0])
    return service, AssessmentStore(service.organization_id), value


def prepare(service, store, value):
    with service.db.session() as session:
        row, created = store.prepare(session, value)
        session.commit()
        return row.id, row.input_fingerprint, created


def claim(service, store, key, fingerprint):
    with service.db.session() as session:
        token = store.claim(session, key, fingerprint)
        session.commit()
        return token


def test_persisted_brief_is_reused_without_inference_and_preserves_exact_source_bindings(harness):
    service, store, value = setup(harness)
    key, fingerprint, created = prepare(service, store, value)
    assert created
    token = claim(service, store, key, fingerprint)
    assert token and claim(service, store, key, fingerprint) is None
    model = Model(draft_for(value))
    result, provenance = run(model, value)
    with service.db.session() as session:
        assert store.finish(session, key, token, value, result, provider_calls=provenance["provider_calls"])
        session.commit()
    for _ in range(3):
        assert prepare(service, store, value) == (key, fingerprint, False)
        with service.db.session() as session:
            saved = store.exact(session, value.event.id, fingerprint)
            assert saved.status == "succeeded" and saved.result == result
            assert saved.created_at and saved.started_at and saved.finished_at
    assert len(model.calls) == 1
    with service.db.session() as session:
        bindings = list(session.scalars(select(InterestAssessmentBinding)))
        assert {(r.kind, r.reference_id) for r in bindings} == {
            ("topic", "match-0"), ("topic", "match-1"), ("evidence", "source"), ("evidence", "target")}
        saved = store.get(session, key)
        assert all(row.text not in json.dumps(saved.input_manifest) for row in value.evidence)
        assert saved.result["citations"][0]["unit_id"] == "article-2"
        assert not store.finish(session, key, token, value, result, provider_calls=1)


def test_revised_input_supersedes_inflight_work_and_old_worker_cannot_publish(harness):
    service, store, value = setup(harness)
    key, fingerprint, _ = prepare(service, store, value)
    token = claim(service, store, key, fingerprint)
    revised = value.model_copy(update={"profile_revision": 2})
    next_key, next_fingerprint, created = prepare(service, store, revised)
    assert created and next_key != key and next_fingerprint != fingerprint
    result, _ = run(Model(draft_for(value)), value)
    with service.db.session() as session:
        assert store.get(session, key).status == "superseded"
        assert session.get(InterestAssessmentAttempt, token).status == "superseded"
        assert session.get(InterestAssessmentAttempt, token).finished_at is not None
        assert not store.finish(session, key, token, value, result, provider_calls=1)
        assert not store.fail(session, key, token, "model_timeout")
        assert store.get(session, key).result is None
    next_token = claim(service, store, next_key, next_fingerprint)
    with service.db.session() as session:
        # A worker must not publish a different dossier under its reserved key.
        assert not store.finish(session, next_key, next_token, value, result, provider_calls=1)
        result, _ = run(Model(draft_for(revised)), revised)
        assert store.finish(session, next_key, next_token, revised, result, provider_calls=1)
        session.commit()
    newer = revised.model_copy(update={"profile_revision": 3})
    prepare(service, store, newer)
    with service.db.session() as session:
        assert store.get(session, next_key).status == "succeeded"
        assert store.get(session, next_key).result == result


def test_retry_is_explicit_bounded_and_does_not_store_provider_secrets(harness):
    service, store, value = setup(harness)
    key, fingerprint, _ = prepare(service, store, value)
    for attempt in range(3):
        token = claim(service, store, key, fingerprint)
        assert token
        with service.db.session() as session:
            assert store.fail(session, key, token, "provider echoed Authorization: secret-test-value")
            session.commit()
        assert prepare(service, store, value) == (key, fingerprint, False)
        with service.db.session() as session:
            row = store.get(session, key)
            assert row.status == "failed" and row.error_code == "provider_unavailable"
            assert row.attempts == attempt + 1
            assert store.retry(session, key, fingerprint) is (attempt < 2)
            session.commit()


def test_cross_org_reads_and_writes_are_rejected_even_in_privileged_session(harness):
    service, store, value = setup(harness)
    key, fingerprint, _ = prepare(service, store, value)
    token = claim(service, store, key, fingerprint)
    other = AssessmentStore("other-organization")
    with service.db.session(include_all_organizations=True) as session:
        session.add(Organization(id="other-organization", name="Other", slug="other-assessment"))
        session.commit()
        assert other.get(session, key) is None
        assert other.exact(session, value.event.id, fingerprint) is None
        assert other.claim(session, key, fingerprint) is None
        assert not other.fail(session, key, token, "model_timeout")
        assert not other.retry(session, key, fingerprint)
        result, _ = run(Model(draft_for(value)), value)
        assert not other.finish(session, key, token, value, result, provider_calls=1)
        with pytest.raises(DomainError):
            other.prepare(session, value)
        with pytest.raises(DomainError):
            other.prepare(session, value.model_copy(update={"organization_id": other.organization_id}))
    with service.db.organization_context(other.organization_id), service.db.session() as session:
        assert list(session.scalars(select(InterestEventAssessment))) == []
        assert list(session.scalars(select(InterestAssessmentBinding))) == []


def test_concurrent_reservations_and_claims_produce_one_assessment_and_one_owner(harness):
    service, store, value = setup(harness)
    barrier = Barrier(6)
    def reserve(_):
        barrier.wait(timeout=15)
        return prepare(service, store, value)
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(reserve, range(6)))
    assert len({row[0] for row in rows}) == 1
    assert sum(row[2] for row in rows) == 1
    key, fingerprint, _ = rows[0]
    with ThreadPoolExecutor(max_workers=6) as pool:
        tokens = list(pool.map(lambda _: claim(service, store, key, fingerprint), range(6)))
    assert len([token for token in tokens if token]) == 1
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(InterestEventAssessment)) == 1
        assert session.scalar(select(func.count()).select_from(InterestAssessmentBinding)) == 4
        attempts = list(session.scalars(select(InterestAssessmentAttempt)))
        assert len(attempts) == 1 and attempts[0].id == next(token for token in tokens if token)
        assert attempts[0].number == 1 and attempts[0].status == "running"


def test_unverified_result_cannot_be_persisted(harness):
    service, store, value = setup(harness)
    key, fingerprint, _ = prepare(service, store, value)
    token = claim(service, store, key, fingerprint)
    result = draft_for(value)
    result["why_in_radar"][0]["evidence_ids"] = ["target"]
    with service.db.session() as session:
        with pytest.raises(DomainError, match="exact interest"):
            store.finish(session, key, token, value, result, provider_calls=1)
        assert store.get(session, key).status == "running"
        assert store.get(session, key).result is None


def test_migration_roundtrip_preserves_existing_corpus_and_matches(harness):
    from helvetic_lens.models import RegulatoryEvent, TopicEventMatch
    service, _, value = setup(harness)
    with service.db.session() as session:
        match_ids = list(session.scalars(select(TopicEventMatch.id)))
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "d6c8e0173a94")
        assert "interest_event_assessments" not in inspect(connection).get_table_names()
        command.upgrade(config, "head")
        tables = inspect(connection)
        for model in (InterestEventAssessment, InterestAssessmentBinding):
            columns = {row["name"] for row in tables.get_columns(model.__tablename__)}
            assert columns == set(model.__table__.columns.keys())
        names = {row["name"] for row in tables.get_unique_constraints("interest_event_assessments")}
        assert "uq_interest_assessment_input" in names
        names = {row["name"] for row in tables.get_indexes("interest_assessment_bindings")}
        assert "ix_interest_binding_reference" in names
    with service.db.session() as session:
        assert session.get(RegulatoryEvent, value.event.id)
        assert list(session.scalars(select(TopicEventMatch.id))) == match_ids
