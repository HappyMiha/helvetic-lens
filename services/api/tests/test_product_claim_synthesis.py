"""Fictional claim inputs: consent, exact citations, dependencies and retained access."""
import json
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_product_claim_review import body, item, link, seed
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_operations import action
from test_product_research import question

from helvetic_lens.product_investigation_models import (
    ClaimEvidence,
    DossierClaim,
    Investigation,
    InvestigationSource,
)
from helvetic_lens.product_investigations import scope
from helvetic_lens.product_models import DossierEntry


def setup(signed, product="pharma"):
    values = seed(signed, product=product)
    client, _, _, root, ids, _, _, _, _ = values
    response = post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]), reason="PRIVATE reviewer rationale must never enter the model."))
    assert response.status_code == 200, response.text
    thread, _ = question(client, root, "Fictional finding demonstration record interpretation")
    return values, root + "/discussion/" + thread["id"]


def preview(client, path):
    result = client.get(path + "/research-preview?evidence_scope=claims_v1")
    assert result.status_code == 200, result.text
    return result.json()


def request(value):
    return {"request_key": str(uuid4()), "expected_revision": value["expected_revision"],
        "expected_evidence": value["evidence_fingerprint"], "evidence_scope": "claims_v1"}


def answer(value):
    source = next(s for s in value["input"]["sources"] if s["kind"] == "investigation_quote")
    return json.dumps({"findings": [{"claim": "Fictional answer derived from a retained quotation.",
        "citations": [{"source_id": source["id"], "quote": source["text"][:250]}]}],
        "unknowns": ["PRIVATE generated gap tied to a captured claim."], "search_queries": ["fictional official source"]})


def generate(client, model, path):
    value = preview(client, path)
    model.responses = [answer(value)]
    data = request(value)
    response = post(client, path + "/research", data)
    assert response.status_code == 200, response.text
    return value, data, response.json()


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_explicit_claim_preview_sends_exact_input_and_retains_both_sides(signed, product):
    values, path = setup(signed, product)
    client, service, _, root, ids, _, runs, _, evidence = values
    with service.db.session() as session:
        link(session, runs, ids, evidence)
    # Re-review the new complete comparison context.
    assert post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]))).status_code == 200
    value, data, saved = generate(client, signed[3], path)
    assert value["input"]["claims"][0]["id"] == ids[0]
    assert value["input"]["claims"][0]["human_review"]["human_status"] == "ACCEPTED"
    assert {s["relation"] for s in value["input"]["sources"] if s["kind"] == "investigation_quote"} == {"SUPPORTS", "CONTRADICTS"}
    assert value["input"]["claims"][0]["comparisons"][0]["kind"] == "CONTRADICTS"
    assert "PRIVATE reviewer" not in json.dumps(value) and "claim_contexts" not in value
    assert json.loads(signed[3].calls[0][1]) == value["input"]
    assert "claim_contexts" not in saved["data"] and saved["data"]["claim_freshness"]["status"] == "current"
    assert saved["data"]["claims"] == value["input"]["claims"]
    assert client.get(path).json()["accepted"] is None
    assert post(client, path + "/research", data).json() == saved
    assert post(client, path + "/research", {**data, "evidence_scope": "saved"}).status_code == 409
    assert len(signed[3].calls) == 1


def test_legacy_and_versioned_consent_are_separate(signed):
    values, path = setup(signed)
    client, _, _, _, _, _, _, _, _ = values
    modern = preview(client, path)
    legacy = client.get(path + "/research-preview").json()
    assert "claims" not in legacy["input"] and not any(s["kind"] == "investigation_quote" for s in legacy["input"]["sources"])
    assert post(client, path + "/research", {"request_key": str(uuid4()), "expected_revision": 1, "evidence_scope": "claims_v1"}).status_code == 422
    assert post(client, path + "/research", {**request(modern), "evidence_scope": "saved"}).status_code == 409
    assert post(client, path + "/research", {**request(modern), "expected_evidence": legacy["evidence_fingerprint"]}).status_code == 409
    signed[3].responses = [json.dumps({"findings": [], "unknowns": ["No legacy claim inputs."], "search_queries": ["fictional sources"]})]
    result = post(client, path + "/research", {"request_key": str(uuid4()), "expected_revision": legacy["expected_revision"]})
    assert result.status_code == 200 and json.loads(signed[3].calls[0][1]) == legacy["input"]


@pytest.mark.parametrize("change", ["review", "capture", "comparison", "exclude", "unfinished"])
def test_preview_and_inference_revalidate_claim_context(signed, change):
    values, path = setup(signed)
    client, service, doc, root, ids, sources, runs, _, evidence = values
    value = preview(client, path)
    def mutate():
        if change == "review":
            with service.db.session() as session:
                session.get(DossierClaim, ids[0]).revision += 1
                session.commit()
        else:
            with service.db.session() as session:
                if change == "capture":
                    source = session.get(InvestigationSource, sources[0])
                    source.snapshot = {**source.snapshot, "fixture_revision": 2}
                elif change == "comparison":
                    link(session, runs, ids, evidence)
                elif change == "exclude":
                    source = session.get(InvestigationSource, sources[0])
                    session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", request_key=str(uuid4()), url=source.url,
                        data_json={"decision": "exclude", "revision": 1}))
                else:
                    session.get(Investigation, runs[0]).status = "running"
                session.commit()
    async def infer(*args, **kwargs):
        mutate()
        return answer(value)
    service.model_client.complete = infer
    assert post(client, path + "/research", request(value)).status_code == 409
    assert post(client, path + "/research", request(value)).status_code == 409
    with service.db.session() as session:
        assert session.scalar(select(DossierEntry).where(DossierEntry.kind == "research")) is None


