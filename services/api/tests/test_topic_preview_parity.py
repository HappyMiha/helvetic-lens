"""Preview promises must agree with activation on the same entitled evidence."""

import pytest
from sqlalchemy import func, select
from test_topic_history import execute, saved_events
from test_topic_live import enqueue
from test_topic_matching import add_event, create_topic, plan

from helvetic_lens.models import (
    Job,
    MonitoringTopic,
    Organization,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryWork,
    TopicEventMatch,
)
from helvetic_lens.topic_matching import RULE_REVISION


@pytest.mark.parametrize(("title", "overrides", "expected", "signal"), [
    ("Federal publication", {"concepts": ["RS 141.0"], "synonyms": []}, True, "official_identifier"),
    ("Citizenship framework", {"concepts": ["citizenship benefits"], "synonyms": []}, True, "fts_term"),
    ("Federal publication", {"concepts": ["jurisdiction"], "synonyms": []}, False, None),
    ("Naturalisation sport act", {}, False, None),
    ("Naturalisation Act", {"languages": ["fr"]}, False, None),
    ("Naturalisation Act", {"jurisdictions": ["GE"]}, False, None),
    ("Naturalisation Act", {"importance_floor": "high"}, False, None),
    ("Naturalisation Act", {"event_kinds": ["repealed"]}, False, None),
    ("Naturalisation Act", {"document_kinds": ["court_decision"]}, False, None),
    ("Naturalisation Act", {"source_pack_ids": ["swiss-parliament"]}, False, None),
])
def test_preview_history_and_live_share_decision_reasons_and_confidence(harness, title, overrides, expected, signal):
    client, _, service, model = harness
    event_id = add_event(service, title=title)
    response = client.post("/api/monitoring-topics/preview", json=plan(**overrides))
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["candidate_count"] == int(expected)
    assert preview["scanned_event_count"] == 1 and preview["count_is_complete"] is True
    assert preview["visibility_scope"] == "organization_saved_events"
    assert preview["rule_revision"] == RULE_REVISION and preview["sample_captured_at"]
    with service.db.session() as session:
        for table in (MonitoringTopic, Job, TopicEventMatch):
            assert session.scalar(select(func.count()).select_from(table)) == 0
    topic = create_topic(client, **overrides)
    history = execute(service, topic["backfill_job"]["id"])["result"]["data"]
    assert history["matched"] == int(expected)
    live_id, _ = enqueue(service, event_id)
    live = execute(service, live_id)["result"]["data"]
    assert live["reused"] == int(expected) and live["matched"] == 0
    with service.db.session() as session:
        match = session.scalar(select(TopicEventMatch))
        if expected:
            candidate = preview["items"][0]
            assert candidate["reason_signals"] == match.reason_signals_json
            assert candidate["confidence"] == match.confidence_band
            assert candidate["source_url"] == match.evidence_references_json["source_url"]
            assert signal in {value["type"] for value in candidate["reason_signals"]}
        else:
            assert match is None
    assert model.calls == []


def test_preview_accepts_the_same_nested_jurisdiction_metadata_as_production(harness):
    client, _, service, _ = harness
    event_id = add_event(service)
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, event_id)
        session.get(RegulatoryWork, event.work_id).metadata_json = {"jurisdictions": {"primary": "CH"}}
        session.commit()
    preview = client.post("/api/monitoring-topics/preview", json=plan()).json()
    topic = create_topic(client)
    history = execute(service, topic["backfill_job"]["id"])["result"]["data"]
    assert preview["candidate_count"] == history["matched"] == 1


def test_shared_public_events_without_owner_admission_are_not_preview_promises(harness):
    client, _, service, _ = harness
    event_id = add_event(service)
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Separate preview owner", slug="separate-preview-owner")
        session.add(other)
        session.flush()
        admission = session.scalar(select(RegulatoryEventState).where(RegulatoryEventState.event_id == event_id))
        admission.organization_id = other.id
        session.commit()
    preview = client.post("/api/monitoring-topics/preview", json=plan()).json()
    assert preview["candidate_count"] == preview["scanned_event_count"] == 0
    assert preview["sample_detected_from"] is None and preview["sample_detected_through"] is None
    topic = create_topic(client)
    assert execute(service, topic["backfill_job"]["id"])["result"]["data"]["processed"] == 0


def test_preview_exposes_500_event_sample_and_10_result_display_limits_separately(harness):
    client, _, service, model = harness
    saved_events(service, 501)
    preview = client.post("/api/monitoring-topics/preview", json=plan()).json()
    assert preview["candidate_count"] == preview["scanned_event_count"] == 500
    assert preview["count_is_complete"] is False and preview["display_truncated"] is True
    assert len(preview["items"]) == preview["representative_limit"] == 10
    assert preview["sample_detected_from"] and preview["sample_detected_through"]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 0
        assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 0
    topic = create_topic(client)
    assert execute(service, topic["backfill_job"]["id"])["state"] == "queued"
    history = execute(service, topic["backfill_job"]["id"])["result"]["data"]
    assert history["matched"] == history["processed"] == 501
    assert model.calls == []
