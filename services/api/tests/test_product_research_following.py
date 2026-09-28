"""Personal research updates exercise native HTTP, scopes, jobs and erasure."""
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_evidence_search import QUOTE, retained
from test_product_following import follow
from test_product_guests import accept, guest, invitation
from test_product_investigations import complete
from test_product_teams import switch
from test_product_web_research import setup

from helvetic_lens.db import utcnow
from helvetic_lens.models import OrganizationMembership, User, UserSession
from helvetic_lens.product_investigation_models import Investigation, InvestigationSource
from helvetic_lens.product_investigations import event
from helvetic_lens.product_models import DossierEntry, DossierMember, PrivateDossierFollow, ProductDossier


def finished(service, doc, *, status="completed", unchanged=False):
    identifier, source_id = retained(service, doc, status=status)
    with service.db.session() as session:
        run = session.get(Investigation, identifier)
        if unchanged:
            source = session.get(InvestigationSource, source_id)
            source.snapshot = {**source.snapshot, "unchanged_from": "previous-source"}
        event(session, run, "investigation_finished", status=status)
        session.commit()
    return identifier


def seen(client, root, state):
    return post(client, root + "/follow/read", {"expected_revision": state["revision"], "marker": state["marker"]})


@pytest.mark.parametrize("product", ["pharma", "loyer"])
@pytest.mark.parametrize("audience", ["draft", "workspace", "team"])
def test_private_personal_lifecycle_exact_markers_and_current_evidence(signed, product, audience):
    client, service, _, _ = signed
    doc, root = setup(client, product, audience)
    old_run = finished(service, doc)
    baseline = client.get(root + "/follow").json()
    assert baseline["research"]["total"] == 1 and not baseline["unread"] and not baseline["following"]
    first = follow(client, root + "/follow")
    assert first == follow(client, root + "/follow")
    new_run = finished(service, doc)
    state = client.get(root + "/follow").json()
    assert state["unread"] and state["research"]["unseen"] == 1
    page = client.get(root + "/follow/updates")
    assert page.status_code == 200 and page.headers["cache-control"] == "no-store", page.text
    items = page.json()["items"]
    assert [i["investigation_id"] for i in items] == [new_run, old_run]
    assert [i["unseen"] for i in items] == [True, False]
    assert items[0]["sources"][0]["quote"] == QUOTE and items[0]["finding_count"] == 1
    assert items[0]["sources"][0]["sha256"] and items[0]["findings"][0]["source_id"]
    assert seen(client, root, first).status_code == 409
    ack = seen(client, root, state)
    assert ack.status_code == 200 and not ack.json()["unread"]
    assert seen(client, root, state).json() == ack.json()
    assert not client.get(root + "/follow/updates").json()["items"][0]["unseen"]
    paused = follow(client, root + "/follow", False, ack.json()["revision"])
    assert post(client, root + "/follow", {"expected_revision": 1, "following": True}).status_code == 409
    finished(service, doc)
    resumed = follow(client, root + "/follow", True, paused["revision"])
    assert not resumed["unread"] and resumed["research"]["total"] == 3
    listing = client.get(f"/api/products/{product}/followed-private-dossiers").json()
    assert listing["total"] == 1 and listing["items"][0] == resumed
    assert client.get(f"/api/products/{product}/followed-dossiers").json()["total"] == 0
    assert client.get(root.replace(product, "loyer" if product == "pharma" else "pharma") + "/follow").status_code == 404
    assert client.post(root + "/follow", json={"expected_revision": 0, "following": False}).status_code == 403
    for data in ({"expected_revision": True, "following": False}, {"expected_revision": 0, "following": "true"}):
        assert post(client, root + "/follow", data).status_code == 422
    client.cookies.clear()
    for suffix in ("/follow", "/follow/updates"):
        assert client.get(root + suffix).status_code == 401


def test_pending_failed_unchanged_and_internal_ticks_do_not_notify(signed):
    client, service, _, _ = signed
    doc, root = setup(client)
    state = follow(client, root + "/follow")
    for status in ("queued", "running", "paused", "failed", "cancelled"):
        finished(service, doc, status=status)
    finished(service, doc, unchanged=True)
    run_id, _ = retained(service, doc)
    with service.db.session() as session:
        event(session, session.get(Investigation, run_id), "plan_updated", reason="Internal progress")
        session.commit()
    assert client.get(root + "/follow").json() == state
    assert client.get(root + "/follow/updates").json()["total"] == 0


