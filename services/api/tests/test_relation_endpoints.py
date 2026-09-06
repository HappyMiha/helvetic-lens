"""A confirmed relation must connect the displayed pair in its actual direction."""

import pytest
from sqlalchemy import func, select
from test_relation_analysis import relation_delivery
from test_relation_evidence_gate import draft, finish

from helvetic_lens.models import (
    DocumentWatch,
    Job,
    OrganizationRelationCandidate,
    RegulatoryEvent,
    RegulatoryRelation,
    RegulatoryWork,
    RelationCandidate,
)
from helvetic_lens.relation_identity import relation_direction


@pytest.mark.parametrize(
    "subject,object_,expected",
    [
        ("source", "target", "outgoing"),
        ("target", "source", "incoming"),
        ("other", "target", None),
        ("source", "other", None),
        ("source", "source", None),
        (None, "target", None),
        ("source", None, None),
    ],
)
def test_relation_pair_direction_requires_both_identities(subject, object_, expected):
    assert (
        relation_direction({"subject_work_id": subject, "object_work_id": object_}, "source", "target")
        == expected
    )
    assert (
        relation_direction({"subject_work_id": subject, "object_work_id": object_}, "source", "source")
        is None
    )


@pytest.mark.parametrize(
    "official",
    [
        {"id": "official-1", "state": "confirmed"},
        {"id": "official-1", "state": "confirmed", "subject_work_id": "other", "object_work_id": "target"},
        {"id": "official-1", "state": "confirmed", "subject_work_id": "source", "object_work_id": "other"},
        {"id": "official-1", "state": "confirmed", "subject_work_id": "source", "object_work_id": "source"},
    ],
)
def test_matching_citation_id_cannot_prove_an_unrelated_official_pair(official):
    value = draft()
    value["citation_rows"] = [6]
    value["actions"][0]["citation_rows"] = [6]
    report = finish(value, official=official)
    assert not report["supported"] and report["actions"] == []
    assert report["official_relation"] is None and report["potential_severity"] == "none"


def test_incoming_official_pair_remains_valid_evidence():
    value = draft()
    value["citation_rows"] = [6]
    value["actions"][0]["citation_rows"] = [6]
    report = finish(
        value,
        official={
            "id": "official-1",
            "state": "confirmed",
            "type": "amends",
            "subject_work_id": "target",
            "object_work_id": "source",
        },
    )
    assert report["supported"] and report["actions"]


@pytest.mark.parametrize("side", ["subject_work_id", "object_work_id"])
def test_mismatched_pair_is_not_official_in_inbox_prompt_or_successor_action(harness, side):
    client, _, service, model = harness
    delivery_id, _ = relation_delivery(harness, confirmed=True, relation_type="replaces")
    with service.db.session() as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        candidate = session.get(RelationCandidate, delivery.candidate_id)
        unrelated = RegulatoryWork(
            authority="test", kind="act", canonical_key="unrelated-endpoint", title="Unrelated work"
        )
        session.add(unrelated)
        session.flush()
        relation = session.get(RegulatoryRelation, candidate.relation_id)
        setattr(relation, side, unrelated.id)
        session.get(RegulatoryEvent, candidate.event_id).event_type = "replaced"
        jobs = session.scalar(select(func.count()).select_from(Job))
        watches = session.scalar(select(func.count()).select_from(DocumentWatch))
        session.commit()
        context = service._relation_analysis_context(session, delivery_id, "test-runtime")
        assert context["official_relation"] is None
        assert not any(row["source_kind"] == "official_relation" for row in context["evidence"])
    for route in ("/api/impact-inbox", "/api/impact-inbox/page"):
        response = client.get(route)
        assert response.status_code == 200, response.text
        item = response.json()["items"][0]["items"][0]
        assert item["official_relation"] is None and item["replacement"] is None
        assert item["status"] == "awaiting_analysis" and item["severity"] == "unknown"
        assert "official source records" not in item["potential_effect"]
        assert item["links"]["relation_evidence"] is None
        assert client.get(route, params={"severity": "high"}).json()["items"] == []
    response = client.post(f"/api/relation-candidates/{delivery_id}/monitor-successor")
    assert response.status_code == 409 and response.json()["code"] == "successor_not_confirmed"
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == jobs
        assert session.scalar(select(func.count()).select_from(DocumentWatch)) == watches
    assert model.calls == []


def test_incoming_replacement_uses_official_subject_as_successor(harness):
    client, _, service, model = harness
    delivery_id, _ = relation_delivery(harness, confirmed=True, relation_type="replaces")
    with service.db.session() as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        candidate = session.get(RelationCandidate, delivery.candidate_id)
        source, target = candidate.source_work_id, candidate.target_work_id
        watch = session.get(DocumentWatch, delivery.watch_id)
        law_id = watch.law_id
        relation = session.get(RegulatoryRelation, candidate.relation_id)
        relation.subject_work_id, relation.object_work_id = target, source
        session.commit()
        context = service._relation_analysis_context(session, delivery_id, "test-runtime")
        official = context["official_relation"]
        assert official["direction"] == "incoming" and official["subject_work_id"] == target
        assert official["object_work_id"] == source
        assert any(row["source_kind"] == "official_relation" for row in context["evidence"])
    for route in ("/api/impact-inbox", "/api/impact-inbox/page"):
        item = client.get(route).json()["items"][0]["items"][0]
        assert item["status"] == "confirmed_relation" and item["official_relation"]["direction"] == "incoming"
        assert item["replacement"]["successor"]["work_id"] == target
        assert item["replacement"]["successor"]["law_id"] == law_id
        assert item["replacement"]["successor"]["monitored"] is True
        assert item["replacement"]["predecessor"]["work_id"] == source
        assert item["replacement"]["predecessor"]["work_id"] != item["replacement"]["successor"]["work_id"]
    with service.db.session() as session:
        count = session.scalar(select(func.count()).select_from(DocumentWatch))
    response = client.post(f"/api/relation-candidates/{delivery_id}/monitor-successor")
    assert response.status_code == 201, response.text
    assert response.json()["id"] == law_id
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(DocumentWatch)) == count
    assert model.calls == []


def test_prepared_digest_cannot_derive_urgency_from_unrelated_replacement(harness, monkeypatch):
    from test_digest_periods import recipient
    from test_digest_resume import record_mail

    from helvetic_lens import digests

    _, _, service, model = harness
    delivery_id, _ = relation_delivery(harness, confirmed=True, relation_type="replaces")
    with service.db.session() as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        candidate = session.get(RelationCandidate, delivery.candidate_id)
        session.get(RegulatoryEvent, candidate.event_id).event_type = "replaced"
        session.commit()
        event_id, relation_id, source_id = candidate.event_id, candidate.relation_id, candidate.source_work_id
    user_id = recipient(service)
    service.save_digest_preference(user_id, enabled=True, frequency="daily", sources=[], severities=["high"])
    job = service.enqueue_digest_now(user_id)
    sent = record_mail(monkeypatch)
    with service.db.session() as session:
        checkpoint = digests.prepare_batch(session, job["target_id"], settings=service.settings)
    assert checkpoint["complete"] and event_id in checkpoint["event_ids"]
    with service.db.session() as session:
        session.get(RegulatoryRelation, relation_id).object_work_id = source_id
        session.commit()
    result = digests.deliver(
        service.db,
        service.environment_settings,
        job["target_id"],
        selection=checkpoint,
        analysis_settings=service.settings,
    )
    assert result["status"] == "skipped" and result["item_count"] == 0
    assert sent == [] and model.calls == []
