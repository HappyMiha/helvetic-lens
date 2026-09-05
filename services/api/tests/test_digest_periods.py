"""Digest periods filter in SQL before hydrating historical evidence."""

from datetime import timedelta

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import insert
from test_relation_analysis import relation_delivery

from helvetic_lens import digests
from helvetic_lens.auth_mail import AuthMailer
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.impact_inbox import ImpactInboxReader, principal_key
from helvetic_lens.models import (
    DigestDelivery,
    DigestPreference,
    Organization,
    OrganizationMembership,
    OrganizationRelationCandidate,
    RegulatoryEvent,
    RegulatoryEventUserState,
    RelationCandidate,
    User,
    new_id,
)


def seed_events(harness, specs):
    """Clone synthetic relation fixtures, keeping each event/candidate distinct."""
    _, _, service, _ = harness
    delivery_id, _ = relation_delivery(harness, confirmed=True)
    with service.db.session() as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        candidate = session.get(RelationCandidate, delivery.candidate_id)
        source_event = session.get(RegulatoryEvent, candidate.event_id)
        source_event.detected_at = utcnow() - timedelta(days=365)
        session.flush()
        def values(row):
            return {column.key: getattr(row, column.key) for column in row.__table__.columns}
        event_base, candidate_base, delivery_base = map(values, (source_event, candidate, delivery))
        for offset in range(0, len(specs), 500):
            events, candidates, deliveries = [], [], []
            for spec in specs[offset:offset + 500]:
                event_id, candidate_id = spec["id"], new_id()
                events.append({**event_base, **{k: v for k, v in spec.items() if k != "organization_id"},
                               "dedupe_key": event_id})
                candidates.append({**candidate_base, "id": candidate_id, "event_id": event_id})
                deliveries.append({**delivery_base, "id": new_id(), "candidate_id": candidate_id,
                                   "organization_id": spec.get("organization_id", service.organization_id)})
            session.execute(insert(RegulatoryEvent), events)
            session.execute(insert(RelationCandidate), candidates)
            session.execute(insert(OrganizationRelationCandidate), deliveries)
        session.commit()


def recipient(service, email="period-reader@example.ch"):
    with service.db.session(include_all_organizations=True) as session:
        user = User(email=email, password_hash="test-only", name="Period reader")
        session.add(user)
        session.flush()
        session.add(OrganizationMembership(organization_id=service.organization_id, user_id=user.id, role="viewer"))
        session.commit()
        return user.id


def test_period_sql_excludes_large_history_future_other_sources_and_private_states(harness):
    _, _, service, model = harness
    end = utcnow() - timedelta(hours=1)
    start = end - timedelta(days=1)
    user_id, other_id = recipient(service), recipient(service, "other-reader@example.ch")
    with service.db.session() as session:
        foreign = Organization(name="Period outsider", slug="period-outsider")
        session.add(foreign)
        session.commit()
        foreign_id = foreign.id
    ids = {name: new_id() for name in ("start", "inside", "end", "wrong_source", "muted", "dismissed", "other_reader", "foreign")}
    specs = [{"id": new_id(), "detected_at": start - timedelta(microseconds=1),
              "connector": "archived-source"} for _ in range(10_000)]
    specs += [{"id": id_, "detected_at": start if name == "start" else end if name == "end" else end - timedelta(seconds=1),
               **({"connector": "wrong", "authority": "wrong"} if name == "wrong_source" else {}),
               **({"organization_id": foreign_id} if name == "foreign" else {})}
              for name, id_ in ids.items()]
    # Insert foreign rows only through this test's explicitly privileged setup.
    with service.db.organization_context(service.organization_id):
        seed_events(harness, [s for s in specs if "organization_id" not in s])
    with service.db.session(include_all_organizations=True) as session:
        template = session.get(RegulatoryEvent, ids["inside"])
        candidate = session.query(RelationCandidate).filter_by(event_id=template.id).one()
        delivery = session.query(OrganizationRelationCandidate).filter_by(candidate_id=candidate.id).one()
        session.add(OrganizationRelationCandidate(organization_id=foreign_id, candidate_id=candidate.id, watch_id=delivery.watch_id))
        # An event visible ONLY to the foreign organization.
        session.add(RegulatoryEvent(id=ids["foreign"], work_id=template.work_id, authority="foreign-source",
                                    event_type="created", dedupe_key=ids["foreign"], detected_at=start,
                                    provenance_method="test-only", connector="foreign-source"))
        session.flush()
        foreign_candidate = RelationCandidate(event_id=ids["foreign"], source_work_id=candidate.source_work_id,
                                             target_work_id=candidate.target_work_id, score=1, rule_revision="test",
                                             expires_at=end + timedelta(days=1))
        session.add(foreign_candidate)
        session.flush()
        session.add(OrganizationRelationCandidate(organization_id=foreign_id, candidate_id=foreign_candidate.id, watch_id=delivery.watch_id))
        for name, owner, org, state in [("muted", user_id, service.organization_id, "muted"),
                                       ("dismissed", user_id, service.organization_id, "dismissed"),
                                       ("other_reader", other_id, service.organization_id, "muted"),
                                       ("start", user_id, foreign_id, "muted"),
                                       ("inside", user_id, service.organization_id, "read")]:
            session.add(RegulatoryEventUserState(organization_id=org, event_id=ids[name], user_id=owner,
                                                 principal_key=principal_key(owner), state=state))
        session.commit()
    preference = DigestPreference(sources=["swiss_parliament"], severities=[])
    with service.db.session() as session:
        loaded = []
        sa_event.listen(session, "loaded_as_persistent", lambda _session, row: loaded.append(row))
        reader = ImpactInboxReader(service.organization_id, user_id, settings=service.settings, prompts=service.prompt_settings)
        page = reader.page(session, digests.inbox_filters(preference, start, end))
        assert {item["event_id"] for item in page["items"]} == {ids["start"], ids["inside"], ids["other_reader"]}
        assert len([row for row in loaded if isinstance(row, OrganizationRelationCandidate)]) == 3
        assert len([row for row in loaded if isinstance(row, RegulatoryEvent)]) == 3
        assert len([row for row in loaded if isinstance(row, RegulatoryEventUserState)]) == 1
        before = len(loaded)
        assert reader.source_options(session) == ["archived-source", "swiss-parliament", "swiss_parliament", "wrong"]
        assert len(loaded) == before  # Column-only source menu, no payload hydration.
    assert model.calls == []


