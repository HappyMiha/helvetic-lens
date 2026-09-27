"""Real durable comparisons, retained originals, audience changes and editor review."""
import json
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_product_community import action, command
from test_product_dossiers import ROOT, create, post
from test_product_dossiers import signed as signed
from test_product_guests import accept, guest, invitation
from test_product_investigations import complete, tick
from test_product_public_research import setup
from test_product_publications import draft, preview_and_publish
from test_product_teams import switch

from helvetic_lens.product_claim_evolution import KINDS, prepare
from helvetic_lens.product_investigation_models import (
    ClaimChange,
    ClaimEvidence,
    DossierClaim,
    Investigation,
    InvestigationSource,
)
from helvetic_lens.product_models import DossierEntry, ProductDossier, ProductPublication, PublicContribution

FIRST = "Earlier registry: Alpine Therapeutics owns Helvetic Molecule AG."
SECOND = "Later registry: Alpine Therapeutics transferred Helvetic Molecule AG to another owner."


def fixture(signed, monkeypatch, *, public=False, product="pharma", kind="UPDATES", during=None, invalid=None):
    client, service, identity, model = signed
    if public:
        doc, publication, root = setup(client, service, identity, product=product)
        with service.db.session() as session:
            session.get(ProductPublication, publication["id"]).sources_json = []
            session.commit()
    else:
        doc, _ = create(client)
        with service.db.session() as session:
            session.get(ProductDossier, doc["id"]).product = product
            session.commit()
        root = ROOT.replace("pharma", product) + "/" + doc["id"]
        publication = None
    calls = []

    async def response(system, user, **kwargs):
        data = json.loads(user)
        calls.append(data)
        if "source" in data:
            if data["source"]["kind"] == "public_publication":
                return json.dumps({"claims": []})
            part = data["source"]["excerpts"][0]
            assert "previous" not in data
            assert data["existing_claims"] == []  # Independent extraction in each run.
            return json.dumps({"claims": [{"statement": part["text"], "quote": part["text"],
                "locator": part["passage"], "relation": "SUPPORTS"}]})
        if during:
            during(data)
        pair = {"current_claim_id": data["current"][0]["id"], "previous_claim_id": data["previous"][0]["id"], "kind": kind}
        if invalid == "foreign":
            pair["previous_claim_id"] = str(uuid4())
        if invalid == "text":
            pair["explanation"] = "Invented model text must never be persisted."
        return json.dumps({"changes": [pair, {**pair, "kind": "CORROBORATES"}] if invalid == "conflict" else [pair]})

    monkeypatch.setattr(model, "complete", response)
    items = []
    def submit(text):
        if public:
            body = command(kind="comment", analyse_publicly=True)
            body["content"].update(body=text, sources=[])
            result = post(client, root + "/discussion", body)
            assert result.status_code == 201, result.text
            item = result.json()["contribution"]
            run = item["research"]
        else:
            result = post(client, root + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": text, "analyse": True})
            assert result.status_code == 201, result.text
            item = result.json()
            run = item["analysis"]
        items.append(item)
        return run
    runs = root + ("/research" if public else "/investigations")
    first = complete(client, service, runs, submit(FIRST))
    assert first["claims"], first
    return client, service, doc, root, runs, first, submit, calls, items, publication


@pytest.mark.parametrize("product", ["pharma", "loyer"])
@pytest.mark.parametrize("public", [False, True])
@pytest.mark.parametrize("kind", list(KINDS))
def test_independent_findings_are_compared_once_and_originals_preserved(signed, monkeypatch, product, public, kind):
    client, service, doc, root, runs, first, submit, calls, _, _ = fixture(signed, monkeypatch, public=public, product=product, kind=kind)
    second = complete(client, service, runs, submit(SECOND))
    assert second["status"] == "completed", second
    assert len([c for c in calls if "current" in c]) == 1
    assert len([c for c in calls if c.get("source", {}).get("kind") in {"human_contribution", "public_contribution"}]) == 2
    assert sum(b["phase"] == "compare" for b in second["branches"]) == 1
    tick(service, second["id"])
    assert len(calls) == (5 if public else 3)  # Completed delivery is not a second paid comparison.
    if public:
        client.cookies.clear()
    page = client.get(root + "/evidence-changes")
    assert page.status_code == 200 and "no-store" in page.headers["cache-control"], page.text
    change = page.json()["items"][0]
    assert page.json()["total"] == 1 and change["kind"] == kind and change["explanation"] == KINDS[kind]
    for label, value, text in [("previous", first, FIRST), ("current", second, SECOND)]:
        assert change[label]["statement"] == text
        assert change[label]["investigation_id"] == value["id"]
        assert change[label]["evidence"]["quote"] == text
        assert len(change[label]["evidence"]["source"]["sha256"]) == 64
    prior = client.get(runs + "/" + first["id"]).json()["claims"][0]
    assert {k: prior[k] for k in ("statement", "status", "revision", "history")} == {
        k: first["claims"][0][k] for k in ("statement", "status", "revision", "history")}
    assert prior["later_evidence"] == {"status": {"CORROBORATES": None, "CONTRADICTS": "CONTESTED", "UPDATES": "SUPERSEDED"}[kind],
        "changes": [{"kind": kind, "count": 1}]}
    if public:
        for hidden in (doc["id"], "organization_id", "reviewed_by_user_id", "last_request_key", "artifact_key"):
            assert hidden not in page.text
        assert client.get(root + "/evidence-changes/workspace").status_code == 401
    assert client.get(root.replace(product, "loyer" if product == "pharma" else "pharma") + "/evidence-changes").status_code == 404


@pytest.mark.parametrize("invalid", ["foreign", "text", "conflict"])
def test_invalid_comparison_cannot_add_unattributed_or_cross_scope_links(signed, monkeypatch, invalid):
    client, service, _, root, runs, _, submit, _, _, _ = fixture(signed, monkeypatch, invalid=invalid)
    result = complete(client, service, runs, submit(SECOND))
    assert any(b["phase"] == "compare" and b["status"] == "failed" for b in result["branches"])
    assert client.get(root + "/evidence-changes").json()["total"] == 0
    assert "Invented model text" not in json.dumps(result)


@pytest.mark.parametrize("change", ["hide", "remove", "erase", "withdraw", "republish", "source"])
def test_withdrawn_previous_evidence_disappears_before_counts_and_never_taints_new_claims(signed, monkeypatch, change):
    client, service, doc, root, runs, first, submit, _, items, _ = fixture(signed, monkeypatch, public=True)
    second = complete(client, service, runs, submit(SECOND))
    assert client.get(root + "/evidence-changes").json()["total"] == 1
    if change in {"hide", "remove"}:
        assert action(client, root + "/discussion", items[0], change).status_code == 200
    elif change == "withdraw":
        assert post(client, ROOT + "/" + doc["id"] + "/publication/withdraw", {
            "expected_revision": 1, "request_key": str(uuid4())}).status_code == 200
    elif change == "republish":
        preview_and_publish(client, doc["id"], {**draft(1), "living_research": True})
    elif change == "erase":
        with service.db.session() as session:
            session.delete(session.get(PublicContribution, items[0]["id"]))
            session.commit()
            assert session.scalar(select(func.count()).select_from(ClaimChange)) == 0
    else:
        with service.db.session() as session:
            session.get(InvestigationSource, first["sources"][0]["id"]).url = "https://example.org/old-report"
            session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", url="https://example.org/old-report",
                request_key=str(uuid4()), body="Private removal reason", data_json={"decision": "exclude", "revision": 1}))
            session.commit()
    client.cookies.clear()
    page = client.get(root + "/evidence-changes?status=all")
    if change == "withdraw":
        assert page.status_code == 404
    else:
        assert page.json()["items"] == [] and page.json()["total"] == 0
    if change not in {"withdraw", "republish"}:
        visible = client.get(runs + "/" + second["id"])
        assert visible.status_code == 200 and SECOND in visible.text
        assert FIRST not in visible.text and first["claims"][0]["id"] not in visible.text
    assert "Private removal reason" not in page.text


