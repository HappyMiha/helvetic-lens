"""Search planning is an explicit model request, never hidden source retrieval."""
import json

import pytest
from sqlalchemy import func, select
from test_auth import _register
from test_product_dossiers import ROOT, create, post
from test_product_dossiers import signed as signed

from helvetic_lens import product_research
from helvetic_lens.config import DomainError
from helvetic_lens.models import OrganizationMembership
from helvetic_lens.product_models import DossierEntry

PLAN = {
    "angles": [{"label": "Official terminology", "reason": "Find the title of the relevant Swiss legislation.",
                "provider": "fedlex", "query": "Heilmittel"},
               {"label": "Published evidence", "reason": "Find literature describing safety evidence and its limits.",
                "provider": "europepmc", "query": "drug safety assessment"}],
    "clarifications": ["Which medicine and time period matter?"]}


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_plan_uses_only_submitted_question_and_does_not_search_or_change_topics(signed, monkeypatch, product):
    client, service, _, model = signed
    doc, _ = create(client)
    post(client, ROOT + "/" + doc["id"] + "/entries", {
        "request_key": "b09df172-5dbf-4b27-bc43-ea179cdbb2cd", "kind": "note", "body": "Confidential client code PRIVATE-MATTER-42"})
    async def unexpected_search(*args, **kwargs):
        pytest.fail("Planning must not contact public sources")
    monkeypatch.setattr(product_research, "public_search", unexpected_search)
    with service.db.session() as session:
        before = session.scalar(select(func.count()).select_from(DossierEntry))
    model.responses = ["```json\n" + json.dumps(PLAN) + "\n```"]
    question = "What evidence affects medicine safety assessment?"
    result = post(client, f"/api/products/{product}/discover/plan", {"question": "  " + question + "  "})
    assert result.status_code == 200, result.text
    assert result.json()["question"] == question and result.json()["angles"] == PLAN["angles"]
    assert result.json()["model"] == service.settings.apertus_model
    assert result.json()["model_provider"] == service.settings.apertus_provider
    assert "no-store" in result.headers["cache-control"]
    assert len(model.calls) == 1 and json.loads(model.calls[0][1]) == {"product": product, "question": question}
    assert "PRIVATE-MATTER-42" not in str(model.calls)
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(DossierEntry)) == before


@pytest.mark.parametrize("answer", [
    "not JSON",
    {**PLAN, "angles": []},
    {**PLAN, "angles": [{**PLAN["angles"][0], "provider": "invented-web-search"}]},
    {**PLAN, "angles": [{**PLAN["angles"][0], "query": "a" * 301}]},
    {**PLAN, "angles": [{**PLAN["angles"][0], "url": "https://invented.example/"}]},
    {**PLAN, "findings": ["An unsupported answer"]},
    {**PLAN, "clarifications": ["a" * 241]},
])
def test_invalid_or_invented_plans_are_rejected_without_partial_results(signed, answer):
    client, _, _, model = signed
    model.responses = [json.dumps(answer) if isinstance(answer, dict) else answer]
    result = post(client, "/api/products/pharma/discover/plan", {"question": "Help research medicine safety"})
    assert result.status_code == 502
    assert "angles" not in result.json() and "unchanged" in result.json()["detail"]


def test_plan_requires_session_csrf_editor_and_bounded_explicit_input(signed):
    client, service, identity, model = signed
    path = "/api/products/pharma/discover/plan"
    data = {"question": "Research medicine safety"}
    assert client.post(path, json=data).status_code == 403
    for values in ({"question": "   "}, {"question": "a" * 301}, {**data, "dossier_id": "hidden-context"}):
        assert post(client, path, values).status_code == 422
    assert post(client, path.replace("pharma", "unknown"), data).status_code == 422
    reader = _register(client, "planner-viewer@example.ch").json()
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=reader["user"]["id"], organization_id=identity["organization"]["id"], role="viewer"))
        session.commit()
    assert post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]}).status_code == 200
    assert post(client, path, data).status_code == 403
    client.cookies.clear()
    assert client.post(path, json=data).status_code == 401
    assert model.calls == []


def test_model_unavailable_preserves_manual_search(signed):
    client, _, _, model = signed
    async def unavailable(*args, **kwargs):
        raise DomainError("The configured model is unavailable. Retry later.", 503, "model_unavailable")
    model.complete = unavailable
    result = post(client, "/api/products/pharma/discover/plan", {"question": "Research medicine safety"})
    assert result.status_code == 503 and result.json()["code"] == "model_unavailable"
    response = client.get("/api/products/pharma/discover?q=medicine")
    assert response.status_code == 200 and response.json()["items"] == []


def test_planning_shares_the_bounded_discovery_budget_across_products(signed):
    client, _, _, model = signed
    for _ in range(5):
        assert client.get("/api/products/pharma/discover?q=medicine").status_code == 200
    model.responses = [json.dumps(PLAN)]
    data = {"question": "Research medicine safety"}
    assert post(client, "/api/products/pharma/discover/plan", data).status_code == 200
    limited = post(client, "/api/products/loyer/discover/plan", data)
    assert limited.status_code == 429 and limited.json()["code"] == "rate_limited"
    assert len(model.calls) == 1
