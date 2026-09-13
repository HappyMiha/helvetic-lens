import copy
from uuid import uuid4

import pytest
import test_tender_repository as persistence
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from test_tender_matching import NOW, profile
from test_tender_repository import create, ingest, parsed, publication, read, revised

from helvetic_lens import tender_repository as tenders
from helvetic_lens.config import DomainError
from helvetic_lens.tender_models import (
    TenderDossierVersion,
    TenderMaterialSection,
    TenderPublicationSnapshot,
    TenderVersionSection,
)
from helvetic_lens.tender_observations import observe_publication

db = persistence.db
template = persistence.template


def many_lots():
    raw = publication(lots=True)
    raw["lots"] = [
        {"id": str(uuid4()), "title": {"en": f"Software development {index}"}, "projectSubType": "service"}
        for index in range(12)
    ]
    return raw


def test_public_original_and_common_terms_are_shared_across_lots_but_keep_exact_locators(db):
    monitor = create(db, active=True)
    raw = many_lots()
    dossiers = ingest(db, monitor, raw)
    assert len(dossiers) == 12
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(TenderPublicationSnapshot)) == 1
        terms = list(
            session.scalars(select(TenderVersionSection).where(TenderVersionSection.name == "terms"))
        )
        assert len(terms) == 12 and len({item.section_id for item in terms}) == 1
        for index, dossier in enumerate(dossiers):
            item = tenders.get_dossier(session, "owner", dossier, now=NOW)
            assert item["material"]["title"]["locator"] == f"/lots/{index}/title"
            assert item["material"]["title"]["value"] == {"en": f"Software development {index}"}
            assert (
                tenders.evidence_version(session, "owner", dossier, item["evidence_version_id"], now=NOW)[
                    "original"
                ]
                == raw
            )


def test_revision_keeps_old_common_terms_and_shared_original_immutable(db):
    monitor = create(db, active=True)
    raw = many_lots()
    dossiers = ingest(db, monitor, raw)
    original = read(db, dossiers[0])
    changed = revised(raw)
    changed["terms"]["termsCriteria"][0]["description"]["en"] = "4 references required"
    ingest(db, monitor, changed)
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(TenderPublicationSnapshot)) == 2
        terms = session.scalars(select(TenderVersionSection).where(TenderVersionSection.name == "terms"))
        assert len({item.section_id for item in terms}) == 2
        history = tenders.dossier_history(session, "owner", dossiers[0], now=NOW)["items"]
        assert history[1]["material"] == original["material"]
        assert history[0]["material"]["terms"] != original["material"]["terms"]
        assert (
            tenders.evidence_version(session, "owner", dossiers[0], original["evidence_version_id"], now=NOW)[
                "original"
            ]
            == raw
        )


def test_cross_tenant_reuse_never_shares_private_versions_or_references(db):
    first = create(db, active=True)
    raw = publication()
    (first_dossier,) = ingest(db, first, raw)
    with db.organization_context("org-b"), db.session() as session:
        second = tenders.create_profile(session, "owner", profile().model_dump(mode="json"), "org-b")
        from helvetic_lens.tender_models import TenderMonitor

        session.get(TenderMonitor, second["id"]).status = "active"
        session.flush()
        (second_dossier,) = observe_publication(session, second["id"], parsed(raw), now=NOW)
        session.commit()
        assert session.scalar(select(func.count()).select_from(TenderPublicationSnapshot)) == 1
        assert {item.organization_id for item in session.scalars(select(TenderVersionSection))} == {"org-b"}
        assert session.scalar(select(func.count()).select_from(TenderDossierVersion)) == 1
        with pytest.raises(DomainError) as failure:
            tenders.get_dossier(session, "owner", first_dossier, now=NOW)
        assert failure.value.status == 404
    with db.session() as session:
        assert {item.organization_id for item in session.scalars(select(TenderVersionSection))} == {"org-a"}
        with pytest.raises(DomainError):
            tenders.get_dossier(session, "owner", second_dossier, now=NOW)
        with pytest.raises(DomainError):
            tenders.get_dossier(session, "peer", first_dossier, now=NOW)


@pytest.mark.parametrize("model", [TenderPublicationSnapshot, TenderMaterialSection])
def test_referenced_public_evidence_cannot_be_deleted(db, model):
    monitor = create(db, active=True)
    ingest(db, monitor, publication())
    with db.session() as session:
        with pytest.raises(IntegrityError):
            session.execute(delete(model))
        session.rollback()


@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_incomplete_or_mutated_normalized_evidence_is_rejected(db, damage):
    monitor = create(db, active=True)
    (dossier,) = ingest(db, monitor, publication())
    with db.session() as session:
        field = session.scalar(select(TenderVersionSection).where(TenderVersionSection.name == "terms"))
        if damage == "missing":
            session.delete(field)
        else:
            data = copy.deepcopy(field.section.data)
            data["value"] = "Altered terms"
            field.section.data = data
        session.commit()
    with db.session() as session:
        with pytest.raises(DomainError) as failure:
            tenders.get_dossier(session, "owner", dossier, now=NOW)
        assert failure.value.code == "tender_evidence_invalid"
