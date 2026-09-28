"""Search real retained evidence without external queries or stale permissions."""
import hashlib
from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from test_auth import _register
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_web_research import setup

from helvetic_lens import decision_engines as decisions
from helvetic_lens.db import utcnow
from helvetic_lens.models import OrganizationMembership, User, UserSession
from helvetic_lens.product_evidence_search import BATCH_SIZE
from helvetic_lens.product_investigation_models import (
    DossierClaim,
    Investigation,
)
from helvetic_lens.product_investigations import Extraction, apply_extraction, snapshot
from helvetic_lens.product_models import DossierEntry

QUOTE = "The medicine must be kept between two and eight degrees Celsius."
STATEMENT = "The product requires refrigerated storage."


def retained(service, doc, texts=None, *, finding=True, status="completed"):
    with service.db.session() as session:
        run = Investigation(dossier_id=doc["id"], organization_id=service.organization_id,
            question="Source evidence", status=status, request_key=str(uuid4()), external_discovery=False)
        session.add(run)
        session.flush()
        texts = texts or [QUOTE]
        source, _ = snapshot(session, run, {"kind": "team_contribution", "key": str(uuid4()),
            "title": "Saved source", "url": "https://example.org/source", "status": "complete",
            "sha256": hashlib.sha256(" ".join(texts).encode()).hexdigest(),
            "excerpts": [{"text": text, "passage": f"p{i}"} for i, text in enumerate(texts)]}, captured=True)
        if finding:
            apply_extraction(session, run, source, Extraction.model_validate({"claims": [{
                "statement": STATEMENT, "relation": "SUPPORTS", "quote": texts[0], "locator": "p0"}]}))
        session.commit()
        return run.id, source.id


def local(monkeypatch, service, hook=None, failure=None):
    service.environment_settings.laya_base_url = "http://127.0.0.1:18761/v1/systemone"
    service.environment_settings.laya_api_key = SecretStr("fixture-local")
    calls = []
    async def choose(self, state, instructions, criteria):
        assert self.name == "laya" and self.url.startswith("http://127.0.0.1")
        calls.append(state)
        if hook:
            hook(len(calls))
        if failure:
            raise decisions.DecisionUnavailable(failure)
        useful = "two and eight" in state["quotation"]
        probability = 0.93 if useful else 0.07
        return decisions.Decision("laya", "fixture-multilingual", "A" if useful else "B",
            {"A": probability, "B": 1 - probability}, 0.86, 0.93, 3.4, None, None)
    monkeypatch.setattr(decisions.SystemOneEngine, "choose", choose)
    return calls


def search(client, root, query="Wie muss das Arzneimittel gelagert werden?", **values):
    return post(client, root + "/evidence-search", {"query": query, **values})


@pytest.mark.parametrize("product", ["pharma", "loyer"])
@pytest.mark.parametrize("audience", ["draft", "workspace", "team"])
def test_semantic_has_no_lexical_gate_and_keeps_exact_citations(signed, monkeypatch, product, audience):
    client, service, _, _ = signed
    doc, root = setup(client, product, audience)
    run_id, source_id = retained(service, doc)
    calls = local(monkeypatch, service)
    result = search(client, root)
    assert result.status_code == 200, result.text
    page = result.json()
    assert page["total_records"] == page["examined_records"] == len(calls) == 2
    assert page["method"] == "local_semantic_hybrid" and page["next_offset"] is None
    assert len(page["items"]) == 2 and all(row["semantic_match"] and not row["literal_match"] for row in page["items"])
    assert {row["kind"] for row in page["items"]} == {"passage", "claim"}
    assert all(row["investigation_id"] == run_id and row["source_id"] == source_id and row["quote"] == QUOTE for row in page["items"])
    assert next(row for row in page["items"] if row["kind"] == "claim")["claim_status"] == "SUPPORTED"
    assert page["measurement"]["estimated_cost_usd"] is None and page["measurement"]["accuracy"] is None
    assert page["measurement"]["requests_completed"] == 2 and page["measurement"]["latency_ms"] >= 0
    assert "no-store" in result.headers["cache-control"]
    assert search(client, root, mode="literal").json()["items"] == []
    assert len(calls) == 2
    assert client.get(f"/api/products/{product}/public-knowledge?q=Celsius").json()["total"] == 0
    check = search(client, root, check_only=True, as_of=page["as_of"], fingerprint=page["fingerprint"])
    assert check.status_code == 200 and check.json() == {"current": True} and len(calls) == 2


