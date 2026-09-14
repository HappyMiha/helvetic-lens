"""Selected historic source versions remain exact after a native source update."""

from datetime import timedelta

import pytest
from sqlalchemy import select
from test_business_item_work import seed
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import monitoring_evidence_versions as versions
from helvetic_lens.config import DomainError


def fixture(db, monkeypatch, domain, *, export=True):
    if domain != "tenders":
        if domain == "ip":
            import test_trademark_workflow as fixtures
        else:
            import test_auction_workflow as fixtures
        grant = fixtures.grant
        monkeypatch.setattr(fixtures, "grant", lambda *args, **kwargs: grant(*args, export_allowed=export, **kwargs))
    return seed(db, domain, shared=False)


def read(db, domain, data, *, user="owner", revision=None, now=None):
    monitor, item, when, _ = data
    with db.session() as session:
        return (versions.tender(session, user, monitor, item, revision_id=revision, now=now or when)
            if domain == "tenders" else
            versions.licensed(session, user, domain, monitor, item, revision_id=revision, now=now or when))


def advance(db, domain, data):
    monitor, _, now, permission = data
    if domain == "tenders":
        from test_tender_repository import ingest, publication, revised
        raw = revised(publication())
        raw["project-info"]["title"]["en"] = "Changed official procurement title"
        ingest(db, {"id": monitor}, raw)
    elif domain == "ip":
        from test_trademark_sources import accept
        from test_trademark_workflow import source_facts, sync
        accept(db, permission, cursor=1, facts=source_facts(owners=["Changed Owner AG"]))
        sync(db, monitor, now + timedelta(seconds=1))
    else:
        from test_auction_sources import accept
        from test_auction_workflow import sync
        accept(db, permission, cursor=1, ends_at=now + timedelta(days=10))
        sync(db, monitor, now=now + timedelta(seconds=1))


@pytest.mark.parametrize("domain", ("tenders", "ip", "auctions"))
def test_selected_old_version_never_becomes_the_new_current_head(db, monkeypatch, domain):
    data = fixture(db, monkeypatch, domain)
    before = read(db, domain, data)
    advance(db, domain, data)
    when = data[2] + timedelta(seconds=2)
    current = read(db, domain, data, now=when)
    selected = read(db, domain, data, revision=before["selected_revision_id"], now=when)
    assert current["sequence"] > selected["sequence"]
    assert selected["after"] == before["after"]
    assert selected["before"] == before["before"]
    assert selected["newer_available"]
    assert current["before"] == selected["after"]
    assert "original" not in selected["after"]["facts"]
    with pytest.raises(DomainError):
        read(db, domain, data, user="peer", revision=before["selected_revision_id"], now=when)
    with pytest.raises(DomainError) as missing:
        read(db, domain, data, revision="missing", now=when)
    assert missing.value.status == 404


@pytest.mark.parametrize("domain", ("ip", "auctions"))
def test_display_permission_does_not_grant_export(db, monkeypatch, domain):
    data = fixture(db, monkeypatch, domain, export=False)
    with pytest.raises(DomainError) as denied:
        read(db, domain, data)
    assert denied.value.status == 403


@pytest.mark.parametrize("domain", ("ip", "auctions"))
def test_revoked_export_permission_also_removes_historical_snapshot(db, monkeypatch, domain):
    data = fixture(db, monkeypatch, domain)
    before = read(db, domain, data)
    if domain == "ip":
        from helvetic_lens import trademark_sources as sources
    else:
        from helvetic_lens import auction_sources as sources
    with db.session() as session:
        sources.revoke_permission(session, data[3], now=data[2])
        session.commit()
    with pytest.raises(DomainError):
        read(db, domain, data, revision=before["selected_revision_id"])


@pytest.mark.parametrize("domain", ("tenders", "ip", "auctions"))
def test_corrupt_historical_profile_cannot_borrow_current_configuration(db, monkeypatch, domain):
    data = fixture(db, monkeypatch, domain)
    before = read(db, domain, data)
    if domain == "tenders":
        from helvetic_lens.tender_models import TenderProfileRevision as Revision
    elif domain == "ip":
        from helvetic_lens.trademark_models import TrademarkConfigurationRevision as Revision
    else:
        from helvetic_lens.auction_models import AuctionConfigurationRevision as Revision
    with db.session() as session:
        revision = session.scalar(select(Revision).where(Revision.monitor_id == data[0],
            Revision.revision == before["profile_revision"]))
        revision.configuration_hash = "0" * 64
        session.commit()
    with pytest.raises(DomainError) as denied:
        read(db, domain, data, revision=before["selected_revision_id"])
    assert denied.value.status == 503


def test_private_simap_document_revision_is_not_a_public_evidence_download(db):
    from test_tender_document_observations import item, record
    from test_tender_documents import capture, seed
    from test_tender_matching import NOW

    monitor, dossier, grant, _ = seed(db)
    data = monitor["id"], dossier, NOW, None
    public = read(db, "tenders", data)
    record(db, dossier, grant, 1, item(db, dossier, capture(db, dossier, grant)))
    record(db, dossier, grant, 2, item(db, dossier, capture(db, dossier, grant, b"Private changed document text")))
    with pytest.raises(DomainError) as denied:
        read(db, "tenders", data, now=NOW + timedelta(seconds=60))
    assert denied.value.code == "monitoring_export_authenticated_documents_excluded"
    previous = read(db, "tenders", data, revision=public["selected_revision_id"], now=NOW + timedelta(seconds=60))
    assert previous["after"] == public["after"]
