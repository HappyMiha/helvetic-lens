"""Changed organizational applicability must not remain a current AI conclusion."""

import pytest
from sqlalchemy import func, select
from test_relation_analysis import relation_delivery

from helvetic_lens.impact_inbox import ImpactInboxReader
from helvetic_lens.models import Job, Organization, Profile, RegulatoryEvent, RelationImpactAnalysis
from helvetic_lens.relation_freshness import uses_profile


def analyse(harness, *, confirmed=False):
    client, _, service, _ = harness
    delivery, _ = relation_delivery(harness, confirmed=confirmed, relation_type="replaces")
    service.settings.apertus_base_url = "https://model.example/v1"
    response = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs")
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["state"] == "succeeded", job
    return delivery, job["result"]["data"]


def change_profile(client):
    response = client.patch("/api/profile", json={
        "name": "Changed organization", "description": "Only processes archived employee records.",
        "business_areas": ["Human resources"],
    })
    assert response.status_code == 200, response.text


def test_profile_edit_invalidates_history_inbox_and_severity_without_spending_tokens(harness):
    client, _, service, model = harness
    delivery, saved = analyse(harness)
    assert client.get(f"/api/relation-candidates/{delivery}/analyses").json()["current"]["id"] == saved["id"]
    change_profile(client)
    with service.db.session() as session:
        jobs_before = session.scalar(select(func.count()).select_from(Job))
    history = client.get(f"/api/relation-candidates/{delivery}/analyses").json()
    assert history["current"] is None and history["items"][0]["stale"] is True
    assert history["items"][0]["result"] == saved["result"]
    for route in ("/api/impact-inbox", "/api/impact-inbox/page"):
        response = client.get(route)
        assert response.status_code == 200, response.text
        item = response.json()["items"][0]["items"][0]
        assert item["status"] == "stale" and item["severity"] == "unknown"
        assert item["current_analysis_id"] is None and item["latest_attempt_id"] == saved["id"]
        assert item["potential_effect"] != saved["result"]["explanation"]
        assert item["suggested_next_step"] != saved["result"]["actions"][0]["title"]
        assert client.get(route, params={"severity": "medium"}).json()["items"] == []
    # The worker/preview both use this selector: no stale AI severity may enter a digest.
    with service.db.session() as session:
        current, latest, total = ImpactInboxReader._latest_analyses(session, delivery, settings=service.settings)
        assert current is None and latest.id == saved["id"] and total == 1
        assert session.scalar(select(func.count()).select_from(Job)) == jobs_before
        record = session.get(RelationImpactAnalysis, saved["id"])
        assert record.result == saved["result"] and record.use_count == 1
    assert len(model.calls) == 1
    citation = saved["result"]["citations"][0]
    assert client.get(citation["url"]).json()["text"] == citation["quote"]


def test_failed_new_profile_attempt_never_revives_old_applicability(harness):
    client, _, _, model = harness
    delivery, old = analyse(harness)
    change_profile(client)
    model.invalid = True
    failed = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()
    assert failed["state"] == "retrying"
    history = client.get(f"/api/relation-candidates/{delivery}/analyses").json()
    assert history["current"] is None and history["latest_attempt"]["status"] == "failed"
    assert next(row for row in history["items"] if row["id"] == old["id"])["stale"]
    item = client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]
    assert item["current_analysis_id"] is None and item["severity"] == "unknown"
    model.invalid = False
    fresh = client.post(f"/api/relation-candidates/{delivery}/analyse-jobs").json()
    assert fresh["state"] == "succeeded"
    history = client.get(f"/api/relation-candidates/{delivery}/analyses").json()
    assert history["current"]["id"] == fresh["result"]["data"]["id"]
    assert not history["current"]["stale"]
    assert client.get("/api/impact-inbox/page").json()["total_impacts"] == 1


@pytest.mark.parametrize("plan", [{}, {"execution": {}}, {"execution": None}, {"execution": {"profile_revision": "bad"}}, {"execution": {"profile_revision": 99}}])
def test_missing_or_mismatched_provenance_is_history_only(harness, plan):
    client, _, service, _ = harness
    delivery, saved = analyse(harness)
    with service.db.session() as session:
        session.get(RelationImpactAnalysis, saved["id"]).analysis_plan = plan
        session.commit()
    assert not uses_profile(plan, 1)
    history = client.get(f"/api/relation-candidates/{delivery}/analyses").json()
    assert history["current"] is None and history["items"][0]["stale"]
    assert client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]["current_analysis_id"] is None


def test_official_replacement_urgency_survives_a_stale_organization_assessment(harness):
    client, _, service, _ = harness
    _, saved = analyse(harness, confirmed=True)
    with service.db.session() as session:
        session.get(RegulatoryEvent, saved["event_id"]).impact = "high"
        session.commit()
    change_profile(client)
    item = client.get("/api/impact-inbox/page").json()["items"][0]["items"][0]
    assert item["current_analysis_id"] is None and item["latest_attempt_id"] == saved["id"]
    assert item["status"] == "confirmed_relation" and item["official_relation"]
    assert item["severity"] == "high"
    assert item["suggested_next_step"] != saved["result"]["actions"][0]["title"]


def test_another_organizations_matching_revision_cannot_validate_a_stale_report(harness):
    client, _, service, _ = harness
    delivery, saved = analyse(harness)
    change_profile(client)
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Unrelated profile", slug="unrelated-profile")
        session.add(other)
        session.flush()
        session.add(Profile(id=other.id, organization_id=other.id, revision=1))
        session.commit()
    with service.db.session(include_all_organizations=True) as session:
        current, latest, count = ImpactInboxReader._latest_analyses(session, delivery, settings=service.settings)
        assert current is None and latest.id == saved["id"] and count == 1
        histories, _ = ImpactInboxReader(service.organization_id, None, settings=service.settings)._page_histories(session, [delivery])
        assert histories[delivery][0] is None