def test_changed_review_invalidates_answer_and_cannot_be_reconfirmed(signed):
    values, path = setup(signed)
    client, _, _, root, ids, _, _, _, _ = values
    _, data, saved = generate(client, signed[3], path)
    current = client.get(path).json()
    assert post(client, path + "/accept", {"expected_revision": current["revision"], "entry_id": saved["id"]}).status_code == 200
    before = client.get(path).json()
    assert not before["answer_needs_review"]
    assert post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]), decision="dismissed")).status_code == 200
    after = client.get(path).json()
    assert after["answer_needs_review"] and any(r["code"] == "claim_changed" for r in after["answer_review"]["reasons"])
    assert after["answer_review"]["fingerprint"] != before["answer_review"]["fingerprint"]
    assert after["accepted"]["data"]["claim_freshness"]["status"] == "changed"
    assert post(client, path + "/accept", {"expected_revision": after["revision"], "entry_id": saved["id"], "expected_review": after["answer_review"]["fingerprint"]}).status_code == 409
    assert post(client, path + "/research", data).json()["data"]["claim_freshness"]["status"] == "changed"
    assert len(signed[3].calls) == 1


@pytest.mark.parametrize("change", ["exclude", "delete", "unfinished"])
def test_unavailable_claim_hides_retained_note_replay_exports_and_followup(signed, change):
    values, path = setup(signed)
    client, service, doc, root, ids, sources, runs, _, _ = values
    _, data, saved = generate(client, signed[3], path)
    current = client.get(path).json()
    assert post(client, path + "/accept", {"expected_revision": current["revision"], "entry_id": saved["id"]}).status_code == 200
    task, task_data = action(client, root, title="PRIVATE generated gap copied to action", detail="PRIVATE generated gap detail",
        research_origin={"thread_id": current["id"], "entry_id": saved["id"], "gap_index": 0})
    with service.db.session() as session:
        if change == "exclude":
            source = session.get(InvestigationSource, sources[0])
            session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", request_key=str(uuid4()), url=source.url,
                data_json={"decision": "exclude", "revision": 1}))
        elif change == "delete":
            session.delete(session.get(DossierClaim, ids[0]))
        else:
            session.get(Investigation, runs[0]).status = "running"
        session.commit()
    for response in [client.get(path), post(client, path + "/research", data), client.get(root + "/export"), client.get(root + "/brief"),
                     client.get(root + "/actions"), post(client, root + "/actions", task_data)]:
        assert response.status_code in (200, 201), response.text
        assert "PRIVATE generated gap" not in response.text and "Fictional answer derived" not in response.text
    response = client.get(path).json()
    assert response["accepted"]["data"]["claim_freshness"]["status"] == "unavailable" and response["answer_needs_review"]
    assert post(client, path + "/accept", {"expected_revision": response["revision"], "entry_id": saved["id"]}).status_code == 409
    assert len(signed[3].calls) == 1


def test_oversized_group_is_omitted_whole_and_public_or_running_claims_are_absent(signed):
    values, path = setup(signed)
    client, service, _, _, ids, sources, runs, _, _ = values
    with service.db.session() as session:
        run = session.get(Investigation, runs[0])
        existing = session.scalar(select(ClaimEvidence).where(ClaimEvidence.claim_id == ids[0]))
        for _ in range(9):
            session.add(ClaimEvidence(**scope(run), claim_id=ids[0], source_id=sources[0], quote=existing.quote, locator=existing.locator, relation="CONTRADICTS"))
        session.get(Investigation, runs[1]).status = "running"
        session.commit()
    result = preview(client, path)
    assert result["input"]["claims"] == [] and result["selection"]["omitted_claim_groups"] == 1
    assert not signed[3].calls


def test_claim_preview_and_notes_do_not_cross_dossiers_or_anonymous_access(signed):
    values, path = setup(signed)
    client, service, _, _, ids, _, _, _, _ = values
    other, other_path = setup(signed)
    with service.db.session() as session:
        session.get(DossierClaim, ids[0]).statement = "PRIVATE foreign claim statement"
        session.commit()
    result = preview(client, other_path)
    assert "PRIVATE foreign claim statement" not in json.dumps(result)
    assert not set(ids) & {claim["id"] for claim in result["input"]["claims"]}
    assert client.post(other_path + "/research", json=request(result)).status_code == 403
    client.cookies.clear()
    assert client.get(path + "/research-preview?evidence_scope=claims_v1").status_code == 401
    assert client.get(other_path).status_code == 401
    assert not signed[3].calls


def test_current_brief_preserves_all_claim_quotes_and_escapes_context(signed):
    values, path = setup(signed)
    client, service, _, root, ids, _, _, _, _ = values
    with service.db.session() as session:
        session.get(DossierClaim, ids[0]).statement = "Fictional <script>claim</script> interpretation"
        session.commit()
    _, _, saved = generate(client, signed[3], path)
    current = client.get(path).json()
    assert post(client, path + "/accept", {"expected_revision": current["revision"], "entry_id": saved["id"]}).status_code == 200
    brief = client.get(root + "/brief")
    assert brief.status_code == 200 and "Claim context supplied at generation" in brief.text
    assert "SUPPORTS" in brief.text and "CONTRADICTS" in brief.text
    assert "&lt;script&gt;claim&lt;/script&gt;" in brief.text and "<script>" not in brief.text
    assert "not independent truth" in brief.text
