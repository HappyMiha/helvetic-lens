"""Real native sources/decisions, no external submission or mailer."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from test_business_monitor_sharing import configure
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import business_item_work as work
from helvetic_lens.business_item_models import BusinessItemWorkEvent as Event
from helvetic_lens.config import DomainError
from helvetic_lens.models import User

DOMAINS = ("tenders", "ip", "auctions")


def seed(db, domain, *, shared=True):
    if domain == "tenders":
        from test_tender_matching import NOW
        from test_tender_repository import create, ingest, publication
        monitor = create(db, active=True)
        item = ingest(db, monitor, publication())[0]
        monitor, version, permission = monitor["id"], 1, None
    elif domain == "ip":
        from test_trademark_sources import NOW
        from test_trademark_workflow import rows, running
        permission, monitor = running(db)
        item, version = rows(db, monitor)[0]["id"], 2
    else:
        from test_auction_rules import NOW
        from test_auction_workflow import running, view
        permission, monitor = running(db)
        item, version = view(db, monitor)["id"], 2
    if shared:
        configure(db, domain, monitor, version=version, now=NOW)
    return monitor, item, NOW, permission


def read(db, domain, seed, user="owner", **kwargs):
    monitor, item, now, _ = seed
    with db.session() as session:
        return work.read(session, user, domain, monitor, item, now=now, **kwargs)


def act(db, domain, seed, *, user="owner", snapshot=None, assigned="peer", comment="Check evidence", decision=None):
    monitor, item, now, _ = seed
    snapshot = snapshot or read(db, domain, seed, user)
    with db.session() as session:
        result = work.act(session, user, domain, monitor, item, now=now,
            expected_version=snapshot["version"], expected_binding=snapshot["binding"],
            assigned_user_id=assigned, comment=comment, decision=decision)
        session.commit()
        return result


@pytest.mark.parametrize("domain", DOMAINS)
def test_assignment_note_and_native_decision_are_separate_atomic_actions(db, domain):
    data = seed(db, domain)
    initial = read(db, domain, data)
    assert initial["can_write"] and initial["needs_review"] and initial["history"] == []
    note = act(db, domain, data, comment="  Ask colleague\nfor evidence  ")
    assert note["needs_review"] and note["decision"] is None
    assert note["assigned"]["id"] == "peer" and note["version"] == initial["version"] + 1
    assert note["history"][0]["comment"] == "Ask colleague\nfor evidence"
    assert note["history"][0]["binding"] == initial["binding"]
    chosen = {"tenders": "no_bid", "ip": "counsel", "auctions": "inspect"}[domain]
    result = act(db, domain, data, user="peer", decision=chosen, comment="Reviewed this exact evidence")
    assert result["decision"] == chosen and not result["needs_review"]
    assert result["history"][0]["decision"] == chosen
    assert result["history"][0]["actor"]["id"] == "peer"
    assert result["history"][0]["assigned"]["id"] == "peer"
    assert result["history"][1]["decision"] is None
    assert result["history"][1]["comment"] == note["history"][0]["comment"]
    # A new comment with the same decision must not be discarded as a no-op.
    again = act(db, domain, data, decision=chosen, comment="Additional reasoning", assigned=None)
    assert len(again["history"]) == 3 and again["assigned"] is None
    assert again["history"][1]["assigned"]["id"] == "peer"
    page = read(db, domain, data, limit=1)
    older = read(db, domain, data, limit=1, before_version=page["next_before_version"])
    assert older["history"][0]["version"] == result["version"]
    viewer = read(db, domain, data, user="viewer")
    assert not viewer["can_write"] and len(viewer["history"]) == 3


@pytest.mark.parametrize("domain", DOMAINS)
def test_stale_colleague_and_invalid_input_cannot_overwrite_or_leave_audit(db, domain):
    data = seed(db, domain)
    old = read(db, domain, data)
    saved = act(db, domain, data)
    with pytest.raises(DomainError):
        act(db, domain, data, snapshot=old, user="peer", assigned="owner", comment="stale")
    for override in ({"assigned": "viewer"}, {"assigned": "missing"}, {"comment": "x" * 4001},
                     {"comment": "bad\x00text"}, {"user": "viewer"}, {"decision": "external_bid"}):
        with pytest.raises(DomainError):
            act(db, domain, data, **override)
    forged = {**saved, "binding": {**saved["binding"], "fingerprint": "0" * 64}}
    with pytest.raises(DomainError):
        act(db, domain, data, snapshot=forged)
    assert read(db, domain, data) == saved
    with db.organization_context("org-b"), pytest.raises(DomainError):
        read(db, domain, data)


@pytest.mark.parametrize("domain", DOMAINS)
def test_private_scope_and_inactive_assignee_preserve_unresolved_history(db, domain):
    data = seed(db, domain, shared=False)
    with pytest.raises(DomainError):
        act(db, domain, data, assigned="peer")
    with pytest.raises(DomainError):
        read(db, domain, data, user="peer")
    own = act(db, domain, data, assigned="owner")
    assert own["needs_review"]
    configure(db, domain, data[0], version=1 if domain == "tenders" else 2, now=data[2])
    with db.session() as session:
        session.get(User, "owner").active = False
        session.commit()
    inherited = read(db, domain, data, user="peer")
    assert inherited["assigned"]["available"] is False and inherited["needs_review"]
    reassigned = act(db, domain, data, user="peer", assigned="peer", comment="Take over unresolved work")
    assert reassigned["assigned"]["available"] and reassigned["needs_review"]
    assert reassigned["history"][1]["assigned"]["id"] == "owner"
    with db.session() as session:
        session.get(User, "owner").active = True
        session.commit()
    configure(db, domain, data[0], version=2 if domain == "tenders" else 3,
        scope="private", responsible=None, now=data[2])
    with pytest.raises(DomainError):
        read(db, domain, data, user="peer")


@pytest.mark.parametrize("domain", DOMAINS)
def test_failed_audit_rolls_back_assignment_and_native_decision(db, domain, monkeypatch):
    data = seed(db, domain)
    initial = read(db, domain, data)
    monkeypatch.setattr(work, "MAX_EVENTS", 0)
    decision = {"tenders": "bid", "ip": "relevant", "auctions": "inspect"}[domain]
    monitor, item, now, _ = data
    with db.session() as session:
        with pytest.raises(DomainError):
            work.act(session, "owner", domain, monitor, item, now=now,
                expected_version=initial["version"], expected_binding=initial["binding"],
                assigned_user_id="peer", comment="must rollback", decision=decision)
        # Prove even a caller that commits after catching the domain error cannot
        # preserve a partial owner/decision write.
        session.commit()
    assert read(db, domain, data) == initial
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 0


@pytest.mark.parametrize("domain", ("ip", "auctions"))
def test_revoked_source_withholds_comments_and_rejects_more_work(db, domain):
    data = seed(db, domain)
    act(db, domain, data, comment="source-derived private comment")
    if domain == "ip":
        from helvetic_lens import trademark_sources as sources
    else:
        from helvetic_lens import auction_sources as sources
    with db.session() as session:
        sources.revoke_permission(session, data[3], now=data[2])
        session.commit()
    result = read(db, domain, data, user="peer")
    assert result["state"] == "unavailable" and result["history"] == [] and not result["can_write"]
    assert result["assigned"] is None
    with pytest.raises(DomainError):
        act(db, domain, data)


@pytest.mark.parametrize("domain", DOMAINS)
def test_native_assignment_filters_and_material_reopening_preserve_old_notes(db, domain):
    data = seed(db, domain, shared=False)
    monitor, item, now, permission = data
    chosen = {"tenders": "bid", "ip": "relevant", "auctions": "inspect"}[domain]
    decided = act(db, domain, data, assigned="owner", decision=chosen, comment="Old evidence rationale")
    if domain == "tenders":
        from test_tender_repository import ingest, publication, revised

        from helvetic_lens import tender_repository as repository
        raw = revised(publication())
        raw["project-info"]["title"]["en"] = "Material changed tender title"
        ingest(db, {"id": monitor}, raw)
        listing = repository.list_dossiers
    elif domain == "ip":
        from test_trademark_sources import accept
        from test_trademark_workflow import source_facts, sync

        from helvetic_lens import trademark_workflow as workflow
        accept(db, permission, cursor=1, facts=source_facts(owners=["Changed Owner AG"]))
        sync(db, monitor, now + timedelta(seconds=1))
        listing = workflow.list_candidates
    else:
        from test_auction_sources import accept
        from test_auction_workflow import sync

        from helvetic_lens import auction_workflow as workflow
        accept(db, permission, cursor=1, ends_at=now + timedelta(days=10))
        sync(db, monitor, now=now + timedelta(seconds=1))
        listing = workflow.list_items
    current_data = monitor, item, now + timedelta(seconds=2), permission
    current = read(db, domain, current_data)
    assert current["needs_review"] and current["decision"] == chosen
    assert current["assigned"]["id"] == "owner"
    assert current["history"][0]["comment"] == "Old evidence rationale"
    assert current["history"][0]["binding"] == decided["binding"]
    assert current["history"][0]["older_evidence"]
    with pytest.raises(DomainError):
        act(db, domain, current_data, snapshot=decided, assigned="owner", decision=chosen)
    with db.session() as session:
        assert [r["id"] for r in listing(session, "owner", monitor, now=current_data[2], assignment="mine")["items"]] == [item]
        assert listing(session, "owner", monitor, now=current_data[2], assignment="unassigned")["items"] == []
        with pytest.raises(DomainError):
            listing(session, "owner", monitor, now=current_data[2], assignment="invented")
    unassigned = act(db, domain, current_data, assigned=None, comment="Unresolved; reassign")
    assert unassigned["needs_review"]
    with db.session() as session:
        assert listing(session, "owner", monitor, now=current_data[2], assignment="mine")["items"] == []
        assert [r["id"] for r in listing(session, "owner", monitor, now=current_data[2], assignment="unassigned")["items"]] == [item]


def test_tender_historical_document_comment_cannot_leak_when_latest_is_public(db):
    from test_tender_document_observations import item as document_item
    from test_tender_document_observations import record
    from test_tender_documents import capture
    from test_tender_documents import seed as documents_seed
    from test_tender_matching import NOW
    from test_tender_repository import ingest, revised
    monitor, dossier, grant, raw = documents_seed(db)
    first = capture(db, dossier, grant)
    record(db, dossier, grant, 1, document_item(db, dossier, first))
    second = capture(db, dossier, grant, b"Private requirements: 5 references")
    record(db, dossier, grant, 2, document_item(db, dossier, second))
    data = monitor["id"], dossier, NOW + timedelta(minutes=1), None
    private = act(db, "tenders", data, assigned="owner", comment="Personal authenticated document reasoning", decision="bid")
    assert private["binding"]["sequence"] == 2
    public = revised(raw)
    public["project-info"]["title"]["en"] = "Public subsequent qualification update"
    ingest(db, monitor, public)
    configure(db, "tenders", monitor["id"], now=data[2])
    own = read(db, "tenders", data)
    assert own["state"] == "available" and own["history"][0]["comment"] == "Personal authenticated document reasoning"
    peer = read(db, "tenders", data, user="peer")
    assert peer["state"] == "available"
    assert peer["history"][0] == {"id": own["history"][0]["id"], "version": private["version"], "state": "unavailable"}
    assert "reasoning" not in str(peer)


@pytest.mark.parametrize("domain", DOMAINS)
def test_legacy_native_decision_entry_points_append_owner_and_evidence(db, domain):
    data = seed(db, domain, shared=False)
    monitor, item, now, _ = data
    act(db, domain, data, assigned="owner", comment="Assigned before legacy action")
    if domain == "tenders":
        from test_tender_repository import decide
        from test_tender_repository import read as dossier
        decide(db, dossier(db, item))
    elif domain == "ip":
        from test_trademark_workflow import review
        review(db, monitor)
    else:
        from test_auction_workflow import action
        action(db, monitor, decision="inspect")
    result = read(db, domain, data)
    assert result["history"][0]["assigned"]["id"] == "owner"
    assert result["history"][0]["comment"] == ""
    assert result["history"][0]["actor"]["id"] == "owner"
    assert result["history"][0]["decision"] in work.DECISIONS[domain]


def test_auction_stop_following_survives_full_work_history_and_revoked_source(db, monkeypatch):
    from test_auction_workflow import action

    from helvetic_lens import auction_sources
    data = seed(db, "auctions", shared=False)
    monitor, _, now, permission = data
    action(db, monitor, following=True)
    with db.session() as session:
        auction_sources.revoke_permission(session, permission, now=now)
        session.commit()
    monkeypatch.setattr(work, "MAX_EVENTS", 0)
    assert action(db, monitor, following=False)["following"] is False
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 0
