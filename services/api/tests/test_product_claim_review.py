"""Explicit human decisions on fictional retained claims, with live auth boundaries."""
import copy
import json
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_product_dossiers import ROOT, post
from test_product_dossiers import signed as signed
from test_product_entity_identity import QUOTE
from test_product_entity_identity import seed as entities
from test_product_guests import accept, guest, invitation
from test_product_teams import switch

from helvetic_lens.product_investigation_models import (
    ClaimChange,
    ClaimEvidence,
    ClaimReview,
    DossierClaim,
    Investigation,
    InvestigationSource,
)
from helvetic_lens.product_investigations import scope
from helvetic_lens.product_models import DossierEntry, DossierMember, ProductPublication, PublicContribution


def seed(signed, **kwargs):
    client, service, doc, root, _, sources, runs, publication = entities(signed, **kwargs)
    claims, evidence = [], []
    with service.db.session() as session:
        for index, run_id in enumerate(runs):
            run = session.get(Investigation, run_id)
            claim = DossierClaim(**scope(run), statement=f"Fictional finding {index}: the demonstration record needs interpretation.",
                status="CONTESTED" if index == 0 else "SUPPORTED", history=[{"fixture": "Original extraction retained"}])
            session.add(claim)
            session.flush()
            link = ClaimEvidence(**scope(run), claim_id=claim.id, source_id=sources[index],
                relation="SUPPORTS", quote=QUOTE, locator="p1")
            session.add(link)
            session.flush()
            claims.append(claim.id)
            evidence.append(link.id)
        session.add(ClaimEvidence(**scope(session.get(Investigation, runs[0])), claim_id=claims[0], source_id=sources[0],
            relation="CONTRADICTS", quote=QUOTE, locator="p1"))
        session.commit()
    return client, service, doc, root, claims, sources, runs, publication, evidence


def item(client, root, identifier):
    response = client.get(root + "/claim-reviews")
    assert response.status_code == 200, response.text
    return next(row for row in response.json()["items"] if row["id"] == identifier)


def body(value, **changes):
    return {"claim_id": value["id"], "request_key": str(uuid4()), "expected_revision": value["revision"],
        "evidence_fingerprint": value["evidence_fingerprint"], "decision": "accepted",
        "reason": "Fictional reviewer considered both retained quotations.", **changes}


def link(session, runs, ids, evidence):
    row = ClaimChange(**scope(session.get(Investigation, runs[1])), claim_id=ids[1], evidence_id=evidence[1],
        previous_claim_id=ids[0], previous_investigation_id=runs[0], previous_evidence_id=evidence[0],
        previous_revision=1, previous_status="CONTESTED", kind="CONTRADICTS", explanation="Fictional conflicting evidence.")
    session.add(row)
    session.commit()
    return row.id


@pytest.mark.parametrize("public", [False, True])
@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_finding_review_updates_same_ledger_without_changing_evidence(signed, public, product):
    client, service, doc, root, ids, _, _, _, _ = seed(signed, public=public, product=product)
    with service.db.session() as session:
        original = copy.deepcopy(session.get(DossierClaim, ids[0]).history)
    value = item(client, root, ids[0])
    assert value["human_status"] == "PROPOSED" and value["finding_status"] == "PENDING_REVIEW"
    assert value["claim"]["evidence_status"] == "CONTESTED"
    assert {e["relation"] for e in value["evidence"]} == {"SUPPORTS", "CONTRADICTS"}
    route, data = root + "/claim-reviews/review", body(value, confirm_public=public)
    assert client.post(route, json=data).status_code == 403
    if public:
        assert post(client, route, {**data, "confirm_public": False}).status_code == 409
    saved = post(client, route, data)
    assert saved.status_code == 200, saved.text
    value = saved.json()
    assert value["human_status"] == value["finding_status"] == "ACCEPTED"
    assert value["id"] == ids[0] and value["revision"] == 1 and not value["stale"]
    assert post(client, route, data).json() == value
    assert post(client, route, {**data, "reason": "A different note"}).status_code == 409
    assert post(client, route, {**data, "request_key": str(uuid4())}).status_code == 409
    for decision, state in (("dismissed", "REJECTED"), ("needs_more_evidence", "UNRESOLVED")):
        response = post(client, route, body(value, decision=decision, confirm_public=public))
        assert response.status_code == 200, response.text
        value = response.json()
        assert value["human_status"] == state and not value["stale"]
    assert [row["decision"] for row in value["history"]] == ["accepted", "dismissed", "needs_more_evidence"]
    assert post(client, route, data).json() == value, "Late replay returns current decision without reinstating acceptance"
    with service.db.session() as session:
        claim = session.get(DossierClaim, ids[0])
        assert claim.status == "CONTESTED" and claim.revision == 1 and claim.history == original
        assert session.scalar(select(func.count()).select_from(ClaimReview)) == 3
        assert session.scalar(select(func.count()).select_from(DossierClaim)) == 2
    if public:
        client.cookies.clear()
        assert item(client, root, ids[0]) == value
        assert client.get(root + "/claim-reviews/workspace").status_code == 401
        for secret in (doc["id"], signed[2]["organization"]["id"], signed[2]["user"]["id"], data["request_key"]):
            assert secret not in json.dumps(value)
    else:
        exported = client.get(root + "/export")
        assert exported.status_code == 200, exported.text
        assert next(row for row in exported.json()["claim_ledger"] if row["id"] == ids[0]) == value
    assert signed[3].calls == []


