"""Wall-clock cadence, compatibility and additive migration evidence."""
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import select

from alembic import command
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.digest_schedule import next_local_delivery, validate_schedule
from helvetic_lens.digests import enqueue_due
from helvetic_lens.models import DigestDelivery, DigestPreference, OrganizationMembership, User


@pytest.mark.parametrize("now,frequency,zone,clock,expected", [
    ("2026-03-28T07:00:00+00:00", "daily", "Europe/Zurich", "08:00", "2026-03-29T06:00:00+00:00"),
    ("2026-10-24T06:00:00+00:00", "daily", "Europe/Zurich", "08:00", "2026-10-25T07:00:00+00:00"),
    ("2026-03-28T01:30:00+00:00", "daily", "Europe/Zurich", "02:30", "2026-03-29T01:00:00+00:00"),
    ("2026-10-24T00:30:00+00:00", "daily", "Europe/Zurich", "02:30", "2026-10-25T00:30:00+00:00"),
    ("2026-03-22T07:00:00+00:00", "weekly", "Europe/Zurich", "08:00", "2026-03-29T06:00:00+00:00"),
    ("2026-09-05T20:00:00+00:00", "daily", "Asia/Tokyo", "08:00", "2026-09-06T23:00:00+00:00"),
    ("2011-12-29T18:00:00+00:00", "daily", "Pacific/Apia", "08:00", "2011-12-30T10:00:00+00:00"),
])
def test_clock_transitions(now, frequency, zone, clock, expected):
    result = next_local_delivery(datetime.fromisoformat(now), frequency, {"timezone":zone,"time":clock})
    assert result == datetime.fromisoformat(expected)


@pytest.mark.parametrize("schedule", [{"timezone":"missing-zone","time":"08:00"}, {"time":"24:00"}, {"time":"8:00"}, {"time":"08:70"}, {"time":12}, {"timezone":"/etc/passwd"}, {"timezone":"localtime"}, {"timezone":"Factory"}, {"timezone":"Europe/Zurich","extra":True}])
def test_invalid_schedule(schedule):
    with pytest.raises(DomainError) as error:
        validate_schedule(schedule)
    assert error.value.status == 422


def user(harness):
    service = harness[2]
    with service.db.session() as session:
        person = User(email="schedule-test@example.invalid",password_hash="synthetic",name="Schedule test")
        session.add(person)
        session.flush()
        session.add(OrganizationMembership(organization_id=service.organization_id,user_id=person.id,role="viewer"))
        session.commit()
        return person.id


def test_local_schedule_save_retry_legacy_omission_and_clear(harness):
    service = harness[2]
    user_id = user(harness)
    args = dict(enabled=True,frequency="daily",severities=[],sources=[])
    saved = service.save_digest_preference(user_id, **args, schedule={"timezone":"Europe/Zurich","time":"08:00"})["preference"]
    assert saved["schedule"] == {"timezone":"Europe/Zurich","time":"08:00"}
    assert service.save_digest_preference(user_id, **args)["preference"]["next_delivery_at"] == saved["next_delivery_at"]
    repeated = service.save_digest_preference(user_id, **args, schedule=saved["schedule"])["preference"]
    assert repeated["next_delivery_at"] == saved["next_delivery_at"]
    with pytest.raises(DomainError):
        service.save_digest_preference(user_id, **args, schedule={"timezone":"invalid","time":"08:00"})
    assert service.digest_overview(user_id)["preference"]["schedule"] == saved["schedule"]
    cleared = service.save_digest_preference(user_id, **args, schedule={"timezone":"UTC","time":None})["preference"]
    assert cleared["schedule"]["time"] is None
    delta = datetime.fromisoformat(cleared["next_delivery_at"]) - utcnow()
    assert timedelta(hours=23,minutes=59) < delta <= timedelta(days=1)
    assert not harness[3].calls


def test_scheduler_keeps_local_clock_across_dst_without_duplicate_delivery(harness, monkeypatch):
    from helvetic_lens import digests
    service = harness[2]
    user_id = user(harness)
    with service.db.session() as session:
        preference = DigestPreference(user_id=user_id,organization_id=service.organization_id,
            enabled=True,frequency="daily",schedule_json={"timezone":"Europe/Zurich","time":"08:00"},
            next_delivery_at=datetime(2026,3,28,7,tzinfo=UTC))
        session.add(preference)
        session.commit()
        preference_id = preference.id
    monkeypatch.setattr(digests,"utcnow",lambda:datetime(2026,3,28,7,1,tzinfo=UTC))
    assert enqueue_due(service.db,service.settings) == {"due":1,"queued":1}
    assert enqueue_due(service.db,service.settings) == {"due":0,"queued":0}
    with service.db.session() as session:
        value = session.get(DigestPreference,preference_id).next_delivery_at
        assert value.replace(tzinfo=UTC) == datetime(2026,3,29,6,tzinfo=UTC)
        assert len(list(session.scalars(select(DigestDelivery)))) == 1



def test_empty_clock_metadata_does_not_reschedule_existing_interval(harness):
    service = harness[2]
    user_id = user(harness)
    args = dict(enabled=True,frequency="weekly",severities=[],sources=[])
    old = service.save_digest_preference(user_id, **args)["preference"]
    new = service.save_digest_preference(user_id, **args, schedule={"timezone":"Asia/Tokyo","time":None})["preference"]
    assert new["next_delivery_at"] == old["next_delivery_at"]


def test_schedule_migration_preserves_existing_preferences(harness):
    service = harness[2]
    user_id = user(harness)
    saved = service.save_digest_preference(user_id,enabled=True,frequency="weekly",severities=["high"],sources=[])["preference"]
    directory = Path(__file__).resolve().parents[1]
    config = Config(str(directory / "alembic.ini"))
    config.set_main_option("script_location",str(directory / "alembic"))
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config,"fe61da50643c")
        command.upgrade(config,"head")
    migrated = service.digest_overview(user_id)["preference"]
    assert migrated["severities"] == ["high"] and migrated["enabled"]
    assert migrated["next_delivery_at"] == saved["next_delivery_at"]
    assert migrated["schedule"]["time"] is None


def test_schedule_api_viewer_csrf_validation_and_omission(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_auth import _csrf, _register, _settings

    from helvetic_lens.main import create_app
    app = create_app(_settings(tmp_path),fetcher=FakeFetcher(),model_client=ScriptedModel())
    with TestClient(app) as client:
        account = _register(client).json()
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == account["user"]["id"])).role = "viewer"
            session.commit()
        body = {"enabled":True,"frequency":"daily","schedule":{"timezone":"Europe/Zurich","time":"08:00"}}
        assert client.put("/api/digests/preferences",json=body).status_code == 403
        saved = client.put("/api/digests/preferences",json=body,headers=_csrf(client))
        assert saved.status_code == 200, saved.text
        for schedule in ({"timezone":"invalid","time":"08:00"},{"timezone":"UTC","time":"25:00"},{"timezone":"UTC","time":"08:00","user_id":"another"}):
            assert client.put("/api/digests/preferences",json={**body,"schedule":schedule},headers=_csrf(client)).status_code == 422
        body.pop("schedule")
        unchanged = client.put("/api/digests/preferences",json=body,headers=_csrf(client)).json()
        assert unchanged["preference"]["schedule"] == saved.json()["preference"]["schedule"]
        assert unchanged["preference"]["next_delivery_at"] == saved.json()["preference"]["next_delivery_at"]
