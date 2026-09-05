"""Source-specific feed context and exact, scoped saved-development navigation."""

import pytest
from conftest import add_law
from sqlalchemy import delete, select
from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session
from test_interest_feed import reader, seed
from test_topic_validity import evaluate

from helvetic_lens.models import (
    Law,
    Organization,
    RegulatoryDate,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryExpression,
    RegulatoryWork,
    Version,
)


def test_exact_event_link_reaches_old_event_and_remains_scoped(harness):
    client, _, service, model = harness
    topic, ids = seed(harness, 25)
    wanted = sorted(ids)[0]
    first = client.get("/api/interest-feed?limit=2").json()
    assert wanted not in [card["event_id"] for card in first["items"]]
    linked = client.get("/api/interest-feed", params={"event": wanted}).json()
    assert [card["event_id"] for card in linked["items"]] == [wanted]
    assert linked["items"][0]["event_url"] == f"/?event={wanted}"
    assert linked["scanned_event_count"] == 1 and not linked["has_more"]
    assert client.get("/api/interest-feed", params={"event": wanted, "cursor": first["next_cursor"]}).status_code == 422
    assert client.get("/api/interest-feed?event=unavailable").json()["items"] == []
    assert client.get("/api/interest-feed", params={"event": "x" * 37}).status_code == 422
    with service.db.session(include_all_organizations=True) as session:
        org = Organization(name="Foreign evidence reader", slug="foreign-feed-evidence")
        session.add(org)
        session.commit()
        assert reader(service, org.id).feed(session, event=wanted)["items"] == []
        session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == wanted))
        session.commit()
    assert client.get("/api/interest-feed", params={"event": wanted}).json()["items"] == []
    assert model.calls == []


def test_provenance_uses_recorded_scope_and_event_dates_without_inventing_precision(harness):
    client, _, service, model = harness
    topic, ids = seed(harness)
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, ids[0])
        work = session.get(RegulatoryWork, event.work_id)
        work.metadata_json = {"jurisdictions": ["CH", "CH-ZH", "CH", None, {"invalid": "scope"}]}
        event.connector_health = "degraded"
        event.provenance_method = "official_metadata"
        session.add_all([
            RegulatoryDate(entity_type="event", entity_id=event.id, kind="effective_from", date_value="2027", precision="year", provenance="official_metadata", source_url="https://example.invalid/date-evidence"),
            RegulatoryDate(entity_type="work", entity_id=work.id, kind="published_at", date_value="1901-01-01", precision="day", provenance="official_metadata"),
        ])
        session.commit()
    evaluate(service, topic, ids[0], "history")
    card = client.get("/api/interest-feed").json()["items"][0]
    assert card["jurisdictions"] == ["CH", "CH-ZH"]
    assert card["provenance_method"] == "official_metadata"
    assert card["connector_health_at_detection"] == "degraded"
    assert card["official_dates"] == [{"kind": "effective_from", "value": "2027", "precision": "year", "provenance": "official_metadata", "source_url": "https://example.invalid/date-evidence"}]
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, ids[0])
        session.get(RegulatoryWork, event.work_id).metadata_json = {}
        event.evidence_json = {k: v for k, v in event.evidence_json.items() if k != "jurisdiction"}
        session.commit()
    evaluate(service, topic, ids[0], "history")
    assert client.get("/api/interest-feed").json()["items"][0]["jurisdictions"] == []
    assert model.calls == []


@pytest.mark.parametrize("invalid", [None, "foreign_version", "foreign_law", "other_expression", "missing_legacy"])
def test_topic_only_artifact_is_exact_visible_version_without_body_hydration(harness, invalid):
    client, _, service, model = harness
    topic, ids = seed(harness)
    law = add_law(client)
    with service.db.session(include_all_organizations=True) as session:
        event = session.get(RegulatoryEvent, ids[0])
        # Bind a saved source version; never substitute the watched law's newest version.
        expression = RegulatoryExpression(work_id=event.work_id, language="en", expression_key="feed-evidence-en")
        session.add(expression)
        session.flush()
        version_id = session.get(Law, law["id"]).current_version_id
        corpus_version = session.scalar(select(RegulatoryDocumentVersion).where(RegulatoryDocumentVersion.legacy_version_id == version_id))
        corpus_version.expression_id = expression.id
        corpus_version.text = "Large source body " * 50000
        corpus_version.passages = [{"text": "Large passage " * 50000}]
        native_version_id = corpus_version.id
        event.document_version_id = corpus_version.id
        event.expression_id = expression.id
        org = Organization(name="Private artifact", slug="private-feed-artifact")
        session.add(org)
        session.flush()
        if invalid == "foreign_version":
            session.get(Version, version_id).owner_organization_id = org.id
        elif invalid == "foreign_law":
            session.get(Law, law["id"]).owner_organization_id = org.id
        elif invalid == "other_expression":
            other = RegulatoryWork(kind="act", authority="synthetic", canonical_key="unrelated-work")
            session.add(other)
            session.flush()
            expression.work_id = other.id
        elif invalid == "missing_legacy":
            corpus_version.legacy_version_id = None
        session.commit()
    evaluate(service, topic, ids[0], "history")
    loaded = []
    def record(_session, row):
        loaded.append(type(row))
    sa_event.listen(Session, "loaded_as_persistent", record)
    try:
        card = client.get("/api/interest-feed", params={"event": ids[0]}).json()["items"][0]
    finally:
        sa_event.remove(Session, "loaded_as_persistent", record)
    expected = f"/evidence/{version_id}" if invalid is None else f"/corpus-evidence/{native_version_id}" if invalid == "missing_legacy" else None
    assert card["source_artifact_url"] == expected
    if invalid == "missing_legacy":
        assert client.get(f"/api/regulatory-versions/{native_version_id}").status_code == 200
    assert card["document_language"] == (None if invalid == "other_expression" else "en")
    assert not set(loaded) & {Version, Law, RegulatoryDocumentVersion}
    assert model.calls == []
