"""Human relevance decisions retain exact evidence without changing personal state."""
from copy import deepcopy
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select
from test_interest_feed import seed
from test_topic_validity import evaluate

from helvetic_lens.db import utcnow
from helvetic_lens.maintenance import cleanup_operational_data
from helvetic_lens.models import (
    MonitoringTopic,
    Organization,
    RegulatoryEvent,
    RegulatoryEventState,
    TopicEventMatch,
    TopicMatchReview,
)
from helvetic_lens.topic_reviews import detail, save


def context(harness):
    client, _, service, _ = harness
    topic, ids = seed(harness)
    with service.db.session() as session:
        match_id = session.scalar(select(TopicEventMatch.id))
    current = client.get(f"/api/topic-matches/{match_id}/reviews").json()["match"]
    return topic, ids[0], match_id, {
        "decision": "rejected", "note": "This topic does not concern our activity.",
        "request_key": "review-request-000001",
        "expected_evaluation_fingerprint": current["evaluation_fingerprint"],
        "expected_review_id": current["review_id"],
    }


def test_review_hides_topic_feed_match_but_preserves_evidence_and_personal_state(harness):
    client, _, service, model = harness
    topic, event_id, match_id, body = context(harness)
    client.patch(f"/api/interest-feed/events/{event_id}/state", json={"state": "read"})
    endpoint = f"/api/topic-matches/{match_id}/reviews"
    before = client.get(endpoint).json()["match"]
    response = client.post(endpoint, json=body)
    assert response.status_code == 201, response.text
    review = response.json()["review"]
    assert review["decision"] == "rejected" and review["created_at"]
    assert review["snapshot"]["evidence"] == before["evidence"]
    assert client.get("/api/interest-feed").json()["items"] == []
    history = client.get(endpoint).json()
    assert history["match"]["decision_is_current"] is True
    assert len(history["items"]) == 1 and history["items"][0]["note"] == body["note"]
    assert client.get(f"/api/monitoring-topics/{topic['id']}/matches/page").json()["items"][0]["id"] == match_id
    restored = client.post(endpoint, json={**body, "request_key": "review-request-000002", "decision": "confirmed", "expected_review_id": review["id"]})
    assert restored.status_code == 201, restored.text
    assert client.get("/api/interest-feed").json()["items"][0]["read_state"] == "read"
    assert len(client.get(endpoint).json()["items"]) == 2
    assert model.calls == []


def test_retry_is_idempotent_and_changed_payload_cannot_reuse_key(harness):
    client, _, service, _ = harness
    _, _, match_id, body = context(harness)
    endpoint = f"/api/topic-matches/{match_id}/reviews"
    first = client.post(endpoint, json=body).json()
    again = client.post(endpoint, json=body)
    assert again.status_code == 201 and again.json()["reused"]
    assert again.json()["review"]["id"] == first["review"]["id"]
    assert client.post(endpoint, json={**body, "note": "Different decision rationale"}).status_code == 409
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(TopicMatchReview)) == 1


@pytest.mark.parametrize("change", ["evidence", "plan", "paused", "expired", "review"])
def test_outdated_review_cannot_override_new_inputs_or_a_colleague(harness, change):
    client, _, service, _ = harness
    topic, event_id, match_id, body = context(harness)
    endpoint = f"/api/topic-matches/{match_id}/reviews"
    with service.db.session() as session:
        if change == "evidence":
            session.get(RegulatoryEvent, event_id).evidence_json = {"correction": "new facts"}
        elif change == "plan":
            session.get(MonitoringTopic, topic["id"]).current_revision += 1
        elif change == "paused":
            session.get(MonitoringTopic, topic["id"]).status = "paused"
        elif change == "expired":
            session.get(TopicEventMatch, match_id).expires_at = utcnow() - timedelta(seconds=1)
        session.commit()
    if change == "review":
        assert client.post(endpoint, json={**body, "request_key": "colleague-review-key"}).status_code == 201
    response = client.post(endpoint, json=body)
    assert response.status_code == 409 and response.json()["code"] == "topic_review_stale", response.text
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(TopicMatchReview)) == (1 if change == "review" else 0)


def test_evidence_correction_keeps_old_review_and_requires_new_confirmation(harness):
    client, _, service, _ = harness
    topic, event_id, match_id, body = context(harness)
    endpoint = f"/api/topic-matches/{match_id}/reviews"
    saved = client.post(endpoint, json=body).json()["review"]
    original = deepcopy(saved["snapshot"])
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, event_id)
        event.evidence_json = {**event.evidence_json, "published_at": "2026-09-05"}
        session.commit()
    evaluate(service, topic, event_id, "history")
    current = client.get(endpoint).json()
    assert not current["match"]["decision_is_current"]
    assert current["items"][0]["snapshot"] == original
    assert len(client.get("/api/interest-feed").json()["items"]) == 1
    response = client.post(endpoint, json={**body, "request_key": "review-new-evidence", "decision": "confirmed",
                                          "expected_review_id": saved["id"], "expected_evaluation_fingerprint": current["match"]["evaluation_fingerprint"]})
    assert response.status_code == 201, response.text
    assert len(client.get(endpoint).json()["items"]) == 2


def test_expiry_cleanup_retains_reviewed_proposal_and_history(harness):
    client, _, service, _ = harness
    _, _, match_id, body = context(harness)
    endpoint = f"/api/topic-matches/{match_id}/reviews"
    review = client.post(endpoint, json=body).json()["review"]
    with service.db.session() as session:
        session.get(TopicEventMatch, match_id).expires_at = utcnow() - timedelta(days=1)
        session.commit()
    cleanup_operational_data(service.db, service.settings)
    history = client.get(endpoint).json()
    assert history["match"]["validity"] == "expired" and not history["match"]["decision_is_current"]
    assert history["items"][0]["id"] == review["id"]


