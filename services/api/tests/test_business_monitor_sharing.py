"""Explicit opt-in and responsibility never widen personal email/source access."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, update
from test_auction_rules import profile as auction_profile
from test_tender_matching import profile as tender_profile
from test_tender_repository import db as db
from test_tender_repository import template as template
from test_trademark_matching import portfolio

from helvetic_lens import (
    auction_repository,
    business_monitor_sharing,
    tender_repository,
    trademark_repository,
)
from helvetic_lens.business_monitor_access import collection_actor, require_private_owner
from helvetic_lens.business_monitor_models import BusinessMonitorScopeEvent
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.models import User

NOW = datetime(2026, 9, 14, 12, tzinfo=UTC)


def create(db, domain):
    module, factory, name = {
        "tenders": (tender_repository, tender_profile, "create_profile"),
        "ip": (trademark_repository, portfolio, "create_monitor"),
        "auctions": (auction_repository, auction_profile, "create_monitor"),
    }[domain]
    with db.session() as session:
        result = getattr(module, name)(session, "owner", factory().model_dump(mode="json"), "scope-test")
        session.commit()
        return result["id"]


def configure(db, domain, monitor, *, actor="owner", version=1, scope="workspace", responsible="peer", confirmed=True, now=NOW):
    with db.session() as session:
        result = business_monitor_sharing.configure(session, actor, domain, monitor,
            expected_version=version, visibility=scope, responsible_user_id=responsible, confirmed=confirmed, now=now)
        session.commit()
        return result


@pytest.mark.parametrize("domain", ("tenders", "ip", "auctions"))
def test_opt_in_scope_reassignment_withdrawal_and_private_email_boundary(db, domain):
    monitor = create(db, domain)
    with db.session() as session:
        own = business_monitor_sharing.read(session, "owner", domain, monitor)
        assert own["visibility"] == "private" and own["history"] == []
        with pytest.raises(DomainError):
            business_monitor_sharing.read(session, "peer", domain, monitor)
    with pytest.raises(DomainError):
        configure(db, domain, monitor, confirmed=False)
    shared = configure(db, domain, monitor)
    assert shared["visibility"] == "workspace" and shared["monitor_version"] == 2
    assert shared["responsible"] == {"id": "peer", "name": "peer", "available": True}
    with db.session() as session:
        for actor in ("peer", "viewer"):
            read = business_monitor_sharing.read(session, actor, domain, monitor)
            assert read["history"][0]["actor"]["id"] == "owner"
            assert read["can_change_scope"] is False
        row = business_monitor_sharing.monitor_for(session, "peer", domain, monitor)
        assert collection_actor(session, row) == "peer"
        with pytest.raises(DomainError):
            require_private_owner(row, "peer")
    for actor in ("viewer", "peer"):
        with pytest.raises(DomainError):
            configure(db, domain, monitor, actor=actor, version=2, scope="private", responsible=None)
    with pytest.raises(DomainError):
        configure(db, domain, monitor, version=1)
    with db.organization_context("org-b"), db.session() as session, pytest.raises(DomainError):
        business_monitor_sharing.read(session, "owner", domain, monitor)
    with db.session() as session:
        session.execute(update(User).where(User.id == "peer").values(active=False))
        session.commit()
    with db.session() as session:
        read = business_monitor_sharing.read(session, "owner", domain, monitor)
        assert read["responsible"]["available"] is False
        with pytest.raises(DomainError):
            collection_actor(session, business_monitor_sharing.monitor_for(session, "owner", domain, monitor))
    assigned = configure(db, domain, monitor, version=2, responsible="owner")
    assert assigned["monitor_version"] == 3 and len(assigned["history"]) == 2
    closed = configure(db, domain, monitor, version=3, scope="private", responsible=None)
    assert closed["monitor_version"] == 4 and len(closed["history"]) == 3
    with db.session() as session:
        with pytest.raises(DomainError):
            business_monitor_sharing.read(session, "viewer", domain, monitor)
        assert session.scalar(select(func.count()).select_from(BusinessMonitorScopeEvent)) == 3


def test_members_are_current_workspace_admins_without_emails_and_c4_is_rejected(db):
    with db.session() as session:
        result = business_monitor_sharing.members(session, "owner", limit=1)
        assert set(result["items"][0]) == {"id", "name"}
        continuation = business_monitor_sharing.members(session, "owner", after_id=result["next_cursor"])
        assert {row["id"] for row in result["items"] + continuation["items"]} == {"owner", "peer"}
        with pytest.raises(DomainError):
            business_monitor_sharing.members(session, "viewer")
        with pytest.raises(DomainError):
            business_monitor_sharing.read(session, "owner", "customs", "missing")


@pytest.mark.parametrize("domain", ("tenders", "ip", "auctions"))
def test_native_email_is_personal_and_sharing_revokes_consent_without_transferring_it(db, domain):
    from helvetic_lens import (
        auction_delivery,
        auction_email_preferences,
        tender_delivery,
        tender_email_preferences,
        trademark_delivery,
        trademark_email_preferences,
    )
    from helvetic_lens.monitoring_centre import inventory

    module, delivery, repository = {
        "tenders": (tender_email_preferences, tender_delivery, tender_repository),
        "ip": (trademark_email_preferences, trademark_delivery, trademark_repository),
        "auctions": (auction_email_preferences, auction_delivery, auction_repository),
    }[domain]
    monitor = create(db, domain)
    with db.session() as session:
        session.get(User, "owner").email_verified_at = NOW
        module.configure(session, "owner", monitor, expected_version=1,
            configuration={"delivery": {"email": "immediate"}}, consent=True, now=NOW)
        session.commit()
    configure(db, domain, monitor, version=2)
    with db.session() as session:
        own = module.view(session, "owner", monitor)
        assert own["configuration"]["delivery"]["email"] == "off"
        assert own["consent_active"] is False and own["revision"] == 2
        for actor in ("peer", "viewer"):
            assert repository.get_monitor(session, actor, monitor)["visibility"] == "workspace"
            assert monitor in {item["id"] for item in repository.list_monitors(session, actor)["items"]}
            assert monitor in {item["id"] for item in inventory(session, Settings(_env_file=None), actor, domain=domain)["items"]}
            assert inventory(session, Settings(_env_file=None), actor, domain=domain, personal_only=True)["items"] == []
            with pytest.raises(DomainError) as denied:
                module.view(session, actor, monitor)
            assert denied.value.status == 404
            with pytest.raises(DomainError) as denied:
                delivery.preview(session, Settings(_env_file=None), actor, monitor, now=NOW)
            assert denied.value.status == 404
        with pytest.raises(DomainError) as denied:
            module.configure(session, "peer", monitor, expected_version=3,
                configuration={"delivery": {"email": "off"}}, consent=False, now=NOW)
        assert denied.value.status == 404
    configure(db, domain, monitor, version=3, scope="private", responsible=None)
    with db.session() as session:
        assert repository.list_monitors(session, "peer")["items"] == []
        assert inventory(session, Settings(_env_file=None), "peer", domain=domain)["items"] == []
        with pytest.raises(DomainError):
            repository.get_monitor(session, "peer", monitor)


def test_shared_tender_public_review_does_not_transfer_authenticated_documents(db):
    from datetime import timedelta

    from test_tender_document_observations import item, record
    from test_tender_documents import capture, seed
    from test_tender_matching import NOW as clock

    from helvetic_lens import tender_document_observations as observations
    from helvetic_lens import tender_documents as documents
    from helvetic_lens.tender_review_changes import review_changes
    from helvetic_lens.tender_today import today

    monitor, dossier, grant, _ = seed(db)
    first = capture(db, dossier, grant)
    record(db, dossier, grant, 1, item(db, dossier, first))
    configure(db, "tenders", monitor["id"], now=clock)
    with db.session() as session:
        for actor in ("peer", "viewer"):
            assert tender_repository.get_dossier(session, actor, dossier, now=clock)["sequence"] == 1
            assert len(today(session, actor, now=clock)["items"]) == 1
            with pytest.raises(DomainError):
                documents.read(session, actor, dossier, first, now=clock)
            with pytest.raises(DomainError):
                documents.index(session, actor, dossier, now=clock)
        current = tender_repository.get_dossier(session, "peer", dossier, now=clock)
        tender_repository.record_decision(session, "peer", dossier, version=current["version"],
            sequence=1, decision="bid", key="peer-public-review", now=clock)
        session.commit()
    # Explicitly resume the existing synthetic active-source fixture as creator;
    # sharing itself has paused it and has not granted document access to peers.
    with db.session() as session:
        session.get(business_monitor_sharing.MODELS["tenders"], monitor["id"]).status = "active"
        session.commit()
    second = capture(db, dossier, grant, b"Private updated qualification requirements")
    observation, _ = record(db, dossier, grant, 2, item(db, dossier, second))
    clock += timedelta(minutes=1)
    with db.session() as session:
        own = tender_repository.get_dossier(session, "owner", dossier, now=clock)
        assert own["sequence"] == 2 and own["review_state"] == "needs_review"
        for actor in ("peer", "viewer"):
            assert today(session, actor, now=clock)["items"] == []
            assert tender_repository.list_dossiers(session, actor, monitor["id"], now=clock)["items"] == []
            assert [item["sequence"] for item in tender_repository.version_index(session, actor, dossier, now=clock)["items"]] == [1]
            assert [item["sequence"] for item in tender_repository.dossier_history(session, actor, dossier, now=clock)["items"]] == [1]
            hidden = review_changes(session, actor, dossier, through_sequence=2, reviewed_sequence=1, now=clock)
            assert len(hidden["items"]) == 1 and hidden["items"][0]["available"] is False
            with pytest.raises(DomainError):
                tender_repository.get_dossier(session, actor, dossier, now=clock)
            with pytest.raises(DomainError):
                tender_repository.evidence_version(session, actor, dossier, own["evidence_version_id"], now=clock)
            with pytest.raises(DomainError):
                observations.read_observation(session, actor, dossier, observation, now=clock)
        with pytest.raises(DomainError):
            tender_repository.record_decision(session, "peer", dossier, version=own["version"],
                sequence=2, decision="bid", key="peer-private-denied", now=clock)
