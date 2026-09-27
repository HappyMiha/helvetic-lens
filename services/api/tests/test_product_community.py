from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_auth import _register
from test_product_dossiers import ROOT, create, post
from test_product_dossiers import signed as signed
from test_product_publications import PUBLIC, draft, preview_and_publish

from helvetic_lens.models import OrganizationMembership, User, UserSession
from helvetic_lens.product_models import ProductDossier, PublicContribution, PublicContributionMutation


def command(**changes):
    return {"request_key": str(uuid4()), "publication_revision": 1, "confirm_public": True,
        "content": {"author_label": "Public contributor", "body": "A deliberate public contribution with evidence.",
            "sources": [{"title": "Source", "url": "https://www.fedlex.admin.ch/"}]}, **changes}


def setup(client):
    doc, _ = create(client)
    publication, _ = preview_and_publish(client, doc["id"])
    return doc, publication, PUBLIC + "/" + publication["id"] + "/discussion"


def save(client, path, body=None):
    response = post(client, path, body or command())
    assert response.status_code == 201, response.text
    return response.json()["contribution"]


def action(client, path, row, kind, **changes):
    return post(client, path + "/" + row["id"] + "/action", {"request_key": str(uuid4()),
        "expected_revision": row["revision"], "action": kind, "reason": "Reviewed source relevance", **changes})


def test_cross_organization_public_read_and_personal_viewer_contribution(signed):
    client, service, owner, _ = signed
    doc, publication, path = setup(client)
    person = _register(client, "participant@example.ch", "Other workspace").json()
    with service.db.session(include_all_organizations=True) as session:
        membership = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == person["user"]["id"]))
        membership.role = "viewer"
        session.commit()
    body = command()
    assert client.post(path, json=body).status_code == 403
    item = save(client, path, body)
    assert save(client, path, body)["id"] == item["id"]
    assert post(client, ROOT, {"invalid": "private writes still denied"}).status_code == 403
    assert client.get(ROOT + "/" + doc["id"]).status_code == 404
    mine = client.get(path + "/workspace").json()
    assert mine["can_post"] and not mine["can_moderate"] and mine["items"][0]["can_edit"]
    client.cookies.clear()
    response = client.get(path)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    public = response.json()
    assert public["total"] == 1 and not public["can_post"]
    assert set(public["items"][0]) == {"id", "revision", "publication_revision", "author_label", "body", "sources", "created_at", "updated_at"}
    for private in (doc["id"], owner["organization"]["id"], person["user"]["id"], person["user"]["email"], "history", "moderation_reason"):
        assert private not in response.text
    assert client.get(path + "/workspace").status_code == 401
    assert client.post(path, json=command()).status_code == 401
    assert client.get(path.replace("pharma", "loyer")).status_code == 404
    assert client.get(path + "/" + item["id"]).status_code == 401


def test_moderation_is_separate_from_authorship_and_hidden_content_is_private(signed):
    client, _, _, _ = signed
    _, _, path = setup(client)
    owner_cookies = dict(client.cookies)
    _register(client, "author@example.ch")
    author_cookies = dict(client.cookies)
    item = save(client, path)
    edited = command(expected_revision=1)
    edited["content"]["body"] = "A revised public contribution reviewed by its author."
    assert action(client, path, item, "hide").status_code == 403
    client.cookies.clear()
    client.cookies.update(owner_cookies)
    assert post(client, path + "/" + item["id"], edited).status_code == 403
    assert action(client, path, item, "remove").status_code == 403
    assert action(client, path, item, "hide", reason=" ").status_code == 422
    result = action(client, path, item, "hide")
    assert result.status_code == 200, result.text
    hidden = result.json()["contribution"]
    assert hidden["status"] == "hidden" and hidden["revision"] == 2
    assert client.get(path).json()["total"] == 0
    assert client.get(path + "/workspace").json()["items"][0]["body"] == item["body"]
    client.cookies.clear()
    client.cookies.update(author_cookies)
    assert post(client, path + "/" + item["id"], edited).status_code == 409
    edited.update(expected_revision=2, request_key=str(uuid4()))
    result = post(client, path + "/" + item["id"], edited)
    assert result.status_code == 200, result.text
    hidden = result.json()["contribution"]
    assert hidden["status"] == "hidden" and hidden["revision"] == 3
    assert client.get(path).json()["items"] == []
    _register(client, "uninvolved@example.ch")
    assert client.get(path + "/workspace").json()["total"] == 0
    client.cookies.clear()
    client.cookies.update(owner_cookies)
    assert action(client, path, {**hidden, "revision": 2}, "restore").status_code == 409
    visible = action(client, path, hidden, "restore").json()["contribution"]
    assert visible["status"] == "visible" and client.get(path).json()["total"] == 1
    assert [event["action"] for event in visible["history"]] == ["restore", "edit", "hide", "create"]


def test_durable_retries_cannot_restore_removed_content_or_cross_records(signed):
    client, service, _, _ = signed
    _, _, path = setup(client)
    body = command()
    item = save(client, path, body)
    edited = command(expected_revision=1)
    edited["content"]["body"] += " Additional evidence."
    current = post(client, path + "/" + item["id"], edited).json()["contribution"]
    removal = {"expected_revision": 2, "request_key": str(uuid4()), "action": "remove"}
    removed = post(client, path + "/" + item["id"] + "/action", removal)
    assert removed.status_code == 200
    for response in (post(client, path, body), post(client, path + "/" + item["id"], edited),
                     post(client, path + "/" + item["id"] + "/action", removal)):
        assert response.status_code in (200, 201)
        retained = response.json()["contribution"]
        assert retained["status"] == "removed" and retained["body"] == "" and retained["sources"] == []
    assert action(client, path, {**current, "revision": 3}, "restore").status_code == 409
    assert post(client, path, {**body, "confirm_public": False}).status_code == 409
    other = save(client, path)
    assert post(client, path + "/" + other["id"], edited).status_code == 409
    with service.db.session() as session:
        events = list(session.scalars(select(PublicContributionMutation).where(PublicContributionMutation.contribution_id == item["id"])))
        assert len(events) == 3
        assert all("body" not in event.__table__.columns for event in events)
    assert client.get(path).json()["total"] == 1