def test_revoke_and_foreign_org_cannot_read_or_review_retained_matches(harness):
    client, _, service, _ = harness
    _, event_id, match_id, body = context(harness)
    with service.db.session(include_all_organizations=True) as session:
        org = Organization(name="Other", slug="topic-review-other")
        session.add(org)
        session.commit()
        from helvetic_lens.config import DomainError
        with pytest.raises(DomainError):
            detail(session, org.id, match_id)
        with pytest.raises(DomainError):
            save(session, org.id, match_id, actor_user_id=None, **body)
        session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == event_id))
        session.commit()
    endpoint = f"/api/topic-matches/{match_id}/reviews"
    assert client.get(endpoint).status_code == 404
    assert client.post(endpoint, json=body).status_code == 404


def test_review_history_pages_are_complete_and_do_not_change_proposals(harness):
    client, _, _, model = harness
    _, _, match_id, body = context(harness)
    endpoint = f"/api/topic-matches/{match_id}/reviews"
    ids = []
    for i in range(5):
        response = client.post(endpoint, json={**body, "request_key": f"history-review-{i:03}", "expected_review_id": ids[-1] if ids else None})
        assert response.status_code == 201, response.text
        ids.append(response.json()["review"]["id"])
    visited, cursor = [], ""
    while True:
        page = client.get(endpoint, params={"limit": 2, "cursor": cursor}).json()
        visited.extend(item["id"] for item in page["items"])
        if not page["has_more"]:
            break
        cursor = page["next_cursor"]
    assert visited == ids[::-1]
    assert client.get(endpoint, params={"cursor": "missing"}).status_code == 422
    assert model.calls == []


def test_actor_is_preserved_from_server_identity_and_not_accepted_from_payload(harness):
    from helvetic_lens.models import User
    client, _, service, _ = harness
    _, _, match_id, body = context(harness)
    endpoint = f"/api/topic-matches/{match_id}/reviews"
    assert client.post(endpoint, json={**body, "actor_user_id": "impersonated"}).status_code == 422
    with service.db.session() as session:
        actor = User(email="reviewer@example.invalid", name="Verified reviewer", password_hash="synthetic-only")
        session.add(actor)
        session.commit()
        actor_id = actor.id
    service.review_topic_match(match_id, actor_user_id=actor_id, **body)
    review = client.get(endpoint).json()["items"][0]
    assert review["actor_user_id"] == actor_id and review["actor_name"] == "Verified reviewer"


def test_match_pages_include_rejected_and_old_proposals_without_cross_topic_cursor(harness):
    from test_topic_matching import create_topic
    client, _, service, _ = harness
    topic, event_ids = seed(harness, 5)
    endpoint = f"/api/monitoring-topics/{topic['id']}/matches/page"
    ids, cursor = [], ""
    while True:
        page = client.get(endpoint, params={"limit": 2, "cursor": cursor}).json()
        ids.extend(row["event_id"] for row in page["items"])
        if not page["has_more"]:
            break
        cursor = page["next_cursor"]
    assert set(ids) == set(event_ids) and len(ids) == len(set(ids))
    other = create_topic(client, key="other-topic-review-key")
    assert client.get(f"/api/monitoring-topics/{other['id']}/matches/page", params={"cursor": cursor}).status_code == 422


def test_review_migration_roundtrip_preserves_existing_match_evidence(harness):
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import inspect

    from alembic import command
    _, _, service, _ = harness
    _, _, match_id, _ = context(harness)
    with service.db.session() as session:
        original = deepcopy(session.get(TopicEventMatch, match_id).evidence_references_json)
    directory = Path(__file__).resolve().parents[1]
    config = Config(str(directory / "alembic.ini"))
    config.set_main_option("script_location", str(directory / "alembic"))
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "fa27c61d3098")
        assert "topic_match_reviews" not in inspect(connection).get_table_names()
        command.upgrade(config, "head")
        assert "ix_topic_match_review_history" in {i["name"] for i in inspect(connection).get_indexes("topic_match_reviews")}
    with service.db.session() as session:
        assert session.get(TopicEventMatch, match_id).evidence_references_json == original
        assert session.scalar(select(func.count()).select_from(TopicMatchReview)) == 0


@pytest.mark.parametrize("same_request", [False, True])
def test_postgres_concurrent_reviews_do_not_overwrite_or_duplicate(harness, same_request):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from helvetic_lens.config import DomainError
    _, _, service, _ = harness
    if service.db.engine.dialect.name != "postgresql":
        pytest.skip("Real row-lock concurrency requires disposable PostgreSQL")
    _, _, match_id, body = context(harness)
    ready = Barrier(2)
    def write(index):
        with service.db.session() as session:
            ready.wait(timeout=10)
            try:
                return save(session, service.organization_id, match_id, actor_user_id=None,
                            **{**body, "request_key": body["request_key"] if same_request else f"parallel-review-{index}"})
            except DomainError as error:
                return error.code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, [1, 2]))
    successes = [result for result in results if isinstance(result, dict)]
    if same_request:
        assert len(successes) == 2
        assert {result["reused"] for result in successes} == {False, True}
        assert len({result["review"]["id"] for result in successes}) == 1
    else:
        assert len(successes) == 1 and "topic_review_stale" in results
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(TopicMatchReview)) == 1
