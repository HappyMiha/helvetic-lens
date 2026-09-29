"""Fictional editor context, distinct consent and inherited dependency privacy."""
import asyncio
import json
from uuid import uuid4

import pytest
from test_product_claim_interpretation import choice
from test_product_claim_review import body, item, link
from test_product_claim_synthesis import answer, generate, preview, request, setup
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_operations import action
from test_product_source_authority import assessment, choices

from helvetic_lens import product_claim_synthesis as synthesis
from helvetic_lens.product_investigation_models import (
    ClaimChange,
    ClaimEvidence,
    DossierClaim,
    Investigation,
    InvestigationSource,
)
from helvetic_lens.product_investigations import scope
from helvetic_lens.product_models import DossierEntry

TYPED = "claims_typed_v1"


def reviewed(signed, product="pharma"):
    values, path = setup(signed, product)
    client, service, _, root, ids, sources, runs, _, evidence = values
    with service.db.session() as session:
        link(session, runs, ids, evidence)
    role = "PRIMARY_BINDING" if product == "loyer" else "REGULATORY_PUBLICATION"
    code = "CASE_HOLDING" if product == "loyer" else "REGULATORY_STATUS"
    for index in (0, 1):
        response = post(client, root + "/claim-reviews/review", body(item(client, root, ids[index]),
            interpretation=choice("SOURCE_STATEMENT", code) if index == 0 else choice(),
            source_assessments=choices(
                assessment(sources[0], evidence[0], role if index == 0 else "USER_DOCUMENT", reason="SECRET editorial explanation"),
                assessment(sources[1], evidence[1], "SECONDARY_COMMENTARY")),
            reason="SECRET reviewer rationale"))
        assert response.status_code == 200, response.text
    return values, path


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_independent_claim_types_and_source_roles_are_explicit_exact_inputs(signed, product):
    values, path = reviewed(signed, product)
    client, _, _, root, ids, sources, _, _, _ = values
    old = preview(client, path)
    assert "editor_context" not in json.dumps(old["input"])
    value, data, saved = generate(client, signed[3], path, TYPED)
    assert old["evidence_fingerprint"] != value["evidence_fingerprint"]
    own = next(c for c in value["input"]["claims"] if c["id"] == ids[0])
    paired = own["comparisons"][0]
    assert own["editor_context"]["interpretation"]["kind"] == "SOURCE_STATEMENT"
    assert paired["id"] == ids[1] and paired["editor_context"]["interpretation"]["kind"] == "AI_INTERPRETATION"
    own_roles = {r["source_record_id"]: r["category"] for r in own["editor_context"]["source_assessments"]["items"]}
    pair_roles = {r["source_record_id"]: r["category"] for r in paired["editor_context"]["source_assessments"]["items"]}
    assert own_roles[sources[0]] in ("PRIMARY_BINDING", "REGULATORY_PUBLICATION")
    assert pair_roles[sources[0]] == "USER_DOCUMENT" and own_roles[sources[1]] == "SECONDARY_COMMENTARY"
    source_map = {s["id"]: s for s in value["input"]["sources"]}
    for claim in value["input"]["claims"]:
        for node in (claim, *claim["comparisons"]):
            for role in node["editor_context"]["source_assessments"]["items"]:
                assert source_map[role["citation_id"]]["source_record_id"] == role["source_record_id"]
    assert "SECRET" not in json.dumps(value) and "SECRET" not in json.dumps(saved)
    assert json.loads(signed[3].calls[0][1]) == value["input"]
    assert saved["data"]["claims"] == value["input"]["claims"]
    assert post(client, path + "/research", data).json() == saved
    assert post(client, path + "/research", {**data, "evidence_scope": "claims_v1"}).status_code == 409
    assert len(signed[3].calls) == 1
    current = client.get(path).json()
    assert post(client, path + "/accept", {"expected_revision": current["revision"], "entry_id": saved["id"]}).status_code == 200
    brief = client.get(root + "/brief")
    assert "Editor context (current)" in brief.text and "User document" in brief.text


def test_typed_consent_requires_matching_preview_and_never_upgrades_old_requests(signed):
    values, path = reviewed(signed)
    client = values[0]
    old, value = preview(client, path), preview(client, path, TYPED)
    assert post(client, path + "/research", {"request_key": str(uuid4()), "expected_revision": 1, "evidence_scope": TYPED}).status_code == 422
    assert post(client, path + "/research", {**request(value), "expected_evidence": old["evidence_fingerprint"]}).status_code == 409
    assert post(client, path + "/research", {**request(value), "evidence_scope": "claims_v1"}).status_code == 409
    assert not signed[3].calls


def test_stale_classifications_and_missing_roles_are_unknown_not_provider_facts(signed):
    values, path = reviewed(signed)
    client, service, _, _, ids, sources, _, _, _ = values
    with service.db.session() as session:
        source = session.get(InvestigationSource, sources[0])
        source.snapshot = {**source.snapshot, "fictional_revision": 2}
        session.commit()
    value = preview(client, path, TYPED)
    for claim in value["input"]["claims"]:
        for node in (claim, *claim["comparisons"]):
            context = node["editor_context"]
            assert context["status"] == "stale" and context["interpretation"] is None
            assert all(r["category"] == "UNASSESSED" for r in context["source_assessments"]["items"])
    assert "REGULATORY_PUBLICATION" not in json.dumps(value["input"])
    other, other_path = setup(signed)
    unknown = preview(client, other_path, TYPED)
    node = next(c for c in unknown["input"]["claims"] if c["id"] == other[4][1])
    assert node["editor_context"]["status"] == "unreviewed"
    assert node["editor_context"]["interpretation"] is None
    assert all(r["category"] == "UNASSESSED" for r in node["editor_context"]["source_assessments"]["items"])


