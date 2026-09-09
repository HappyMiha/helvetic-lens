"""Measured diagnostics remain bounded, scoped and honest about missing usage."""
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from test_auth import _register, _settings
from test_brief_feedback import prepared
from test_interest_execution import artifacts, execution

from helvetic_lens import brief_diagnostics
from helvetic_lens.db import utcnow
from helvetic_lens.main import create_app
from helvetic_lens.models import InterestEventAssessment, Organization, OrganizationMembership

__all__ = ["artifacts", "execution"]
PATH = "/api/integration-logs/briefs"


def test_saved_measurements_exclude_prompts_results_and_reserved_output(execution, harness):
    service, saved, _ = prepared(execution)
    before = len(execution[4]["requests"])
    with service.db.session() as session:
        record = session.get(InterestEventAssessment, saved["id"])
        original = deepcopy(record.provenance)
        record.provenance = {**original, "secret": "do-not-publish-test-secret", "usage": {"completion_tokens": 777}}
        session.commit()
    response = harness[0].get(PATH)
    assert response.status_code == 200, response.text
    data = response.json()
    row = data["items"][0]
    assert row["id"] == saved["id"] and row["measurement"]["state"] == "recorded"
    assert row["measurement"]["input_tokens"] == sum(m["input_tokens"] for m in original["execution"]["generation_measurements"])
    assert row["measurement"]["provider_calls"] == original["provider_calls"]
    assert row["measurement"]["output_tokens"] is None
    assert row["measurement"]["duration_ms"] == original["execution"]["duration_ms"]
    assert "do-not-publish" not in response.text and "what_happened" not in response.text
    assert "history_context" not in row and "input_manifest" not in row
    assert data["ai_calls"] == 0 and len(execution[4]["requests"]) == before


@pytest.mark.parametrize("damage", ["missing", "failed", "boolean", "negative", "wrong_launch", "calls", "partial"])
def test_invalid_missing_and_partial_measurements_are_not_invented(execution, damage):
    service, saved, _ = prepared(execution)
    provenance = deepcopy(saved["provenance"])
    status = "succeeded"
    if damage == "missing":
        provenance = {}
    elif damage == "failed":
        status = "failed"
    elif damage == "boolean":
        provenance["execution"]["duration_ms"] = True
    elif damage == "negative":
        provenance["execution"]["generation_measurements"][0]["input_tokens"] = -1
    elif damage == "wrong_launch":
        provenance["execution"]["generation_measurements"][0]["deployment_id"] = "b"*32
    elif damage == "calls":
        provenance["provider_calls"] = True
    else:
        provenance["provider_calls"] = 2
    data = brief_diagnostics.measurement(provenance, status)
    if damage == "partial":
        assert data["state"] == "recorded" and data["measured_calls"] == 1
        assert data["complete_input_coverage"] is False
    else:
        assert data["state"] == ("missing" if damage in {"missing", "failed"} else "invalid")
        assert data["input_tokens"] is data["provider_calls"] is data["duration_ms"] is None


def test_cursor_window_scope_and_scalar_query(execution, harness):
    service, saved, _ = prepared(execution)
    with service.db.session() as session:
        source = session.get(InterestEventAssessment, saved["id"])
        foreign = Organization(name="Foreign diagnostics", slug="foreign-diagnostics")
        session.add(foreign)
        session.flush()
        for i in range(26):
            session.add(InterestEventAssessment(organization_id=foreign.id if i==0 else service.organization_id,
                event_id=source.event_id,input_fingerprint=uuid4().hex,input_manifest=source.input_manifest,
                status="failed",created_at=utcnow()-timedelta(days=100 if i==1 else 0, seconds=i+1)))
        session.commit()
    statements=[]
    def capture(_conn,_cursor,sql,_params,_context,_many):
        statements.append(sql)
    event.listen(service.db.engine,"before_cursor_execute",capture)
    try:
        first=harness[0].get(PATH,params={"status":"failed","limit":10}).json()
        second=harness[0].get(PATH,params={"status":"failed","limit":10,"cursor":first["next_cursor"]}).json()
        third=harness[0].get(PATH,params={"status":"failed","limit":10,"cursor":second["next_cursor"]}).json()
    finally:
        event.remove(service.db.engine,"before_cursor_execute",capture)
    ids=[row["id"] for page in [first,second,third] for row in page["items"]]
    assert len(ids)==len(set(ids))==24
    assert all("interest_event_assessments.result" not in sql and "history_context" not in sql for sql in statements)
    assert harness[0].get(PATH,params={"status":"succeeded","cursor":first["next_cursor"]}).status_code==422
    assert harness[0].get(PATH,params={"days":365}).status_code==422
    assert harness[0].get(PATH,params={"limit":51}).status_code==422


def test_real_viewer_and_unauthenticated_diagnostics_are_denied(tmp_path):
    app=create_app(_settings(tmp_path),fetcher=FakeFetcher(),model_client=ScriptedModel())
    with TestClient(app) as client:
        assert client.get(PATH).status_code==401
        attempts_path = f"{PATH}/{uuid4()}/attempts"
        reuse_path = f"{PATH}/{uuid4()}/reuse"
        assert client.get(attempts_path).status_code == 401
        assert client.get(reuse_path).status_code == 401
        registered=_register(client).json()
        assert client.get(PATH).status_code==200
        assert client.get(attempts_path).status_code == 404
        assert client.get(reuse_path).status_code == 404
        with app.state.service.db.session(include_all_organizations=True) as session:
            membership=session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id==registered["user"]["id"]))
            membership.role="viewer"
            session.commit()
        assert client.get(PATH).status_code==403
        assert client.get(attempts_path).status_code == 403
        assert client.get(reuse_path).status_code == 403