@pytest.mark.parametrize("mutation", ["capture", "claim", "comparison", "comparison_review", "citation"])
def test_changed_evidence_requires_explicit_review(signed, mutation):
    client, service, _, root, ids, sources, runs, _, evidence = seed(signed)
    if mutation == "comparison_review":
        with service.db.session() as session:
            change_id = link(session, runs, ids, evidence)
    value = item(client, root, ids[0])
    data = body(value)
    saved = post(client, root + "/claim-reviews/review", data).json()
    with service.db.session() as session:
        if mutation == "capture":
            source = session.get(InvestigationSource, sources[0])
            source.snapshot = {"excerpts": [{"passage": "p1", "text": QUOTE + " More fictional context."}]}
        elif mutation == "claim":
            session.get(DossierClaim, ids[0]).revision += 1
        elif mutation == "citation":
            session.get(ClaimEvidence, evidence[0]).quote = "Invented text absent from capture"
        elif mutation == "comparison":
            link(session, runs, ids, evidence)
        else:
            row = session.get(ClaimChange, change_id)
            row.status, row.revision = "dismissed", 2
        session.commit()
    stale = item(client, root, ids[0])
    assert stale["stale"] and stale["human_status"] == "UNRESOLVED" and stale["finding_status"] == "PENDING_REVIEW"
    assert stale["history"] == saved["history"]
    assert post(client, root + "/claim-reviews/review", data).status_code == 409
    if mutation != "citation":
        reviewed = post(client, root + "/claim-reviews/review", body(stale, decision="needs_more_evidence"))
        assert reviewed.status_code == 200 and not reviewed.json()["stale"]
    else:
        assert stale["reviewable"] is False and stale["evidence_fingerprint"] is None


@pytest.mark.parametrize("public", [False, True])
def test_hidden_related_source_hides_previous_review_reason(signed, public):
    client, service, doc, root, ids, sources, runs, _, evidence = seed(signed, public=public)
    with service.db.session() as session:
        link(session, runs, ids, evidence)
    saved = post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]),
        confirm_public=public, reason="Secret contextual detail from the other source.")).json()
    with service.db.session() as session:
        if public:
            run = session.get(Investigation, runs[1])
            session.get(PublicContribution, run.public_contribution_id).status = "hidden"
        else:
            source = session.get(InvestigationSource, sources[1])
            session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", request_key=str(uuid4()),
                url=source.url, body="Exclude fictional source", data_json={"decision": "exclude", "revision": 1}))
        session.commit()
    visible = item(client, root, ids[0])
    assert visible["stale"] and visible["history_unavailable"] and visible["history"] == []
    assert visible["decision"] is None and visible["human_status"] == "UNRESOLVED"
    assert "Secret contextual" not in json.dumps(visible) and sources[1] not in json.dumps(visible)
    assert post(client, root + "/claim-reviews/review", body(saved, confirm_public=public)).status_code == 409


@pytest.mark.parametrize("mutation", ["exclude", "withdraw", "revision", "contribution", "unfinished"])
def test_current_source_publication_and_run_eligibility_before_counts_and_writes(signed, mutation):
    client, service, doc, root, ids, sources, runs, publication, _ = seed(signed, public=True)
    value = item(client, root, ids[0])
    with service.db.session() as session:
        if mutation == "exclude":
            source = session.get(InvestigationSource, sources[0])
            session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", request_key=str(uuid4()),
                url=source.url, body="Exclude fictional source", data_json={"decision": "exclude", "revision": 1}))
        elif mutation in {"withdraw", "revision"}:
            pub = session.get(ProductPublication, publication["id"])
            if mutation == "withdraw":
                pub.status = "withdrawn"
            else:
                pub.revision += 1
        elif mutation == "contribution":
            run = session.get(Investigation, runs[0])
            session.get(PublicContribution, run.public_contribution_id).revision += 1
        else:
            session.get(Investigation, runs[0]).status = "running"
        session.commit()
    result = client.get(root + "/claim-reviews")
    if mutation == "withdraw":
        assert result.status_code == 404
    else:
        assert result.status_code == 200 and all(row["id"] != ids[0] for row in result.json()["items"])
        assert result.json()["total"] == (0 if mutation == "revision" else 1)
    assert post(client, root + "/claim-reviews/review", body(value, confirm_public=True)).status_code == 404


