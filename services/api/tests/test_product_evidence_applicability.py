"""Fictional professional research journeys; no live legal or medical facts."""
import hashlib
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_iterative_research import complete, pipeline
from test_product_selected_direction import choose

from helvetic_lens import decision_search, decision_sources
from helvetic_lens import product_evidence_applicability as applicability
from helvetic_lens.product_investigation_models import Investigation

SCENARIOS = {
    "legal": {"question": "Alpin courtyard rules in Canton A in 2024 — what applies?",
        "dimension": "jurisdiction", "requested": "Canton A", "other": "Canton B",
        "overview": "Fictional Canton B guidance describes quiet courtyard use in 2024; it does not determine the Canton A rule.",
        "counter": "A fictional tenant statement claims unrestricted courtyard use in Canton A; this is an allegation, not a court holding.",
        "targeted": "The fictional Canton A rule dated 2024 addresses quiet courtyard use; exceptions still require the actual lease.",
        "limit": "Other-canton guidance and a tenant allegation do not settle the applicable rule or lease exceptions."},
    "pharma": {"question": "Alpin medicine for indication A in Market A in 2024 — what is supported?",
        "dimension": "market", "requested": "Market A", "other": "Market B",
        "overview": "A fictional Market B notice concerns Product Beta for indication B in 2024; it does not determine Market A reimbursement.",
        "counter": "A fictional applicant claims unrestricted Market A access; this is an applicant statement, not the reimbursement decision.",
        "targeted": "The fictional Market A decision lists Product Alpha for indication A in 2024 with restricted eligibility; it is not an efficacy finding.",
        "limit": "Another market's notice and the applicant's claim do not establish local access or clinical efficacy."},
}


def start(client, domain="legal", product=None):
    product = product or domain
    command = {"request_key": str(uuid4()), "question": SCENARIOS[domain]["question"], "public_query_confirmed": True}
    response = post(client, f"/api/products/{product}/explore", command)
    assert response.status_code == 202, response.text
    value = response.json()
    return f'/api/products/{product}/dossiers/{value["dossier_id"]}', value["investigation"], command


