"""Whole-snapshot journal checks using explicitly synthetic source permissions."""

from dataclasses import replace
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5
from xml.sax.saxutils import escape

import pytest
from sqlalchemy import func, select
from test_hazard_cap import NOW, SENT, info, message
from test_hazard_sources import db as _database_fixture
from test_hazard_sources import grant
from test_hazard_sources import template as _template_fixture

from helvetic_lens import hazard_meteoalarm as source
from helvetic_lens import hazard_sources as journal
from helvetic_lens.config import DomainError
from helvetic_lens.hazard_cap import HazardCAPError, decode_cap
from helvetic_lens.hazard_meteoalarm_store import publish
from helvetic_lens.hazard_source_models import (
    HazardCurrentWarning,
    HazardMessageEvidence,
    HazardSourceSelection,
)

db = _database_fixture
template = _template_fixture

FIRST = source.ISSUER_PREFIX + "synthetic-1"
SECOND = source.ISSUER_PREFIX + "synthetic-2"
SENDER = "fixture@example.invalid"


def weather_info(**kwargs):
    parameters = '<parameter><valueName>awareness_type</valueName><value>1; Wind</value></parameter>'
    return info(extra=parameters + kwargs.pop("extra", ""), **kwargs)


def original(*, identifier=FIRST, **kwargs):
    return message(identifier=identifier, infos=kwargs.pop("infos", weather_info()), **kwargs).encode()


def permission(db, **kwargs):
    return grant(db, protocol="meteoalarm-v2", source_key="meteoswiss-meteoalarm", endpoint=source.FEED_URL,
                 sender="meteoalarm-switzerland-channel", notifications_allowed=True, private_decisions_allowed=True, **kwargs)


def snapshot(*originals, when=NOW, updated=None):
    entries, bodies = [], []
    for payload in originals:
        cap = decode_cap(payload, received_at=when, profile="meteoalarm-v2")
        url = source.CAP_BASE + str(uuid5(NAMESPACE_URL, cap.identity.identifier))
        sent = cap.identity.sent.isoformat()
        entries.append(f'''<entry><id>{url}?index_info=0</id><published>{sent}</published><updated>{sent}</updated>
            <cap:identifier>{escape(cap.identity.identifier)}</cap:identifier><cap:sent>{sent}</cap:sent>
            <cap:message_type>{cap.message_type}</cap:message_type><cap:status>Actual</cap:status><cap:scope>Public</cap:scope>
            <link type="application/cap+xml" href="{url}"/></entry>''')
        bodies.append((url, payload))
    payload = f'''<feed xmlns="{source.ATOM}" xmlns:cap="{source.CAP}"><id>{source.FEED_ID}</id>
        <link rel="self" href="{source.FEED_URL}"/><updated>{(updated or when).isoformat()}</updated>
        {''.join(entries)}</feed>'''.encode()
    feed = source.parse_feed(payload, now=when)
    originals = tuple(source.verify_original(warning, dict(bodies)[warning.url]) for warning in feed.warnings)
    return source.Snapshot(feed, originals, when - timedelta(seconds=1), when)


def accept(db, permission_id, batch, cursor=0):
    with db.session() as session:
        result = publish(session, permission_id, batch, expected_generation=1, expected_cursor=cursor, now=batch.completed_at)
        session.commit()
        return result


def current(db):
    with db.session() as session:
        row = session.get(HazardSourceSelection, "meteoswiss-meteoalarm")
        return row.cursor_version, row.last_poll_hash


