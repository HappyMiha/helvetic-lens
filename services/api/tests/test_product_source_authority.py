"""Fictional editor assessments: exact source scope, not legal/clinical assertions."""
import copy
import json
from uuid import uuid4

import pytest
from test_product_claim_review import body, item, link, seed
from test_product_dossiers import post
from test_product_dossiers import signed as signed

from helvetic_lens.product_investigation_models import DossierClaim, Investigation, InvestigationSource
from helvetic_lens.product_models import DossierEntry, PublicContribution


def assessment(source, evidence, category="SECONDARY_COMMENTARY", **extra):
    return {"source_id": source, "evidence_id": evidence, "category": category,
        "reason": "Fictional editor assessment based on the retained demonstration citation.", **extra}


def choices(*items, **extra):
    return {"schema_version": 1, "domain_pack_version": "1.4.0", "items": list(items), **extra}


@pytest.mark.parametrize("product,primary,other", [
    ("loyer", "PRIMARY_BINDING", "REGULATORY_PUBLICATION"),
    ("pharma", "REGULATORY_PUBLICATION", "PRIMARY_BINDING"),
])
@pytest.mark.parametrize("public", [False, True])
def test_same_address_mixed_sources_retain_individual_roles_and_history(signed, product, primary, other, public):
    client, service, _, root, ids, sources, runs, _, evidence = seed(signed, product=product, public=public)
    with service.db.session() as session:
        session.get(InvestigationSource, sources[1]).url = session.get(InvestigationSource, sources[0]).url
        link(session, runs, ids, evidence)
        claim = session.get(DossierClaim, ids[0])
        original = copy.deepcopy((claim.statement, claim.status, claim.revision, claim.history))
    first = item(client, root, ids[0])
    assert "source_assessments" not in first
    options = client.get(root + "/claim-reviews").json()["source_assessment_options"]
    assert options["limit"] == 12 and options["domain_pack_version"] == "1.4.0"
    assert primary in {row["category"] for row in options["categories"]}
    assert other not in {row["category"] for row in options["categories"]}
    payload = choices(assessment(sources[0], evidence[0], primary), assessment(sources[1], evidence[1]))
    data = body(first, source_assessments=payload, confirm_public=public)
    route = root + "/claim-reviews/review"
    assert client.post(route, json=data).status_code == 403
    if public:
        assert post(client, route, {**data, "confirm_public": False}).status_code == 409
    response = post(client, route, data)
    assert response.status_code == 200, response.text
    saved = response.json()
    recorded = saved["source_assessments"]
    assert recorded["method"] == "editor_assessment"
    assert {row["source_id"]: row["category"] for row in recorded["items"]} == {
        sources[0]: primary, sources[1]: "SECONDARY_COMMENTARY"}
    assert saved["history"][0]["basis"]["source_assessments"] == recorded
    for row in recorded["items"]:
        current = next(value for value in first["evidence"] + first["comparisons"][0]["evidence"] if value["id"] == row["evidence_id"])
        assert row["source"] == current["source"] and row["quote"] == current["quote"] and row["locator"] == current["locator"]
    assert "source_assessments" not in item(client, root, ids[1]), "No inheritance to another review at the same address"
    assert post(client, route, data).json() == saved
    assert post(client, route, {**data, "source_assessments": choices()}).status_code == 409
    assert post(client, route, body(saved, confirm_public=public)).status_code == 409
    assert post(client, route, body(first, source_assessments=payload, confirm_public=public)).status_code == 409
    cleared = post(client, route, body(saved, source_assessments=choices(), confirm_public=public)).json()
    assert cleared["revision"] == 2 and not cleared["source_assessments"]["items"]
    assert cleared["history"][0]["basis"]["source_assessments"] == recorded
    assert post(client, route, data).json() == cleared
    with service.db.session() as session:
        claim = session.get(DossierClaim, ids[0])
        assert (claim.statement, claim.status, claim.revision, claim.history) == original
    if public:
        client.cookies.clear()
        assert item(client, root, ids[0]) == cleared
    else:
        assert next(row for row in client.get(root + "/export").json()["claim_ledger"] if row["id"] == ids[0]) == cleared
    assert signed[3].calls == []


@pytest.mark.parametrize("mutation,status", [("foreign_source", 422), ("foreign_citation", 422), ("duplicate", 422),
    ("category", 422), ("pack", 409), ("forged_pin", 422), ("over_limit", 422)])