def test_publication_revision_consent_input_bounds_and_withdrawal(signed):
    client, _, _, _ = signed
    doc, publication, path = setup(client)
    assert post(client, path, command(confirm_public=False)).status_code == 409
    assert post(client, path, command(publication_revision=2)).status_code == 409
    item = save(client, path)
    publication, _ = preview_and_publish(client, doc["id"], draft(1))
    assert post(client, path, command()).status_code == 409
    assert post(client, path + "/" + item["id"], command(expected_revision=1)).status_code == 409
    assert client.get(path).json()["publication_revision"] == 2
    assert post(client, path.replace("pharma", "loyer"), command(publication_revision=2)).status_code == 404
    _, _, other = setup(client)
    assert post(client, other + "/" + item["id"], command(expected_revision=1)).status_code == 404
    assert client.get(path, params={"offset": -1}).status_code == 422
    assert client.get(path, params={"offset": 100001}).status_code == 422
    assert post(client, ROOT + "/" + doc["id"] + "/publication/withdraw",
        {"request_key": str(uuid4()), "expected_revision": publication["revision"]}).status_code == 200
    for route in (path, path + "/workspace"):
        assert client.get(route).status_code == 404
    assert action(client, path, item, "hide").status_code == 404
    assert post(client, path, command(publication_revision=3)).status_code == 404


@pytest.mark.parametrize("url", ["https://127.0.0.1/private", "https://name:secret@example.ch/", "javascript:alert(1)"])
def test_contribution_sources_validate_without_fetching(signed, url):
    client, _, _, _ = signed
    _, _, path = setup(client)
    body = command()
    body["content"]["sources"][0]["url"] = url
    assert post(client, path, body).status_code == 422
    assert client.get(path).json()["items"] == []


def test_pages_and_actor_and_parent_erasure_keep_other_contributors(signed):
    client, service, owner, _ = signed
    doc, publication, path = setup(client)
    kept = save(client, path)
    person = _register(client, "erasable@example.ch").json()
    removed = save(client, path)
    with service.db.session(include_all_organizations=True) as session:
        for index in range(22):
            session.add(PublicContribution(organization_id=owner["organization"]["id"], publication_id=publication["id"],
                author_user_id=owner["user"]["id"], publication_revision=1, revision=1, author_label="Public writer",
                body=f"Deliberate public contribution {index}", sources_json=[]))
        session.commit()
    first, second = client.get(path).json(), client.get(path, params={"offset": 20}).json()
    assert first["total"] == second["total"] == 24
    assert len(first["items"]) == 20 and len(second["items"]) == 4
    assert not ({row["id"] for row in first["items"]} & {row["id"] for row in second["items"]})
    with service.db.session(include_all_organizations=True) as session:
        # The actual account erasure selector follows these CASCADE ownership edges.
        from helvetic_lens.account_erasure_store import erase_selected, select_private_rows
        user = session.get(User, person["user"]["id"])
        selection = select_private_rows(session, user, [])
        assert selection.counts["product_public_contributions"] == 1
        erase_selected(session, user, selection)
        session.commit()
        assert session.get(PublicContribution, removed["id"]) is None
        assert session.get(PublicContribution, kept["id"]) is not None
        session.delete(session.get(ProductDossier, doc["id"]))
        session.commit()
        assert session.scalar(select(PublicContribution)) is None
        assert session.scalar(select(PublicContributionMutation)) is None
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("change", ["membership", "session", "inactive"])
def test_current_principal_rechecks_even_if_request_identity_was_resolved(signed, monkeypatch, change):
    client, service, owner, _ = signed
    _, _, path = setup(client)
    from helvetic_lens import product_community
    original = product_community.participant

    def changed_principal(session, identity, product, identifier, **kwargs):
        if kwargs.get("write"):
            if change == "membership":
                session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == identity.user_id))
            elif change == "session":
                session.get(UserSession, identity.session_id).revoked_at = product_community.utcnow()
            else:
                session.get(User, identity.user_id).active = False
            session.flush()
        return original(session, identity, product, identifier, **kwargs)

    monkeypatch.setattr(product_community, "participant", changed_principal)
    assert post(client, path, command()).status_code in (401, 403)
    with service.db.session() as session:
        assert session.scalar(select(PublicContribution)) is None


def test_duplicate_sources_extra_private_fields_and_oversize_content_rejected(signed):
    client, _, _, _ = signed
    _, _, path = setup(client)
    body = command()
    duplicate = deepcopy(body)
    duplicate["content"]["sources"] *= 2
    assert post(client, path, duplicate).status_code == 422
    body["content"]["body"] = "x" * 12001
    assert post(client, path, body).status_code == 422
    assert post(client, path, command(organization_id=str(uuid4()))).status_code == 422


def test_discussion_migration_preserves_existing_publications_and_foreign_keys(signed):
    from test_account_deletion_migration import config

    from alembic import command as migration

    client, service, _, _ = signed
    _, publication, path = setup(client)
    with service.db.engine.begin() as connection:
        migration.downgrade(config(connection), "f6c495bef124")
        migration.upgrade(config(connection), "head")
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    assert client.get(PUBLIC + "/" + publication["id"]).status_code == 200
    assert save(client, path)["revision"] == 1
