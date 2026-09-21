"""SIMAP 1.5.1 specific-lot abandonment, based on the public IWB contract."""

from copy import deepcopy

import pytest
from sqlalchemy import select
from test_tender_matching import LOT_A, LOT_B, NOW, facts_from_publication, match_lot, profile, record, source
from test_tender_repository import create, decide, ingest, parsed, publication, read, revised
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import tender_repository
from helvetic_lens.tender_models import TenderDossierVersion
from helvetic_lens.tender_observations import observe_publication


def abandonment(raw):
    result = deepcopy(raw)
    result["type"] = result["base"]["type"] = "abandonment"
    result["abandonedLot"] = result.pop("lots")[0]
    result["base"]["referencingLotId"] = result["abandonedLot"]["id"]
    result["abandonment"] = {"reasons": ["d_offers_do_not_allow_economical_procurement"]}
    for key in ("dates", "procurement", "terms"):
        result.pop(key, None)
    return result


def test_abandoned_lot_retains_exact_evidence_without_borrowing_umbrella_facts():
    raw = abandonment(source(lots=True))
    # Neither an office address nor extra umbrella procurement describes this lot.
    raw["procurement"] = {"cpvCode": {"code": "72000000"}}
    original = deepcopy(raw)
    checked = record(raw)
    (item,) = facts_from_publication(checked, now=NOW)
    assert item.lot_id == LOT_A and item.phase == "cancelled"
    assert item.text[0].locator == "/abandonedLot/title/en"
    assert item.evidence_sha256 == checked["evidence_sha256"]
    assert item.contract_canton is None and item.contract_country is None
    assert item.cpv_codes is None and item.project_cpv_codes is None
    assert item.qualification_coverage == "unknown"
    assessment = match_lot(profile(), item, now=NOW)
    assert assessment["verdict"] == "excluded"
    assert "discovery_phase_closed" in {reason["code"] for reason in assessment["exclusions"]}
    assert raw == original


@pytest.mark.parametrize("bad", [
    "type", "scope", "lot", "lots", "reference", "bad_reference", "empty", "scalar", "project_lots",
])
def test_abandoned_lot_rejects_conflicting_or_unidentified_scope(bad):
    raw = abandonment(source(lots=True))
    if bad == "type":
        raw["type"] = raw["base"]["type"] = "tender"
    elif bad == "scope":
        raw["base"]["lotsType"] = "without"
    elif bad == "lot":
        raw["lot"] = deepcopy(raw["abandonedLot"])
    elif bad == "lots":
        raw["lots"] = [deepcopy(raw["abandonedLot"])]
    elif bad == "reference":
        raw["base"]["referencingLotId"] = LOT_B
    elif bad == "bad_reference":
        raw["base"]["referencingLotId"] = "not-a-uuid"
    elif bad == "empty":
        raw["abandonedLot"] = {}
    elif bad == "project_lots":
        raw["lots"] = [raw["abandonedLot"]]
        raw["abandonedLot"] = raw["base"]["referencingLotId"] = None
    else:
        raw["abandonedLot"] = "unexpected"
    with pytest.raises(ValueError):
        facts_from_publication(record(raw), now=NOW)


def test_abandonment_changes_only_the_named_followed_lot_and_keeps_original_history(db):
    monitor = create(db, active=True)
    initial = publication(lots=True)
    initial["lots"][1]["title"]["en"] = "Software development for the second lot"
    first, sibling = ingest(db, monitor, initial)
    decide(db, read(db, first))
    before_sibling = read(db, sibling)
    changed = abandonment(revised(initial))
    original = deepcopy(changed)
    assert ingest(db, monitor, changed) == [first]
    item = read(db, first)
    assert item["material"]["phase"]["value"] == "cancelled"
    assert item["material"]["title"]["locator"] == "/abandonedLot/title"
    assert item["review_state"] == "needs_review"
    assert read(db, sibling) == before_sibling
    assert changed == original
    assert ingest(db, monitor, changed) == []
    with db.session() as session:
        versions = list(session.scalars(select(TenderDossierVersion).where(
            TenderDossierVersion.dossier_id == first).order_by(TenderDossierVersion.sequence)))
        assert len(versions) == 2
        assert versions[0].material["phase"]["value"] == "open"
        assert versions[1].source_hash == parsed(changed)["evidence_sha256"]
        evidence = tender_repository.evidence_version(
            session, "owner", first, item["evidence_version_id"], now=NOW)
        assert evidence["original"] == changed


def test_whole_project_cancellation_uses_only_existing_permitted_dossiers(db):
    monitor = create(db, active=True)
    initial = publication(lots=True)
    initial["lots"][1]["title"]["en"] = "Software development for the second lot"
    first, second = ingest(db, monitor, initial)
    other = create(db, active=True, key="separate-monitor")
    other_first = ingest(db, other, initial)[0]
    other_before = read(db, other_first)
    with db.organization_context("org-b"):
        foreign = create(db, active=True, key="other-organization")
        foreign_first = ingest(db, foreign, initial)[0]
        foreign_before = read(db, foreign_first)
    changed = abandonment(revised(initial))
    changed["abandonedLot"] = changed["base"]["referencingLotId"] = None
    assert facts_from_publication(parsed(changed), now=NOW) == ()
    # Search/header work can constrain an update to an exact known lot.
    with db.session() as session:
        assert observe_publication(session, monitor["id"], parsed(changed), now=NOW,
                                   allowed_lot_ids={LOT_A}) == [first]
        session.commit()
    assert read(db, first)["material"]["phase"]["value"] == "cancelled"
    assert read(db, second)["material"]["phase"]["value"] == "open"
    assert ingest(db, monitor, changed) == [second]
    assert ingest(db, monitor, changed) == []
    item = read(db, second)
    assert item["material"]["phase"]["value"] == "cancelled"
    assert item["material"]["title"]["coverage"] == "unknown"
    assert item["material"]["title"]["locator"] == "/abandonedLot"
    assert item["material"]["procurement"]["coverage"] == "unknown"
    assert item["material"]["title"]["value"] is None
    assert read(db, other_first) == other_before
    empty = create(db, active=True, key="no-existing-lots")
    assert ingest(db, empty, changed) == []
    with db.organization_context("org-b"):
        assert ingest(db, monitor, changed) == []
        assert read(db, foreign_first) == foreign_before


def test_project_abandonment_cannot_supply_unbounded_or_conflicting_lot_identity():
    raw = abandonment(source(lots=True))
    raw["abandonedLot"] = raw["base"]["referencingLotId"] = None
    with pytest.raises(ValueError, match="Too many"):
        facts_from_publication(record(raw), now=NOW, existing_lot_ids=[LOT_A] * 1001)
    with pytest.raises(ValueError):
        facts_from_publication(record(raw), now=NOW, existing_lot_ids=["invalid"])
    raw["base"]["referencingLotId"] = LOT_A
    with pytest.raises(ValueError, match="omits"):
        facts_from_publication(record(raw), now=NOW)
