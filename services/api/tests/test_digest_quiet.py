"""Recipient quiet hours: real UTC boundaries and durable no-mail deferral."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from test_digest_resume import checkpoint, execute, record_mail, setup_delivery
from test_digest_schedule import user
from test_topic_history import dispatch

from helvetic_lens import digests, jobs
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.digest_schedule import quiet_until, validate_schedule
from helvetic_lens.models import DigestDelivery, DigestPreference, Job, OutboxMessage


@pytest.mark.parametrize("stamp,start,end,expected", [
    ("2026-09-06T20:00:00+00:00", "22:00", "07:00", "2026-09-07T05:00:00+00:00"),
    ("2026-09-07T05:00:00+00:00", "22:00", "07:00", None),
    ("2026-09-06T19:59:59+00:00", "22:00", "07:00", None),
    ("2026-09-06T10:00:00+00:00", "12:00", "13:00", "2026-09-06T11:00:00+00:00"),
    ("2026-03-29T00:59:59+00:00", "22:00", "02:30", "2026-03-29T01:00:00+00:00"),
    ("2026-10-25T00:15:00+00:00", "22:00", "02:30", "2026-10-25T00:30:00+00:00"),
    ("2026-10-25T01:15:00+00:00", "22:00", "02:30", "2026-10-25T01:30:00+00:00"),
])
def test_quiet_boundaries_and_both_dst_occurrences(stamp, start, end, expected):
    actual = quiet_until(datetime.fromisoformat(stamp), {"timezone":"Europe/Zurich", "quiet_start":start, "quiet_end":end})
    assert actual == (datetime.fromisoformat(expected) if expected else None)


@pytest.mark.parametrize("fields", [
    {"quiet_start":"22:00"}, {"quiet_end":"07:00"},
    {"quiet_start":"22:00","quiet_end":"22:00"},
    {"quiet_start":"25:00","quiet_end":"07:00"},
    {"quiet_start":10,"quiet_end":"07:00"},
])
def test_invalid_quiet_pair(fields):
    with pytest.raises(DomainError) as error:
        validate_schedule(fields)
    assert error.value.code == "digest_quiet_hours_invalid"


def test_quiet_save_preserves_due_and_old_client_fields(harness):
    service = harness[2]
    person = user(harness)
    args = dict(enabled=True, frequency="daily", sources=[], severities=[])
    saved = service.save_digest_preference(person, **args, schedule={"timezone":"UTC","time":"08:00"})["preference"]
    quiet = service.save_digest_preference(person, **args, schedule={"quiet_start":"22:00","quiet_end":"07:00"})["preference"]
    assert quiet["next_delivery_at"] == saved["next_delivery_at"]
    old_client = service.save_digest_preference(person, **args, schedule={"timezone":"UTC","time":"08:00"})["preference"]
    assert old_client["schedule"] == quiet["schedule"]
    cleared = service.save_digest_preference(person, **args, schedule={"quiet_start":None,"quiet_end":None})["preference"]
    assert cleared["schedule"]["quiet_start"] is None
    assert cleared["next_delivery_at"] == saved["next_delivery_at"]


@pytest.mark.parametrize("unsubscribe", [False, True])
def test_deferred_job_resumes_once_or_honors_unsubscribe(harness, monkeypatch, unsubscribe):
    service = harness[2]
    job, person, _ = setup_delivery(harness, count=2)
    sent = record_mail(monkeypatch)
    now = utcnow().replace(hour=23, minute=0, second=0, microsecond=0) + timedelta(days=1)
    clock = [now]
    monkeypatch.setattr(digests, "utcnow", lambda:clock[0])
    monkeypatch.setattr(jobs, "utcnow", lambda:clock[0])
    service.save_digest_preference(person, enabled=True, frequency="daily", sources=[], severities=["high"],
                                  schedule={"timezone":"UTC","quiet_start":"22:00","quiet_end":"07:00"})
    # Leave the original outbox pending, as an inline/duplicate claim can do.
    result = execute(service, job["id"])
    assert result["state"] == "queued" and result["attempts"] == 0
    cp = checkpoint(service, job["id"])
    assert cp["complete"] and cp["processed"] == 2
    wake = now.replace(hour=7) + timedelta(days=1)
    with service.db.session() as session:
        stored = session.get(Job, job["id"])
        assert stored.available_at.replace(tzinfo=UTC) == wake
        assert session.get(DigestDelivery, job["target_id"]).status == "queued"
        pending = list(session.scalars(select(OutboxMessage).where(OutboxMessage.job_id == job["id"], OutboxMessage.state == "pending")))
        assert len(pending) == 1 and pending[0].available_at.replace(tzinfo=UTC) == wake
    assert dispatch(service, limit=10) == []
    assert execute(service, job["id"])["state"] == "queued"
    assert checkpoint(service, job["id"]) == cp and sent == []
    if unsubscribe:
        with service.db.session() as session:
            session.scalar(select(DigestPreference)).enabled = False
            session.commit()
    clock[0] = wake
    assert dispatch(service, limit=10) == [job["id"]]
    assert execute(service, job["id"])["state"] == "succeeded"
    execute(service, job["id"])
    assert len(sent) == (0 if unsubscribe else 1)
    assert harness[3].calls == []


def test_quiet_boundary_is_rechecked_after_render(harness, monkeypatch):
    service = harness[2]
    job, person, _ = setup_delivery(harness, count=2)
    sent = record_mail(monkeypatch)
    clock = [utcnow().replace(hour=21, minute=59, second=59, microsecond=0) + timedelta(days=1)]
    monkeypatch.setattr(digests, "utcnow", lambda:clock[0])
    monkeypatch.setattr(jobs, "utcnow", lambda:clock[0])
    service.save_digest_preference(person, enabled=True, frequency="daily", sources=[], severities=["high"],
                                  schedule={"timezone":"UTC","quiet_start":"22:00","quiet_end":"07:00"})
    render = digests.render_message
    def slow_render(*args):
        value = render(*args)
        clock[0] += timedelta(seconds=1)
        return value
    monkeypatch.setattr(digests, "render_message", slow_render)
    assert execute(service, job["id"])["state"] == "queued"
    assert sent == []
    with pytest.raises(DomainError) as error:
        digests.deliver(service.db, service.settings, job["target_id"])
    assert error.value.code == "digest_quiet_hours"



def test_quiet_api_old_client_preserves_pair_and_invalid_update_is_atomic(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_auth import _csrf, _register, _settings

    from helvetic_lens.main import create_app

    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        _register(client)
        body = {"enabled":True, "frequency":"daily", "schedule":{"timezone":"UTC","time":"08:00","quiet_start":"22:00","quiet_end":"07:00"}}
        assert client.put("/api/digests/preferences", json=body).status_code == 403
        saved = client.put("/api/digests/preferences", json=body, headers=_csrf(client))
        assert saved.status_code == 200, saved.text
        for schedule in ({"quiet_start":"07:00"}, {"quiet_end":None}):
            invalid = client.put("/api/digests/preferences", json={**body,"schedule":schedule}, headers=_csrf(client))
            assert invalid.status_code == 422
        old = client.put("/api/digests/preferences", json={**body,"schedule":{"timezone":"UTC","time":"08:00"}}, headers=_csrf(client))
        assert old.json()["preference"]["schedule"] == saved.json()["preference"]["schedule"]
        assert old.json()["preference"]["next_delivery_at"] == saved.json()["preference"]["next_delivery_at"]
