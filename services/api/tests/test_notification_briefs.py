"""Notifications reuse validated personal-language briefs without producing alerts or AI."""
import asyncio

import pytest
from sqlalchemy import delete, func, select
from test_digest_briefs import artifacts, execution, ready
from test_digest_periods import recipient

from helvetic_lens.models import InterestEventAssessment, Job, Profile, RegulatoryEventState

__all__ = ["artifacts", "execution"]


async def notifications(service, user, **kwargs):
    async with service.runtime_cache_scope():
        return service.interest_notifications(user, **kwargs)


@pytest.mark.parametrize("locale", ["de", "fr", "it", "rm", "en"])
def test_saved_notification_uses_current_user_language_once_per_page(execution, locale):
    service, user, saved = ready(execution, locale=f"{locale}-CH")
    state = execution[4]
    before = len(state["requests"])
    page = asyncio.run(notifications(service, user, locale=locale))
    assert len(state["requests"]) == before + 1  # metadata only, not per-event probes
    assert len(page["items"]) == 1 and page["ai_calls"] == 0
    event = page["items"][0]
    assert event["event_id"] == execution[2]
    assert event["brief"]["status"] == "available"
    assert event["brief"]["assessment_id"] == saved["id"] and event["brief"]["locale"] == locale
    assert event["brief"]["what_happened"] == saved["result"]["what_happened"]
    assert event["brief"]["evidence_links"] and event["source_url"]
    assert len(state["generated"]) == 1
    repeated = asyncio.run(notifications(service, user, locale=locale))
    assert repeated["items"][0]["brief"] == event["brief"]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(InterestEventAssessment)) == 1
        assert session.scalar(select(func.count()).select_from(Job).where(Job.type == "interest_event_brief")) == 0


@pytest.mark.parametrize("condition", ["language", "profile", "offline", "failed", "pending", "invalid", "revoked"])
def test_unavailable_brief_does_not_hide_source_or_leak_saved_prose(execution, condition):
    service, user, saved = ready(execution)
    state = execution[4]
    with service.db.session() as session:
        if condition == "profile":
            session.scalar(select(Profile)).revision += 1
        elif condition in {"failed", "pending"}:
            session.get(InterestEventAssessment, saved["id"]).status = "queued" if condition == "pending" else "failed"
        elif condition == "invalid":
            row = session.get(InterestEventAssessment, saved["id"])
            row.result = {**row.result, "what_happened": {"text": "UNVERIFIED", "evidence_ids": ["foreign"]}}
        elif condition == "revoked":
            session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == execution[2]))
        session.commit()
    if condition == "offline":
        state["runtime"] = {}
    page = asyncio.run(notifications(service, user, locale="fr" if condition == "language" else "en"))
    if condition == "revoked":
        assert page["items"] == []
    else:
        item = page["items"][0]
        assert item["source_url"] and item["event_id"] == execution[2]
        status = {"language": "not_scheduled", "profile": "stale", "offline": "runtime_unverified",
                  "failed": "failed", "pending": "pending", "invalid": "unavailable"}[condition]
        assert item["brief"]["status"] == status
        assert "what_happened" not in item["brief"] and "importance" not in item["brief"]
    assert len(state["generated"]) == 1


def test_shared_brief_does_not_share_personal_read_or_dismiss_state(execution):
    service, user, saved = ready(execution)
    other = recipient(service, "other-notification@example.ch")
    service.set_interest_feed_state(execution[2], "read", user)
    assert asyncio.run(notifications(service, user))["items"] == []
    page = asyncio.run(notifications(service, other))
    assert page["items"][0]["brief"]["assessment_id"] == saved["id"]
    service.set_interest_feed_state(execution[2], "dismissed", other)
    assert asyncio.run(notifications(service, other))["items"] == []
    assert len(execution[4]["generated"]) == 1


def test_notification_http_bounds_and_request_language(execution, harness):
    service, _, saved = ready(execution, locale="fr-CH")
    client = harness[0]
    response = client.get("/api/interest-feed/notifications", headers={"Accept-Language": "fr-CH"})
    assert response.status_code == 200, response.text
    brief = response.json()["items"][0]["brief"]
    assert brief["locale"] == "fr" and brief["assessment_id"] == saved["id"]
    assert brief["status"] == "available"
    for limit in (0, 6, 50):
        assert client.get("/api/interest-feed/notifications", params={"limit": limit}).status_code == 422
    assert client.get("/api/interest-feed/notifications", params={"cursor": "broken"}).status_code == 422
    assert len(execution[4]["generated"]) == 1


def test_multiple_events_share_one_probe_and_keep_bounded_continuation(execution):
    from test_digest_topics import settled_matches
    from test_interest_automation import second_event
    service, user, _ = ready(execution)
    other = second_event(execution)
    settled_matches(service)
    state = execution[4]
    before = len(state["requests"])
    page = asyncio.run(notifications(service, user))
    assert {item["event_id"] for item in page["items"]} == {execution[2], other}
    assert len(state["requests"]) == before + 1
    first = asyncio.run(notifications(service, user, limit=1))
    assert len(first["items"]) == 1 and first["next_cursor"]
    second = asyncio.run(notifications(service, user, limit=1, cursor=first["next_cursor"]))
    assert len(second["items"]) == 1 and second["items"][0]["event_id"] != first["items"][0]["event_id"]
    assert len(state["generated"]) == 1
