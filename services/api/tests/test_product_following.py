from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_auth import _register
from test_product_community import action, command, save, setup
from test_product_dossiers import ROOT, post
from test_product_dossiers import signed as signed
from test_product_publications import draft, preview_and_publish

from helvetic_lens.models import OrganizationMembership, User, UserSession
from helvetic_lens.product_models import ProductDossier, ProductPublication, PublicDossierFollow

LIST = "/api/products/pharma/followed-dossiers"


def follow(client, path, following=True, revision=0):
    response = post(client, path, {"expected_revision": revision, "following": following})
    assert response.status_code == 200, response.text
    return response.json()


def test_personal_follow_is_private_across_organizations_colleagues_and_products(signed):
    client, service, owner, _ = signed
    doc, _, discussion = setup(client)
    path = discussion.replace("/discussion", "/follow")
    owner_cookies = dict(client.cookies)
    person = _register(client, "follower@example.ch").json()
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=person["user"]["id"], organization_id=owner["organization"]["id"], role="viewer"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": owner["organization"]["id"]}).status_code == 200
    assert client.post(path, json={"expected_revision": 0, "following": True}).status_code == 403
    state = follow(client, path)
    assert state["following"] and not state["unread"] and state["revision"] == 1
    assert follow(client, path) == state
    assert client.get(LIST).json()["total"] == 1
    assert post(client, ROOT, {"invalid": "viewer still cannot write private work"}).status_code == 403
    assert client.get(ROOT + "/" + doc["id"]).status_code == 404
    assert client.get(LIST.replace("pharma", "loyer")).json()["total"] == 0
    assert client.get(path.replace("pharma", "loyer")).status_code == 404
    assert post(client, path.replace("pharma", "loyer"), {"expected_revision": 0, "following": True}).status_code == 404
    # Following is personal and survives switching the active organization.
    assert post(client, "/api/auth/session/organization", {"organization_id": person["organization"]["id"]}).status_code == 200
    assert client.get(LIST).json()["total"] == 1
    client.cookies.clear()
    client.cookies.update(owner_cookies)
    assert client.get(LIST).json()["total"] == 0
    assert client.get(path).json()["revision"] == 0
    client.cookies.clear()
    for route in (LIST, path):
        response = client.get(route)
        assert response.status_code == 401 and response.headers["cache-control"] == "no-store"
    assert client.post(path, json={"expected_revision": 0, "following": True}).status_code == 401


def test_visible_changes_and_stale_read_markers_never_expose_hidden_activity(signed):
    client, _, _, _ = signed
    _, _, discussion = setup(client)
    path = discussion.replace("/discussion", "/follow")
    original = follow(client, path)
    item = save(client, discussion)
    changed = client.get(path).json()
    assert changed["unread"] and changed["marker"] != original["marker"]
    assert post(client, path + "/read", {"expected_revision": 1, "marker": original["marker"]}).status_code == 409
    acknowledged = post(client, path + "/read", {"expected_revision": 1, "marker": changed["marker"]})
    assert acknowledged.status_code == 200 and not acknowledged.json()["unread"]
    hidden = action(client, discussion, item, "hide").json()["contribution"]
    hidden_state = client.get(path).json()
    assert hidden_state["unread"]
    edit = command(expected_revision=hidden["revision"])
    edit["content"]["body"] = "An entirely private hidden edit must not reveal activity."
    assert post(client, discussion + "/" + item["id"], edit).status_code == 200
    assert client.get(path).json()["marker"] == hidden_state["marker"]
    assert client.get(LIST).json()["items"][0]["marker"] == hidden_state["marker"]
    assert "private hidden edit" not in client.get(LIST).text
    restored = action(client, discussion, {**hidden, "revision": 3}, "restore")
    assert restored.status_code == 200
    assert client.get(path).json()["marker"] != hidden_state["marker"]