def test_permission_filter_before_update_paging_and_acknowledgement(signed):
    client, service, _, _ = signed
    doc, root = setup(client)
    follow(client, root + "/follow")
    for _ in range(23):
        finished(service, doc)
    pages = [client.get(root + f"/follow/updates?offset={offset}").json() for offset in (0, 10, 20)]
    assert [len(p["items"]) for p in pages] == [10, 10, 3]
    assert len({x["investigation_id"] for p in pages for x in p["items"]}) == 23
    assert all(p["total"] == 23 for p in pages)
    old = client.get(root + "/follow").json()
    with service.db.session() as session:
        session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", url="https://example.org/source",
            request_key=str(uuid4()), data_json={"revision": 1, "decision": "exclude"}, body="private exclusion"))
        session.commit()
    hidden = client.get(root + "/follow").json()
    assert hidden["research"]["total"] == hidden["research"]["unseen"] == 0 and not hidden["unread"]
    assert seen(client, root, old).status_code == 409
    for offset in (0, 20):
        result = client.get(root + f"/follow/updates?offset={offset}")
        assert result.json()["items"] == [] and QUOTE not in result.text
    assert client.get(root + "/follow/updates?offset=-1").status_code == 422


@pytest.mark.parametrize("role", ["VIEWER", "CONTRIBUTOR", "EDITOR"])
def test_guest_personal_follow_never_opens_sibling_or_native_workspace(signed, role):
    client, service, owner, _ = signed
    doc, root = setup(client, audience="team")
    sibling, _ = setup(client, audience="team")
    account, cookies = guest(client, service)
    invite = invitation(client, root, account, role)
    switch(client, cookies)
    accept(client, root, invite)
    follow(client, root + "/follow")
    finished(service, doc)
    state = client.get(root + "/follow").json()
    assert state["research"]["unseen"] == 1
    path = "/api/products/pharma/followed-private-dossiers"
    listing = client.get(path)
    assert listing.status_code == 200 and listing.json()["total"] == 1, listing.text
    assert sibling["id"] not in listing.text and owner["organization"]["id"] not in listing.text
    assert client.get(root + "/follow/updates").json()["total"] == 1
    assert seen(client, root, state).status_code == 200
    assert client.get(root.replace(doc["id"], sibling["id"]) + "/follow").status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        session.delete(session.get(DossierMember, (doc["id"], account["user"]["id"])))
        session.commit()
    assert client.get(path).json()["total"] == 0
    for suffix in ("/follow", "/follow/updates"):
        assert client.get(root + suffix).status_code == 404
    assert seen(client, root, state).status_code == 404


@pytest.mark.parametrize("revocation", ["membership", "session", "account"])
def test_personal_mutations_recheck_current_login(signed, monkeypatch, revocation):
    from helvetic_lens import product_private_following as module

    client, service, _, _ = signed
    _, root = setup(client)
    original = module.selected
    def revoke(session, identity, *args, **kwargs):
        if revocation == "membership":
            session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == identity.user_id))
        elif revocation == "session":
            session.get(UserSession, identity.session_id).revoked_at = utcnow()
        else:
            session.get(User, identity.user_id).active = False
        session.flush()
        return original(session, identity, *args, **kwargs)
    monkeypatch.setattr(module, "selected", revoke)
    assert post(client, root + "/follow", {"expected_revision": 0, "following": True}).status_code in (401, 403)
    with service.db.session() as session:
        assert session.scalar(select(PrivateDossierFollow)) is None


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_real_recurring_jobs_notify_once_skip_unchanged_and_link_evolution(signed, monkeypatch, product):
    from test_product_web_research import SECOND, due, enable, newest, pipeline

    from helvetic_lens.product_web_research import enqueue_due

    client, service, _, model = signed
    _, root = setup(client, product)
    fixture = pipeline(monkeypatch, service, model)
    follow(client, root + "/follow")
    enable(client, root)
    assert enqueue_due(service.db, service.settings)["started"] == 1
    complete(client, service, root + "/investigations", newest(client, root))
    first = client.get(root + "/follow").json()
    assert first["research"]["unseen"] == 1
    acknowledged = seen(client, root, first).json()
    assert due(service, next_day=True)["started"] == 1
    complete(client, service, root + "/investigations", newest(client, root))
    assert client.get(root + "/follow").json() == acknowledged
    fixture["text"] = SECOND
    assert due(service, next_day=True)["started"] == 1
    complete(client, service, root + "/investigations", newest(client, root))
    changed = client.get(root + "/follow").json()
    assert changed["research"]["unseen"] == 1 and changed["research"]["total"] == 2
    update = client.get(root + "/follow/updates").json()["items"][0]
    assert update["comparisons"][0]["current"]["evidence"]["quote"] == SECOND
    assert update["comparisons"][0]["previous"]["evidence"]["source"]["sha256"]
    assert sum(update["comparison_counts"].values()) == 1
    assert seen(client, root, first).status_code == 409


