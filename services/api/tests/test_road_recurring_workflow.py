import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_road_delivery import Mailer, deliver, opt_in
from test_road_feed import NOW, feed, record
from test_road_jobs import current, refresh, setup, states, totals
from test_road_recurrence import recurrence
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import road_delivery as mail
from helvetic_lens import road_events as events
from helvetic_lens import road_sources as sources
from helvetic_lens import road_today
from helvetic_lens.config import DomainError


def test_pre_feature_canonical_source_bytes_and_hashes_remain_readable_without_migration():
    fixture = json.loads(Path(__file__).with_name('road_pre_recurrence.json').read_text(encoding='utf-8'))
    encoded = sources._encoded(fixture['body'])
    row = SimpleNamespace(content=encoded, content_size=len(encoded), content_hash=sources._hash(encoded),
                          expires_at=NOW + timedelta(days=1), source_id='event-1',
                          semantic_hash=fixture['semantic_hash'], version_at=NOW)
    decoded = sources._read_version(row, now=NOW)
    assert decoded.semantic_hash == fixture['semantic_hash']
    assert decoded.records[0].semantic_hash == fixture['record_semantic_hash']
    assert sources._encode_situation(decoded) == encoded


@pytest.mark.parametrize("mapping", ["opposite", "unknown"])
def test_unrelated_or_unverified_corridors_cannot_consume_recurring_schedule_budget(db, monkeypatch, mapping):
    clauses = record(validity_extra=recurrence())
    if mapping == "unknown":
        clauses += record(identifier="unmapped-clause", validity_extra=recurrence()).replace("synthetic-1", "unreviewed-version")
    row, _, _, settings = setup(db, xml=feed(clauses), reverse=True)

    def unexpected(*args, **kwargs):
        raise AssertionError("Do not expand a schedule without a verified corridor intersection")

    monkeypatch.setattr(events, "temporal_state", unexpected)
    assert refresh(db, row, settings)["changed"] == 0
    assert totals(db) == (0, 0)


def test_recurring_source_rolls_current_window_preserves_review_and_never_invents_clearance(db):
    xml = feed(record(validity_extra=recurrence('10:01:00Z', '10:03:00Z')))
    row, permission, _, settings = setup(db, xml=xml, notifications=True)
    settings.auth_email_mode, settings.auth_smtp_host = 'smtp', 'smtp.example.invalid'
    settings.auth_email_from = 'monitoring@example.invalid'
    settings.public_base_url = 'https://example.test'
    row = opt_in(db, row)
    assert refresh(db, row, settings)['changed'] == 1
    planned = current(db, row)
    assert states(planned) == {'planned'}
    fact = next(iter(planned['payload']['corridors'].values()))['facts'][0]
    assert fact['recurring'] is True and fact['valid_from'] == '2026-09-13T10:01:00+00:00'
    assert refresh(db, row, settings)['changed'] == 0
    with db.session() as session:
        events.review_event(session, 'owner', planned['id'], expected_version=planned['version'], sequence=planned['sequence'])
        session.commit()
    assert refresh(db, row, settings, minute=1)['changed'] == 1
    active = current(db, row, minute=1)
    assert active['id'] == planned['id'] and states(active) == {'active'}
    assert active['reviewed_sequence'] == 1 and active['sequence'] == 2
    with db.session() as session:
        preview = mail.preview(session, settings, 'owner', row['id'], now=NOW + timedelta(minutes=1))
        assert [item['sequence'] for item in preview['items']] == [2]
        assert road_today.today(session, settings, 'owner', now=NOW + timedelta(minutes=1))['items']
        with pytest.raises(DomainError):
            events.events_page(session, 'peer', row['id'], now=NOW + timedelta(minutes=1))
    fake = Mailer()
    assert deliver(db, row, settings, fake, now=NOW + timedelta(minutes=1))['status'] == 'sent'
    assert len(fake.calls) == 1
    assert refresh(db, row, settings, minute=2)['changed'] == 0
    assert refresh(db, row, settings, minute=3)['changed'] == 1
    upcoming = current(db, row, minute=3)
    assert upcoming['id'] == active['id'] and states(upcoming) == {'planned'}
    assert 'cleared' not in str(upcoming['payload'])
    assert totals(db) == (1, 3)
    with db.session() as session:
        history = events.history_page(session, 'owner', planned['id'], now=NOW + timedelta(minutes=3))
        assert [v['sequence'] for v in history['items']] == [1, 2, 3]
        sources.revoke_permission(session, permission, now=NOW + timedelta(minutes=3))
        session.commit()
    assert current(db, row, minute=3)['payload'] is None
    with db.session() as session:
        assert mail.preview(session, settings, 'owner', row['id'], now=NOW + timedelta(minutes=3))['items'] == []
