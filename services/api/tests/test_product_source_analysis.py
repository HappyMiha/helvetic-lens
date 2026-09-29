"""Fictional typed answer output: literal quotations, explicit consent and retained privacy."""
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_product_claim_review import body, item
from test_product_claim_synthesis import answer, preview, request, setup
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_operations import action
from test_product_research import question
from test_product_reviewed_synthesis import reviewed, second_degree

from helvetic_lens import product_research as research
from helvetic_lens.product_investigation_models import DossierClaim, InvestigationSource
from helvetic_lens.product_models import DossierEntry

FORMAT = "source_analysis_v1"


def separated(client, path, scope="claims_typed_v1"):
    response = client.get(path + f"/research-preview?evidence_scope={scope}&answer_format={FORMAT}")
    assert response.status_code == 200, response.text
    return response.json()


def payload(value):
    return {**request(value), "answer_format": FORMAT}


def output(value):
    source = next(s for s in value["input"]["sources"] if s["kind"] == "investigation_quote")
    citation = {"source_id": source["id"], "quote": source["text"][:250]}
    return {"findings": [
        {"kind": "SOURCE_QUOTE", "claim": citation["quote"], "citations": [citation]},
        {"kind": "AI_INTERPRETATION", "claim": "PRIVATE fictional <script>AI interpretation</script>.", "citations": [citation]}],
        "unknowns": ["PRIVATE fictional gap"], "search_queries": ["fictional official evidence"]}


def generate(client, model, path, scope="claims_typed_v1"):
    value = separated(client, path, scope)
    model.responses = [json.dumps(output(value))]
    data = payload(value)
    result = post(client, path + "/research", data)
    assert result.status_code == 200, result.text
    return value, data, result.json()


@pytest.mark.parametrize("product,scope", [("pharma", "claims_v1"), ("loyer", "claims_typed_v1")])
def test_format_retains_literal_quotes_separate_analysis_exact_inputs_export_and_brief(signed, product, scope):
    values, path = reviewed(signed, product)
    client, service, _, root, ids, _, _, _, _ = values
    old = preview(client, path, scope)
    value, data, saved = generate(client, signed[3], path, scope)
    assert value["input"] == old["input"] and value["evidence_fingerprint"] != old["evidence_fingerprint"]
    assert value["answer_contract"] == research.SOURCE_ANALYSIS
    assert json.loads(signed[3].calls[0][1]) == value["input"]
    assert "Use SOURCE_QUOTE only" in signed[3].calls[0][0]
    assert "contradict" in json.dumps(value["input"]).lower()
    assert saved["data"]["findings"] == output(value)["findings"]
    assert saved["data"]["answer_contract"] == value["answer_contract"]
    assert saved["body"].startswith("Quoted saved text:\n") and "AI interpretation:\n" in saved["body"]
    assert saved["data"]["claim_freshness"]["status"] == "current"
    assert client.get(path).json()["accepted"] is None
    assert post(client, path + "/research", data).json() == saved
    assert post(client, path + "/research", {**data, "answer_format": "standard"}).status_code == 409
    assert len(signed[3].calls) == 1
    with service.db.session() as session:
        assert set(session.scalars(select(DossierClaim.id).where(DossierClaim.dossier_id == values[2]["id"]))) == set(ids)
    exported = client.get(root + "/export").json()
    note = next(e for e in exported["entries"] if e["id"] == saved["id"])
    assert note["data"]["findings"] == saved["data"]["findings"]
    current = client.get(path).json()
    assert post(client, path + "/accept", {"expected_revision": current["revision"], "entry_id": saved["id"]}).status_code == 200
    brief = client.get(root + "/brief")
    assert brief.status_code == 200 and "<h5>Quoted saved text</h5>" in brief.text and "<h5>AI interpretation</h5>" in brief.text
    assert "PRIVATE fictional &lt;script&gt;AI interpretation&lt;/script&gt;." in brief.text and "<script>" not in brief.text
    assert research.SOURCE_ANALYSIS["boundary"] in brief.text
    finding = brief.text.split("<h5>Quoted saved text</h5>")[1].split("</section>")[0]
    assert finding.count(output(value)["findings"][0]["claim"]) == 1