def second_degree(signed, monkeypatch):
    values, path = setup(signed)
    client, service, doc, root, ids, sources, runs, _, evidence = values
    with service.db.session() as session:
        link(session, runs, ids, evidence)
        previous = session.get(Investigation, runs[1])
        run = Investigation(dossier_id=doc["id"], organization_id=previous.organization_id,
            status="completed", request_key=str(uuid4()), question="Fictional extra context", external_discovery=False)
        session.add(run)
        session.flush()
        original = session.get(InvestigationSource, sources[1])
        source = InvestigationSource(**scope(run), source_key="third", kind="contribution", title="Additional fictional context",
            url="https://example.test/third", sha256=original.sha256, snapshot=original.snapshot)
        claim = DossierClaim(**scope(run), statement="Unranked extra context", status="SUPPORTED")
        session.add_all([source, claim])
        session.flush()
        quote = session.get(ClaimEvidence, evidence[1])
        citation = ClaimEvidence(**scope(run), claim_id=claim.id, source_id=source.id, quote=quote.quote, locator=quote.locator, relation="SUPPORTS")
        session.add(citation)
        session.flush()
        session.add(ClaimChange(**scope(run), claim_id=claim.id, evidence_id=citation.id,
            previous_claim_id=ids[1], previous_investigation_id=runs[1], previous_evidence_id=evidence[1],
            previous_revision=1, previous_status="SUPPORTED", kind="CONTRADICTS", explanation="Fictional extra context."))
        session.commit()
        extra_source = source.id
    assert post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]))).status_code == 200
    assert post(client, root + "/claim-reviews/review", body(item(client, root, ids[1]), interpretation=choice(), decision="needs_more_evidence")).status_code == 200
    monkeypatch.setattr(synthesis, "CLAIMS", 1)
    return values, path, extra_source


def test_related_review_extra_source_inherits_note_export_brief_and_action_privacy(signed, monkeypatch):
    values, path, extra_source = second_degree(signed, monkeypatch)
    client, service, doc, root, ids, _, _, _, _ = values
    value, data, saved = generate(client, signed[3], path, TYPED)
    assert [c["id"] for c in value["input"]["claims"]] == [ids[0]]
    assert extra_source not in {s.get("source_record_id") for s in value["input"]["sources"]}
    with service.db.session() as session:
        pins = session.get(DossierEntry, saved["id"]).data_json["claim_contexts"]
        assert extra_source in {s for pin in pins for s in pin["sources"]}
    current = client.get(path).json()
    assert post(client, path + "/accept", {"expected_revision": current["revision"], "entry_id": saved["id"]}).status_code == 200
    _, task_data = action(client, root, title="PRIVATE generated gap action", detail="PRIVATE generated gap detail",
        research_origin={"thread_id": current["id"], "entry_id": saved["id"], "gap_index": 0})
    with service.db.session() as session:
        source = session.get(InvestigationSource, extra_source)
        session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", request_key=str(uuid4()), url=source.url,
            data_json={"decision": "exclude", "revision": 1}))
        session.commit()
    for response in (client.get(path), post(client, path + "/research", data), client.get(root + "/export"),
                     client.get(root + "/brief"), client.get(root + "/actions"), post(client, root + "/actions", task_data)):
        assert response.status_code in (200, 201), response.text
        assert "PRIVATE generated gap" not in response.text and "Fictional answer derived" not in response.text
    assert client.get(path).json()["accepted"]["data"]["claim_freshness"]["status"] == "unavailable"


def test_related_review_change_during_inference_rejects_result(signed, monkeypatch):
    values, path, _ = second_degree(signed, monkeypatch)
    client, service, _, root, ids, _, _, _, _ = values
    value = preview(client, path, TYPED)
    def change_review():
        return post(client, root + "/claim-reviews/review", body(item(client, root, ids[1]), interpretation=choice("UNKNOWN", "UNCLASSIFIED")))
    async def infer(*args, **kwargs):
        response = await asyncio.to_thread(change_review)
        assert response.status_code == 200, response.text
        return answer(value)
    service.model_client.complete = infer
    assert post(client, path + "/research", request(value)).status_code == 409
    assert post(client, path + "/research", request(value)).status_code == 409


def test_typed_metadata_does_not_bypass_exact_citation_validation(signed):
    values, path = reviewed(signed)
    client = values[0]
    value = preview(client, path, TYPED)
    result = json.loads(answer(value))
    result["findings"][0]["citations"][0]["quote"] = "Invented passage that the editor did not verify."
    signed[3].responses = [json.dumps(result)]
    response = post(client, path + "/research", request(value))
    assert response.status_code == 502
    assert "unsupported citation" in response.text
