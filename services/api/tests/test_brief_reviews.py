"""Shared relevance reviews preserve exact saved evidence and private feedback."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_brief_feedback import prepared
from test_interest_execution import artifacts, execution

from helvetic_lens import brief_reviews
from helvetic_lens.config import DomainError
from helvetic_lens.models import InterestBriefReview, InterestEventAssessment

__all__ = ["artifacts", "execution"]


def request(page, decision="confirmed", **values):
    return {"request_id": str(uuid4()), "expected_previous_id": page["latest"]["id"] if page["latest"] else None,
            "target_fingerprint": page["target_fingerprint"], "decision": decision,
            "note": "Reviewed relevance against the saved evidence.", **values}


def test_review_roundtrip_replay_withdrawal_and_original_preservation(execution, harness):
    service, saved, _ = prepared(execution)
    client, path = harness[0], f"/api/interest-briefs/{saved['id']}/reviews"
    before_calls = len(execution[4]["requests"])
    page = client.get(path).json()
    data = request(page)
    first = client.post(path, json=data)
    assert first.status_code == 200, first.text
    assert client.post(path, json=data).json() == {"review": first.json()["review"], "reused": True}
    for decision in ("rejected", "withdrawn"):
        data = request(client.get(path).json(), decision)
        assert client.post(path, json=data).status_code == 200
    page = client.get(path, params={"limit": 2}).json()
    assert page["latest"]["decision"] == "withdrawn" and page["matches_saved_assessment"]
    assert [row["decision"] for row in page["items"]] == ["withdrawn", "rejected"]
    older = client.get(path, params={"limit": 2, "cursor": page["next_cursor"]}).json()
    assert older["items"] == [first.json()["review"]] and not older["has_more"]
    assert older["latest"]["decision"] == "withdrawn"
    with service.db.session() as session:
        assert session.get(InterestEventAssessment, saved["id"]).result == saved["result"]
    assert len(execution[4]["requests"]) == before_calls


def test_changed_saved_prose_invalidates_review_and_stale_submission(execution, harness):
    service, saved, _ = prepared(execution)
    client, path = harness[0], f"/api/interest-briefs/{saved['id']}/reviews"
    old = request(client.get(path).json())
    assert client.post(path, json=old).status_code == 200
    stale = request(client.get(path).json(), "rejected")
    with service.db.session() as session:
        row = session.get(InterestEventAssessment, saved["id"])
        revised = deepcopy(row.result)
        revised["what_happened"]["text"] = "Different imported saved wording."
        row.result = revised
        session.commit()
    assert client.post(path, json=stale).status_code == 409
    page = client.get(path).json()
    assert not page["matches_saved_assessment"] and len(page["items"]) == 1
    with service.db.session() as session:
        assert brief_reviews.current(session, service.organization_id, session.get(InterestEventAssessment, saved["id"])) is None
    assert client.post(path, json=old).json()["reused"]  # a receipt, not a new decision
    assert client.post(path, json=request(page)).status_code == 200


@pytest.mark.parametrize("extra", [{"actor_user_id": "spoofed"}, {"note": " "}, {"note": "x" * 2001},
                                   {"decision": "useful"}, {"target_fingerprint": "invalid"}])
def test_review_input_rejects_spoofing_or_personal_vote(execution, harness, extra):
    _, saved, _ = prepared(execution)
    client, path = harness[0], f"/api/interest-briefs/{saved['id']}/reviews"
    assert client.post(path, json=request(client.get(path).json(), **extra)).status_code == 422


def test_foreign_organization_and_cursor_are_not_authorization(execution):
    service, saved, _ = prepared(execution)
    with service.db.session(include_all_organizations=True) as session:
        with pytest.raises(DomainError) as error:
            brief_reviews.read(session, str(uuid4()), saved["id"])
        assert error.value.status == 404
        with pytest.raises(DomainError) as error:
            brief_reviews.read(session, service.organization_id, saved["id"], cursor=str(uuid4()))
        assert error.value.code == "invalid_brief_review_page"


def test_concurrent_admin_decisions_preserve_the_first_accepted_intent(execution):
    service, saved, _ = prepared(execution)
    with service.db.session() as session:
        page = brief_reviews.read(session, service.organization_id, saved["id"])
    barrier = Barrier(4)
    def submit(index):
        barrier.wait(timeout=15)
        with service.db.session() as session:
            try:
                return brief_reviews.save(session, service.organization_id, saved["id"], None,
                    brief_reviews.ReviewInput(**request(page, "confirmed" if index % 2 else "rejected")))
            except DomainError as error:
                assert error.code == "brief_review_conflict"
                return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, range(4)))
    assert sum(row is not None for row in results) == 1
    with service.db.session() as session:
        assert len(list(session.scalars(select(InterestBriefReview)))) == 1


def test_real_auth_viewer_reads_shared_review_but_cannot_write(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_organization_access import csrf, register, settings
    from test_topic_matching import add_event

    from helvetic_lens.main import create_app
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    service = app.state.service
    with TestClient(app) as admin, TestClient(app) as viewer, TestClient(app) as foreign:
        account = register(admin, "brief-review-admin@example.invalid").json()
        with service.db.organization_context(account["organization"]["id"]), service.db.session() as session:
            event = add_event(service)
            row = InterestEventAssessment(organization_id=service.organization_id, event_id=event,
                input_fingerprint="synthetic-auth-only", input_manifest={"locale": "fr"}, status="succeeded", result={})
            session.add(row)
            session.commit()
            identity = row.id
        path = f"/api/interest-briefs/{identity}/reviews"
        assert viewer.get(path).status_code == 401
        invite = admin.post("/api/organization/invitations", headers=csrf(admin),
            json={"email": "brief-review-viewer@example.invalid", "role": "viewer"}).json()
        register(viewer, "brief-review-viewer@example.invalid", invitation_token=invite["token"])
        data = request(admin.get(path).json())
        assert viewer.post(path, json=data, headers=csrf(viewer)).status_code == 403
        assert admin.post(path, json=data).status_code == 403
        created = admin.post(path, json=data, headers=csrf(admin))
        assert created.status_code == 200, created.text
        assert viewer.get(path).json()["latest"]["actor_user_id"] == account["user"]["id"]
        register(foreign, "brief-review-foreign@example.invalid")
        assert foreign.get(path).status_code == 404
        assert foreign.post(path, json=data, headers=csrf(foreign)).status_code == 404


@pytest.mark.parametrize("locale", ["de", "fr", "it", "rm", "en"])
def test_rejection_withholds_recommendation_in_reader_digest_and_notifications(execution, locale):
    import asyncio

    from test_digest_briefs import preview, ready
    from test_notification_briefs import notifications

    from helvetic_lens.digest_briefs import REJECTED_COPY, render
    service, user, saved = ready(execution, locale=f"{locale}-CH")
    with service.db.session() as session:
        page = brief_reviews.read(session, service.organization_id, saved["id"])
        brief_reviews.save(session, service.organization_id, saved["id"], None,
            brief_reviews.ReviewInput(**request(page, "rejected")))
    digest = asyncio.run(preview(service, user))["events"][0]["brief"]
    notification = asyncio.run(notifications(service, user, locale=locale))["items"][0]
    assert digest["status"] == notification["brief"]["status"] == "rejected"
    assert notification["source_url"] and notification["event_id"] == execution[2]
    for brief in (digest, notification["brief"]):
        assert "importance" not in brief and "what_happened" not in brief
        lines, html = render(brief, locale, lambda url: url)
        assert REJECTED_COPY[locale] in lines and saved["result"]["what_happened"]["text"] not in html
    with service.db.session() as session:
        assert session.get(InterestEventAssessment, saved["id"]).result == saved["result"]
        page = brief_reviews.read(session, service.organization_id, saved["id"])
        brief_reviews.save(session, service.organization_id, saved["id"], None,
            brief_reviews.ReviewInput(**request(page, "withdrawn")))
    restored = asyncio.run(preview(service, user))["events"][0]["brief"]
    assert restored["status"] == "available" and restored["assessment_id"] == saved["id"]
    assert len(execution[4]["generated"]) == 1


def test_review_migration_preserves_assessment_and_personal_feedback(execution):
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import inspect

    from alembic import command
    from helvetic_lens import brief_feedback
    from helvetic_lens.models import InterestBriefFeedback
    service, saved, _ = prepared(execution)
    with service.db.session() as session:
        personal = brief_feedback.save(session, service.organization_id, "user:qa", None, saved["id"],
            brief_feedback.FeedbackInput(request_id=uuid4(), decision="useful"))["feedback"]
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    with service.db.engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "db1d256c8fe9")
        assert "interest_brief_reviews" not in inspect(connection).get_table_names()
        command.upgrade(cfg, "head")
    with service.db.session() as session:
        assert session.get(InterestEventAssessment, saved["id"]).result == saved["result"]
        assert session.get(InterestBriefFeedback, personal["id"]).decision == "useful"
