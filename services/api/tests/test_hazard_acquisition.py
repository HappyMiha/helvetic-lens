"""Durable native collector boundaries; all permissions and originals are fixtures."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from test_hazard_meteoalarm_store import NOW, original, permission, snapshot
from test_hazard_sources import db as _database_fixture
from test_hazard_sources import template as _template_fixture

from helvetic_lens import hazard_acquisition as acquisition
from helvetic_lens import hazard_sources as journal
from helvetic_lens.hazard_meteoalarm import MeteoAlarmError
from helvetic_lens.hazard_source_models import HazardMessageEvidence, HazardSourcePoll, HazardSourceSelection

db = _database_fixture
template = _template_fixture


def settings(permission_id):
    return SimpleNamespace(hazard_watch_enabled=True, hazard_source_enabled=True,
                           hazard_source_permission_id=permission_id)


def poll(db):
    with db.session() as session:
        row = session.get(HazardSourcePoll, "meteoswiss-meteoalarm")
        return {"next": journal._utc(row.next_request_at), "lease": row.lease_token,
                "success": journal._utc(row.last_success_at) if row.last_success_at else None,
                "failures": row.failures, "code": row.last_code}


def test_only_one_collector_claims_a_source_and_preserves_start_to_start_budget(db):
    permit = permission(db)
    config = settings(permit)
    ticks = [NOW]
    calls = []

    def download(*, now, checkpoint):
        checkpoint()
        assert acquisition.claim(db, permit, now=now()) is None
        calls.append(now())
        ticks[0] += timedelta(seconds=10)
        checkpoint()
        return snapshot(original(), when=now())

    result = acquisition.collect(db, config, downloader=download, now=lambda: ticks[0])
    assert result["state"] == "published" and result["present"] == 1
    assert poll(db) == {"next": NOW + timedelta(seconds=120), "lease": None,
                        "success": NOW + timedelta(seconds=10), "failures": 0, "code": "published"}
    assert acquisition.collect(db, config, downloader=download, now=lambda: ticks[0])["state"] == "deferred"
    ticks[0] = NOW + timedelta(seconds=120)
    assert acquisition.collect(db, config, downloader=download, now=lambda: ticks[0])["state"] == "published"
    assert len(calls) == 2
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(HazardMessageEvidence)) == 1


def test_provider_failure_keeps_previous_snapshot_and_honours_retry_after(db):
    permit = permission(db)
    config = settings(permit)
    acquisition.collect(db, config, downloader=lambda **_: snapshot(original()), now=lambda: NOW)
    ticks = [NOW + timedelta(seconds=120)]

    def limited(**_):
        raise MeteoAlarmError("meteoalarm_rate_limited", retry_after_seconds=900)

    result = acquisition.collect(db, config, downloader=limited, now=lambda: ticks[0])
    assert result == {"state": "unavailable", "code": "meteoalarm_rate_limited"}
    state = poll(db)
    assert state["next"] == ticks[0] + timedelta(seconds=900)
    assert state["success"] == NOW and state["failures"] == 1 and state["lease"] is None
    with db.session() as session:
        selected = session.get(HazardSourceSelection, "meteoswiss-meteoalarm")
        assert journal._utc(selected.last_poll_at) == NOW
        result = journal.read_current(session, "meteoswiss-meteoalarm", now=NOW + timedelta(minutes=6))
        assert result["items"][0]["reason"] == "hazard_source_poll_not_current"
    ticks[0] = state["next"]
    acquisition.collect(db, config, downloader=lambda **_: snapshot(when=ticks[0]), now=lambda: ticks[0])
    assert poll(db)["failures"] == 0 and poll(db)["success"] == ticks[0]


@pytest.mark.parametrize("change", ["disabled", "revoked", "reselected", "expired_lease"])
def test_in_flight_revocation_configuration_or_lease_change_cannot_publish(db, change):
    permit = permission(db)
    config = settings(permit)
    ticks = [NOW]

    def download(*, now, checkpoint):
        checkpoint()
        batch = snapshot(original())
        if change == "disabled":
            config.hazard_source_enabled = False
        elif change == "reselected":
            config.hazard_source_permission_id = "another-source"
        elif change == "revoked":
            with db.session() as session:
                journal.revoke_permission(session, permit, now=NOW)
                session.commit()
        else:
            ticks[0] += timedelta(seconds=acquisition.LEASE_SECONDS)
        return batch

    result = acquisition.collect(db, config, downloader=download, now=lambda: ticks[0])
    assert result["state"] == "unavailable"
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(HazardMessageEvidence)) == 0
        selected = session.get(HazardSourceSelection, "meteoswiss-meteoalarm")
        assert selected.last_poll_at is None and selected.cursor_version == 0


def test_crashed_worker_lease_can_expire_but_previous_owner_cannot_publish(db):
    permit = permission(db)
    first = acquisition.claim(db, permit, now=NOW)
    assert first is not None
    assert acquisition.claim(db, permit, now=NOW + timedelta(seconds=120)) is None
    retry_at = NOW + timedelta(seconds=acquisition.LEASE_SECONDS)
    second = acquisition.claim(db, permit, now=retry_at)
    assert second is not None and second.token != first.token
    with db.session() as session, pytest.raises(journal.DomainError) as error:
        acquisition.owned(session, first, now=retry_at)
    assert error.value.code == "hazard_source_lease_lost"


def test_missing_or_disabled_source_never_requests_network(db):
    def unexpected(**_):
        pytest.fail("Network requested without a configured enabled source")

    config = settings("")
    assert acquisition.collect(db, config, downloader=unexpected)["state"] == "unconfigured"
    config.hazard_watch_enabled = False
    assert acquisition.collect(db, config, downloader=unexpected)["state"] == "disabled"
