"""Personal notifications preserve unseen arrivals and recheck current authority."""
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_product_dossiers import post
from test_product_dossiers import signed as signed

from helvetic_lens.db import utcnow
from helvetic_lens.feed_following_models import FeedFollow
from helvetic_lens.feed_models import Feed, FeedAssessment, FeedUpdate
from helvetic_lens.models import OrganizationMembership, User, UserSession


def create_feed(client, product="legal"):
    response = post(client, "/api/feeds", {"request_key": str(uuid4()), "name": "Source changes",
        "query": "Watch synthetic policy changes", "product": product, "status": "paused"})
    assert response.status_code == 201, response.text
    return response.json()


def add_update(service, identifier, sequence):
    with service.db.session() as session:
        session.add(FeedUpdate(feed_id=identifier, sequence=sequence, source_key="https://example.org/policy",
            title="Synthetic change", url="https://example.org/policy", content_hash=str(sequence) * 64))
        session.commit()


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_in_app_subscription_is_independent_and_only_acknowledges_shown_material(signed, product):
    client, service, _, _ = signed
    feed = create_feed(client, product)
    root = f"/api/feeds/{feed['id']}/follow"
    baseline = client.get(root).json()
    assert baseline["following"] and baseline["revision"] == 1 and baseline["unread_count"] == 0
    assert client.get(f"/api/products/{'loyer' if product == 'legal' else product}/dossiers").json()["total"] == 0
    add_update(service, feed["id"], 1)
    shown = client.get(root).json()
    assert shown["unread_count"] == 1
    add_update(service, feed["id"], 2)
    body = {"expected_revision": shown["revision"], "through_sequence": shown["latest_sequence"]}
    seen = post(client, root + "/read", body)
    assert seen.status_code == 200 and seen.json()["seen_sequence"] == 1 and seen.json()["unread_count"] == 1
    assert post(client, root + "/read", body).json() == seen.json()
    current = client.get(f"/api/feeds/{feed['id']}").json()
    assert current["follow"] == seen.json() and current["unread_count"] == 1
    assert post(client, root + "/read", {**body, "through_sequence": 2}).status_code == 409
    assert post(client, root + "/read", {"expected_revision": seen.json()["revision"], "through_sequence": 3}).status_code == 409
    mute = {"expected_revision": seen.json()["revision"], "following": False}
    muted = post(client, root, mute)
    assert muted.status_code == 200 and muted.json()["unread_count"] == 0
    assert post(client, root, mute).json() == muted.json()
    assert post(client, root, {**mute, "following": True}).status_code == 409
    assert client.post(root, json={**mute, "expected_revision": muted.json()["revision"]}).status_code == 403
    assert post(client, root, {"expected_revision": True, "following": True}).status_code == 422
    client.cookies.clear()
    assert client.get(root).status_code == 401


@pytest.mark.parametrize("revocation", ["membership", "account", "session"])
def test_personal_follow_rechecks_authority_inside_transaction(signed, monkeypatch, revocation):
    from helvetic_lens import feed_following

    client, service, _, _ = signed
    feed = create_feed(client)
    original = feed_following.selected

    def revoke(session, identifier, identity, **kwargs):
        if revocation == "membership":
            session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == identity.user_id))
        elif revocation == "account":
            session.get(User, identity.user_id).active = False
        else:
            session.get(UserSession, identity.session_id).revoked_at = utcnow()
        session.flush()
        return original(session, identifier, identity, **kwargs)

    monkeypatch.setattr(feed_following, "selected", revoke)
    response = post(client, f"/api/feeds/{feed['id']}/follow", {"expected_revision": 1, "following": False})
    assert response.status_code in (401, 403, 404), response.text
    with service.db.session() as session:
        assert session.scalar(select(FeedFollow)).following


def test_feed_schema_upgrade_and_nonempty_downgrade_guard(signed):
    from sqlalchemy import inspect
    from test_account_deletion_migration import config

    from alembic import command

    client, service, _, _ = signed
    with service.db.engine.begin() as connection:
        command.downgrade(config(connection), "0ed495bef125")
        assert "product_feeds" not in inspect(connection).get_table_names()
        command.upgrade(config(connection), "head")
        assert "product_feed_follows" in inspect(connection).get_table_names()
        assert "product_feed_assessments" in inspect(connection).get_table_names()
    feed = create_feed(client)
    with service.db.engine.connect() as connection:
        with pytest.raises(RuntimeError, match="Retained feed"):
            command.downgrade(config(connection), "0ed495bef125")
        assert connection.execute(select(Feed.id)).scalar() == feed["id"]
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_unread_counts_follow_current_semantic_scope_without_erasing_history(signed):
    from helvetic_lens.feed_intelligence import spec

    client, service, _, _ = signed
    feed = create_feed(client)
    for sequence in (1, 2, 3):
        add_update(service, feed["id"], sequence)
    with service.db.session() as session:
        row = session.get(Feed, feed["id"])
        binding = spec(session, row)["binding"]
        update = session.scalar(select(FeedUpdate).where(FeedUpdate.feed_id == row.id, FeedUpdate.sequence == 1))
        session.add(FeedAssessment(feed_id=row.id, update_id=update.id, spec_binding=binding,
            plan_binding="1" * 64, decision_key="2" * 64, verdict="unrelated"))
        session.commit()
    state = client.get(f"/api/feeds/{feed['id']}/follow").json()
    assert state["unread_count"] == 2 and state["latest_sequence"] == 3
    with service.db.session() as session:
        row = session.get(Feed, feed["id"])
        row.revision += 1
        session.commit()
    assert client.get(f"/api/feeds/{feed['id']}/follow").json()["unread_count"] == 3
