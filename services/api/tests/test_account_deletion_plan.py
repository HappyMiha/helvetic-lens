"""Erasure preview isolation, administrative handover and changing scope."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update
from test_monitoring_configuration_export import seed
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens.account_deletion_plan import inventory
from helvetic_lens.config import DomainError
from helvetic_lens.models import AssistantConversation, OrganizationMembership, User
from helvetic_lens.monitoring_centre import MODELS
from helvetic_lens.monitoring_connector_models import MonitoringConnectorConfiguration


def plan(db, *, user="owner", organization="org-a"):
    with db.session(include_all_organizations=True) as session:
        return inventory(session, user, organization)


def monitor(db, domain, *, user="owner", organization="org-a", **values):
    app = SimpleNamespace(state=SimpleNamespace(service=SimpleNamespace(db=db)))
    identity = {"user": {"id": user}, "organization": {"id": organization}}
    return seed(app, identity, domain, **values)


def test_all_nine_owned_categories_and_workspace_consent_without_any_mutation(db):
    owned = {monitor(db, domain) for domain in MODELS}
    with db.session(include_all_organizations=True) as session:
        connector = session.get(MonitoringConnectorConfiguration, "commute")
        connector.revision = 1
        connector.encrypted_credentials = "synthetic-secret-not-a-real-key"
        session.commit()
    preview = plan(db)
    assert {row[1] for row in preview.monitors} == owned
    assert len(preview.public["categories"]) == 9
    assert all(row["owned"] == 1 for row in preview.public["categories"])
    assert preview.public["can_delete"]
    assert preview.erase_organizations == ("org-b",)
    assert preview.public["workspace_erasure_confirmation_required"]
    assert [(row["id"], row["disposition"]) for row in preview.public["workspaces"]] == [
        ("org-a", "leave_workspace"), ("org-b", "erase_private_workspace")]
    assert "synthetic-secret" not in json.dumps(preview.public)
    assert plan(db).public == preview.public
    with db.session(include_all_organizations=True) as session:
        assert session.get(User, "owner").active
        assert session.get(MonitoringConnectorConfiguration, "commute").revision == 1


def test_shared_owned_monitors_require_handover_but_colleagues_inventory_is_not_exposed(db):
    shared = {monitor(db, domain, visibility="workspace") for domain in ("tenders", "ip", "auctions")}
    private_peer = monitor(db, "air", user="peer")
    shared_peer = monitor(db, "tenders", user="peer", visibility="workspace")
    preview = plan(db).public
    assert not preview["can_delete"]
    assert {row["monitor_id"] for row in preview["blockers"]} == shared
    assert private_peer not in json.dumps(preview) and shared_peer not in json.dumps(preview)
    assert sum(row["owned"] for row in preview["categories"]) == 3


def test_former_workspace_private_monitors_are_in_scope_without_disclosing_workspace(db):
    shared = monitor(db, "tenders", organization="org-b", visibility="workspace")
    private = monitor(db, "air", organization="org-b")
    with db.session(include_all_organizations=True) as session:
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.organization_id == "org-b"))
        session.commit()
    preview = plan(db)
    assert {row[1] for row in preview.monitors} == {shared, private}
    assert len(preview.public["workspaces"]) == 1
    assert preview.public["blockers"] == [{"kind": "monitor_owner", "domain": "tenders", "monitor_id": shared,
        "organization_id": None, "membership_required": True}]
    assert "org-b" not in json.dumps(preview.public)


def test_removed_or_inactive_admin_cannot_be_used_as_the_surviving_administrator(db):
    before = plan(db).public
    with db.session(include_all_organizations=True) as session:
        session.execute(update(User).where(User.id == "peer").values(active=False))
        session.commit()
    current = plan(db).public
    assert current["fingerprint"] != before["fingerprint"] and not current["can_delete"]
    assert {"kind": "workspace_administrator", "organization_id": "org-a"} in current["blockers"]
    assert "org-a" not in plan(db).erase_organizations


def test_last_platform_admin_and_sole_workspace_viewer_are_protected(db):
    with db.session(include_all_organizations=True) as session:
        session.execute(update(User).where(User.id == "owner").values(platform_admin=True))
        session.execute(update(OrganizationMembership).where(OrganizationMembership.organization_id == "org-b")
            .values(role="viewer"))
        session.commit()
    current = plan(db)
    assert current.erase_organizations == ()
    assert {"kind": "platform_administrator"} in current.public["blockers"]
    assert {"kind": "workspace_administrator", "organization_id": "org-b"} in current.public["blockers"]


def test_colleague_private_data_prevents_erasing_a_sole_member_workspace(db):
    identifier = monitor(db, "air", user="peer")
    with db.session(include_all_organizations=True) as session:
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.organization_id == "org-a",
            OrganizationMembership.user_id != "owner"))
        session.commit()
    current = plan(db)
    assert "org-a" not in current.erase_organizations
    assert {"kind": "workspace_private_data", "organization_id": "org-a"} in current.public["blockers"]
    assert identifier not in json.dumps(current.public)


def test_fingerprint_tracks_monitor_versions_personal_objects_and_roster_changes(db):
    identifier = monitor(db, "air")
    before = plan(db).public["fingerprint"]
    with db.session(include_all_organizations=True) as session:
        session.execute(update(MODELS["air"]).where(MODELS["air"].id == identifier).values(version=2))
        session.commit()
    changed = plan(db).public["fingerprint"]
    assert changed != before
    with db.session(include_all_organizations=True) as session:
        session.add(AssistantConversation(id=str(uuid4()), organization_id="org-b", user_id="owner",
            principal_key="user:owner", context_key="home", route="/", title="Secret conversation",
            draft="Secret draft", messages_json=[], locale="en-CH"))
        session.commit()
    current = plan(db).public
    assert current["fingerprint"] != changed and current["personal_counts"]["conversations"] == 1
    assert "Secret" not in json.dumps(current)


def test_former_colleague_digest_preferences_are_not_erased_with_a_sole_member_workspace(db):
    from helvetic_lens.models import DigestPreference

    with db.session(include_all_organizations=True) as session:
        session.add(DigestPreference(id="private-peer-digest", organization_id="org-a", user_id="peer",
            enabled=False, frequency="weekly"))
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.organization_id == "org-a",
            OrganizationMembership.user_id != "owner"))
        session.commit()
    current = plan(db)
    assert "org-a" not in current.erase_organizations
    assert {"kind": "workspace_private_data", "organization_id": "org-a"} in current.public["blockers"]
    assert "private-peer-digest" not in json.dumps(current.public)


def test_preview_requires_live_identity_membership_and_full_scope(db):
    with db.session() as session, pytest.raises(ValueError):
        inventory(session, "owner", "org-a")
    for user, organization in (("missing", "org-a"), ("peer", "org-b")):
        with pytest.raises(DomainError):
            plan(db, user=user, organization=organization)
    with db.session(include_all_organizations=True) as session:
        session.get(User, "owner").active = False
        session.commit()
    with pytest.raises(DomainError):
        plan(db)
    with db.session(include_all_organizations=True) as session:
        assert session.scalar(select(User.id).where(User.id == "owner")) == "owner"