def test_literal_search_all_passages_and_older_semantic_windows(signed, monkeypatch):
    client, service, _, _ = signed
    doc, root = setup(client)
    texts = [f"Archive passage {i:02d} about unrelated administration." for i in range(27)]
    texts[21] = QUOTE
    retained(service, doc, texts, finding=False)
    calls = local(monkeypatch, service)
    words = search(client, root, "two eight", mode="literal").json()
    assert words["total_records"] == 27 and words["matching_records"] == 1 and len(words["items"]) == 1
    assert words["items"][0]["locator"] == "p21" and not calls
    seen, positive, offset, as_of = [], [], 0, None
    for _ in range(3):
        result = search(client, root, offset=offset, as_of=as_of)
        assert result.status_code == 200, result.text
        page = result.json()
        seen.extend(row["locator"] for row in page["items"])
        positive.extend(row["locator"] for row in page["items"] if row["semantic_match"])
        assert page["examined_records"] <= BATCH_SIZE
        offset, as_of = page["next_offset"], page["as_of"]
    assert len(set(seen)) == 27 and positive == ["p21"] and offset is None and len(calls) == 27
    # New captures cannot shift a previously started traversal.
    retained(service, doc, [QUOTE], finding=False)
    old = search(client, root, mode="literal", as_of=as_of, query="two eight").json()
    assert old["total_records"] == 27 and old["matching_records"] == 1
    fresh = search(client, root, mode="literal", query="two eight").json()
    assert fresh["total_records"] == 28 and fresh["matching_records"] == 2


@pytest.mark.parametrize("failure", ["timeout", "quota", "invalid_response", "not_configured"])
def test_local_failure_retains_literal_recovery_with_unknown_cost(signed, monkeypatch, failure):
    client, service, _, _ = signed
    doc, root = setup(client)
    retained(service, doc)
    calls = local(monkeypatch, service, failure=failure)
    result = search(client, root, "two eight")
    assert result.status_code == 200, result.text
    page = result.json()
    assert page["method"] == "literal_fallback" and page["measurement"]["error"] == failure
    assert len(calls) == 1 and len(page["items"]) == 2
    assert all(row["literal_match"] and row["confidence"] is None for row in page["items"])
    assert page["measurement"]["estimated_cost_usd"] is None


@pytest.mark.parametrize("change", ["source", "session", "membership", "account", "claim"])
def test_late_access_or_evidence_change_never_returns_old_results(signed, monkeypatch, change):
    client, service, identity, _ = signed
    doc, root = setup(client, audience="workspace")
    run_id, _ = retained(service, doc)
    def revoke(count):
        if count != 1:
            return
        with service.db.session() as session:
            if change == "source":
                session.add(DossierEntry(dossier_id=doc["id"], actor_user_id=identity["user"]["id"],
                    request_key=str(uuid4()), kind="source_review", url="https://example.org/source",
                    data_json={"revision": 1, "decision": "exclude"}))
            elif change == "session":
                for row in session.scalars(select(UserSession).where(UserSession.user_id == identity["user"]["id"])):
                    row.revoked_at = utcnow()
            elif change == "membership":
                membership = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]))
                session.delete(membership)
            elif change == "account":
                session.get(User, identity["user"]["id"]).active = False
            else:
                claim = session.scalar(select(DossierClaim).where(DossierClaim.investigation_id == run_id))
                claim.status, claim.revision = "CONTESTED", claim.revision + 1
            session.commit()
    calls = local(monkeypatch, service, revoke)
    response = search(client, root)
    assert response.status_code in {401, 403, 404, 409}, response.text
    assert QUOTE not in response.text and len(calls) == 1


def test_validation_tenant_vertical_csrf_pending_and_empty(signed, monkeypatch):
    client, service, _, _ = signed
    doc, root = setup(client)
    retained(service, doc, status="running")
    calls = local(monkeypatch, service)
    assert search(client, root).json()["total_records"] == 0 and not calls
    for values in [{"query": " "}, {"query": "a" * 301}, {"offset": True}, {"mode": "jev"},
                   {"as_of": "2026-01-01"}, {"as_of": (utcnow() + timedelta(days=1)).isoformat()}, {"unexpected": True}]:
        assert search(client, root, **values).status_code == 422
    assert client.post(root + "/evidence-search", json={"query": "test"}).status_code == 403
    assert search(client, root.replace("pharma", "loyer")).status_code == 404
    assert _register(client, "outsider@example.ch", "Another tenant").status_code == 201
    response = search(client, root)
    assert response.status_code == 404 and not calls


