"""Batch history selection must retain current conclusions and human decisions."""

from datetime import timedelta

import pytest
from sqlalchemy import event, insert, select
from sqlalchemy.orm import Session
from test_digest_periods import seed_events

from helvetic_lens import relation_analysis
from helvetic_lens.db import utcnow
from helvetic_lens.impact_inbox import ImpactInboxReader
from helvetic_lens.models import (
    Organization,
    OrganizationRelationCandidate,
    OrganizationRelationReview,
    RelationCandidate,
    RelationImpactAnalysis,
    new_id,
)


def history_corpus(harness, count=50, archive=100):
    _, _, service, _ = harness
    stamp = utcnow()-timedelta(minutes=1)
    seed_events(harness, [{"id": f"83000000-0000-0000-0000-{i:012d}", "detected_at": stamp, "connector": "history-batch"} for i in range(count)])
    expected = {}
    with service.db.session() as session:
        deliveries = session.execute(select(OrganizationRelationCandidate, RelationCandidate).join(RelationCandidate)
                                     .where(RelationCandidate.event_id.like("83000000-%")).order_by(RelationCandidate.event_id)).all()
        for i, (delivery, candidate) in enumerate(deliveries):
            candidate.relation_id = None
            kind = i % 4
            expected[delivery.id] = kind
            if kind == 0:
                continue
            common = {"organization_id": service.organization_id, "organization_candidate_id": delivery.id, "created_at": stamp}
            analysis = {**common, "analysis_plan": {"execution": {"profile_revision": 1, "configuration_fingerprint": relation_analysis.configuration_fingerprint(service.settings)}}, "candidate_id": candidate.id, "event_id": candidate.event_id, "target_work_id": candidate.target_work_id,
                        "cache_key": "0"*64, "model": "test-only", "evidence_json": [{"text": "Synthetic archived evidence "*30}]}
            analyses, reviews = [], []
            for j in range(archive+1):
                valid = (kind == 1 and j == archive) or (kind == 2 and j == 0)
                failed = kind == 2 and j == archive
                analyses.append({**analysis, "id": f"81000000-0000-0000-0000-{i*1000+j:012d}", "status": "failed" if failed else "succeeded",
                                 "error": "Synthetic failed attempt" if failed else None,
                                 "result": None if failed else {"schema_version": relation_analysis.SCHEMA_VERSION if valid else "legacy",
                                                                "supported": True, "explanation": "Saved synthetic conclusion", "potential_severity": "low"}})
                reviews.append({**common, "id": f"82000000-0000-0000-0000-{i*1000+j:012d}",
                                "decision": "confirmed" if kind == 1 and j == 0 else "rejected" if kind == 2 and j == 0 else "annotated",
                                "note": f"Synthetic note {j}"})
            session.execute(insert(RelationImpactAnalysis), analyses)
            session.execute(insert(OrganizationRelationReview), reviews)
        session.commit()
    return expected


