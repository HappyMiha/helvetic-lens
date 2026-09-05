"""A history badge must not materialize every past analysis/evidence payload."""

from datetime import timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import event, insert, inspect
from test_relation_analysis import relation_delivery

from alembic import command
from helvetic_lens import relation_analysis
from helvetic_lens.db import utcnow
from helvetic_lens.impact_inbox import ImpactInboxReader
from helvetic_lens.models import (
    Organization,
    OrganizationRelationCandidate,
    RelationCandidate,
    RelationImpactAnalysis,
)


def history_rows(service, delivery_id, count=10_000):
    with service.db.session() as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        candidate = session.get(RelationCandidate, delivery.candidate_id)
        base = {
            "organization_id": delivery.organization_id, "organization_candidate_id": delivery.id,
            "candidate_id": candidate.id, "event_id": candidate.event_id,
            "target_work_id": candidate.target_work_id, "cache_key": "0" * 64,
            "analysis_plan": {"execution": {"profile_revision": 1}},
            "model": "test-only", "status": "succeeded", "created_at": utcnow() - timedelta(hours=1),
            "evidence_json": [{"text": "Synthetic archived evidence. " * 30}],
        }
        # Equal timestamps force the stable ID tiebreaker; most of this history
        # is successful but obsolete, with one much older current-schema result.
        for start in range(0, count, 500):
            rows = [{**base, "id": f"99000000-0000-0000-0000-{index:012d}",
                     "result": {"schema_version": relation_analysis.SCHEMA_VERSION if index == 0 else "old-test-schema",
                                "supported": True, "explanation": "Synthetic retained conclusion."}}
                    for index in range(start, min(count, start + 500))]
            session.execute(insert(RelationImpactAnalysis), rows)
        latest_id = f"99000000-0000-0000-0000-{count:012d}"
        session.execute(insert(RelationImpactAnalysis), [{**base, "id": latest_id,
                        "status": "failed", "result": None, "error": "Test-only failed attempt"}])
        session.commit()
        return "99000000-0000-0000-0000-000000000000", latest_id


def test_large_history_reads_only_latest_and_current_payloads(harness):
    client, _, service, model = harness
    delivery_id, _ = relation_delivery(harness)
    current_id, latest_id = history_rows(service, delivery_id)
    loaded, queries = [], []

    def count_query(_connection, _cursor, statement, _parameters, _context, _many):
        if "relation_impact_analyses" in statement and statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    with service.db.session() as session:
        event.listen(session, "loaded_as_persistent", lambda _session, row: loaded.append(row))
        event.listen(service.db.engine, "before_cursor_execute", count_query)
        try:
            current, latest, count = ImpactInboxReader._latest_analyses(session, delivery_id)
        finally:
            event.remove(service.db.engine, "before_cursor_execute", count_query)
        assert count == 10_001 and (current.id, latest.id) == (current_id, latest_id)
        assert len(queries) == 3 and len(loaded) == 2
        assert len(session.identity_map) == 2
    body = client.get("/api/impact-inbox").json()
    item = body["items"][0]["items"][0]
    assert item["current_analysis_id"] == current_id and item["latest_attempt_id"] == latest_id
    assert item["analysis_history_count"] == 10_001 and item["status"] == "possible_impact"
    assert model.calls == []


@pytest.mark.parametrize("result,status", [(None, "failed"), ({"schema_version": "legacy"}, "succeeded"),
                                         ({"schema_version": relation_analysis.SCHEMA_VERSION}, "succeeded")])
def test_empty_legacy_and_current_history_keep_selection_and_tenant_scope(harness, result, status):
    _, _, service, _ = harness
    delivery_id, _ = relation_delivery(harness)
    with service.db.session() as session:
        assert ImpactInboxReader._latest_analyses(session, delivery_id) == (None, None, 0)
    current_id, _ = history_rows(service, delivery_id, count=1)
    with service.db.session() as session:
        current = session.get(RelationImpactAnalysis, current_id)
        current.result, current.status = result, status
        foreign = Organization(name="History outsider", slug="history-outsider")
        session.add(foreign)
        session.commit()
        foreign_id = foreign.id
    with service.db.session() as session:
        current, latest, count = ImpactInboxReader._latest_analyses(session, delivery_id)
        assert bool(current) == (status == "succeeded" and result and result.get("schema_version") == relation_analysis.SCHEMA_VERSION)
        assert latest.status == "failed" and count == 2
    with service.db.organization_context(foreign_id), service.db.session() as session:
        assert ImpactInboxReader._latest_analyses(session, delivery_id) == (None, None, 0)


def check_history_index_roundtrip(service, delivery_id):
    directory = Path(__file__).resolve().parents[1]
    config = Config(str(directory / "alembic.ini"))
    config.set_main_option("script_location", str(directory / "alembic"))
    with service.db.session() as session:
        before = ImpactInboxReader._latest_analyses(session, delivery_id)
        expected = (before[0].id, before[1].id, before[2])
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "f9c208b5a431")
        assert "ix_relation_analysis_org_candidate_time" not in {item["name"] for item in inspect(connection).get_indexes("relation_impact_analyses")}
        command.upgrade(config, "head")
        assert "ix_relation_analysis_org_candidate_time" in {item["name"] for item in inspect(connection).get_indexes("relation_impact_analyses")}
    with service.db.session() as session:
        after = ImpactInboxReader._latest_analyses(session, delivery_id)
        assert (after[0].id, after[1].id, after[2]) == expected


def test_history_index_roundtrip_preserves_saved_selection(harness):
    _, _, service, _ = harness
    delivery_id, _ = relation_delivery(harness)
    history_rows(service, delivery_id, count=3)
    check_history_index_roundtrip(service, delivery_id)


def test_newer_attempt_between_queries_waits_for_the_next_read(harness, monkeypatch):
    _, _, service, _ = harness
    delivery_id, _ = relation_delivery(harness)
    expected_current, expected_latest = history_rows(service, delivery_id, count=1)
    with service.db.session() as session:
        original = session.scalar
        injected = False

        def read(*args, **kwargs):
            nonlocal injected
            value = original(*args, **kwargs)
            if not injected and isinstance(value, RelationImpactAnalysis):
                injected = True
                session.execute(insert(RelationImpactAnalysis), [{
                    "id": "99000000-0000-0000-0000-000000099999",
                    "organization_id": value.organization_id,
                    "organization_candidate_id": value.organization_candidate_id,
                    "candidate_id": value.candidate_id, "event_id": value.event_id,
                    "target_work_id": value.target_work_id, "cache_key": "1" * 64,
                    "analysis_plan": {"execution": {"profile_revision": 1}},
                    "model": "test-only", "status": "succeeded",
                    "result": {"schema_version": relation_analysis.SCHEMA_VERSION},
                    "created_at": value.created_at + timedelta(minutes=1),
                }])
            return value

        monkeypatch.setattr(session, "scalar", read)
        current, latest, count = ImpactInboxReader._latest_analyses(session, delivery_id)
        assert (current.id, latest.id, count) == (expected_current, expected_latest, 2)
        current, latest, count = ImpactInboxReader._latest_analyses(session, delivery_id)
        assert current.id == latest.id == "99000000-0000-0000-0000-000000099999"
        assert count == 3