def test_inflight_revocation_discards_comparison_and_explicit_retry_is_bounded(signed, monkeypatch):
    def revoke(data):
        with signed[1].db.session() as session:
            claim = session.get(DossierClaim, data["previous"][0]["id"])
            claim.revision += 1
            session.commit()
    client, service, _, root, runs, _, submit, calls, _, _ = fixture(signed, monkeypatch, during=revoke)
    second = complete(client, service, runs, submit(SECOND))
    assert any(b["phase"] == "compare" and b["status"] == "failed" for b in second["branches"])
    assert client.get(root + "/evidence-changes").json()["total"] == 0
    async def retry(system, user, **kwargs):
        data = json.loads(user)
        calls.append(data)
        assert "source" not in data
        return json.dumps({"changes": [{"current_claim_id": data["current"][0]["id"],
            "previous_claim_id": data["previous"][0]["id"], "kind": "UPDATES"}]})
    monkeypatch.setattr(signed[3], "complete", retry)
    response = post(client, runs + "/" + second["id"] + "/control", {"action": "retry", "expected_revision": second["revision"]})
    assert response.status_code == 200, response.text
    complete(client, service, runs, response.json())
    assert client.get(root + "/evidence-changes").json()["total"] == 1
    assert len([v for v in calls if "current" in v]) == 2
    assert len([v for v in calls if "source" in v]) == 2


