"""Owner handover preserves shared decisions and revokes personal access."""

import pytest
from sqlalchemy import delete, func, select, update
from test_business_item_work import act, read, seed
from test_business_monitor_sharing import configure
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import auction_email_preferences, tender_email_preferences, trademark_email_preferences
from helvetic_lens.business_monitor_handover import handover
from helvetic_lens.business_monitor_models import BusinessMonitorScopeEvent
from helvetic_lens.business_monitor_sharing import MODELS
from helvetic_lens.config import DomainError
from helvetic_lens.models import OrganizationMembership, User

EMAIL = {"tenders": tender_email_preferences, "ip": trademark_email_preferences,
         "auctions": auction_email_preferences}


def transfer(db, domain, identifier, now, *, actor="owner", successor="peer", confirmed=True, version=None):
    with db.session() as session:
        row = session.get(MODELS[domain], identifier)
        result = handover(session, actor, domain, identifier, expected_version=version or row.version,
            successor_user_id=successor, confirmed=confirmed, now=now)
        session.commit()
        return result


@pytest.mark.parametrize("domain", EMAIL)
def test_handover_and_owner_erasure_preserve_native_work_without_email_consent(db, domain):
    data = seed(db, domain)
    identifier, _, now, _ = data
    chosen = {"tenders": "no_bid", "ip": "counsel", "auctions": "inspect"}[domain]
    previous = act(db, domain, data, decision=chosen, comment="Retained shared decision")
    with db.session() as session:
        session.get(User, "owner").email_verified_at = now
        row = session.get(MODELS[domain], identifier)
        EMAIL[domain].configure(session, "owner", identifier, expected_version=row.version,
            configuration={"delivery": {"email": "immediate"}}, consent=True, now=now)
        session.commit()
    result = transfer(db, domain, identifier, now)
    assert result["creator"]["id"] == "peer" and result["responsible"]["id"] == "peer"
    event = result["history"][0]
    assert event["action"] == "handover"
    assert event["previous_owner"]["id"] == "owner" and event["owner"]["id"] == "peer"
    assert not result["can_change_scope"]
    with db.session() as session:
        current = EMAIL[domain].view(session, "peer", identifier)
        assert not current["consent_active"] and current["configuration"]["delivery"]["email"] == "off"
        with pytest.raises(DomainError):
            EMAIL[domain].view(session, "owner", identifier)
        session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == "owner"))
        session.execute(delete(User).where(User.id == "owner"))
        session.commit()
    retained = read(db, domain, data, user="peer")
    assert retained["decision"] == previous["decision"] and not retained["needs_review"]
    assert retained["history"][0]["comment"] == "Retained shared decision"
    assert retained["history"][0]["actor"] is None
    with db.session() as session:
        row = session.get(MODELS[domain], identifier)
        assert row is not None and row.owner_user_id == "peer"
        assert row.status == "paused"


@pytest.mark.parametrize("domain", EMAIL)
def test_handover_refuses_wrong_owner_role_scope_and_stale_revision_atomically(db, domain):
    data = seed(db, domain)
    identifier, _, now, _ = data
    with db.session() as session:
        before = session.get(MODELS[domain], identifier).version
        count = session.scalar(select(func.count()).select_from(BusinessMonitorScopeEvent))
    for kwargs in ({"confirmed": False}, {"actor": "peer"}, {"actor": "viewer"},
                   {"successor": "viewer"}, {"successor": "missing"}, {"successor": "owner"},
                   {"version": before + 1}):
        with pytest.raises(DomainError):
            transfer(db, domain, identifier, now, **kwargs)
    with db.organization_context("org-b"), pytest.raises(DomainError):
        transfer(db, domain, identifier, now, version=before)
    with db.session() as session:
        session.execute(update(User).where(User.id == "peer").values(active=False))
        session.commit()
    with pytest.raises(DomainError):
        transfer(db, domain, identifier, now)
    with db.session() as session:
        row = session.get(MODELS[domain], identifier)
        assert row.owner_user_id == "owner" and row.version == before
        assert session.scalar(select(func.count()).select_from(BusinessMonitorScopeEvent)) == count


@pytest.mark.parametrize("domain", EMAIL)
def test_private_monitor_cannot_be_handed_over_without_explicit_sharing(db, domain):
    identifier, _, now, _ = seed(db, domain, shared=False)
    with pytest.raises(DomainError):
        transfer(db, domain, identifier, now)
    with db.session() as session:
        row = session.get(MODELS[domain], identifier)
        assert row.owner_user_id == "owner" and row.visibility == "private"


def test_tender_handover_does_not_transfer_old_authenticated_document_access(db):
    from test_tender_documents import NOW, capture
    from test_tender_documents import seed as documents_seed

    from helvetic_lens import tender_documents as documents
    from helvetic_lens.tender_models import TenderDocumentAccess, TenderDocumentSnapshot
    monitor, dossier, grant, _ = documents_seed(db)
    snapshot = capture(db, dossier, grant)
    configure(db, "tenders", monitor["id"], version=monitor["version"], now=NOW)
    transfer(db, "tenders", monitor["id"], NOW)
    with db.session() as session:
        assert documents.index(session, "peer", dossier, now=NOW)["items"] == []
        with pytest.raises(DomainError):
            documents.read(session, "peer", dossier, snapshot, now=NOW)
        assert session.get(TenderDocumentAccess, grant).revoked_at is not None
        assert session.get(TenderDocumentSnapshot, snapshot).body == b"3 references required"
