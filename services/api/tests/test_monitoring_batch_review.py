"""Native batch decisions preserve private scope, exact versions and atomicity."""

from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from test_business_item_work import seed
from test_monitoring_evidence_ask import settings
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import business_item_work as work
from helvetic_lens import monitoring_batch_review as batch
from helvetic_lens.business_item_models import BusinessItemWorkEvent
from helvetic_lens.config import DomainError
from helvetic_lens.monitoring_evidence_ask import Record


@pytest.mark.parametrize("domain,decision", [("tenders", "no_bid"), ("ip", "reviewed"), ("auctions", "inspect")])
def test_native_business_preview_explicit_decision_and_retry_conflict(db, domain, decision):
    monitor, item, now, _ = seed(db, domain, shared=False)
    record = Record(domain, monitor, item)
    with db.session() as session:
        before = session.connection().exec_driver_sql("SELECT total_changes()").scalar()
        preview = batch.preview(session, settings(), "owner", [record], now=now, locale="en-CH")
        assert session.connection().exec_driver_sql("SELECT total_changes()").scalar() == before
        binding = preview["items"][0]["binding"]
        assert decision in preview["items"][0]["actions"]
        result = batch.apply(session, settings(), "owner", [(record, binding, decision)], now=now, locale="en-CH")
        assert result["applied"] and result["count"] == 1
        session.commit()
    with db.session() as session:
        current = work.read(session, "owner", domain, monitor, item, now=now)
        assert current["decision"] == decision and len(current["history"]) == 1
        assert current["assigned"] is None
        with pytest.raises(DomainError):
            batch.apply(session, settings(), "owner", [(record, binding, decision)], now=now, locale="en-CH")
        assert session.scalar(select(func.count()).select_from(BusinessItemWorkEvent)) == 1


@pytest.mark.parametrize("domain", ["tenders", "ip", "auctions"])
def test_invalid_choice_scope_locale_duplicate_and_boundaries_do_not_review(db, domain):
    monitor, item, now, _ = seed(db, domain, shared=False)
    record = Record(domain, monitor, item)
    with db.session() as session:
        binding = batch.preview(session, settings(), "owner", [record], now=now, locale="en-CH")["items"][0]["binding"]
        for who, selected, locale, action in [("peer", record, "en-CH", "monitor"),
            ("owner", replace(record, monitor_id="missing"), "en-CH", "monitor"),
            ("owner", record, "de-CH", "monitor"), ("owner", record, "en-CH", "send_bid")]:
            with pytest.raises(DomainError):
                batch.apply(session, settings(), who, [(selected, binding, action)], now=now, locale=locale)
        for records in ([], [record, record], [replace(record, item_id=str(n)) for n in range(21)]):
            with pytest.raises(DomainError):
                batch.preview(session, settings(), "owner", records, now=now, locale="en-CH")
        assert session.scalar(select(func.count()).select_from(BusinessItemWorkEvent)) == 0


def test_late_native_failure_rolls_back_prior_batch_decision(db, monkeypatch):
    from test_tender_matching import NOW
    from test_tender_repository import create, ingest, publication
    records = []
    now = NOW
    for number in range(2):
        monitor = create(db, active=True, key=f"batch-{number}")
        item = ingest(db, monitor, publication())[0]
        records.append(Record("tenders", monitor["id"], item))
    with db.session() as session:
        preview = batch.preview(session, settings(), "owner", records, now=now, locale="en-CH")
        original = batch._act
        calls = []

        def fail_second(*args, **kwargs):
            calls.append(args[2])
            if len(calls) == 2:
                raise DomainError("Synthetic late decision conflict", 409, "test_conflict")
            return original(*args, **kwargs)

        monkeypatch.setattr(batch, "_act", fail_second)
        choices = [(record, item["binding"], "monitor") for record, item in zip(records, preview["items"], strict=True)]
        with pytest.raises(DomainError):
            batch.apply(session, settings(), "owner", choices, now=now, locale="en-CH")
        assert len(calls) == 2
        assert session.scalar(select(func.count()).select_from(BusinessItemWorkEvent)) == 0


@pytest.mark.parametrize("domain", ["tenders", "ip", "auctions"])
def test_new_source_revision_keeps_update_unreviewed(db, domain):
    monitor, item, now, permission = seed(db, domain, shared=False)
    record = Record(domain, monitor, item)
    with db.session() as session:
        previous = batch.preview(session, settings(), "owner", [record], now=now, locale="en-CH")["items"][0]
    if domain == "tenders":
        from test_tender_repository import ingest, publication, revised
        raw = revised(publication())
        raw["project-info"]["title"]["en"] = "Updated official procurement title"
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
    with db.session() as session:
        with pytest.raises(DomainError):
            batch.apply(session, settings(), "owner", [(record, previous["binding"], "monitor")],
                now=now+timedelta(seconds=2), locale="en-CH")
        current = work.read(session, "owner", domain, monitor, item, now=now+timedelta(seconds=2))
        assert current["needs_review"] and not current["history"]


@pytest.mark.parametrize("domain", ["tenders", "ip", "auctions"])
def test_source_withdrawal_rejects_saved_preview(db, domain):
    monitor, item, now, permission = seed(db, domain, shared=False)
    record = Record(domain, monitor, item)
    with db.session() as session:
        binding = batch.preview(session, settings(), "owner", [record], now=now, locale="en-CH")["items"][0]["binding"]
        if domain == "tenders":
            from helvetic_lens.tender_models import TenderDossier
            from helvetic_lens.tender_rights import restrict
            project = session.get(TenderDossier, item).project_id
            restrict(session, scope="project", target_id=project, policy_reference="Synthetic withdrawal", now=now)
        else:
            if domain == "ip":
                from helvetic_lens import trademark_sources as sources
            else:
                from helvetic_lens import auction_sources as sources
            sources.revoke_permission(session, permission, now=now)
        session.commit()
    with db.session() as session:
        with pytest.raises(DomainError):
            batch.apply(session, settings(), "owner", [(record, binding, "monitor")], now=now, locale="en-CH")
        assert session.scalar(select(func.count()).select_from(BusinessItemWorkEvent)) == 0