def test_complete_snapshots_refresh_and_withdraw_without_fabricating_official_revision(db):
    permit = permission(db)
    batch = snapshot(original())
    first = accept(db, permit, batch)
    assert first["cursor"] == 2 and first["present"] == 1
    assert accept(db, permit, batch, cursor=first["cursor"])["replay"] is True
    again = accept(db, permit, snapshot(original(), when=NOW + timedelta(minutes=2), updated=NOW), first["cursor"])
    with db.session() as session:
        evidence = session.scalar(select(HazardMessageEvidence))
        identity = evidence.id
        assert evidence.material_sequence == 1 and evidence.history_complete
        assert journal.read_message(session, permit, identity, now=NOW + timedelta(minutes=2), fresh=True).state == "active"
        assert session.scalar(select(func.count()).select_from(HazardMessageEvidence)) == 1
    withdrawn = accept(db, permit, snapshot(when=NOW + timedelta(minutes=4)), again["cursor"])
    assert withdrawn["present"] == 0
    with db.session() as session:
        head = session.scalar(select(HazardCurrentWarning))
        assert head.state == "active" and not head.present
        assert head.material_sequence == 1
        with pytest.raises(DomainError) as error:
            journal.read_message(session, permit, identity, now=NOW + timedelta(minutes=4), fresh=True)
        assert error.value.code == "hazard_source_no_longer_listed"
        assert journal.read_message(session, permit, identity, now=NOW + timedelta(minutes=4), fresh=False).state == "active"


def test_partial_wrong_or_rollback_snapshots_do_not_advance_freshness_or_withdraw(db):
    permit = permission(db)
    first = accept(db, permit, snapshot(original()))
    later = snapshot(original(), when=NOW + timedelta(minutes=2))
    for broken in (replace(later, originals=()),
                   replace(later, originals=(replace(later.originals[0], evidence_sha256="0" * 64),)),
                   snapshot(when=NOW + timedelta(minutes=2), updated=NOW - timedelta(minutes=1))):
        before = current(db)
        with db.session() as session:
            with pytest.raises(DomainError):
                publish(session, permit, broken, expected_generation=1, expected_cursor=first["cursor"], now=broken.completed_at)
            session.commit()  # Catching the error must not accidentally publish partial state.
        assert current(db) == before
    with db.session() as session:
        assert session.scalar(select(HazardCurrentWarning)).present


def test_failed_later_original_rolls_back_earlier_original_in_same_poll(db):
    permit = permission(db)
    first = accept(db, permit, snapshot(original()))
    # First new item can ingest, but a conflicting immutable old ID then fails.
    added = original(identifier=SECOND, sent="2026-09-13T08:30:00+00:00")
    changed = original(infos=weather_info(instruction="Changed bytes under the same source ID."))
    broken = snapshot(added, changed, when=NOW + timedelta(minutes=2))
    before = current(db)
    with db.session() as session:
        with pytest.raises(DomainError) as error:
            publish(session, permit, broken, expected_generation=1, expected_cursor=first["cursor"], now=broken.completed_at)
        assert error.value.code == "hazard_conflicting_identity"
        session.commit()
    assert current(db) == before
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(HazardMessageEvidence)) == 1


def test_mid_history_update_keeps_original_and_explicit_unknown_predecessor(db):
    permit = permission(db)
    missing = source.ISSUER_PREFIX + "unobserved"
    imported = original(kind="Update", refs=f"{SENDER},{missing},2026-09-13T08:00:00+00:00")
    result = accept(db, permit, snapshot(imported))
    with db.session() as session:
        row = session.scalar(select(HazardMessageEvidence))
        assert not row.history_complete and row.kind == "imported" and row.raw_payload == imported
        assert journal.read_message(session, permit, row.id, now=NOW, fresh=True).message_type == "Update"
    followup = original(identifier=SECOND, kind="Update", sent="2026-09-13T09:30:00+00:00",
                        refs=f"{SENDER},{FIRST},{SENT}", infos=weather_info(instruction="Updated official instruction."))
    accept(db, permit, snapshot(followup, when=NOW + timedelta(minutes=2)), result["cursor"])
    with db.session() as session:
        head = session.scalar(select(HazardCurrentWarning))
        row = session.get(HazardMessageEvidence, head.evidence_id)
        assert head.material_sequence == 2 and row.kind == "updated" and not row.history_complete
        assert session.scalar(select(func.count()).select_from(HazardCurrentWarning)) == 1