@pytest.mark.parametrize("public", [False, True])
def test_guest_current_roles_and_real_reviewer_erasure(signed, public):
    from test_account_deletion_api import confirmation

    from helvetic_lens.models import OrganizationMembership

    client, service, doc, root, ids, _, _, _, _ = seed(signed, public=public)
    value = item(client, root, ids[0])
    owner_cookies = dict(client.cookies)
    account, cookies = guest(client, service)
    private = ROOT + "/" + doc["id"]
    assert post(client, private + "/team/enable", {"expected_revision": 1}).status_code == 200
    invite = invitation(client, private, account, "EDITOR")
    switch(client, cookies)
    accept(client, private, invite)
    with service.db.session(include_all_organizations=True) as session:
        session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == account["user"]["id"])).role = "viewer"
        session.commit()
    first = post(client, root + "/claim-reviews/review", body(value, confirm_public=public))
    assert first.status_code == 200, first.text
    with service.db.session(include_all_organizations=True) as session:
        member = session.scalar(select(DossierMember).where(DossierMember.user_id == account["user"]["id"], DossierMember.dossier_id == doc["id"]))
        member.role = "VIEWER"
        session.commit()
    assert post(client, root + "/claim-reviews/review", body(first.json(), confirm_public=public)).status_code == 403
    with service.db.session(include_all_organizations=True) as session:
        session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == account["user"]["id"])).role = "organization_admin"
        session.commit()
    erased = post(client, "/api/account/deletion", confirmation(client))
    assert erased.status_code == 200, erased.text
    if not public:
        switch(client, owner_cookies)
    history = item(client, root, ids[0])["history"]
    assert len(history) == 1 and history[0]["reviewer"] == "Former dossier editor"
    with service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(ClaimReview)).reviewed_by_user_id is None


def test_private_public_and_foreign_claims_never_mix(signed):
    client, service, doc, root, ids, _, runs, _, _ = seed(signed, public=True)
    value = item(client, root, ids[0])
    private = ROOT + "/" + doc["id"]
    assert client.get(private + "/claim-reviews").json()["total"] == 0
    assert post(client, private + "/claim-reviews/review", body(value)).status_code == 404
    assert post(client, root + "/claim-reviews/review", body(value, claim_id=str(uuid4()), confirm_public=True)).status_code == 404
    with service.db.session() as session:
        run = session.get(Investigation, runs[0])
        run.publication_id = run.publication_revision = run.public_contribution_id = run.public_contribution_revision = None
        session.commit()
    assert post(client, root + "/claim-reviews/review", body(value, confirm_public=True)).status_code == 404
    assert post(client, private + "/claim-reviews/review", body(value)).status_code == 409


def test_database_scope_cascade_and_review_limit(signed):
    client, service, _, root, ids, _, runs, _, _ = seed(signed)
    saved = post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]))).json()
    with service.db.session() as session:
        row = session.scalar(select(ClaimReview))
        row.investigation_id = runs[1]
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
        row = session.scalar(select(ClaimReview))
        row.revision = 100
        session.commit()
    assert post(client, root + "/claim-reviews/review", body(saved, expected_revision=100)).status_code == 409
    with service.db.session() as session:
        session.delete(session.get(DossierClaim, ids[0]))
        session.commit()
        assert session.scalar(select(func.count()).select_from(ClaimReview)) == 0


def test_additive_migration_preserves_claims_and_refuses_destructive_rollback(signed):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from test_account_deletion_migration import config

    from alembic import command as migrate
    from helvetic_lens.db import Base

    client, service, _, root, ids, _, _, _, _ = seed(signed)
    with service.db.engine.connect() as connection:
        migrate.downgrade(config(connection), "0ad495bef125")
        migrate.upgrade(config(connection), "head")
        context = MigrationContext.configure(connection, opts={"include_object": lambda obj, name, kind, reflected, other:
            kind != "table" or name == "product_claim_reviews"})
        assert compare_metadata(context, Base.metadata) == []
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    value = item(client, root, ids[0])
    assert post(client, root + "/claim-reviews/review", body(value)).status_code == 200
    with service.db.engine.connect() as connection, pytest.raises(RuntimeError, match="Retain claim reviews"):
        migrate.downgrade(config(connection), "0ad495bef125")
    assert item(client, root, ids[0])["human_status"] == "ACCEPTED"