def test_invalid_contract_combinations_and_changed_contract_fail_before_inference(signed, monkeypatch):
    values, path = setup(signed)
    client = values[0]
    old = preview(client, path)
    explicit = client.get(path + "/research-preview?evidence_scope=claims_v1&answer_format=standard").json()
    assert explicit["evidence_fingerprint"] == old["evidence_fingerprint"]
    assert "answer_contract" not in explicit and "answer_format" not in explicit
    value = separated(client, path, "claims_v1")
    for changes, status in [({"answer_format": "future"}, 422), ({"evidence_scope": "saved"}, 422),
        ({"expected_evidence": None}, 422), ({"expected_evidence": old["evidence_fingerprint"]}, 409),
        ({"answer_format": "standard"}, 409)]:
        assert post(client, path + "/research", {**payload(value), **changes}).status_code == status
    for query in ("answer_format=source_analysis_v1", "evidence_scope=claims_v1&answer_format=future"):
        assert client.get(path + "/research-preview?" + query).status_code == 422
    monkeypatch.setattr(research, "SOURCE_ANALYSIS", {**research.SOURCE_ANALYSIS, "boundary": "Changed contract."})
    assert post(client, path + "/research", payload(value)).status_code == 409
    assert not signed[3].calls


@pytest.mark.parametrize("group", ["structure", "evidence"])
def test_strict_kinds_literal_text_and_every_citation_are_validated_before_save(signed, group):
    values, path = setup(signed)
    client, service, *_ = values
    value = separated(client, path)
    valid = output(value)
    variants = []
    for field, replacement in [("kind", None), ("kind", "SOURCE_FACT"), ("claim", "A paraphrase masquerading as literal saved text."),
        ("citations", valid["findings"][0]["citations"] * 2)]:
        broken = deepcopy(valid)
        if replacement is None:
            broken["findings"][0].pop(field)
        else:
            broken["findings"][0][field] = replacement
        variants.append(broken)
    for source_id, quote in [("invented", valid["findings"][0]["claim"]), ("S1", "Wholly fabricated source quotation.")]:
        broken = deepcopy(valid)
        broken["findings"][0].update(claim=quote, citations=[{"source_id": source_id, "quote": quote}])
        variants.append(broken)
    broken = deepcopy(valid)
    broken["findings"][1]["citations"][0]["quote"] = "Invented citation attached to AI interpretation."
    variants.append(broken)
    broken = deepcopy(valid)
    broken["findings"][0]["authority"] = "verified"
    variants.append(broken)
    # Each fixture stays within the real per-user inference rate limit.
    for broken in (variants[:4] if group == "structure" else variants[4:]):
        signed[3].responses = [json.dumps(broken)]
        result = post(client, path + "/research", payload(value))
        assert result.status_code == 502, result.text
    with service.db.session() as session:
        assert session.scalar(select(DossierEntry).where(DossierEntry.kind == "research")) is None
    schema = research.SeparatedResearchAnswer.model_json_schema()
    assert "kind" in schema["$defs"]["SeparatedFinding"]["required"]
    assert schema["$defs"]["SeparatedFinding"]["additionalProperties"] is False
    assert "kind" not in research.ResearchAnswer.model_json_schema()["$defs"]["Finding"]["properties"]