def setup(monkeypatch, service, model, domain="legal", *, mode=None, callback=None):
    pipeline(monkeypatch, service, model)  # Existing configured fictional Jev/Laya gates.
    scenario = SCENARIOS[domain]
    trace = {"requests": [], "queries": [], "reads": []}

    async def search(settings, query, index, depth, product):
        trace["queries"].append(query)
        key = query.rsplit(" ", 1)[-1]
        assert key in {"overview", "counter", "targeted"}
        return {"items": [{"id": hashlib.sha256(query.encode()).hexdigest()[:32],
            "title": "Fictional " + domain + " " + key, "summary": "Controlled public-source fixture",
            "url": f"https://example.org/{domain}/{key}"}],
            "lanes": [{"status": "complete", "name": "Fictional index"}], "search_requests": 3}

    async def read(settings, query, item, mode, **kwargs):
        trace["reads"].append(item["url"])
        text = scenario[item["url"].rsplit("/", 1)[-1]]
        return {"status": "complete", "url": item["url"], "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "excerpts": [{"passage": "p1", "text": text}], "text_truncated": False}

    def cite(source):
        return {"source_id": source["id"], "quote": source["excerpts"][0]["text"], "locator": "p1"}

    def point(source, role="context"):
        return {"statement": source["excerpts"][0]["text"], "evidence": [{**cite(source), "role": role}]}

    async def response(system, user, **kwargs):
        data = json.loads(user)
        phase = kwargs["response_schema"]["title"]
        trace["requests"].append({"phase": phase, "input": deepcopy(data)})
        context = data.get("evidence_applicability")
        if context:
            assert applicability.SYSTEM in system
        if callback:
            callback(data, phase)
        if phase == "ResearchPlan":
            prefix = domain + (" chosen" if data.get("selected_direction") else "")
            return json.dumps({"objective": data["question"], "completion_criteria": ["Distinguish the requested scope from contextual material."],
                "branches": [{"question": scenario["question"], "query": prefix + " overview",
                    "purpose": "Test the uncertain name and scope against quoted public material.", "priority": 5},
                    {"question": "What conflicting account concerns " + scenario["requested"] + "?", "query": prefix + " counter",
                    "purpose": "Check a competing account without assuming it is an official finding.", "priority": 4}]})
        if phase == "ResearchExtraction":
            source = data["source"]
            text = source["excerpts"][0]["text"]
            draft = {**cite(source), "policy_id": domain + "-research/v1", "dimension": scenario["dimension"],
                "requested_detail": scenario["requested"], "source_detail": scenario["other"] if text == scenario["overview"] else scenario["requested"],
                "relation": "different" if text == scenario["overview"] else "aligned", "reason": scenario["limit"]}
            value = {"claims": [{"statement": text, "existing_claim_id": None, "relation": "SUPPORTS", "quote": text, "locator": "p1"}],
                "entities": [], "relationships": [], "source_class": {"category": "unknown", "quote": text, "locator": "p1"}}
            if data.get("read_question"):
                value["read_relevance"] = {**cite(source), "question_id": data["read_question"]["question_id"],
                    "category": "context", "reason": scenario["limit"], "limitations": []}
            if context and mode != "missing":
                if mode == "quote":
                    draft["quote"] = "INVALID PRIVATE OPTIONAL CANARY"
                elif mode == "source":
                    draft["source_id"] = str(uuid4())
                elif mode == "requested":
                    draft["requested_detail"] = "PRIVATE INFERRED TARGET"
                elif mode == "dimension":
                    draft["dimension"] = "invented_dimension"
                elif mode == "source_detail":
                    draft["source_detail"] = "INVENTED SOURCE DETAIL"
                elif mode == "unresolved":
                    draft.update(source_detail="", relation="unresolved")
                value["applicability_checks"] = "INVALID PRIVATE OPTIONAL CANARY" if mode == "shape" else [draft]
            return json.dumps(value)
        if phase == "Reflection":
            readings = context["readings"] if context else []
            mismatch = next((r for r in readings if any(c["relation"] == "different" for c in r["checks"])), None)
            gaps = []
            if mismatch:
                source = next(s for s in data["sources"] if s["id"] == mismatch["source_id"])
                gaps = [{**cite(source), "question": "Find the direct decision for " + scenario["requested"] + ".",
                    "query": domain + " targeted", "purpose": "Resolve the quoted scope mismatch for " + scenario["requested"] + ".",
                    "priority": 5, "kind": "missing_evidence"}]
            value = {"gaps": gaps, "outcome": scenario["limit"]}
            if data.get("branch_assessment_question"):
                value["assessment"] = {"question_id": data["branch_assessment_question"]["question_id"], "status": "partial",
                    "points": [point(s) for s in data["sources"]], "limitations": [scenario["limit"]]}
            return json.dumps(value)
        sources = data["sources"]
        source = sources[0]
        if phase == "EarlyOrientation":
            return json.dumps({"interpretations": [{**cite(source), "meaning": "Alpin may refer to the recorded subject; the intended scope remains correctable.",
                "why": "The read material exposes distinct source scopes.", "signal": "possible"}],
                "uncertainties": [scenario["limit"]], "clarification": "Should the next check establish the local decision or compare the other account?",
                "directions": [{**cite(source), "question": "Investigate the direct decision: " + scenario["question"], "why": "Check the requested scope against direct evidence."},
                    {**cite(sources[1]), "question": "Compare the competing account for " + scenario["requested"] + ".", "why": "Keep the alternative interpretation available."}]})
        assert phase == "Briefing"
        value = {"understanding": "The evidence separates the requested scope from a contextual comparison.",
            "findings": [{**cite(s), "statement": s["excerpts"][0]["text"],
                "basis": "analogy" if s["excerpts"][0]["text"] == scenario["overview"] else "contradiction" if s["excerpts"][0]["text"] == scenario["counter"] else "direct"} for s in sources],
            "uncertainties": [scenario["limit"]], "clarification": "", "directions": []}
        if data.get("direction_assessment_target"):
            chosen = next((s for s in sources if s["excerpts"][0]["text"] == scenario["targeted"]), source)
            value["direction_assessment"] = {"selection": data["direction_assessment_target"]["selection"], "status": "partial",
                "points": [point(chosen, "support")], "limitations": [scenario["limit"]]}
        return json.dumps(value)

    monkeypatch.setattr(decision_search, "federated_retrieve", search)
    monkeypatch.setattr(decision_sources, "safe_inspect", read)
    monkeypatch.setattr(model, "complete", response)
    return trace


@pytest.mark.parametrize("domain,product", [("legal", "legal"), ("pharma", "pharma"), ("legal", "pharma"), ("pharma", "legal")])
def test_scope_mismatch_drives_real_followup_and_preserves_contextual_evidence(signed, monkeypatch, domain, product):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, domain)
    root, run, command = start(client, domain, product)
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["status"] == "ready", final["stop_reason"]
    assert domain + " targeted" in trace["queries"]
    assert len(trace["reads"]) == 3
    assert final["question"] == command["question"]
    last = next(r["input"] for r in reversed(trace["requests"]) if r["phase"] == "Briefing")
    context = last["evidence_applicability"]
    assert context["policy"]["primary_policy"] == product + "-research/v1"
    assert {p["domain"] for p in context["policy"]["policies"]} == {"LEGAL", "PHARMA"}
    assert len(context["readings"]) == 3 and not context["unassessed_source_ids"]
    assert any(c["relation"] == "different" for r in context["readings"] for c in r["checks"])
    assert {f["basis"] for f in final["exploration"]["briefing"]["findings"]} == {"direct", "contradiction", "analogy"}
    assert SCENARIOS[domain]["limit"] in final["exploration"]["briefing"]["uncertainties"]
    assert "applicability_policy" not in json.dumps(final)
    assert not client.get(root + "/web-research").json()["policy"]["enabled"]
    assert all(final["research"]["used"].get(k, 0) <= v for k, v in final["research"]["limits"].items())


@pytest.mark.parametrize("domain", ["legal", "pharma"])
def test_typed_choice_retains_policy_and_memory_then_answers_with_current_scope(signed, monkeypatch, domain):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, domain)
    root, parent, _ = start(client, domain)
    _, direction, child, body = choose(client, service, root, parent)
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["status"] == "ready", final["stop_reason"]
    plan = next(r["input"] for r in trace["requests"] if r["phase"] == "ResearchPlan" and r["input"].get("selected_direction"))
    assert plan["research_memory"]["episodes"] and plan["question"] == direction["question"]
    assert plan["evidence_applicability"]["policy"]["primary_policy"] == domain + "-research/v1"
    assert final["exploration"]["briefing"]["assessment"]["limitations"] == [SCENARIOS[domain]["limit"]]
    assert post(client, root + "/investigations/" + parent["id"] + "/exploration/reply", body).json()["id"] == child["id"]
    with service.db.session() as session:
        assert applicability.current(session, session.get(Investigation, child["id"]))
    assert not client.get(root + "/web-research").json()["policy"]["enabled"]