def test_known_native_permission_requires_a_completed_current_snapshot_for_fresh_reads(db):
    permit = permission(db)
    first = accept(db, permit, snapshot(original()))
    with db.session() as session:
        row = session.scalar(select(HazardMessageEvidence))
        with pytest.raises(DomainError) as error:
            journal.read_message(session, permit, row.id, now=NOW + timedelta(minutes=6), fresh=True)
        assert error.value.code == "hazard_source_poll_not_current"
        journal.revoke_permission(session, permit, now=NOW + timedelta(seconds=1))
        session.commit()
    with pytest.raises(DomainError):
        accept(db, permit, snapshot(when=NOW + timedelta(minutes=2)), first["cursor"])


@pytest.mark.parametrize("case", ["late_parent", "wrong_identity"])
def test_unobserved_history_cannot_rewrite_an_imported_root_or_forge_known_references(db, case):
    permit = permission(db)
    missing = source.ISSUER_PREFIX + "unobserved"
    imported = original(kind="Update", refs=f"{SENDER},{missing},2026-09-13T08:00:00+00:00")
    first = accept(db, permit, snapshot(imported))
    before = current(db)
    if case == "late_parent":
        later = original(identifier=missing, sent="2026-09-13T08:00:00+00:00")
        expected = "hazard_late_missing_predecessor"
    else:
        later = original(identifier=SECOND, kind="Update", sent="2026-09-13T09:30:00+00:00",
                         refs=f"{SENDER},{FIRST},2026-09-13T08:59:00+00:00")
        expected = "hazard_reference_identity_conflict"
    with pytest.raises(HazardCAPError, match=expected):
        accept(db, permit, snapshot(later, when=NOW + timedelta(minutes=2)), first["cursor"])
    assert current(db) == before
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(HazardCurrentWarning)) == 1
        assert session.scalar(select(func.count()).select_from(HazardMessageEvidence)) == 1


def test_meteoalarm_original_http_links_and_translated_impacts_are_preserved():
    def impacts(value):
        return f'<parameter><valueName>impacts</valueName><value>{value}</value></parameter>'
    english = weather_info(extra=impacts("Falling branches.")).replace("https://example.invalid", "http://example.invalid")
    german = weather_info(language="de-CH", extra=impacts("Herabfallende Äste."))
    payload = original(infos=english + german)
    with pytest.raises(HazardCAPError, match="hazard_invalid_link"):
        decode_cap(payload, received_at=NOW)
    decoded = decode_cap(payload, received_at=NOW, profile="meteoalarm-v2")
    assert decoded.unsupported == () and decoded.infos[0].web.startswith("http://")
    assert ("impacts", "Herabfallende Äste.") in decoded.infos[1].parameters


@pytest.mark.parametrize(("code", "events", "hazards"), [
    ("1; Wind", "", ["storm"]), ("3; Thunderstorm", "", ["storm"]),
    ("2; snow-ice", "", []), ("2; snow-ice", "OET-108", []),
    ("2; snow-ice", "OET-184", ["heavy_snow"]),
    ("2; snow-ice", "OET-023", []), ("2; snow-ice", "OET-026", []), ("2; snow-ice", "OET-185", []),
    ("12; flooding", "", ["flood"]), ("1; Snow", "", []),
])
def test_weather_classification_never_turns_ice_or_conflicting_codes_into_snow(code, events, hazards):
    body = weather_info().replace("1; Wind", code)
    if events:
        body = body.replace("</info>", f'<eventCode><valueName>OET:v1.0</valueName><value>{events}</value></eventCode></info>')
    decoded = decode_cap(original(infos=body), received_at=NOW, profile="meteoalarm-v2")
    result = source.classify_weather(decoded, importance={"Severe": "warning"})
    assert result["hazards"] == hazards and result["complete"] == bool(hazards)