def test_page_selects_histories_in_four_queries_with_bounded_payloads(harness):
    client, _, service, model = harness
    expected = history_corpus(harness)
    queries, loaded = [], []
    def query(_connection, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith("SELECT") and any(table in statement for table in ("relation_impact_analyses", "organization_relation_reviews")):
            queries.append(statement)
    def record(_session, row):
        if isinstance(row, (RelationImpactAnalysis, OrganizationRelationReview)):
            loaded.append(row)
    event.listen(service.db.engine, "before_cursor_execute", query)
    event.listen(Session, "loaded_as_persistent", record)
    try:
        response = client.get("/api/impact-inbox/page", params={"source": "history-batch"})
        assert response.status_code == 200, response.text
        body = response.json()
    finally:
        event.remove(service.db.engine, "before_cursor_execute", query)
        event.remove(Session, "loaded_as_persistent", record)
    assert body["total_events"] == body["total_impacts"] == 50
    assert len(queries) == 4
    assert len(loaded) == sum({0: 0, 1: 3, 2: 4, 3: 2}[kind] for kind in expected.values())
    for group in body["items"]:
        item = group["items"][0]
        kind = expected[item["organization_candidate_id"]]
        assert item["analysis_history_count"] == item["review_history_count"] == (101 if kind else 0)
        if kind == 1:
            assert item["current_analysis_id"] == item["latest_attempt_id"]
            assert item["organization_review"]["decision"] == "confirmed" and item["latest_review"]["decision"] == "annotated"
        elif kind == 2:
            assert item["current_analysis_id"] != item["latest_attempt_id"] and item["latest_attempt_status"] == "failed"
            assert item["organization_review"]["decision"] == "rejected" and item["latest_review"]["decision"] == "annotated"
        elif kind == 3:
            assert item["current_analysis_id"] is None and item["status"] == "stale" and item["organization_review"] is None
        else:
            assert item["latest_attempt_id"] is None and item["latest_review"] is None
    assert model.calls == []


def test_legacy_large_page_splits_candidate_history_batches(harness, monkeypatch):
    client, _, _, _ = harness
    history_corpus(harness, count=121, archive=1)
    sizes = []
    original = ImpactInboxReader._page_histories
    def batch(self, session, ids):
        sizes.append(len(ids))
        return original(self, session, ids)
    monkeypatch.setattr(ImpactInboxReader, "_page_histories", batch)
    response = client.get("/api/impact-inbox", params={"source": "history-batch"})
    assert response.status_code == 200, response.text
    assert response.json()["total_events"] == 121 and sizes == [100, 21]


@pytest.mark.parametrize("model", [RelationImpactAnalysis, OrganizationRelationReview])
def test_new_history_after_scalar_selection_waits_for_next_read(harness, monkeypatch, model):
    _, _, service, _ = harness
    expected = history_corpus(harness, count=2, archive=1)
    delivery_id = next(id_ for id_, kind in expected.items() if kind == 1)
    reader = ImpactInboxReader(service.organization_id, None, settings=service.settings)
    relevant = (model.status == "succeeded") if model == RelationImpactAnalysis else model.decision.in_(("confirmed", "rejected"))
    with service.db.session() as session:
        prior = reader._history_selection(session, model, [delivery_id], relevant)[delivery_id]
        expected_ids = (prior[0].id, prior[1].id, prior[2])
        template = {column.name: getattr(prior[1], column.name) for column in model.__mapper__.columns}
        new = {**template, "id": new_id(), "created_at": prior[1].created_at+timedelta(minutes=1)}
        if model == OrganizationRelationReview:
            new["decision"] = "rejected"
        original = session.execute
        injected = False
        def execute(statement, *args, **kwargs):
            nonlocal injected
            result = original(statement, *args, **kwargs)
            if not injected and "first_value" in str(statement):
                injected = True
                frozen = result.freeze()
                original(insert(model), [new])
                return frozen()
            return result
        monkeypatch.setattr(session, "execute", execute)
        selected = reader._history_selection(session, model, [delivery_id], relevant)[delivery_id]
        assert (selected[0].id, selected[1].id, selected[2]) == expected_ids
        following = reader._history_selection(session, model, [delivery_id], relevant)[delivery_id]
        assert following[0].id == following[1].id == new["id"] and following[2] == 3


def test_batch_selector_explicitly_scopes_even_privileged_sessions(harness):
    _, _, service, _ = harness
    expected = history_corpus(harness, count=2, archive=1)
    with service.db.session() as session:
        other = Organization(name="Other history batch", slug="other-history-batch")
        session.add(other)
        session.commit()
        other_id = other.id
    with service.db.session(include_all_organizations=True) as session:
        reader = ImpactInboxReader(other_id, None, settings=service.settings)
        assert reader._page_histories(session, list(expected)) == ({}, {})
        assert reader._page_histories(session, []) == ({}, {})
        with pytest.raises(ValueError):
            reader._page_histories(session, [new_id() for _ in range(101)])