@pytest.mark.parametrize("revocation", ["hide", "publication", "source"])
def test_real_public_research_enters_follow_marker_and_withdrawn_evidence_disappears(signed, monkeypatch, revocation):
    from test_product_investigations import pipeline
    from test_product_public_research import setup as public_setup
    from test_product_public_research import submit

    from helvetic_lens.product_models import ProductPublication, PublicContribution

    client, service, identity, model = signed
    doc, publication, root = public_setup(client, service, identity)
    finished(service, doc)  # Never include private research in the public inbox.
    follow(client, root + "/follow")
    pipeline(monkeypatch, service, model)
    contribution, _ = submit(client, root)
    before_completion = client.get(root + "/follow").json()
    assert seen(client, root, before_completion).status_code == 200
    complete(client, service, root + "/research", contribution["research"])
    after = client.get(root + "/follow").json()
    assert after["research"]["unseen"] == after["research"]["total"] == 1
    assert after["marker"] != before_completion["marker"] and after["unread"]
    assert seen(client, root, before_completion).status_code == 409
    data = client.get(root + "/follow/updates")
    assert QUOTE not in data.text and data.json()["total"] == 1
    with service.db.session() as session:
        if revocation == "hide":
            session.get(PublicContribution, contribution["id"]).status = "hidden"
        elif revocation == "publication":
            session.get(ProductPublication, publication["id"]).revision += 1
        else:
            session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", url="https://example.org/registry",
                request_key=str(uuid4()), data_json={"decision": "exclude", "revision": 1}))
        session.commit()
    assert client.get(root + "/follow/updates").json()["total"] == 0
    assert client.get(root + "/follow").json()["research"]["unseen"] == 0
    assert seen(client, root, after).status_code == 409
    client.cookies.clear()
    assert client.get(root + "/follow/updates").status_code == 401


def test_native_migration_roundtrip_and_personal_erasure_leave_host_evidence(signed):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from test_account_deletion_migration import config

    from alembic import command
    from helvetic_lens.account_erasure_store import erase_selected, select_private_rows
    from helvetic_lens.db import Base

    client, service, owner, _ = signed
    with service.db.engine.connect() as connection:
        command.downgrade(config(connection), "04d495bef125")
        command.upgrade(config(connection), "head")
        selected = {"product_private_follows", "product_public_follows"}
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, other: kind != "table" or name in selected})
        assert compare_metadata(context, Base.metadata) == []
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    doc, root = setup(client, audience="team")
    follow(client, root + "/follow")
    finished(service, doc)
    account, cookies = guest(client, service)
    item = invitation(client, root, account, "VIEWER")
    switch(client, cookies)
    accept(client, root, item)
    follow(client, root + "/follow")
    with service.db.session(include_all_organizations=True) as session:
        user = session.get(User, account["user"]["id"])
        selection = select_private_rows(session, user, [])
        assert selection.counts["product_private_follows"] == 1
        erase_selected(session, user, selection)
        session.commit()
        assert session.get(ProductDossier, doc["id"])
        assert session.scalar(select(PrivateDossierFollow)).owner_user_id == owner["user"]["id"]
    with service.db.engine.connect() as connection:
        with pytest.raises(RuntimeError, match="personal follows"):
            command.downgrade(config(connection), "04d495bef125")