def test_default_output_and_saved_legacy_notes_keep_original_contract(signed):
    values, path = setup(signed)
    client, service, *_ = values
    value = preview(client, path)
    calls = []
    async def infer(prompt, text, **kwargs):
        calls.append((prompt, text, kwargs["response_schema"]))
        return answer(value)
    service.model_client.complete = infer
    data = {**request(value), "answer_format": "standard"}
    saved = post(client, path + "/research", data).json()
    assert "answer_format" not in saved["data"] and "answer_contract" not in saved["data"]
    assert all("kind" not in finding for finding in saved["data"]["findings"])
    assert calls[0][2] == research.ResearchAnswer.model_json_schema()
    assert "Use SOURCE_QUOTE only" not in calls[0][0]
    del data["answer_format"]
    assert post(client, path + "/research", data).json() == saved and len(calls) == 1


def test_empty_evidence_can_only_save_research_gaps(signed):
    values, _ = setup(signed)
    client, service, _, root, *_ = values
    # A separate empty dossier has no inherited claim inputs.
    from test_product_dossiers import ROOT, create
    doc, _ = create(client)
    thread, _ = question(client, ROOT + "/" + doc["id"])
    path = ROOT + "/" + doc["id"] + "/discussion/" + thread["id"]
    value = separated(client, path)
    assert not value["input"]["sources"]
    signed[3].responses = [json.dumps({"findings": [], "unknowns": ["Need retained evidence."], "search_queries": ["fictional source"]})]
    result = post(client, path + "/research", payload(value))
    assert result.status_code == 200 and result.json()["data"]["findings"] == []


@pytest.mark.parametrize("dependency", ["direct", "related"])
def test_withdrawn_dependency_hides_both_output_kinds_replay_export_brief_and_actions(signed, monkeypatch, dependency):
    values, path, extra = second_degree(signed, monkeypatch)
    client, service, doc, root, _, sources, _, _, _ = values
    _, data, saved = generate(client, signed[3], path)
    current = client.get(path).json()
    assert post(client, path + "/accept", {"expected_revision": current["revision"], "entry_id": saved["id"]}).status_code == 200
    _, task_data = action(client, root, title="PRIVATE fictional gap action", detail="PRIVATE fictional detail",
        research_origin={"thread_id": current["id"], "entry_id": saved["id"], "gap_index": 0})
    with service.db.session() as session:
        source = session.get(InvestigationSource, sources[0] if dependency == "direct" else extra)
        session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", request_key=str(uuid4()), url=source.url,
            data_json={"decision": "exclude", "revision": 1}))
        session.commit()
    replay = post(client, path + "/research", data)
    assert replay.json()["data"]["claim_freshness"]["status"] == "unavailable"
    assert "findings" not in replay.json()["data"] and "answer_contract" not in replay.json()["data"]
    for response in (client.get(path), replay, client.get(root + "/export"), client.get(root + "/brief"),
                     client.get(root + "/actions"), post(client, root + "/actions", task_data)):
        assert response.status_code in (200, 201), response.text
        assert "PRIVATE fictional" not in response.text
    assert len(signed[3].calls) == 1


def test_changed_context_blocks_stale_acceptance_and_results_generated_during_change(signed):
    values, path = setup(signed)
    client, service, _, root, ids, *_ = values
    _, _, saved = generate(client, signed[3], path)
    current = client.get(path).json()
    assert post(client, path + "/accept", {"expected_revision": current["revision"], "entry_id": saved["id"]}).status_code == 200
    assert post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]), decision="dismissed")).status_code == 200
    changed = client.get(path).json()
    assert changed["answer_needs_review"] and changed["accepted"]["data"]["claim_freshness"]["status"] == "changed"
    assert post(client, path + "/accept", {"expected_revision": changed["revision"], "entry_id": saved["id"], "expected_review": changed["answer_review"]["fingerprint"]}).status_code == 409
    value = separated(client, path)
    async def infer(*args, **kwargs):
        with service.db.session() as session:
            session.get(DossierClaim, ids[0]).revision += 1
            session.commit()
        return json.dumps(output(value))
    service.model_client.complete = infer
    assert post(client, path + "/research", payload(value)).status_code == 409
    assert post(client, path + "/research", payload(value)).status_code == 409
