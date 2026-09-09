"""Real saved-reader projections, privacy, concurrent increments and migration."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import event, select
from test_digest_briefs import artifacts, execution, preview, ready
from test_interest_brief_reader import read as current_read
from test_notification_briefs import (
    notifications,
)
from test_notification_briefs import (
    test_unavailable_brief_does_not_hide_source_or_leak_saved_prose as unavailable_scenario,
)

from alembic import command
from helvetic_lens import brief_reuse
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.models import BriefReuseObservation, InterestEventAssessment

__all__ = ["artifacts", "execution"]


def observed(service, identity, days=7):
    with service.db.session() as session:
        return brief_reuse.read(session, service.organization_id, identity, days=days)


def test_actual_readers_reuse_without_regeneration_or_personal_tracking(execution, harness):
    service, user, saved = ready(execution)
    before = len(execution[4]["generated"])
    assert observed(service, saved["id"])["items"] == []
    for _ in range(2):
        assert current_read(execution)["status"] == "available"
        assert asyncio.run(notifications(service, user))["items"][0]["brief"]["status"] == "available"
    assert asyncio.run(preview(service, user))["events"][0]["brief"]["status"] == "available"
    result = observed(service, saved["id"])
    assert {row["surface"]:row["projections"] for row in result["items"]} == {
        "reader":2, "notifications":2, "digest_preview":1}
    assert result["complete_accounting"] is False
    assert len(execution[4]["generated"]) == before
    response = harness[0].get(f"/api/integration-logs/briefs/{saved['id']}/reuse")
    assert response.status_code == 200 and response.json() == result
    assert observed(service, saved["id"]) == result  # inspection is not counted
    with service.db.session() as session:
        assert len(list(session.scalars(select(BriefReuseObservation)))) == 3
        assert session.get(InterestEventAssessment, saved["id"]).result == saved["result"]
    columns = set(BriefReuseObservation.__table__.columns.keys())
    assert columns == {"organization_id","assessment_id","day","surface","projections","first_at","last_at"}


@pytest.mark.parametrize("condition", ["language","profile","offline","failed","pending","invalid","revoked"])
def test_unavailable_projections_are_not_counted(execution, condition):
    unavailable_scenario(execution, condition)
    with execution[0].db.session() as session:
        assert list(session.scalars(select(BriefReuseObservation))) == []


def test_concurrent_observations_are_atomic_and_days_are_bounded(execution):
    service, _, saved = ready(execution)
    payload = {"assessment_id":saved["id"],"status":"available"}
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda _: brief_reuse.observe(service.db, service.organization_id, [payload, payload], "reader"), range(12)))
    result = observed(service, saved["id"])
    assert result["items"][0]["projections"] == 12  # duplicate card within one response counts once
    with service.db.session() as session:
        row = session.scalar(select(BriefReuseObservation))
        row.day = (utcnow().date()-timedelta(days=7)).isoformat()
        session.commit()
    assert observed(service, saved["id"], 7)["items"] == []
    assert observed(service, saved["id"], 30)["items"][0]["projections"] == 12
    with service.db.session() as session:
        with pytest.raises(DomainError):
            brief_reuse.read(session, str(uuid4()), saved["id"])
        with pytest.raises(DomainError):
            brief_reuse.read(session, service.organization_id, saved["id"], days=365)
    brief_reuse.observe(service.db, str(uuid4()), [payload], "reader")
    assert observed(service, saved["id"], 30)["items"][0]["projections"] == 12


def test_telemetry_failure_does_not_break_current_reader(execution):
    service, _, saved = ready(execution)
    def fail_insert(_conn,_cursor,sql,_params,_context,_many):
        if "INSERT INTO brief_reuse_observations" in sql:
            raise RuntimeError("synthetic private error must not escape")
    event.listen(service.db.engine,"before_cursor_execute",fail_insert)
    try:
        response = current_read(execution)
    finally:
        event.remove(service.db.engine,"before_cursor_execute",fail_insert)
    assert response["status"] == "available" and response["result"] == saved["result"]
    assert observed(service, saved["id"])["items"] == []


def test_reuse_migration_does_not_invent_old_usage_or_change_answers(execution):
    service, _, saved = ready(execution)
    current_read(execution)
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root/"alembic.ini"))
    cfg.set_main_option("script_location", str(root/"alembic"))
    with service.db.engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.downgrade(cfg,"de40589fb21c")
        command.upgrade(cfg,"head")
    assert observed(service, saved["id"])["items"] == []
    with service.db.session() as session:
        assert session.get(InterestEventAssessment,saved["id"]).result == saved["result"]