def test_private_follow_list_pages_filter_inaccessible_rows_before_count(signed):
    from helvetic_lens.legal_profile_models import LegalMonitoringProfile

    client, service, identity, _ = signed
    account, cookies = guest(client, service)
    with service.db.session() as session:
        for index in range(24):
            profile = LegalMonitoringProfile(created_by_user_id=identity["user"]["id"], creation_key=str(uuid4()),
                config_json={"name": f"Private archive {index}"})
            session.add(profile)
            session.flush()
            doc = ProductDossier(profile_id=profile.id, product="pharma", creation_key=str(uuid4()))
            session.add(doc)
            session.flush()
            for user_id in (identity["user"]["id"], account["user"]["id"]):
                session.add(PrivateDossierFollow(dossier_id=doc.id, owner_user_id=user_id, seen_marker="0" * 64,
                    updated_at=utcnow() - timedelta(seconds=index)))
        session.commit()
    route = "/api/products/pharma/followed-private-dossiers"
    first, second = client.get(route).json(), client.get(route + "?offset=20").json()
    assert first["total"] == second["total"] == 24
    assert len(first["items"]) == 20 and len(second["items"]) == 4
    assert len({i["dossier_id"] for p in (first, second) for i in p["items"]}) == 24
    switch(client, cookies)
    for suffix in ("", "?offset=20"):
        assert client.get(route + suffix).json()["total"] == 0


@pytest.mark.parametrize("withdrawal", ["current_corpus", "previous_corpus", "earlier_url"])
def test_saved_page_updates_keep_both_original_version_permissions(signed, monkeypatch, withdrawal):
    from test_product_document_history import setup as pages
    from test_product_monitoring_research import due, enable, model
    from test_product_page_research import changed, last_run

    from helvetic_lens.models import Organization, Version

    client, service, _, target = signed
    _, root, law_id, baseline, _ = pages(client)
    earlier_url = "https://example.ch/earlier-original"
    with service.db.session() as session:
        session.get(Version, baseline).source_url = earlier_url
        session.commit()
    follow(client, root + "/follow")
    enable(client, root, include_page_changes=True)
    current = changed(client, service, law_id, "The saved page describes a new private evidence requirement.")
    model(monkeypatch, target)
    due(service)
    complete(client, service, root + "/investigations", last_run(client, root))
    before = client.get(root + "/follow").json()
    assert before["research"]["unseen"] == 1
    assert client.get(root + "/follow/updates").json()["total"] == 1
    with service.db.session() as session:
        if withdrawal == "earlier_url":
            session.add(DossierEntry(dossier_id=root.split('/')[-1], request_key=str(uuid4()), kind="source_review",
                url=earlier_url, data_json={"decision": "exclude", "revision": 1}))
        else:
            other = Organization(name="Revoked corpus", slug="revoked-notification-corpus")
            session.add(other)
            session.flush()
            session.get(Version, current if withdrawal == "current_corpus" else baseline).owner_organization_id = other.id
        session.commit()
    after = client.get(root + "/follow").json()
    assert after["research"]["unseen"] == 0 and after["research"]["total"] == 0
    hidden = client.get(root + "/follow/updates")
    assert hidden.json()["items"] == [] and "private evidence requirement" not in hidden.text
    assert seen(client, root, before).status_code == 409


def test_unverified_guest_does_not_gain_list_access_through_new_native_membership(signed):
    client, service, owner, _ = signed
    doc, root = setup(client, audience="team")
    account, cookies = guest(client, service)
    item = invitation(client, root, account, "VIEWER")
    switch(client, cookies)
    accept(client, root, item)
    follow(client, root + "/follow")
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=account["user"]["id"], organization_id=owner["organization"]["id"], role="viewer"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": owner["organization"]["id"]}).status_code == 200
    with service.db.session(include_all_organizations=True) as session:
        session.get(User, account["user"]["id"]).email_verified_at = None
        session.commit()
    assert client.get("/api/products/pharma/followed-private-dossiers").json()["total"] == 0
    assert client.get(root + "/follow").status_code == 404
