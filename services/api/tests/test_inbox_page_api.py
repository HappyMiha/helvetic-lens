"""Public inbox pages must bound reads and preserve existing filter semantics."""

import base64
from datetime import timedelta

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_digest_periods import recipient, seed_events
from test_impact_inbox import _add_second_delivery
from test_relation_analysis import relation_delivery

from helvetic_lens import relation_analysis
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.impact_inbox import ImpactInboxFilters, ImpactInboxReader
from helvetic_lens.models import (
    Organization,
    OrganizationRelationCandidate,
    RegulatoryEvent,
    RelationCandidate,
    RelationImpactAnalysis,
    new_id,
)


def test_public_pages_have_stable_equal_time_order_and_only_hydrate_selected_events(harness):
    client, _, service, model = harness
    stamp = utcnow() - timedelta(minutes=1)
    ids = [f"88000000-0000-0000-0000-{i:012d}" for i in range(121)]
    seed_events(harness, [{"id": id_, "detected_at": stamp, "connector": "page-test"} for id_ in ids])
    loaded = []
    def record(_session, row):
        if isinstance(row, (OrganizationRelationCandidate, RegulatoryEvent)):
            loaded.append(row.id)
    sa_event.listen(Session, "loaded_as_persistent", record)
    try:
        result, cursor, captured = [], "", None
        for expected_count in (50, 50, 21):
            loaded.clear()
            response = client.get("/api/impact-inbox/page", params={"source": "page-test", "cursor": cursor})
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["counts_scope"] == "page"
            assert body["total_events"] == body["total_impacts"] == body["scanned_event_count"] == expected_count
            assert len(loaded) == expected_count * 2
            assert not captured or captured == body["captured_at"]
            captured = body["captured_at"]
            result.extend(item["event_id"] for item in body["items"])
            cursor = body["next_cursor"]
        assert result == list(reversed(ids)) and cursor is None and not body["has_more"]
        assert model.calls == []
    finally:
        sa_event.remove(Session, "loaded_as_persistent", record)


def test_paging_advances_through_empty_severity_pages_and_binds_filter_account_scope(harness):
    client, _, service, _ = harness
    end = utcnow()
    ids = [new_id() for _ in range(3)]
    seed_events(harness, [{"id": id_, "detected_at": end - timedelta(seconds=i+1), "impact": "high" if i == 2 else "low"}
                          for i, id_ in enumerate(ids)])
    params = {"severity": "high", "limit": 2}
    first = client.get("/api/impact-inbox/page", params=params).json()
    assert first["items"] == [] and first["scanned_event_count"] == 2 and first["has_more"]
    second = client.get("/api/impact-inbox/page", params={**params, "cursor": first["next_cursor"]}).json()
    assert [item["event_id"] for item in second["items"]] == [ids[2]]
    mismatch = client.get("/api/impact-inbox/page", params={"cursor": first["next_cursor"]})
    assert mismatch.status_code == 422 and mismatch.json()["code"] == "invalid_inbox_cursor"
    user_id = recipient(service)
    with service.db.session() as session:
        with pytest.raises(DomainError) as error:
            ImpactInboxReader(service.organization_id, user_id, settings=service.settings, prompts=service.prompt_settings).paginated(session, ImpactInboxFilters(severity="high"), cursor=first["next_cursor"])
        assert error.value.code == "invalid_inbox_cursor"
        foreign = Organization(name="Page outsider", slug="page-outsider")
        session.add(foreign)
        session.commit()
        foreign_id = foreign.id
    with service.db.organization_context(foreign_id), service.db.session() as session:
        reader = ImpactInboxReader(foreign_id, None, settings=service.settings, prompts=service.prompt_settings)
        with pytest.raises(DomainError):
            reader.paginated(session, ImpactInboxFilters(severity="high"), cursor=first["next_cursor"])
        assert reader.paginated(session, ImpactInboxFilters())["items"] == []


def test_page_excludes_new_admissions_until_first_page_is_refreshed(harness):
    client, _, service, _ = harness
    end = utcnow()
    ids = [new_id() for _ in range(3)]
    seed_events(harness, [{"id": id_, "detected_at": end - timedelta(minutes=i+1), "connector": "page-test"}
                          for i, id_ in enumerate(ids)])
    first = client.get("/api/impact-inbox/page", params={"source": "page-test", "limit": 1}).json()
    with service.db.session() as session:
        template = session.get(RegulatoryEvent, ids[1])
        candidate = session.scalar(select(RelationCandidate).where(RelationCandidate.event_id == ids[1]))
        delivery = session.scalar(select(OrganizationRelationCandidate).where(OrganizationRelationCandidate.candidate_id == candidate.id))
        new_event = RegulatoryEvent(work_id=template.work_id, authority=template.authority, connector="page-test", event_type="created",
                                    dedupe_key="late-page-test", detected_at=end - timedelta(seconds=90), provenance_method="test")
        session.add(new_event)
        session.flush()
        new_candidate = RelationCandidate(event_id=new_event.id, source_work_id=candidate.source_work_id, target_work_id=candidate.target_work_id,
                                          score=1, rule_revision="test", expires_at=end+timedelta(days=1))
        session.add(new_candidate)
        session.flush()
        session.add(OrganizationRelationCandidate(candidate_id=new_candidate.id, watch_id=delivery.watch_id))
        session.commit()
        inserted = new_event.id
    following = client.get("/api/impact-inbox/page", params={"source": "page-test", "cursor": first["next_cursor"]}).json()
    assert [item["event_id"] for item in following["items"]] == ids[1:]
    fresh = client.get("/api/impact-inbox/page", params={"source": "page-test"}).json()
    assert [item["event_id"] for item in fresh["items"]] == [ids[0], inserted, *ids[1:]]


