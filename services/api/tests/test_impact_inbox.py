from conftest import add_law, policy
from sqlalchemy import select
from test_relation_analysis import relation_delivery

from helvetic_lens.impact_inbox import ImpactInboxFilters
from helvetic_lens.models import (
    DocumentWatch,
    LegacyDocumentMapping,
    OrganizationRelationCandidate,
    RegulatoryWork,
    RelationCandidate,
    User,
)


def _add_second_delivery(harness, first_delivery_id: str):
    client, fetcher, service, _ = harness
    second_url = "https://example.com/second-law"
    fetcher.values[second_url] = policy(45)
    second_law = add_law(client, url=second_url, name="Second monitored act")
    with service.db.session(include_all_organizations=True) as session:
        first_delivery = session.get(OrganizationRelationCandidate, first_delivery_id)
        first = session.get(RelationCandidate, first_delivery.candidate_id)
        mapping = session.scalar(
            select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == second_law["id"])
        )
        target = session.get(RegulatoryWork, mapping.work_id)
        watch = session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == second_law["id"]))
        candidate = RelationCandidate(
            event_id=first.event_id,
            source_work_id=first.source_work_id,
            target_work_id=target.id,
            source_version_id=first.source_version_id,
            status="active",
            score=0.61,
            score_components_json={"title_terms": 0.61},
            why_json=[{"reason": "A saved identifier and title terms matched."}],
            evidence_json={"method": "test"},
            rule_revision="test-v1",
            expires_at=first.expires_at,
        )
        session.add(candidate)
        session.flush()
        delivery = OrganizationRelationCandidate(
            candidate_id=candidate.id,
            watch_id=watch.id,
            status="pending",
        )
        session.add(delivery)
        session.commit()
        return delivery.id


def test_inbox_groups_law_impacts_by_event_and_filters_saved_fields(harness):
    client, _, service, _ = harness
    first_delivery, _ = relation_delivery(harness)
    second_delivery = _add_second_delivery(harness, first_delivery)

    page = client.get("/api/impact-inbox")
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["total_events"] == 1
    assert body["total_impacts"] == 2
    assert {item["organization_candidate_id"] for item in body["items"][0]["items"]} == {
        first_delivery,
        second_delivery,
    }
    assert all(item["status"] == "awaiting_analysis" for item in body["items"][0]["items"])

    watched_law = body["items"][0]["items"][0]["law_id"]
    filtered = client.get("/api/impact-inbox", params={"watched_law": watched_law}).json()
    assert filtered["total_events"] == 1
    assert len(filtered["items"][0]["items"]) == 1

    reviewed = client.post(
        f"/api/relation-candidates/{first_delivery}/reviews",
        json={"decision": "confirmed", "note": "Reviewed against the saved source."},
    )
    assert reviewed.status_code == 201
    reviewed_item = client.get("/api/impact-inbox").json()["items"][0]["items"][0]
    assert reviewed_item["status"] == "confirmed_relation"
    assert reviewed_item["organization_review"]["decision"] == "confirmed"
    assert reviewed_item["official_relation"] is None


def test_inbox_personal_state_does_not_change_another_user(harness):
    client, _, service, _ = harness
    delivery_id, _ = relation_delivery(harness)
    event_id = client.get("/api/impact-inbox").json()["items"][0]["event_id"]
    with service.db.session(include_all_organizations=True) as session:
        first = User(email="first-state@example.ch", password_hash="test", name="First")
        second = User(email="second-state@example.ch", password_hash="test", name="Second")
        session.add_all([first, second])
        session.commit()
        first_id, second_id = first.id, second.id

    service.set_impact_inbox_state(event_id, "dismissed", first_id)
    first_page = service.impact_inbox(ImpactInboxFilters(), first_id)
    second_page = service.impact_inbox(ImpactInboxFilters(), second_id)
    assert first_page["items"][0]["read_state"] == "dismissed"
    assert second_page["items"][0]["read_state"] == "unread"
    assert first_page["items"][0]["items"][0]["organization_candidate_id"] == delivery_id


def test_reanalysis_adds_history_and_keeps_last_valid_result_on_failure(harness):
    client, _, service, model = harness
    delivery_id, _ = relation_delivery(harness)
    service.settings.apertus_base_url = "https://model.example/v1"

    first = client.post(f"/api/relation-candidates/{delivery_id}/analyse-jobs")
    assert first.status_code == 202 and first.json()["state"] == "succeeded"
    current_id = first.json()["result"]["data"]["id"]
    model.invalid = True
    retried = client.post(f"/api/relation-candidates/{delivery_id}/reanalyse-jobs")
    assert retried.status_code == 202

    history = client.get(f"/api/relation-candidates/{delivery_id}/analyses").json()
    assert history["total"] == 2
    assert history["current"]["id"] == current_id
    assert history["latest_attempt"]["status"] == "failed"
    item = client.get("/api/impact-inbox").json()["items"][0]["items"][0]
    assert item["status"] == "possible_impact"
    assert item["latest_attempt_status"] == "failed"


def test_confirmed_replacement_links_successor_and_preserves_predecessor(harness):
    client, fetcher, _, _ = harness
    delivery_id, _ = relation_delivery(
        harness, confirmed=True, relation_type="replaces"
    )
    event = client.get("/api/impact-inbox").json()["items"][0]
    item = event["items"][0]
    assert item["status"] == "confirmed_relation"
    assert item["replacement"]["predecessor"]["law_id"] == item["law_id"]
    assert item["replacement"]["successor"]["title"].startswith("Revision of")
    predecessor_id = item["law_id"]
    fetcher.values[event["source_url"]] = policy(60)

    monitored = client.post(
        f"/api/relation-candidates/{delivery_id}/monitor-successor"
    )
    assert monitored.status_code == 201, monitored.text
    assert monitored.json()["id"] != predecessor_id
    assert any(law["id"] == predecessor_id for law in client.get("/api/laws").json())
    timeline = client.get(f"/api/laws/{predecessor_id}/timeline").json()
    replacement = next(item for item in timeline["relations"] if item["type"] == "replaces")
    assert replacement["reciprocal_label"] == "successor"
    assert replacement["other_title"].startswith("Revision of")