def test_retry_and_preview_use_saved_half_open_period_without_sending_mail(harness, monkeypatch):
    _, _, service, model = harness
    end = utcnow() - timedelta(hours=1)
    start = end - timedelta(days=1)
    inside, boundary = new_id(), new_id()
    seed_events(harness, [{"id": inside, "detected_at": start}, {"id": boundary, "detected_at": end}])
    user_id = recipient(service)
    service.save_digest_preference(user_id, enabled=True, frequency="daily", severities=[], sources=[])
    job = service.enqueue_digest_now(user_id)
    with service.db.session() as session:
        delivery = session.get(DigestDelivery, job["target_id"])
        delivery.period_start, delivery.period_end = start, end
        session.commit()
    calls = []
    def mail(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise DomainError("Test-only mail failure", 503, "email_delivery_failed")
        return "test-outbox"
    monkeypatch.setattr(AuthMailer, "send_message", mail)
    with pytest.raises(DomainError, match="Test-only"):
        digests.deliver(service.db, service.environment_settings, job["target_id"])
    result = digests.deliver(service.db, service.environment_settings, job["target_id"])
    assert result["status"] == "succeeded"
    with service.db.session() as session:
        delivery = session.get(DigestDelivery, job["target_id"])
        assert [item["event_id"] for item in delivery.summary["events"]] == [inside]
        assert digests._aware(delivery.period_start) == start and digests._aware(delivery.period_end) == end
        assert session.query(RegulatoryEventUserState).count() == 0
    digests.deliver(service.db, service.environment_settings, job["target_id"])
    assert len(calls) == 2  # Completed delivery is not resent.
    monkeypatch.setattr("helvetic_lens.service.utcnow", lambda: end)
    preview = service.digest_overview(user_id)
    assert [item["event_id"] for item in preview["preview"]["events"]] == [inside]
    assert model.calls == []


def test_empty_filtered_preview_keeps_available_source_menu(harness):
    _, _, service, model = harness
    seed_events(harness, [{"id": new_id(), "detected_at": utcnow() - timedelta(days=30), "connector": "older-source"}])
    user_id = recipient(service)
    saved = service.save_digest_preference(user_id, enabled=False, frequency="daily", severities=[], sources=["no-match"])
    assert saved["preview"] == {"events": [], "truncated": False}
    assert saved["source_options"] == ["older-source", "swiss-parliament", "swiss_parliament"]
    assert model.calls == []


@pytest.mark.parametrize("count,truncated", [(0, False), (49, False), (50, False), (51, True)])
def test_summary_uses_one_more_eligible_event_for_truncation(count, truncated):
    end = utcnow()
    start = end - timedelta(days=1)
    impact = {"severity": "high", "law_id": "law", "law_title": "Law", "potential_effect": "Effect",
              "suggested_next_step": "Review", "links": {}}
    group = {"event_id": "event", "title": "Title", "source": "test", "detected_at": start.isoformat(), "items": [impact]}
    page = {"items": [dict(group, event_id=str(i)) for i in range(count)] + [
        dict(group, detected_at=end.isoformat()),
        dict(group, detected_at=(start - timedelta(microseconds=1)).isoformat()),
        dict(group, read_state="muted"), dict(group, source="other"),
        dict(group, items=[dict(impact, severity="low")]),
    ]}
    summary = digests.filtered_summary(page, DigestPreference(sources=["test"], severities=["high"]), start, end)
    assert len(summary["events"]) == min(count, 50)
    assert summary["truncated"] is truncated