@pytest.mark.parametrize("public", [False, True])
def test_editor_review_is_revisioned_replay_safe_and_keeps_originals(signed, monkeypatch, public):
    client, service, _, root, runs, first, submit, _, _, _ = fixture(signed, monkeypatch, public=public)
    complete(client, service, runs, submit(SECOND))
    route = root + "/evidence-changes"
    value = client.get(route).json()["items"][0]
    body = {"request_key": str(uuid4()), "expected_revision": 1, "status": "dismissed", "reason": "These reports refer to different dates.", "confirm_public": public}
    path = route + "/" + value["id"] + "/review"
    assert client.post(path, json=body).status_code == 403
    if public:
        assert post(client, path, {**body, "confirm_public": False}).status_code == 409
    result = post(client, path, body)
    assert result.status_code == 200, result.text
    assert result.json()["revision"] == 2 and result.json()["history"][0]["reason"] == body["reason"]
    assert post(client, path, body).json() == result.json()
    if not public:
        assert client.get(root + "/export").json()["evidence_changes"] == [result.json()]
    assert post(client, path, {**body, "reason": "Changed review"}).status_code == 409
    assert client.get(route).json()["total"] == 0
    assert client.get(route + "?status=all").json()["total"] == 1
    assert client.get(runs + "/" + first["id"]).json()["claims"][0]["later_evidence"] is None
    body.update(request_key=str(uuid4()), status="active")
    assert post(client, path, body).status_code == 409
    body["expected_revision"] = 2
    assert post(client, path, body).json()["revision"] == 3
    assert client.get(runs + "/" + first["id"]).json()["claims"][0]["later_evidence"]["status"] == "SUPERSEDED"