def test_source_authority_rejects_foreign_unsupported_and_forged_assessments(signed, mutation, status):
    client, _, _, root, ids, sources, _, _, evidence = seed(signed, product="pharma")
    entry = assessment(sources[0], evidence[0])
    payload = choices(entry)
    if mutation == "foreign_source":
        entry["source_id"] = sources[1]
    elif mutation == "foreign_citation":
        entry["evidence_id"] = evidence[1]
    elif mutation == "duplicate":
        payload["items"].append(dict(entry))
    elif mutation == "category":
        entry["category"] = "PRIMARY_BINDING"
    elif mutation == "pack":
        payload["domain_pack_version"] = "1.3.0"
    elif mutation == "forged_pin":
        entry["source"] = {"sha256": "a" * 64}
    else:
        payload["items"] = [dict(entry) for _ in range(13)]
    response = post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]), source_assessments=payload))
    assert response.status_code == status, response.text
    assert not item(client, root, ids[0])["history"]


@pytest.mark.parametrize("public", [False, True])
def test_changed_capture_stales_assessment_and_hidden_related_source_hides_its_basis(signed, public):
    client, service, doc, root, ids, sources, runs, _, evidence = seed(signed, public=public)
    with service.db.session() as session:
        link(session, runs, ids, evidence)
    payload = choices(assessment(sources[1], evidence[1], reason="Sensitive fictional source role explanation."))
    data = body(item(client, root, ids[0]), source_assessments=payload, confirm_public=public)
    saved = post(client, root + "/claim-reviews/review", data).json()
    with service.db.session() as session:
        source = session.get(InvestigationSource, sources[1])
        source.snapshot = {**source.snapshot, "capture_correction": "fictional metadata correction"}
        session.commit()
    stale = item(client, root, ids[0])
    assert stale["stale"] and stale["human_status"] == "UNRESOLVED"
    assert stale["source_assessments"] == saved["source_assessments"]
    assert post(client, root + "/claim-reviews/review", data).status_code == 409
    with service.db.session() as session:
        if public:
            run = session.get(Investigation, runs[1])
            session.get(PublicContribution, run.public_contribution_id).status = "hidden"
        else:
            source = session.get(InvestigationSource, sources[1])
            session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", request_key=str(uuid4()),
                url=source.url, data_json={"decision": "exclude", "revision": 1}))
        session.commit()
    hidden = item(client, root, ids[0])
    assert hidden["history_unavailable"] and not hidden["history"] and "source_assessments" not in hidden
    assert "Sensitive fictional" not in json.dumps(hidden)


def test_role_change_invalidates_search_and_accepted_answer_without_new_provider_categories(signed):
    from test_product_claim_synthesis import answer, preview, request, setup

    from helvetic_lens.product_search_review import snapshot

    values, path = setup(signed)
    client, service, doc, root, ids, sources, _, _, evidence = values
    old = preview(client, path)
    signed[3].responses = [answer(old)]
    response = post(client, path + "/research", request(old))
    assert response.status_code == 200, response.text
    note_id = response.json()["id"]
    thread = client.get(path).json()
    assert post(client, path + "/accept", {"expected_revision": thread["revision"], "entry_id": note_id}).status_code == 200
    old = preview(client, path)
    with service.db.session() as session:
        before = snapshot(session, doc["id"], ids)
    response = post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]),
        source_assessments=choices(assessment(sources[0], evidence[0]))))
    assert response.status_code == 200, response.text
    with service.db.session() as session:
        after = snapshot(session, doc["id"], ids)
    assert after != before
    projected = after[ids[0]]["source_assessments"]["items"]
    assert projected == [{"source_id": sources[0], "category": "SECONDARY_COMMENTARY", "label": "Secondary commentary"}]
    fresh = preview(client, path)
    assert fresh["evidence_fingerprint"] != old["evidence_fingerprint"]
    assert "source_assessments" not in json.dumps(fresh["input"])
    assert "Fictional editor assessment" not in json.dumps(fresh["input"])
    assert post(client, path + "/research", request(old)).status_code == 409
    thread = client.get(path).json()
    assert thread["accepted"]["data"]["claim_freshness"]["status"] == "changed" and thread["answer_needs_review"]
    assert post(client, path + "/accept", {"expected_revision": thread["revision"], "entry_id": note_id,
        "expected_review": thread["answer_review"]["fingerprint"]}).status_code == 409
    assert len(signed[3].calls) == 1
