"""Whole private deadline journey. All rules, calendars and rights here are synthetic."""

import hashlib
from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_trademark_deadlines import PREFERENCE, calendar, install, published, rule
from test_trademark_exports import prepare, read
from test_trademark_history import page
from test_trademark_matching import portfolio
from test_trademark_sources import NOW, RAW, accept, grant
from test_trademark_sources import db as _db
from test_trademark_sources import template as _template
from test_trademark_workflow import review, rows, sync

from helvetic_lens import trademark_deadlines as deadlines
from helvetic_lens import trademark_history as history
from helvetic_lens import trademark_repository as profiles
from helvetic_lens import trademark_sources as sources
from helvetic_lens import trademark_workflow as workflow
from helvetic_lens.config import DomainError
from helvetic_lens.trademark_workflow_models import TrademarkCandidateEvent

db, template = _db, _template


def setup(db):
    ids = install(db)
    permission = grant(db, export_allowed=True, private_decisions_allowed=True)
    evidence = published(date(2026, 6, 11), source_sha256=hashlib.sha256(RAW).hexdigest())
    accept(db, permission, facts=evidence)
    config = {**portfolio().model_dump(mode="json"), "deadline_context": PREFERENCE.model_dump(mode="json")}
    with db.session() as session:
        monitor = profiles.create_monitor(session, "owner", config, str(uuid4()))["id"]
        workflow.start(session, "owner", monitor, 1, now=NOW)
        workflow.refresh(session, "owner", monitor, now=NOW)
        session.commit()
    return permission, monitor, ids, evidence


def test_calendar_revision_reopens_review_and_pins_history_without_erasing_decision(db):
    _, monitor, ids, _ = setup(db)
    first = review(db, monitor, decision="counsel")
    assert first["deadline_context"]["calculated_review_deadline"] == "2026-09-11"
    assert first["deadline_context"]["days_remaining"] == -2
    with db.session() as session:
        event_id = session.scalar(select(TrademarkCandidateEvent.id))
    new_ids = install(db, previous_rule=ids[0], previous_calendar=ids[1],
        calendar_value=calendar(recognized_holidays=(date(2026, 9, 11), date(2026, 9, 14))))
    assert rows(db, monitor)[0]["facts"] is None  # stale review projection cannot claim the old date
    sync(db, monitor)
    second, = rows(db, monitor)
    assert second["sequence"] == 2 and second["decision"] == "counsel" and second["needs_review"]
    assert second["deadline_context"]["calculated_review_deadline"] == "2026-09-15"
    assert second["deadline_context"]["days_remaining"] == 2
    item, = page(db, inbox=True)["items"]
    assert item["deadline_context"] == second["deadline_context"] and "deadline_changed" in item["change_codes"]
    with db.session() as session:
        old = history.event_detail(session, "owner", monitor, first["id"], event_id, now=NOW)
        assert old["deadline_context"]["calendar"]["id"] == ids[1]
        assert old["deadline_context"]["calculated_review_deadline"] == "2026-09-11"
        assert old["current"]["deadline_context"]["calendar"]["id"] == new_ids[1]
        assert history.reviews(session, "owner", monitor, first["id"])["items"][0]["decision"] == "counsel"
    packet = prepare(db, monitor, event_id=event_id)
    assert "2026-09-11" in packet["document"] and "2026-09-15" in packet["document"]
    with db.session() as session:
        deadlines.revoke(session, "calendar", ids[1], now=NOW)
        session.commit()
    with pytest.raises(DomainError) as changed:
        read(db, monitor, packet, download=True)
    assert changed.value.code == "trademark_export_changed"
    with db.session() as session:
        old = history.event_detail(session, "owner", monitor, first["id"], event_id, now=NOW)
        assert old["deadline_context"]["calculated_review_deadline"] is None


def test_rule_change_and_publication_correction_invalidate_prepared_download(db):
    permission, monitor, ids, evidence = setup(db)
    packet = prepare(db, monitor)
    install(db, previous_rule=ids[0], previous_calendar=ids[1],
        rule_value=rule(mapping_reference="Second reviewed synthetic mapping"))
    with pytest.raises(DomainError):
        read(db, monitor, packet, download=True)
    sync(db, monitor)
    reviewed = review(db, monitor)
    corrected = published(date(2026, 6, 12), source_sha256=evidence.source_sha256)
    accept(db, permission, cursor=1, facts=corrected)
    sync(db, monitor, NOW + timedelta(seconds=1))
    new, = rows(db, monitor, NOW + timedelta(seconds=1))
    assert new["needs_review"] and new["sequence"] == reviewed["sequence"] + 1
    assert new["deadline_context"]["calculated_review_deadline"] == "2026-09-14"
    assert new["deadline_context"]["publication_evidence"]["date"] == "2026-06-12"


def test_midnight_changes_export_but_not_candidate_review(db):
    permission, monitor, _, evidence = setup(db)
    before = NOW.replace(hour=21, minute=59, second=50)  # 23:59:50 Zurich
    after = before + timedelta(seconds=20)
    accept(db, permission, cursor=1, facts=evidence, second=int((before - NOW).total_seconds()))
    sync(db, monitor, before)
    reviewed = review(db, monitor, now=before)
    packet = prepare(db, monitor, now=before)
    sync(db, monitor, after)
    later, = rows(db, monitor, after)
    assert not later["needs_review"] and later["sequence"] == reviewed["sequence"]
    assert later["deadline_context"]["days_remaining"] == reviewed["deadline_context"]["days_remaining"] - 1
    with pytest.raises(DomainError) as changed:
        read(db, monitor, packet, now=after, download=True)
    assert changed.value.code == "trademark_export_changed"
    fresh = prepare(db, monitor, key="after-midnight", now=after)
    assert fresh["content_sha256"] != packet["content_sha256"]


def test_source_revocation_hides_all_deadline_evidence_and_private_scope_holds(db):
    permission, monitor, _, _ = setup(db)
    first, = rows(db, monitor)
    with db.session() as session:
        for user in ("peer", "viewer"):
            with pytest.raises(DomainError):
                workflow.list_candidates(session, user, monitor, now=NOW)
        sources.revoke_permission(session, permission, now=NOW)
        session.commit()
    hidden, = rows(db, monitor)
    assert hidden["facts"] is None and hidden.get("deadline_context") is None
    assert not page(db)["items"]
    with db.session() as session:
        event_id = session.scalar(select(TrademarkCandidateEvent.id))
        old = history.event_detail(session, "owner", monitor, first["id"], event_id, now=NOW)
        assert old["snapshot"]["facts"] is None and old["deadline_context"] is None


@pytest.mark.parametrize("locale", ["en-CH", "de-CH", "fr-CH", "it-CH", "rm-CH"])
def test_permitted_packet_contains_auditable_calculation_in_each_locale(db, locale):
    _, monitor, ids, _ = setup(db)
    packet = prepare(db, monitor, locale=locale)
    assert 'lang="' + locale + '"' in packet["document"]
    assert all(identifier in packet["document"] for identifier in ids)
    assert "2026-09-11" in packet["document"] and "2026-09-12T00:00:00+02:00" in packet["document"]
    assert "https://example.invalid/synthetic-reference" in packet["document"]
    assert "<script" not in packet["document"] and "default-src" in packet["document"]
    assert read(db, monitor, packet, download=True)["content_sha256"] == packet["content_sha256"]
