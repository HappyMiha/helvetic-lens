import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from helvetic_lens.maintenance import cleanup_operational_data
from helvetic_lens.models import (
    Job,
    Organization,
    RegulatoryEvent,
    RegulatoryEventState,
    TopicEventMatch,
)
from helvetic_lens.regulatory_corpus import (
    DocumentInput,
    EventInput,
    ExpressionInput,
    IdentifierInput,
)
from helvetic_lens.topic_matching import generate_for_events


def plan(**overrides):
    result = {
        "name": "Naturalisation developments",
        "goal": "Follow material developments about naturalisation in Switzerland.",
        "concepts": ["naturalisation", "SR 141.0"],
        "synonyms": ["citizenship", "Einbürgerung"],
        "exclusions": ["sport"],
        "jurisdictions": ["CH"],
        "languages": ["de", "fr", "it", "rm", "en"],
        "source_pack_ids": ["fedlex-legislation"],
        "document_kinds": ["act"],
        "event_kinds": ["amended", "new_version"],
        "importance_floor": "low",
    }
    result.update(overrides)
    return result


def add_event(service, *, title="Naturalisation Act amendment", language="en"):
    with service.db.session() as session:
        merged = service.regulatory_corpus.merge_document(
            session,
            DocumentInput(
                kind="act",
                authority="fedlex",
                identifiers=(
                    IdentifierInput("sr_rs", "141.0"),
                    IdentifierInput("eli", "https://fedlex.data.admin.ch/eli/cc/topic-match"),
                ),
                title=title,
                stable_official_url="https://fedlex.data.admin.ch/eli/cc/topic-match",
                expression=ExpressionInput(
                    language=language,
                    key=f"topic-match:{language}",
                    title=title,
                ),
                metadata={"jurisdiction": "CH"},
            ),
        )
        event = service.regulatory_corpus.record_event(
            session,
            EventInput(
                work_id=merged.work.id,
                expression_id=merged.expression.id,
                authority="fedlex",
                event_type="amended",
                detected_at=datetime(2026, 9, 4, 8, 0, tzinfo=UTC),
                provenance_method="official_metadata",
                source_url="https://fedlex.data.admin.ch/eli/cc/topic-match",
                evidence={"stream": "rss-de", "language": language, "published_at": "2026-09-04"},
                external_key="topic-match:event",
                connector="fedlex",
                connector_health="healthy",
                impact="medium",
            ),
        )
        session.add(RegulatoryEventState(event_id=event.id))
        session.commit()
        return event.id


