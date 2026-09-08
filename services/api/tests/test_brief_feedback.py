"""Personal feedback preserves exact AI history, permissions and concurrent intent."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from test_interest_execution import artifacts, execution

from helvetic_lens import brief_feedback
from helvetic_lens.config import DomainError
from helvetic_lens.models import InterestBriefFeedback, InterestEventAssessment, RegulatoryEventState

__all__ = ["artifacts", "execution"]


def prepared(execution):
    saved = asyncio.run(execution[1].run(execution[2]))
    return execution[0], saved, f"/api/interest-briefs/{saved['id']}/feedback"


def request(decision="useful", previous=None, **kwargs):
    return {"decision": decision, "expected_previous_id": previous, "request_id": str(uuid4()), **kwargs}


def test_roundtrip_withdrawal_replay_and_history_preserve_original_analysis(execution, harness):
    service, saved, path = prepared(execution)
    client = harness[0]
    before_calls = len(execution[4]["requests"])
    with service.db.session() as session:
        original = deepcopy(session.get(InterestEventAssessment, saved["id"]).result)
    body = request(note="Useful evidence links, but the explanation is too broad.")
    first = client.post(path, json=body)
    assert first.status_code == 200, first.text
    row = first.json()["feedback"]
    assert client.post(path, json=body).json() == {"feedback": row, "reused": True}
    withdrawn = client.post(path, json=request("withdrawn", row["id"]))
    assert withdrawn.status_code == 200
    page = client.get(path, params={"limit": 1}).json()
    assert page["latest"]["decision"] == "withdrawn" and page["has_more"]
    older = client.get(path, params={"limit": 1, "cursor": page["next_cursor"]}).json()
    assert older["items"] == [row] and not older["has_more"]
    assert older["latest"]["decision"] == "withdrawn"
    with service.db.session() as session:
        assert session.get(InterestEventAssessment, saved["id"]).result == original
        assert session.get(InterestEventAssessment, saved["id"]).status == "succeeded"
        assert session.scalar(select(func.count()).select_from(InterestBriefFeedback)) == 2
    assert len(execution[4]["requests"]) == before_calls


def test_stale_revision_and_reused_request_content_are_rejected(execution, harness):
    _, _, path = prepared(execution)
    body = request()
    assert harness[0].post(path, json=body).status_code == 200
    assert harness[0].post(path, json=request("not_useful")).status_code == 409
    assert harness[0].post(path, json={**body, "note": "Changed after submission"}).status_code == 409
    assert len(harness[0].get(path).json()["items"]) == 1


def test_other_principal_and_foreign_cursor_cannot_read_personal_feedback(execution):
    service, saved, _ = prepared(execution)
    data = brief_feedback.FeedbackInput(**request(note="Private user note"))
    with service.db.session() as session:
        first = brief_feedback.save(session, service.organization_id, "user:first", None, saved["id"], data)
    with service.db.session(include_all_organizations=True) as session:
        page = brief_feedback.read(session, service.organization_id, "user:second", saved["id"])
        assert page["latest"] is None and page["items"] == []
        with pytest.raises(DomainError) as error:
            brief_feedback.read(session, service.organization_id, "user:second", saved["id"], cursor=first["feedback"]["id"])
        assert error.value.code == "invalid_feedback_page"
        with pytest.raises(DomainError) as error:
            brief_feedback.read(session, str(uuid4()), "user:first", saved["id"])
        assert error.value.status == 404


@pytest.mark.parametrize("condition", ["revoked", "failed"])
def test_revoked_or_unsuccessful_assessment_cannot_receive_feedback(execution, harness, condition):
    service, saved, path = prepared(execution)
    with service.db.session() as session:
        if condition == "revoked":
            session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == execution[2]))
        else:
            session.get(InterestEventAssessment, saved["id"]).status = "failed"
        session.commit()
    assert harness[0].get(path).status_code == 404
    assert harness[0].post(path, json=request()).status_code == 404


@pytest.mark.parametrize("extra", [{"actor_user_id": "spoofed"}, {"note": "x" * 1001},
                                   {"decision": "confirmed"}, {"request_id": "invalid"}])
def test_payload_cannot_spoof_actor_or_shared_review(execution, harness, extra):
    _, _, path = prepared(execution)
    assert harness[0].post(path, json={**request(), **extra}).status_code == 422


def test_concurrent_personal_edits_do_not_overwrite_each_other(execution):
    service, saved, _ = prepared(execution)
    barrier = Barrier(4)
    def save(index):
        barrier.wait(timeout=15)
        with service.db.session() as session:
            try:
                return brief_feedback.save(session, service.organization_id, "user:concurrent", None,
                    saved["id"], brief_feedback.FeedbackInput(**request(note=f"Concurrent note {index}")))
            except DomainError as error:
                assert error.code == "feedback_conflict"
                return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(save, range(4)))
    assert sum(result is not None for result in results) == 1
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(InterestBriefFeedback)) == 1


def test_daily_allowance_is_atomic_across_different_assessments(execution):
    service, saved, _ = prepared(execution)
    with service.db.session() as session:
        original = session.get(InterestEventAssessment, saved["id"])
        for _ in range(99):
            session.add(InterestBriefFeedback(organization_id=service.organization_id, assessment_id=original.id,
                principal_key="user:quota", request_key=str(uuid4()), request_fingerprint="synthetic-quota",
                decision="withdrawn", note=""))
        targets = [InterestEventAssessment(organization_id=service.organization_id, event_id=original.event_id,
            input_fingerprint=uuid4().hex, input_manifest=dict(original.input_manifest),
            status="succeeded", result=deepcopy(original.result)) for _ in range(4)]
        session.add_all(targets)
        session.commit()
        identities = [row.id for row in targets]
    barrier = Barrier(4)
    def submit(identity):
        barrier.wait(timeout=15)
        with service.db.session() as session:
            try:
                return brief_feedback.save(session, service.organization_id, "user:quota", None,
                    identity, brief_feedback.FeedbackInput(**request()))
            except DomainError as error:
                assert error.code == "feedback_limit"
                return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, identities))
    assert sum(result is not None for result in results) == 1
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(InterestBriefFeedback)) == 100


def test_concurrent_request_replay_is_one_receipt(execution):
    service, saved, _ = prepared(execution)
    data = brief_feedback.FeedbackInput(**request())
    barrier = Barrier(4)
    def submit(_):
        barrier.wait(timeout=15)
        with service.db.session() as session:
            return brief_feedback.save(session, service.organization_id, "user:retry", None, saved["id"], data)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, range(4)))
    assert len({result["feedback"]["id"] for result in results}) == 1
    assert sum(not result["reused"] for result in results) == 1


def test_feedback_migration_preserves_original_saved_assessment(execution):
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import inspect

    from alembic import command
    service, saved, _ = prepared(execution)
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    with service.db.engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "da0c145b7ed8")
        assert "interest_brief_feedback" not in inspect(connection).get_table_names()
        command.upgrade(cfg, "head")
    with service.db.session() as session:
        assert session.get(InterestEventAssessment, saved["id"]).result == saved["result"]
        assert brief_feedback.read(session, service.organization_id, "user:new", saved["id"])["items"] == []


def test_real_viewer_auth_csrf_and_personal_isolation(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_organization_access import csrf, register, settings
    from test_topic_matching import add_event

    from helvetic_lens.main import create_app
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    service = app.state.service
    with TestClient(app) as owner, TestClient(app) as viewer, TestClient(app) as foreign:
        assert viewer.get(f"/api/interest-briefs/{uuid4()}/feedback").status_code == 401
        org = register(owner, "feedback-owner@example.invalid").json()["organization"]["id"]
        with service.db.organization_context(org), service.db.session() as session:
            event = add_event(service)
            row = InterestEventAssessment(organization_id=org, event_id=event, input_fingerprint="synthetic-auth-only",
                input_manifest={"locale": "en"}, status="succeeded", result={})
            session.add(row)
            session.commit()
            identity = row.id
        path = f"/api/interest-briefs/{identity}/feedback"
        invite = owner.post("/api/organization/invitations", headers=csrf(owner),
            json={"email": "feedback-viewer@example.invalid", "role": "viewer"}).json()
        account = register(viewer, "feedback-viewer@example.invalid", invitation_token=invite["token"]).json()
        assert viewer.post(path, json=request()).status_code == 403
        posted = viewer.post(path, json=request(note="Private usefulness note"), headers=csrf(viewer))
        assert posted.status_code == 200, posted.text
        assert owner.get(path).json()["items"] == []
        assert viewer.get(path).json()["latest"]["note"] == "Private usefulness note"
        assert viewer.post(path, json=request(actor_user_id=account["user"]["id"]), headers=csrf(viewer)).status_code == 422
        register(foreign, "feedback-foreign@example.invalid")
        assert foreign.get(path).status_code == 404
        assert foreign.post(path, json=request(), headers=csrf(foreign)).status_code == 404
        with service.db.session(include_all_organizations=True) as session:
            saved = session.scalar(select(InterestBriefFeedback))
            assert saved.actor_user_id == account["user"]["id"] and saved.principal_key == "user:" + saved.actor_user_id