def test_revision_changes_withdrawal_redaction_and_old_follow_retries(signed):
    client, _, _, _ = signed
    doc, _, discussion = setup(client)
    path = discussion.replace("/discussion", "/follow")
    state = follow(client, path)
    second = follow(client, path, False, state["revision"])
    assert client.get(LIST).json()["total"] == 0
    assert post(client, path, {"expected_revision": 0, "following": True}).status_code == 409
    state = follow(client, path, True, second["revision"])
    assert post(client, path, {"expected_revision": 1, "following": False}).status_code == 409
    publication, _ = preview_and_publish(client, doc["id"], draft(1, title="Changed public dossier title"))
    assert client.get(path).json()["unread"]
    assert post(client, ROOT + "/" + doc["id"] + "/publication/withdraw",
        {"request_key": str(uuid4()), "expected_revision": publication["revision"]}).status_code == 200
    result = client.get(LIST)
    row = result.json()["items"][0]
    assert row["publication"] is None and row["marker"] is None and not row["available"]
    assert "Changed public dossier title" not in result.text
    assert post(client, path + "/read", {"expected_revision": state["revision"], "marker": state["marker"]}).status_code == 409
    follow(client, path, False, state["revision"])
    assert post(client, path, {"expected_revision": state["revision"] + 1, "following": True}).status_code == 409


def test_paginated_personal_list_and_native_account_parent_erasure(signed):
    client, service, owner, _ = signed
    doc, publication, discussion = setup(client)
    follow(client, discussion.replace("/discussion", "/follow"))
    owner_cookies = dict(client.cookies)
    person = _register(client, "follow-erase@example.ch").json()
    follow(client, discussion.replace("/discussion", "/follow"))
    with service.db.session(include_all_organizations=True) as session:
        from helvetic_lens.account_erasure_store import erase_selected, select_private_rows
        user = session.get(User, person["user"]["id"])
        selection = select_private_rows(session, user, [])
        assert selection.counts["product_public_follows"] == 1
        erase_selected(session, user, selection)
        session.commit()
        assert session.scalar(select(PublicDossierFollow).where(PublicDossierFollow.owner_user_id == owner["user"]["id"]))
    client.cookies.clear()
    client.cookies.update(owner_cookies)
    with service.db.session() as session:
        template = session.get(ProductPublication, publication["id"])
        for index in range(21):
            source = ProductPublication(dossier_id=doc["id"], product="pharma", status="published", revision=1,
                title=f"Published page {index}", summary=template.summary, body=template.body, author_label=template.author_label,
                sources_json=[], first_published_at=template.first_published_at, updated_at=template.updated_at)
            # Each projection requires its own genuine native parent.
            from helvetic_lens.legal_profile_models import LegalMonitoringProfile
            profile = LegalMonitoringProfile(created_by_user_id=owner["user"]["id"], creation_key=str(uuid4()))
            session.add(profile)
            session.flush()
            parent = ProductDossier(product="pharma", profile_id=profile.id, creation_key=str(uuid4()))
            session.add(parent)
            session.flush()
            source.dossier_id = parent.id
            session.add(source)
            session.flush()
            session.add(PublicDossierFollow(owner_user_id=owner["user"]["id"], publication_id=source.id, seen_marker="0" * 64))
        session.commit()
    first, second = client.get(LIST).json(), client.get(LIST + "?offset=20").json()
    assert first["total"] == second["total"] == 22
    assert len(first["items"]) == 20 and len(second["items"]) == 2
    assert not ({x["publication_id"] for x in first["items"]} & {x["publication_id"] for x in second["items"]})
    assert client.get(LIST + "?offset=-1").status_code == 422
    with service.db.session() as session:
        session.execute(delete(ProductDossier).where(ProductDossier.id == doc["id"]))
        session.commit()
    assert client.get(LIST).json()["total"] == 21


@pytest.mark.parametrize("change", ["membership", "session", "user"])
def test_follow_mutations_revalidate_current_principal(signed, monkeypatch, change):
    client, service, _, _ = signed
    _, _, discussion = setup(client)
    from helvetic_lens import product_following
    original = product_following.selected

    def invalidate(session, identity, *args, **kwargs):
        if change == "membership":
            session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == identity.user_id))
        elif change == "session":
            session.get(UserSession, identity.session_id).revoked_at = product_following.utcnow()
        else:
            session.get(User, identity.user_id).active = False
        session.flush()
        return original(session, identity, *args, **kwargs)

    monkeypatch.setattr(product_following, "selected", invalidate)
    assert post(client, discussion.replace("/discussion", "/follow"), {"expected_revision": 0, "following": True}).status_code in (401, 403)
    with service.db.session() as session:
        assert session.scalar(select(PublicDossierFollow)) is None