def test_pagination_and_incomplete_evidence_never_allow_partial_acceptance(signed):
    client, service, doc, root, ids, sources, runs, _, _ = seed(signed)
    with service.db.session() as session:
        run = session.get(Investigation, runs[0])
        for index in range(10):
            session.add(DossierClaim(**scope(run), statement=f"Fictional uncited draft {index}"))
        for _ in range(100):
            session.add(ClaimEvidence(**scope(run), claim_id=ids[0], source_id=sources[0], relation="CONTEXT", quote=QUOTE, locator="p1"))
        session.commit()
    pages = [client.get(root + f"/claim-reviews?offset={offset}").json() for offset in (0, 10)]
    assert pages[0]["total"] == pages[1]["total"] == 12
    all_items = pages[0]["items"] + pages[1]["items"]
    assert len({value["id"] for value in all_items}) == 12
    limited = next(value for value in all_items if value["id"] == ids[0])
    assert not limited["complete"] and not limited["reviewable"] and len(limited["evidence"]) == 100
    assert post(client, root + "/claim-reviews/review", body(limited, evidence_fingerprint="f" * 64)).status_code == 409
    for value in all_items:
        if not value["evidence"]:
            assert not value["reviewable"]
    with service.db.session() as session:
        source = session.get(InvestigationSource, sources[0])
        session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", request_key=str(uuid4()),
            url=source.url, body="Exclude fictional source", data_json={"decision": "exclude", "revision": 1}))
        session.commit()
    page = client.get(root + "/claim-reviews").json()
    assert page["total"] == 1 and page["items"][0]["id"] == ids[1]


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_actual_coordinator_extraction_then_human_review_preserves_both_claims(signed, monkeypatch, product):
    from test_product_claim_evolution import SECOND, fixture
    from test_product_investigations import complete

    client, service, _, root, runs, first, submit, _, _, _ = fixture(signed, monkeypatch, product=product, kind="CONTRADICTS")
    second = complete(client, service, runs, submit(SECOND))
    original = first["claims"][0]
    value = item(client, root, original["id"])
    assert value["decision"] is None and len(value["comparisons"]) == 1
    assert value["comparisons"][0]["kind"] == "CONTRADICTS"
    saved = post(client, root + "/claim-reviews/review", body(value, decision="needs_more_evidence"))
    assert saved.status_code == 200 and saved.json()["human_status"] == "UNRESOLVED"
    assert saved.json()["comparisons"][0]["claim"]["id"] == second["claims"][0]["id"]
    unchanged = client.get(runs + "/" + first["id"]).json()["claims"][0]
    assert unchanged["statement"] == original["statement"] and unchanged["status"] == original["status"]
    assert unchanged["later_evidence"]["status"] == "CONTESTED"


def test_resumed_related_research_invalidates_and_withholds_earlier_reason(signed):
    client, service, _, root, ids, _, runs, _, evidence = seed(signed)
    with service.db.session() as session:
        link(session, runs, ids, evidence)
    saved = post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]))).json()
    with service.db.session() as session:
        session.get(Investigation, runs[1]).status = "running"
        session.commit()
    value = item(client, root, ids[0])
    assert value["stale"] and value["history_unavailable"] and not value["history"] and not value["comparisons"]
    assert value["human_status"] == "UNRESOLVED"
    assert post(client, root + "/claim-reviews/review", body(saved)).status_code == 409


def test_saved_page_revision_correction_stales_claim_review_without_rewriting_capture(signed, monkeypatch):
    from test_product_contributions import no_discovery
    from test_product_document_history import setup
    from test_product_investigations import complete
    from test_product_monitoring_research import due, enable, model
    from test_product_page_research import changed, last_run

    from helvetic_lens.models import Version

    client, service, _, target = signed
    _, root, law_id, _, _ = setup(client)
    enable(client, root, include_page_changes=True)
    model(monkeypatch, target)
    external = no_discovery(monkeypatch)
    version_id = changed(client, service, law_id, "Fictional demonstration registry now lists six example entries.")
    assert due(service)["started"] == 1
    run = complete(client, service, root + "/investigations", last_run(client, root))
    value = item(client, root, run["claims"][0]["id"])
    saved = post(client, root + "/claim-reviews/review", body(value))
    assert saved.status_code == 200, saved.text
    pin = saved.json()["history"][0]["basis"]["sources"][0]["saved_version"]
    assert pin["id"] == version_id and pin["recorded_revision"] == pin["current_revision"]
    with service.db.session() as session:
        session.get(Version, version_id).evidence_revision += 1
        session.commit()
    stale = item(client, root, value["id"])
    assert stale["stale"] and not stale["reviewable"] and stale["human_status"] == "UNRESOLVED"
    assert stale["evidence"][0]["quote"] == value["evidence"][0]["quote"]
    assert post(client, root + "/claim-reviews/review", body(saved.json())).status_code == 409
    assert external == []