def create_topic(client, key="topic-match-create-0001", **overrides):
    response = client.post(
        "/api/monitoring-topics",
        json={**plan(**overrides), "idempotency_key": key},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_topic_match_persists_exact_evidence_and_reuses_fingerprint(harness):
    client, _, service, _ = harness
    topic = create_topic(client)
    event_id = add_event(service)
    with service.db.session(include_all_organizations=True) as session:
        event = session.get(RegulatoryEvent, event_id)
        first = generate_for_events(session, [event], service.settings)
        second = generate_for_events(session, [event], service.settings)
        session.commit()
        match = session.scalar(select(TopicEventMatch))
        assert first["matched"] == 1 and first["ai_calls"] == 0
        assert second["reused"] == 1
        assert match.topic_id == topic["id"]
        assert match.confidence_band == "high"
        assert match.decision_status == "pending"
        assert match.evidence_references_json["event_id"] == event_id
        assert match.evidence_references_json["source_url"].startswith("https://fedlex")
        assert {item["type"] for item in match.reason_signals_json} >= {
            "official_identifier",
            "concept",
        }

        old_fingerprint = match.evidence_fingerprint
        event.evidence_json = {**event.evidence_json, "published_at": "2026-09-05"}
        session.flush()
        changed = generate_for_events(session, [event], service.settings)
        session.commit()
        assert changed["updated"] == 1
        assert match.evidence_fingerprint != old_fingerprint

    revised = client.put(
        f"/api/monitoring-topics/{topic['id']}",
        json={**plan(synonyms=["citizenship"]), "expected_revision": 1},
    )
    assert revised.status_code == 200 and revised.json()["current_revision"] == 2
    with service.db.session(include_all_organizations=True) as session:
        new_revision = generate_for_events(
            session, [session.get(RegulatoryEvent, event_id)], service.settings
        )
        session.commit()
        assert new_revision["matched"] == 1
        assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 2

    response = client.get(f"/api/monitoring-topics/{topic['id']}/matches")
    assert response.status_code == 200
    assert response.json()[0]["event_id"] == event_id


def test_backfill_job_is_durable_and_matches_only_visible_saved_events(harness):
    client, _, service, _ = harness
    event_id = add_event(service)
    topic = create_topic(client, key="topic-backfill-create-0001")
    assert topic["backfill_job"]["type"] == "topic_match_backfill"
    completed = asyncio.run(service.execute_job(topic["backfill_job"]["id"]))
    assert completed["state"] == "succeeded"
    assert completed["result"]["data"]["matched"] == 1
    with service.db.session() as session:
        match = session.scalar(select(TopicEventMatch).where(TopicEventMatch.event_id == event_id))
        assert match is not None


def test_per_event_organization_and_topic_bounds_are_explicit(harness):
    _, _, service, _ = harness
    event_id = add_event(service, title="Unrelated federal publication")
    with service.db.session(include_all_organizations=True) as session:
        event = session.get(RegulatoryEvent, event_id)
        for index in range(101):
            organization = Organization(name=f"Bound {index}", slug=f"topic-bound-{index}")
            session.add(organization)
            session.flush()
            session.add(RegulatoryEventState(organization_id=organization.id, event_id=event.id))
        session.commit()
        constrained = service.settings.model_copy(
            update={"topic_match_organizations_per_event": 100}
        )
        result = generate_for_events(session, [event], constrained)
        assert result["organizations_considered"] == 100
        assert result["organization_bound_hit"] is True
        assert result["topics_considered"] <= 100 * constrained.topic_match_topics_per_organization_event


@pytest.mark.parametrize(
    ("language", "title", "term"),
    [
        ("de", "Änderung des Bürgerrechtsgesetzes", "Bürgerrecht"),
        ("fr", "Modification de la loi sur la nationalité", "nationalité"),
        ("it", "Modifica della legge sulla cittadinanza", "cittadinanza"),
        ("rm", "Midada da la lescha da burgais", "burgais"),
        ("en", "Amendment of the Citizenship Act", "Citizenship"),
    ],
)
def test_labelled_five_language_topic_matches(harness, language, title, term):
    client, _, service, _ = harness
    event_id = add_event(service, title=title, language=language)
    create_topic(
        client,
        key=f"topic-language-{language}-0001",
        concepts=[term],
        synonyms=[],
    )
    with service.db.session(include_all_organizations=True) as session:
        result = generate_for_events(
            session, [session.get(RegulatoryEvent, event_id)], service.settings
        )
        assert result["matched"] == 1
        assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 1


def test_paused_topic_and_exclusion_do_not_generate_matches(harness):
    client, _, service, _ = harness
    event_id = add_event(service, title="Naturalisation sport act")
    topic = create_topic(client, key="topic-paused-create-0001")
    paused = client.patch(
        f"/api/monitoring-topics/{topic['id']}/status",
        json={"status": "paused", "expected_revision": 1},
    )
    assert paused.status_code == 200
    with service.db.session(include_all_organizations=True) as session:
        result = generate_for_events(
            session, [session.get(RegulatoryEvent, event_id)], service.settings
        )
        assert result["matched"] == 0
        assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 0
        assert session.scalar(
            select(func.count()).select_from(Job).where(Job.type == "topic_match_backfill")
        ) == 1


def test_expired_unreviewed_topic_matches_are_cleaned_up(harness):
    client, _, service, _ = harness
    event_id = add_event(service)
    create_topic(client, key="topic-expiry-create-0001")
    with service.db.session(include_all_organizations=True) as session:
        generate_for_events(session, [session.get(RegulatoryEvent, event_id)], service.settings)
        match = session.scalar(select(TopicEventMatch))
        match.expires_at = datetime.now(UTC) - timedelta(days=1)
        session.commit()
    result = cleanup_operational_data(service.db, service.settings, now=datetime.now(UTC))
    assert result["topic_matches"] == 1
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 0