@pytest.mark.parametrize("role", ["VIEWER", "CONTRIBUTOR", "EDITOR"])
@pytest.mark.parametrize("public", [False, True])
def test_guest_review_uses_current_dossier_role_without_host_membership(signed, monkeypatch, role, public):
    client, service, doc, root, runs, _, submit, _, _, _ = fixture(signed, monkeypatch, public=public)
    complete(client, service, runs, submit(SECOND))
    value = client.get(root + "/evidence-changes").json()["items"][0]
    account, cookies = guest(client, service)
    private = ROOT + "/" + doc["id"]
    assert post(client, private + "/team/enable", {"expected_revision": 1}).status_code == 200
    item = invitation(client, private, account, role)
    switch(client, cookies)
    accept(client, private, item)
    route = root + "/evidence-changes"
    controls = client.get(route + ("/workspace" if public else "")).json()
    assert controls["can_review"] is (role == "EDITOR")
    response = post(client, route + "/" + value["id"] + "/review", {"request_key": str(uuid4()), "expected_revision": 1,
        "status": "dismissed", "reason": "This source concerns a different entity.", "confirm_public": public})
    assert response.status_code == (200 if role == "EDITOR" else 403), response.text


def test_schema_roundtrip_scope_bounds_and_cascades(signed, monkeypatch):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from test_account_deletion_migration import config

    from alembic import command as migrate
    from helvetic_lens.db import Base

    client, service, _, root, runs, first, submit, _, _, _ = fixture(signed, monkeypatch)
    with service.db.engine.connect() as connection:
        migrate.downgrade(config(connection), "ffc495bef124")
        migrate.upgrade(config(connection), "head")
        context = MigrationContext.configure(connection, opts={"include_object": lambda obj, name, kind, reflected, other:
            kind != "table" or name in {"product_claim_evidence", "product_claim_changes"}})
        assert compare_metadata(context, Base.metadata) == []
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    assert client.get(runs + "/" + first["id"]).json()["evidence"] == first["evidence"]
    second = complete(client, service, runs, submit(SECOND))
    with service.db.engine.connect() as connection, pytest.raises(RuntimeError, match="Retained claim changes"):
        migrate.downgrade(config(connection), "ffc495bef124")
    with service.db.session() as session:
        current = session.get(Investigation, second["id"])
        older = session.get(Investigation, first["id"])
        foreign_doc, _ = create(client)
        row = session.scalar(select(ClaimChange))
        row.dossier_id = foreign_doc["id"]
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
        for i in range(30):
            claim = DossierClaim(organization_id=older.organization_id, dossier_id=older.dossier_id,
                investigation_id=older.id, statement=f"Extra supported finding {i}", status="SUPPORTED", history=[])
            session.add(claim)
            session.flush()
            evidence = ClaimEvidence(organization_id=older.organization_id, dossier_id=older.dossier_id,
                investigation_id=older.id, claim_id=claim.id, source_id=first["sources"][0]["id"], relation="SUPPORTS", quote=FIRST, locator="p1")
            session.add(evidence)
            session.flush()
            if i < 22:
                session.add(ClaimChange(organization_id=current.organization_id, dossier_id=current.dossier_id,
                    investigation_id=current.id, evidence_id=second["evidence"][0]["id"], claim_id=second["claims"][0]["id"],
                    previous_claim_id=claim.id, previous_investigation_id=older.id, previous_revision=1,
                    previous_evidence_id=evidence.id,
                    previous_status="SUPPORTED", kind="CORROBORATES", explanation=KINDS["CORROBORATES"], history=[]))
        session.commit()
        assert len(prepare(session, current)["previous"]) == 24
        page = client.get(root + "/evidence-changes").json()
        next_page = client.get(root + "/evidence-changes?offset=20").json()
        assert page["total"] == next_page["total"] == 23 and len(page["items"]) == 20 and len(next_page["items"]) == 3
        assert not {v["id"] for v in page["items"]} & {v["id"] for v in next_page["items"]}
        session.delete(session.get(InvestigationSource, first["sources"][0]["id"]))
        session.commit()
        assert session.get(DossierClaim, first["claims"][0]["id"]) is not None
        assert session.scalar(select(func.count()).select_from(ClaimChange)) == 0
        session.delete(session.get(Investigation, first["id"]))
        session.commit()
        assert session.scalar(select(func.count()).select_from(ClaimChange)) == 0
    assert client.get(root + "/evidence-changes").json()["total"] == 0
    assert client.get(runs + "/" + second["id"]).json()["claims"]


