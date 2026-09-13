import pytest
import test_tender_repository as persistence
from sqlalchemy import func, select
from test_tender_matching import NOW, PROJECT
from test_tender_repository import create, ingest, parsed, publication, read, revised

from helvetic_lens import tender_repository as tenders
from helvetic_lens.tender_models import TenderDossierVersion
from helvetic_lens.tender_observations import observe_publication
from helvetic_lens.tender_rights import SourceRestricted, restrict

db = persistence.db
template = persistence.template


@pytest.mark.parametrize("scope", ["project", "publication"])
def test_current_restriction_blocks_detail_original_and_list_after_evidence_was_saved(db, scope):
    monitor, raw = create(db, active=True), publication()
    (dossier,) = ingest(db, monitor, raw)
    item = read(db, dossier)
    with db.session() as session:
        restrict(
            session,
            scope=scope,
            target_id=PROJECT if scope == "project" else raw["id"],
            policy_reference="local-test-withdrawal",
            now=NOW,
        )
        session.commit()
    with db.session() as session:
        with pytest.raises(SourceRestricted):
            tenders.get_dossier(session, "owner", dossier, now=NOW)
        with pytest.raises(SourceRestricted):
            tenders.evidence_version(session, "owner", dossier, item["evidence_version_id"], now=NOW)
        with pytest.raises(SourceRestricted):
            tenders.record_decision(
                session,
                "owner",
                dossier,
                version=item["version"],
                sequence=item["sequence"],
                decision="bid",
                key="blocked",
                now=NOW,
            )
        assert tenders.list_dossiers(session, "owner", monitor["id"], now=NOW)["items"] == []
        assert tenders.version_index(session, "owner", dossier, now=NOW)["items"] == []
        assert tenders.dossier_history(session, "owner", dossier, now=NOW)["items"] == []
        with pytest.raises(SourceRestricted):
            observe_publication(session, monitor["id"], parsed(raw), now=NOW)
        assert session.scalar(select(func.count()).select_from(TenderDossierVersion)) == 1


def test_one_restricted_old_publication_does_not_hide_other_permitted_versions(db):
    monitor, raw = create(db, active=True), publication()
    (dossier,) = ingest(db, monitor, raw)
    changed = revised(raw)
    ingest(db, monitor, changed)
    with db.session() as session:
        restrict(session, scope="publication", target_id=raw["id"], policy_reference="withdraw-old", now=NOW)
        session.commit()
        assert tenders.get_dossier(session, "owner", dossier, now=NOW)["publication_id"] == changed["id"]
        assert len(tenders.list_dossiers(session, "owner", monitor["id"], now=NOW)["items"]) == 1
        assert [
            item["publication_id"]
            for item in tenders.version_index(session, "owner", dossier, now=NOW)["items"]
        ] == [changed["id"]]


def test_new_publication_cannot_reuse_a_restricted_old_original_for_a_diff(db):
    monitor, raw = create(db, active=True), publication()
    ingest(db, monitor, raw)
    with db.session() as session:
        restrict(
            session,
            scope="publication",
            target_id=raw["id"],
            policy_reference="withdraw-before-change",
            now=NOW,
        )
        session.commit()
        with pytest.raises(SourceRestricted):
            observe_publication(session, monitor["id"], parsed(revised(raw)), now=NOW)
        session.commit()
        assert session.scalar(select(func.count()).select_from(TenderDossierVersion)) == 1
