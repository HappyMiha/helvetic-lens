"""Topic-only delivery, evidence withdrawal and bounded cross-interest selection."""
import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import delete, select
from test_digest_periods import recipient
from test_interest_feed import seed
from test_topic_matching import create_topic
from test_topic_validity import evaluate

from helvetic_lens import digests
from helvetic_lens.auth_mail import AuthMailer
from helvetic_lens.db import utcnow
from helvetic_lens.digest_reader import DigestReader
from helvetic_lens.models import (
    DigestDelivery,
    DigestPreference,
    MonitoringTopic,
    Organization,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryEventUserState,
    TopicEventMatch,
)


def reader(service, user):
    return DigestReader(service.organization_id, user, settings=service.settings, prompts=service.prompt_settings)


def settled_matches(service):
    # Fixtures represent saved history, strictly before a later preview cutoff.
    # Windows can return the same wall-clock tick immediately after commit.
    with service.db.session() as session:
        for match in session.scalars(select(TopicEventMatch)):
            match.matched_at = utcnow() - timedelta(seconds=1)
        session.commit()


def setup(harness, count=1):
    topic, ids = seed(harness, count)
    service = harness[2]
    settled_matches(service)
    user = recipient(service)
    service.save_digest_preference(user, enabled=True, frequency="weekly", sources=[], severities=[])
    return service, user, topic, ids


def test_topic_only_digest_is_grouped_and_uses_saved_evidence_without_inference(harness, monkeypatch):
    service, user, _, ids = setup(harness)
    topic = create_topic(harness[0], key="second-digest-topic", name="Another naturalisation interest")
    evaluate(service, topic, ids[0], "history")
    settled_matches(service)
    preview = service.digest_overview(user, preview_page=True)["preview"]
    assert len(preview["events"]) == 1
    event = preview["events"][0]
    assert event["severity"] == "unknown" and event["impacts"] == []
    assert len(event["topics"]) == 2 and event["topics"][0]["terms"]
    assert event["event_url"] == f"/?event={ids[0]}"
    assert event["source_url"].startswith("https://")
    delivered = []
    def capture(_self, *args, **kwargs):
        delivered.append(args)
        return "development"
    monkeypatch.setattr(AuthMailer, "send_message", capture)
    job = service.enqueue_digest_now(user)
    assert asyncio.run(service.execute_job(job["id"]))["state"] == "succeeded"
    assert len(delivered) == 1 and "Another naturalisation interest" in delivered[0][2]
    assert f"/?event={ids[0]}" in delivered[0][2]
    with service.db.session() as session:
        saved = session.scalar(select(DigestDelivery))
        assert saved.item_count == 1 and len(saved.summary["events"][0]["topics"]) == 2
        assert session.scalar(select(RegulatoryEventUserState)) is None
    assert harness[3].calls == []


def test_one_digest_event_combines_law_and_multiple_topics(harness):
    from test_interest_feed import test_one_card_for_multiple_topics_and_law_without_ai
    test_one_card_for_multiple_topics_and_law_without_ai(harness)
    service = harness[2]
    result = service.digest_overview(recipient(service), preview_page=True)
    event = result["preview"]["events"][0]
    assert len(result["preview"]["events"]) == 1
    assert len(event["topics"]) == 2 and len(event["impacts"]) == 1
    # This fixture has a potential lead awaiting analysis, not a confirmed relation.
    assert event["impacts"][0]["evidence"] is None
    assert event["severity"] == "unknown" and event["event_url"] == f"/?event={event['event_id']}"


def test_direct_watch_only_development_has_event_link_without_invented_analysis(harness):
    from test_interest_feed import (
        test_direct_watched_document_event_is_retained_without_topics_or_relation_candidates,
    )
    test_direct_watched_document_event_is_retained_without_topics_or_relation_candidates(harness)
    service = harness[2]
    user = recipient(service)
    assert service.digest_overview(user, preview_page=True)["preview"]["events"] == []
    # The reused fixture ends by pausing its watch; verify both paused and active.
    from helvetic_lens.models import DocumentWatch
    with service.db.session() as session:
        session.scalar(select(DocumentWatch)).active = True
        session.commit()
    events = service.digest_overview(user, preview_page=True)["preview"]["events"]
    assert len(events) == 1 and events[0]["monitored_documents"]
    assert events[0]["topics"] == [] and events[0]["impacts"] == [] and events[0]["severity"] == "unknown"


