from datetime import UTC, date, datetime, timedelta

from conftest import add_law

from helvetic_lens.registry import ZURICH, detected_group
from helvetic_lens.regulatory_corpus import (
    DocumentInput,
    EventInput,
    ExpressionInput,
    IdentifierInput,
)


def test_zurich_groups_are_non_overlapping_at_midnight_and_dst_boundaries():
    after_midnight = datetime(2026, 3, 29, 22, 30, tzinfo=UTC)  # 00:30 CEST, 30 March
    assert detected_group(datetime(2026, 3, 29, 21, 30, tzinfo=UTC), now=after_midnight) == "Yesterday"
    assert detected_group(datetime(2026, 3, 29, 22, 5, tzinfo=UTC), now=after_midnight) == "Today"

    dst_fallback = datetime(2026, 10, 25, 3, 30, tzinfo=UTC)
    assert detected_group(datetime(2026, 10, 25, 0, 30, tzinfo=UTC), now=dst_fallback) == "Today"
    assert detected_group(datetime(2026, 10, 25, 1, 30, tzinfo=UTC), now=dst_fallback) == "Today"
    assert (
        detected_group(
            datetime(2026, 10, 20, 12, tzinfo=UTC),
            now=dst_fallback,
            custom_start=date(2026, 10, 20),
            custom_end=date(2026, 10, 20),
        )
        == "Custom range"
    )


def _record_event(service, *, work_id, event_type, detected_at, key, impact="unknown"):
    with service.db.session() as session:
        event = service.regulatory_corpus.record_event(
            session,
            EventInput(
                work_id=work_id,
                authority="native",
                event_type=event_type,
                detected_at=detected_at,
                provenance_method="official_metadata",
                source_url="https://regulator.example/events/" + key,
                evidence={"entry": key},
                external_key=key,
                connector="test-feed",
                connector_health="degraded",
                analysis_state="complete" if impact != "unknown" else "pending",
                impact=impact,
            ),
        )
        session.commit()
        return event.id


def test_registry_filters_cursor_read_state_and_saved_timeline(harness):
    client, _, service, model = harness
    law = add_law(client)
    work = client.get("/api/corpus/works").json()[0]
    now = datetime.now(UTC)
    event_ids = [
        _record_event(
            service,
            work_id=work["id"],
            event_type="new_version",
            detected_at=now - timedelta(minutes=index),
            key=f"watched-{index}",
            impact="high" if index == 0 else "low",
        )
        for index in range(3)
    ]

    with service.db.session() as session:
        unwatched = service.regulatory_corpus.merge_document(
            session,
            DocumentInput(
                kind="official_notice",
                authority="native",
                identifiers=(IdentifierInput("notice_id", "notice-unwatched"),),
                title="Unwatched notice",
                expression=ExpressionInput(language="fr", key="notice:fr:unwatched"),
            ),
        )
        session.commit()
        unwatched_work_id = unwatched.work.id
    _record_event(
        service,
        work_id=unwatched_work_id,
        event_type="notice_published",
        detected_at=now - timedelta(hours=1),
        key="unwatched",
    )

    page = client.get(
        "/api/registry",
        params={"view": "events", "limit": 2, "watched": "watched"},
    )
    assert page.status_code == 200
    payload = page.json()
    assert len(payload["items"]) == 2
    assert payload["next_cursor"]
    assert payload["groups"][0]["name"] == "Today"
    assert all(item["watched"] for item in payload["items"])
    assert model.calls == []

    second = client.get(
        "/api/registry",
        params={
            "view": "events",
            "limit": 2,
            "watched": "watched",
            "cursor": payload["next_cursor"],
        },
    ).json()
    assert len(second["items"]) == 1
    assert {item["event_id"] for item in payload["items"] + second["items"]} == set(event_ids)

    exact = client.get(
        "/api/registry",
        params={
            "view": "events",
            "q": law["name"],
            "authority": "native",
            "connector": "test-feed",
            "kind": "unclassified_document",
            "language": "und",
            "lifecycle": "unknown",
            "impact": "high",
            "watched": "watched",
            "read": "unread",
            "health": "degraded",
        },
    ).json()
    assert [item["event_id"] for item in exact["items"]] == [event_ids[0]]
    assert exact["items"][0]["official_dates"] == {}
    assert exact["items"][0]["detected_at"]

    marked = client.patch(f"/api/registry/events/{event_ids[0]}/read", json={"read": True})
    assert marked.status_code == 200
    assert marked.json()["read"] is True
    assert (
        client.get("/api/registry", params={"view": "events", "read": "read"}).json()["items"][0]["event_id"]
        == event_ids[0]
    )

    unwatched_page = client.get(
        "/api/registry",
        params={"view": "events", "watched": "unwatched", "language": "fr"},
    ).json()
    assert [item["title"] for item in unwatched_page["items"]] == ["Unwatched notice"]

    monitored = client.get("/api/registry", params={"view": "monitored"}).json()
    assert monitored["items"][0]["law_id"] == law["id"]
    assert monitored["items"][0]["timeline_url"] == f"/laws/{law['id']}"

    timeline = client.get(f"/api/laws/{law['id']}/timeline")
    assert timeline.status_code == 200
    body = timeline.json()
    assert body["monitoring"]["active"] is True
    assert body["identifiers"]
    assert body["normalized_versions"] == 1
    assert {item["type"] for item in body["timeline"]} >= {"event", "version"}
    assert client.get(f"/api/laws/{law['id']}").json()["regulatory_timeline"]["timeline"]


def test_registry_custom_range_and_invalid_cursor(harness):
    client, _, service, _ = harness
    add_law(client)
    work = client.get("/api/corpus/works").json()[0]
    now = datetime.now(UTC)
    _record_event(
        service,
        work_id=work["id"],
        event_type="created",
        detected_at=now,
        key="custom-range",
    )
    local_day = now.astimezone(ZURICH).date().isoformat()
    response = client.get(
        "/api/registry",
        params={"view": "events", "start": local_day, "end": local_day},
    )
    assert response.status_code == 200
    assert response.json()["groups"][0]["name"] == "Custom range"
    invalid = client.get("/api/registry", params={"view": "events", "cursor": "broken"})
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "invalid_registry_cursor"