def test_completed_source_withdrawal_filters_counts_and_check(signed, monkeypatch):
    client, service, identity, _ = signed
    doc, root = setup(client)
    retained(service, doc)
    calls = local(monkeypatch, service)
    first = search(client, root).json()
    with service.db.session() as session:
        session.add(DossierEntry(dossier_id=doc["id"], actor_user_id=identity["user"]["id"],
            kind="source_review", request_key=str(uuid4()), url="https://example.org/source",
            data_json={"revision": 1, "decision": "exclude"}))
        session.commit()
    check = search(client, root, check_only=True, as_of=first["as_of"], fingerprint=first["fingerprint"])
    assert check.status_code == 409 and QUOTE not in check.text
    result = search(client, root).json()
    assert result["total_records"] == 0 and len(calls) == 2


def test_local_rate_protection_and_bounded_preview(signed, monkeypatch):
    client, service, _, _ = signed
    doc, root = setup(client)
    retained(service, doc, [QUOTE + " extra" * 600], finding=False)
    calls = local(monkeypatch, service)
    for _ in range(6):
        result = search(client, root)
        assert result.status_code == 200, result.text
        item = result.json()["items"][0]
        assert item["text_truncated"] and len(item["quote"]) == 2400
    assert all(len(str(state)) < 4000 for state in calls)
    assert search(client, root).status_code == 429
    assert search(client, root, "two eight", mode="literal").status_code == 200
    assert len(calls) == 6


@pytest.mark.parametrize("role", ["VIEWER", "CONTRIBUTOR", "EDITOR"])
def test_real_guest_can_search_only_invited_dossier_and_revocation_is_live(signed, monkeypatch, role):
    from test_product_guests import accept, guest, invitation
    from test_product_teams import switch

    from helvetic_lens.product_models import DossierMember

    client, service, _, _ = signed
    account, cookies = guest(client, service)
    doc, root = setup(client, audience="team")
    _, sibling = setup(client, audience="team")
    retained(service, doc)
    item = invitation(client, root, account, role)
    switch(client, cookies)
    accept(client, root, item)
    calls = local(monkeypatch, service)
    result = search(client, root)
    assert result.status_code == 200, result.text
    page = result.json()
    assert page["total_records"] == 2 and len(calls) == 2
    assert search(client, sibling).status_code == 404
    with service.db.session() as session:
        membership = session.scalar(select(DossierMember).where(DossierMember.dossier_id == doc["id"],
            DossierMember.user_id == account["user"]["id"]))
        session.delete(membership)
        session.commit()
    revoked = search(client, root, check_only=True, as_of=page["as_of"], fingerprint=page["fingerprint"])
    assert revoked.status_code in {403, 404} and QUOTE not in revoked.text and len(calls) == 2


@pytest.mark.parametrize("withdrawal", ["current_corpus", "previous_corpus", "earlier_url"])
def test_saved_page_search_withdrawal_uses_native_source_visibility(signed, monkeypatch, withdrawal):
    from test_product_document_history import setup as pages
    from test_product_investigations import complete
    from test_product_monitoring_research import due, enable, model
    from test_product_page_research import changed, last_run

    from helvetic_lens.models import Organization, Version

    client, service, _, target = signed
    _, root, law_id, baseline, _ = pages(client)
    earlier_url = "https://example.ch/earlier-original"
    with service.db.session() as session:
        session.get(Version, baseline).source_url = earlier_url
        session.commit()
    enable(client, root, include_page_changes=True)
    current = changed(client, service, law_id, "The saved page describes a new private evidence requirement.")
    model(monkeypatch, target)
    due(service)
    run = complete(client, service, root + "/investigations", last_run(client, root))
    assert run["claims"]
    first = search(client, root, "saved", mode="literal")
    assert first.status_code == 200 and first.json()["total_records"] > 0, first.text
    with service.db.session() as session:
        if withdrawal == "earlier_url":
            session.add(DossierEntry(dossier_id=root.split('/')[-1], request_key=str(uuid4()), kind="source_review",
                url=earlier_url, data_json={"decision": "exclude", "revision": 1}))
        else:
            other = Organization(name="Revoked corpus", slug="revoked-search-corpus")
            session.add(other)
            session.flush()
            session.get(Version, current if withdrawal == "current_corpus" else baseline).owner_organization_id = other.id
        session.commit()
    response = search(client, root, "saved", mode="literal")
    assert response.status_code == 200 and response.json()["total_records"] == 0, response.text
    assert "private evidence requirement" not in response.text
