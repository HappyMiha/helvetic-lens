"""Native snapshot to private reader, review, feeds and consented fake delivery.

These are synthetic publisher scope and geometry proofs, never live coverage.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select
from test_hazard_delivery import Mailer, deliver, opt_in
from test_hazard_lifecycle import command, coverage
from test_hazard_lifecycle import store as _store_fixture
from test_hazard_meteoalarm_store import (
    FIRST,
    NOW,
    SECOND,
    SENDER,
    SENT,
    accept,
    original,
    permission,
    snapshot,
    weather_info,
)
from test_hazard_repository import CONFIG, create
from test_hazard_sources import db as _database_fixture
from test_hazard_sources import template as _template_fixture

from helvetic_lens import hazard_events as events
from helvetic_lens import hazard_jobs as worker
from helvetic_lens import hazard_meteoalarm as source
from helvetic_lens import hazard_today as feeds
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.hazard_models import HazardDevelopment

db = _database_fixture
template = _template_fixture
store = _store_fixture


def setup(db, store, *, initial=None):
    saved = create(db, {**CONFIG, "hazards": ["storm"]})
    permit = permission(db, coverage=(coverage(),), attribution=source.ATTRIBUTION)
    published = accept(db, permit, snapshot(initial or original()))
    config = Settings(_env_file=None, hazard_watch_enabled=True, hazard_source_enabled=True,
        hazard_source_permission_id=permit, auth_email_mode="smtp", auth_smtp_host="smtp.example.invalid",
        auth_email_from="monitoring@example.invalid", public_base_url="https://example.test")
    saved = command(db, store, config, opt_in(db, saved), "start")
    assert worker.refresh(db, config, monitor_id=saved["id"], version=saved["version"], now=NOW, store=store)["changed"] == 1
    with db.session() as session:
        event = session.scalar(select(HazardDevelopment)).id
    return saved, permit, config, published["cursor"], event


def test_native_warning_appears_in_private_feeds_and_preserves_originals_attribution_and_review(db, store):
    payload = original(infos=weather_info(extra="<parameter><valueName>impacts</valueName><value>Falling branches.</value></parameter>"))
    saved, permit, config, cursor, event = setup(db, store, initial=payload)
    with db.session() as session:
        row = events.read_event(session, "owner", saved["id"], event, store=store, now=NOW)
        assert row["source"]["message"]["profile"] == "meteoalarm-v2"
        assert row["source"]["message"]["identity"]["sent"].isoformat() == SENT
        assert ("impacts", "Falling branches.") in row["source"]["message"]["infos"][0]["parameters"]
        assert row["source"]["attribution"] == source.ATTRIBUTION
        assert row["source"]["redistribution"]["disclaimer"] == source.DELAY_DISCLAIMER
        assert row["source"]["redistribution"]["url"] == source.SOURCE_URL
        for inbox in (False, True):
            item, = feeds.page(session, config, "owner", store=store, now=NOW, inbox=inbox)["items"]
            assert item["event_id"] == event and "revision=1" in item["href"]
            assert "Falling branches" not in str(item)
        assert feeds.page(session, config, "peer", store=store, now=NOW)["items"] == []
        with pytest.raises(DomainError):
            events.read_event(session, "peer", saved["id"], event, store=store, now=NOW)
    fake = Mailer()
    assert deliver(db, saved, config, store, fake) == {"status": "sent", "changes": 1}
    assert len(fake.calls) == 1
    body = str(fake.calls[0])
    assert source.ATTRIBUTION in body and source.DELAY_DISCLAIMER in body
    assert SENT in body and source.SOURCE_URL in body
    assert "Falling branches" not in body
    with db.session() as session:
        events.set_review(session, "owner", saved["id"], event, version=row["version"], expected_revision=1,
                          action="reviewed", store=store, now=NOW)
        session.commit()
    changed = original(identifier=SECOND, kind="Update", sent="2026-09-13T09:30:00+00:00",
        refs=f"{SENDER},{FIRST},{SENT}", infos=weather_info(instruction="New official instructions."))
    later = NOW + timedelta(minutes=2)
    accept(db, permit, snapshot(changed, when=later), cursor)
    assert worker.refresh(db, config, monitor_id=saved["id"], version=saved["version"], now=later, store=store)["changed"] == 1
    with db.session() as session:
        row = events.read_event(session, "owner", saved["id"], event, store=store, now=later)
        assert row["revision"] == 2 and row["needs_review"]
        assert feeds.page(session, config, "owner", store=store, now=later, inbox=True)["items"][0]["event_id"] == event
    assert deliver(db, saved, config, store, fake, now=later) == {"status": "sent", "changes": 1}
    assert len(fake.calls) == 2


@pytest.mark.parametrize("cause", ["withdrawn", "stale"])
def test_withdrawal_or_stale_poll_suppresses_pending_mail_and_current_feed_but_preserves_history(db, store, cause):
    saved, permit, config, cursor, event = setup(db, store)
    later = NOW + timedelta(minutes=2 if cause == "withdrawn" else 6)
    if cause == "withdrawn":
        accept(db, permit, snapshot(when=later), cursor)
    with db.session() as session:
        row = events.read_event(session, "owner", saved["id"], event, store=store, now=later)
        assert row["state"] == "unavailable" and "source" not in row
        assert row["reason"] == ("hazard_source_no_longer_listed" if cause == "withdrawn" else "hazard_source_poll_not_current")
        old = events.read_event(session, "owner", saved["id"], event, store=store, now=later, revision=1)
        assert old["historical"] and old["state"] == "active" and old["source"]["history_complete"]
        assert feeds.page(session, config, "owner", store=store, now=later)["items"] == []
    fake = Mailer()
    expected = "no_eligible_changes" if cause == "withdrawn" else "unavailable"
    assert deliver(db, saved, config, store, fake, now=later)["status"] == expected
    assert fake.calls == []


def test_initial_official_update_exposes_missing_history_without_fabricated_original_alert(db, store):
    imported = original(kind="Update", refs=f"{SENDER},{source.ISSUER_PREFIX}missing,2026-09-13T08:00:00+00:00")
    saved, _, _, _, event = setup(db, store, initial=imported)
    with db.session() as session:
        row = events.read_event(session, "owner", saved["id"], event, store=store, now=NOW)
        assert row["source"]["history_complete"] is False
        assert row["source"]["message"]["message_type"] == "Update"
        assert row["revision"] == 1 and row["state"] == "active"