@pytest.mark.parametrize("locale", ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"])
def test_topic_rendering_bounds_and_escapes_saved_names(harness, locale):
    from helvetic_lens.models import User
    service, user, _, ids = setup(harness)
    for index in range(5):
        topic = create_topic(harness[0], key=f"bounded-digest-topic-{index}", name=f"<script>Test {index}</script>")
        evaluate(service, topic, ids[0], "history")
    settled_matches(service)
    summary = service.digest_overview(user, preview_page=True)["preview"]
    event = summary["events"][0]
    assert len(event["topics"]) == 5 and event["topics_truncated"]
    with service.db.session() as session:
        record = session.get(User, user)
        record.locale = locale
        _, text, html = digests.render_message(service.settings,
            DigestDelivery(preference_id="test", summary=summary), record)
    assert digests.INTEREST_MESSAGES[locale]["boundary"] in text
    assert digests.INTEREST_MESSAGES[locale]["more"] in text
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert f"/?event={ids[0]}" in html


def test_match_at_exact_preview_cutoff_waits_for_next_snapshot(harness, monkeypatch):
    service, user, _, _ = setup(harness)
    boundary = utcnow()
    with service.db.session() as session:
        session.scalar(select(TopicEventMatch)).matched_at = boundary
        session.commit()
    monkeypatch.setattr(digests, "utcnow", lambda: boundary)
    assert service.digest_overview(user, preview_page=True)["preview"]["events"] == []
    monkeypatch.setattr(digests, "utcnow", lambda: boundary + timedelta(microseconds=1))
    assert len(service.digest_overview(user, preview_page=True)["preview"]["events"]) == 1


@pytest.mark.parametrize("change", ["paused", "archived", "revision", "evidence", "expired", "rejected", "muted", "revoked", "dismissed"])
def test_prepared_topic_evidence_is_rechecked_before_send(harness, monkeypatch, change):
    service, user, topic, ids = setup(harness)
    job = service.enqueue_digest_now(user)
    with service.db.session() as session:
        checkpoint = digests.prepare_batch(session, job["target_id"], settings=service.settings)
        assert checkpoint["event_ids"] == ids and checkpoint["complete"]
        match = session.scalar(select(TopicEventMatch))
        if change in {"paused", "archived"}:
            session.get(MonitoringTopic, topic["id"]).status = change
        elif change == "revision":
            session.get(MonitoringTopic, topic["id"]).current_revision += 1
        elif change == "evidence":
            session.get(RegulatoryEvent, ids[0]).evidence_json = {"corrected": True}
        elif change == "expired":
            match.expires_at = utcnow() - timedelta(seconds=1)
        elif change in {"rejected", "muted"}:
            match.decision_status = change
        elif change == "revoked":
            session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == ids[0]))
        else:
            session.add(RegulatoryEventUserState(organization_id=service.organization_id, user_id=user,
                principal_key=f"user:{user}", event_id=ids[0], state="dismissed"))
        session.commit()
    def forbid(*args, **kwargs):
        raise AssertionError("Withdrawn evidence must not be delivered")
    monkeypatch.setattr(AuthMailer, "send_message", forbid)
    result = digests.deliver(service.db, service.environment_settings, job["target_id"], selection=checkpoint)
    assert result["status"] == "skipped" and result["item_count"] == 0
    assert harness[3].calls == []


def test_topic_severity_source_and_personal_filters_do_not_invent_impact(harness):
    service, user, _, ids = setup(harness)
    result = service.save_digest_preference(user, enabled=True, frequency="weekly", sources=[], severities=["high"])
    assert result["preview"]["events"] == []
    result = service.save_digest_preference(user, enabled=True, frequency="weekly", sources=[], severities=["unknown"])
    event = result["preview"]["events"][0]
    assert event["severity"] == "unknown" and event["topics"][0]["confidence"] == "high"
    with service.db.session() as session:
        preference = session.scalar(select(DigestPreference))
        end = utcnow()
        filters = digests.inbox_filters(preference, end - timedelta(days=7), end)
        assert reader(service, user).event_page(session, replace(filters, sources=("absent",)))["items"] == []
        reader(service, user).set_feed_state(session, ids[0], "muted")
        assert reader(service, user).event_page(session, filters)["items"] == []
        assert len(reader(service, "someone-else").event_page(session, filters)["items"]) == 1
    assert event["source"] in result["source_options"]


def test_topic_selection_pages_scope_deduplication_and_empty_continuation(harness):
    service, user, _, ids = setup(harness, 56)
    with service.db.session(include_all_organizations=True) as session:
        preference = session.scalar(select(DigestPreference))
        end = utcnow()
        filters = digests.inbox_filters(preference, end - timedelta(days=7), end)
        # First 50 candidate events are stale; traversal must still reach the six others.
        for id_ in sorted(ids, reverse=True)[:50]:
            session.get(RegulatoryEvent, id_).evidence_json = {"changed": True}
        session.commit()
        first = reader(service, user).event_page(session, filters)
        assert first["scanned"] == 50 and first["items"] == [] and first["has_more"]
        second = reader(service, user).event_page(session, replace(filters,
            admitted_before=end), cursor=first["cursor"])
        assert second["scanned"] == 6 and len(second["items"]) == 6 and not second["has_more"]
        org = Organization(name="Outside", slug="digest-topic-outside")
        session.add(org)
        session.commit()
        foreign = DigestReader(org.id, user, settings=service.settings, prompts=service.prompt_settings)
        assert foreign.event_page(session, filters)["items"] == []
        assert foreign.source_options(session) == []
    job = service.enqueue_digest_now(user)
    with service.db.session() as session:
        first = digests.prepare_batch(session, job["target_id"], settings=service.settings)
        assert not first["complete"] and first["event_ids"] == []
        second = digests.prepare_batch(session, job["target_id"], first, settings=service.settings)
        assert second["complete"] and len(second["event_ids"]) == 6
        legacy = {**second}
        legacy.pop("projection_version")
        restarted = digests.prepare_batch(session, job["target_id"], legacy, settings=service.settings)
        assert restarted["restarts"] == 1 and restarted["processed"] == 50 and not restarted["complete"]