def test_personal_state_sql_filters_match_legacy_without_cross_user_effects(harness):
    client, _, service, _ = harness
    relation_delivery(harness)
    item = client.get("/api/impact-inbox/page").json()["items"][0]
    first, second = recipient(service, "page-first@example.ch"), recipient(service, "page-second@example.ch")
    for state in ("read", "dismissed", "muted", "unread"):
        service.set_impact_inbox_state(item["event_id"], state, first)
        for requested in ("read", "dismissed", "muted", "unread"):
            filters = ImpactInboxFilters(state=requested)
            page = service.impact_inbox_page(filters, first)
            assert page["items"] == service.impact_inbox(filters, first)["items"]
            assert page["total_events"] == int(state == requested)
            other = service.impact_inbox_page(filters, second)
            assert other["total_events"] == int(requested == "unread")


def test_source_and_item_type_aliases_preserve_legacy_matches(harness):
    client, _, _, _ = harness
    relation_delivery(harness)
    item = client.get("/api/impact-inbox/page").json()["items"][0]
    for key, values in (("source", (item["source"], item["authority"])),
                        ("item_type", (item["type"], item["document_kind"]))):
        for value in values:
            params = {key: value}
            page = client.get("/api/impact-inbox/page", params=params).json()
            assert page["total_events"] == 1
            assert page["items"] == client.get("/api/impact-inbox", params=params).json()["items"]


def test_watched_law_filter_keeps_legacy_event_severity_order_and_complete_law_group(harness):
    client, _, service, _ = harness
    first, _ = relation_delivery(harness)
    second = _add_second_delivery(harness, first)
    with service.db.session() as session:
        delivery = session.get(OrganizationRelationCandidate, first)
        candidate = session.get(RelationCandidate, delivery.candidate_id)
        session.add(RelationImpactAnalysis(organization_candidate_id=first, candidate_id=candidate.id,
                                          event_id=candidate.event_id, target_work_id=candidate.target_work_id,
                                          cache_key="0"*64, model="test-only", status="succeeded",
                                          analysis_plan={"execution": {"version_binding": relation_analysis.version_binding(candidate.source_version_id, candidate.target_version_id), "profile_revision": 1, "configuration_fingerprint": relation_analysis.configuration_fingerprint(service.settings), "prompt_fingerprint": relation_analysis.relation_prompt_fingerprint(service.prompt_settings)}},
                                          result={"schema_version": relation_analysis.SCHEMA_VERSION, "supported": True,
                                                  "potential_severity": "high", "explanation": "Synthetic tested result"}))
        session.commit()
    unfiltered = client.get("/api/impact-inbox/page", params={"limit": 1}).json()
    assert len(unfiltered["items"]) == 1 and unfiltered["total_impacts"] == 2 and not unfiltered["has_more"]
    second_item = next(item for item in unfiltered["items"][0]["items"] if item["organization_candidate_id"] == second)
    for key in ("law_id", "watch_id"):
        params = {"severity": "high", "watched_law": second_item[key]}
        paged = client.get("/api/impact-inbox/page", params=params).json()
        legacy = client.get("/api/impact-inbox", params=params).json()
        assert paged["items"] == legacy["items"]
        assert paged["total_impacts"] == 1 and paged["items"][0]["items"][0]["severity"] == "unknown"


@pytest.mark.parametrize("filters", [{"source": "missing"}, {"item_type": "missing"}, {"state": "read"}, {"watched_law": "missing"}])
def test_sql_filters_avoid_loading_ineligible_delivery_payloads(harness, filters):
    client, _, _, _ = harness
    relation_delivery(harness)
    loaded = []
    def record(_session, row):
        if isinstance(row, (OrganizationRelationCandidate, RegulatoryEvent)):
            loaded.append(row.id)
    sa_event.listen(Session, "loaded_as_persistent", record)
    try:
        body = client.get("/api/impact-inbox/page", params=filters).json()
    finally:
        sa_event.remove(Session, "loaded_as_persistent", record)
    assert body["items"] == [] and body["scanned_event_count"] == 0 and loaded == []


@pytest.mark.parametrize("value", ["not-base64", base64.urlsafe_b64encode(b"[]").decode(), base64.urlsafe_b64encode(b"["*1000+b"]"*1000).decode(), "a"*4097])
def test_bad_cursors_are_rejected_as_client_errors(harness, value):
    client, _, _, _ = harness
    assert client.get("/api/impact-inbox/page", params={"cursor": value}).status_code == 422


@pytest.mark.parametrize("limit", [0, 51, -1])
def test_api_page_size_has_a_hard_upper_bound(harness, limit):
    client, _, _, _ = harness
    assert client.get("/api/impact-inbox/page", params={"limit": limit}).status_code == 422
