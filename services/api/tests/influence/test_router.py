"""Real router + migrated SQLite. Main-app session/CSRF checks live in test_influence_graph.py."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from helvetic_lens.auth import Identity
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.db import Database
from helvetic_lens.influence_api import influence_router
from helvetic_lens.influence_models import InfluenceDossier, InfluenceReview, InfluenceRevision
from helvetic_lens.models import Organization, OrganizationMembership, User

from .test_contract import document, save_body


@pytest.fixture
def harness(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url="sqlite:///" + (tmp_path / "influence.db").as_posix(),
        data_dir=tmp_path / "data",
    )
    db = Database(settings)
    db.migrate()
    actors = {}
    with db.session(include_all_organizations=True) as session:
        for name in ("owner", "other", "viewer"):
            org = actors["owner"].organization_id if name == "viewer" else str(uuid4())
            if name != "viewer":
                session.add(Organization(id=org, name=name, slug=name))
                session.flush()
            user = str(uuid4())
            role = "viewer" if name == "viewer" else "organization_admin"
            session.add(User(id=user, email=name + "@example.org", password_hash="test-only", name=name))
            session.flush()
            session.add(OrganizationMembership(organization_id=org, user_id=user, role=role))
            actors[name] = Identity(
                user_id=user,
                organization_id=org,
                role=role,
                session_id="synthetic",
                csrf_hash="",
                email=name + "@example.org",
                name=name,
                organization_name=name,
            )
        session.commit()
    app = FastAPI()

    @app.exception_handler(DomainError)
    async def failure(_, error):
        return JSONResponse(status_code=error.status, content={"code": error.code, "detail": error.message})

    # The fixture supplies a trusted identity; it deliberately does not claim
    # to test production cookie authentication or CSRF middleware.
    @app.middleware("http")
    async def actor_context(request, next_call):
        actor = actors.get(request.headers.get("x-test-actor", "owner"))
        request.state.identity = actor
        with db.organization_context(actor.organization_id if actor else db.organization_id):
            return await next_call(request)

    app.include_router(influence_router(SimpleNamespace(db=db)))
    with TestClient(app) as client:
        yield client, db, actors
    db.engine.dispose()


def test_create_edit_review_history_replay_and_archive(harness):
    client, db, _ = harness
    body = save_body()
    response = client.post("/api/influence/dossiers", json=body)
    assert response.status_code == 201, response.text
    original = response.json()
    root = "/api/influence/dossiers/" + original["id"]
    assert client.post("/api/influence/dossiers", json=body).json()["id"] == original["id"]
    conflicting = save_body()
    conflicting["requestId"] = body["requestId"]
    conflicting["document"]["title"] = "Different request with a reused key"
    assert client.post("/api/influence/dossiers", json=conflicting).status_code == 409
    review = {
        "expectedRevision": 1,
        "decision": "reviewed",
        "note": "Checked retained evidence.",
        "requestId": str(uuid4()),
    }
    assert client.post(root + "/reviews", json=review).status_code == 201
    assert len(client.post(root + "/reviews", json=review).json()["reviews"]) == 1
    assert client.post(root + "/reviews", json={**review, "decision": "needs_revision"}).status_code == 409
    changed = document()
    changed["title"] = "Corrected evidence dossier"
    update = save_body(changed, 1)
    result = client.patch(root, json=update)
    assert result.status_code == 200, result.text
    assert result.json()["revision"] == 2 and not result.json()["reviews"]
    assert client.patch(root, json=update).json()["revision"] == 2
    assert client.patch(root, json=save_body(document(), 1)).status_code == 409
    assert client.post(root + "/reviews", json={**review, "requestId": str(uuid4())}).status_code == 409
    previous = client.get(root + "?revision=1").json()
    assert previous["document"] == original["document"] and len(previous["reviews"]) == 1
    assert client.get(root + "/history?limit=1").json()["nextCursor"] == 2
    assert client.get(root + "/history?before_revision=2").json()["items"][0]["revision"] == 1
    archive = {
        "expectedRevision": 2,
        "archived": True,
        "note": "Close research case.",
        "requestId": str(uuid4()),
    }
    assert client.post(root + "/archive", json=archive).json()["archived"]
    assert client.post(root + "/archive", json=archive).json()["revision"] == 3
    assert not client.get("/api/influence/dossiers").json()["items"]
    assert client.get("/api/influence/dossiers?archived=true").json()["items"][0]["id"] == original["id"]
    assert client.patch(root, json=save_body(changed, 3)).status_code == 409
    restore = {**archive, "expectedRevision": 3, "archived": False, "requestId": str(uuid4())}
    assert client.post(root + "/archive", json=restore).json()["revision"] == 4
    with db.session(include_all_organizations=True) as session:
        assert session.execute(text("PRAGMA foreign_key_check")).all() == []
        assert (
            len(
                list(
                    session.scalars(
                        select(InfluenceRevision).where(InfluenceRevision.dossier_id == original["id"])
                    )
                )
            )
            == 4
        )


def test_cross_workspace_and_stale_member_never_access_or_mutate(harness):
    client, db, actors = harness
    created = client.post("/api/influence/dossiers", json=save_body()).json()
    root = "/api/influence/dossiers/" + created["id"]
    assert client.get("/api/influence/dossiers", headers={"x-test-actor": "none"}).status_code == 401
    for suffix in ("", "?revision=1", "/history"):
        assert client.get(root + suffix, headers={"x-test-actor": "other"}).status_code == 404
    assert client.get("/api/influence/dossiers", headers={"x-test-actor": "other"}).json()["items"] == []
    assert (
        client.patch(root, json=save_body(revision=1), headers={"x-test-actor": "other"}).status_code == 404
    )
    assert client.get(root, headers={"x-test-actor": "viewer"}).status_code == 200
    assert (
        client.patch(root, json=save_body(revision=1), headers={"x-test-actor": "viewer"}).status_code == 403
    )
    for actor, expected in (("viewer", 403), ("other", 404)):
        for suffix, fields in (("reviews", {"decision": "reviewed"}), ("archive", {"archived": True})):
            body = {
                "expectedRevision": 1,
                "note": "Unauthorized change.",
                "requestId": str(uuid4()),
                **fields,
            }
            assert (
                client.post(root + "/" + suffix, json=body, headers={"x-test-actor": actor}).status_code
                == expected
            )
    assert (
        client.post(
            "/api/influence/dossiers", json=save_body(), headers={"x-test-actor": "viewer"}
        ).status_code
        == 403
    )
    with db.session(include_all_organizations=True) as session:
        session.execute(
            delete(OrganizationMembership).where(OrganizationMembership.user_id == actors["owner"].user_id)
        )
        session.commit()
    assert client.get(root).status_code == 403
    assert client.patch(root, json=save_body(revision=1)).status_code == 403
    with db.session(include_all_organizations=True) as session:
        assert session.get(InfluenceDossier, created["id"]).revision == 1


def test_account_erasure_detaches_actor_and_workspace_deletion_cascades(harness):
    client, db, actors = harness
    created = client.post("/api/influence/dossiers", json=save_body()).json()
    assert (
        client.post(
            "/api/influence/dossiers/" + created["id"] + "/reviews",
            json={
                "expectedRevision": 1,
                "decision": "reviewed",
                "note": "Retained editorial decision.",
                "requestId": str(uuid4()),
            },
        ).status_code
        == 201
    )
    with db.session(include_all_organizations=True) as session:
        session.execute(
            delete(OrganizationMembership).where(OrganizationMembership.user_id == actors["owner"].user_id)
        )
        session.execute(delete(User).where(User.id == actors["owner"].user_id))
        session.commit()
        revision = session.get(InfluenceRevision, (created["id"], 1))
        assert revision.actor_user_id is None and revision.document["title"] == created["title"]
        review = session.scalar(select(InfluenceReview).where(InfluenceReview.dossier_id == created["id"]))
        assert review.actor_user_id is None and review.note == "Retained editorial decision."
        session.execute(
            delete(OrganizationMembership).where(
                OrganizationMembership.organization_id == actors["owner"].organization_id
            )
        )
        session.execute(delete(Organization).where(Organization.id == actors["owner"].organization_id))
        session.commit()
        assert (
            session.scalar(select(InfluenceRevision).where(InfluenceRevision.dossier_id == created["id"]))
            is None
        )
        assert (
            session.scalar(select(InfluenceReview).where(InfluenceReview.dossier_id == created["id"])) is None
        )
        assert session.execute(text("PRAGMA foreign_key_check")).all() == []


def test_document_brief_visibility_links_history_and_archive(harness):
    from helvetic_lens.models import DocumentWatch, Law
    client, db, actors = harness
    law_id = str(uuid4())
    with db.organization_context(actors['owner'].organization_id), db.session() as session:
        session.add(Law(id=law_id, owner_organization_id=actors['owner'].organization_id,
                        canonical_identity='brief-law', name='Test law', url='https://example.org/law'))
        session.flush()
        session.add(DocumentWatch(law_id=law_id, display_name='Test law'))
        session.commit()
    body = save_body()
    body['document']['lawId'] = law_id
    body['document']['reviewNotes'] = [{
        'id': 'review', 'kind': 'task', 'title': 'Check the contract',
        'author': 'Fictional colleague', 'role': 'Counsel', 'fictional': True,
        'body': 'Inspect the actual signed plan before classifying the bonus.',
        'sourceIds': ['annual-report'], 'status': 'open', 'dueOn': '2026-10-01',
    }]
    missing = save_body({**body['document'], 'lawId': str(uuid4())})
    assert client.post('/api/influence/dossiers', json=missing).status_code == 404
    assert client.post('/api/influence/dossiers', json=body, headers={'x-test-actor': 'other'}).status_code == 404
    result = client.post('/api/influence/dossiers', json=body)
    assert result.status_code == 201, result.text
    row = result.json()
    path = '/api/influence/dossiers/by-law/' + law_id
    page = client.get(path, headers={'x-test-actor': 'viewer'})
    assert page.status_code == 200
    assert page.json()['items'][0]['document']['reviewNotes'][0]['fictional'] is True
    assert 'snapshotText' not in page.json()['items'][0]['document']['sources'][0]
    assert client.get(path, headers={'x-test-actor': 'other'}).status_code == 404
    assert client.post('/api/influence/dossiers', json=body, headers={'x-test-actor': 'viewer'}).status_code == 403
    updated = save_body(body['document'], 1)
    updated['document']['reviewNotes'][0]['status'] = 'in_progress'
    assert client.patch('/api/influence/dossiers/' + row['id'], json=updated).status_code == 200
    old = client.get('/api/influence/dossiers/' + row['id'] + '?revision=1').json()
    assert old['document']['reviewNotes'][0]['status'] == 'open'
    assert old['revisionCreatedAt'] == row['revisionCreatedAt']
    assert client.post('/api/influence/dossiers/' + row['id'] + '/archive', json={
        'expectedRevision': 2, 'requestId': str(uuid4()), 'archived': True, 'note': 'Archive review',
    }).status_code == 200
    assert client.get(path).json()['items'] == []
    with db.session(include_all_organizations=True) as session:
        member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == actors['viewer'].user_id))
        session.delete(member)
        session.commit()
    assert client.get(path, headers={'x-test-actor': 'viewer'}).status_code == 403