def test_interrupted_comparison_is_not_automatically_charged_again(signed, monkeypatch):
    from datetime import timedelta

    from helvetic_lens import jobs
    from helvetic_lens.db import utcnow
    from helvetic_lens.product_investigation_models import InvestigationBranch

    client, service, _, root, runs, _, submit, calls, _, _ = fixture(signed, monkeypatch)
    second = submit(SECOND)
    for _ in range(10):
        tick(service, second["id"])
        with service.db.session() as session:
            branch = session.scalar(select(InvestigationBranch).where(
                InvestigationBranch.investigation_id == second["id"], InvestigationBranch.phase == "compare"))
            if not branch:
                continue
            run = session.get(Investigation, second["id"])
            job = jobs.claim(session, run.job_id, "crashed-worker")
            job.heartbeat_at = utcnow() - timedelta(hours=1)
            branch.checkpoint = {**branch.checkpoint, "inflight": "recorded-before-network", "steps": [{"phase": "compare", "status": "running"}]}
            session.commit()
            break
    else:
        raise AssertionError("No comparison was scheduled")
    with service.db.session() as session:
        jobs.reconcile(session, 30)
        session.commit()
    result = complete(client, service, runs, second)
    assert not any("current" in data for data in calls)
    comparison = next(b for b in result["branches"] if b["phase"] == "compare")
    assert comparison["status"] == "failed" and comparison["steps"][0]["status"] == "interrupted"
    assert client.get(root + "/evidence-changes").json()["total"] == 0


def test_author_erasure_removes_links_but_preserves_independent_host_evidence(signed, monkeypatch):
    from test_account_deletion_api import confirmation

    client, service, doc, root, runs, first, submit, _, _, publication = fixture(signed, monkeypatch, public=True)
    account, cookies = guest(client, service)
    switch(client, cookies)
    complete(client, service, runs, submit(SECOND))
    assert client.get(root + "/evidence-changes").json()["total"] == 1
    response = post(client, "/api/account/deletion", confirmation(client))
    assert response.status_code == 200, response.text
    with service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(ClaimChange)) == 0
        assert session.get(ProductDossier, doc["id"]) and session.get(ProductPublication, publication["id"])
    client.cookies.clear()
    prior = client.get(runs + "/" + first["id"])
    assert prior.status_code == 200 and prior.json()["claims"][0]["later_evidence"] is None
    assert client.get(root + "/evidence-changes").json()["total"] == 0


def test_private_candidates_never_enter_public_comparison_and_midflight_hide_is_fenced(signed, monkeypatch):
    def hide(data):
        assert "PRIVATE-ONLY-FINDING" not in json.dumps(data)
        with signed[1].db.session() as session:
            previous = session.get(Investigation, data["previous"][0]["investigation_id"])
            session.get(PublicContribution, previous.public_contribution_id).status = "hidden"
            session.commit()
    client, service, doc, root, runs, _, submit, calls, _, _ = fixture(signed, monkeypatch, public=True, during=hide)
    private = ROOT + "/" + doc["id"]
    response = post(client, private + "/entries", {"request_key": str(uuid4()), "kind": "note",
        "body": "PRIVATE-ONLY-FINDING about confidential evidence", "analyse": True})
    assert response.status_code == 201
    complete(client, service, private + "/investigations", response.json()["analysis"])
    assert not any("current" in data for data in calls), "Public claims entered the private comparison."
    second = complete(client, service, runs, submit(SECOND))
    assert len([data for data in calls if "current" in data]) == 1
    assert any(b["phase"] == "compare" and b["status"] == "failed" for b in second["branches"])
    assert client.get(root + "/evidence-changes").json()["total"] == 0
    assert SECOND in json.dumps(second) and FIRST not in json.dumps(second)
