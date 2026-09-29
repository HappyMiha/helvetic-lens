"""Fictional, editor-assigned types; no legal or medical factual assertions."""
import copy
from uuid import uuid4

import pytest
from test_product_claim_review import body, item, link, seed
from test_product_dossiers import post
from test_product_dossiers import signed as signed

from helvetic_lens.product_investigation_models import DossierClaim, Investigation, InvestigationSource
from helvetic_lens.product_models import DossierEntry, PublicContribution


def choice(kind="AI_INTERPRETATION", claim_type="AI_ANALYSIS", **values):
    return {"schema_version": 1, "domain_pack_version": "1.3.0", "kind": kind, "claim_type": claim_type, **values}


@pytest.mark.parametrize("product,code,other", [("loyer", "CASE_HOLDING", "CLINICAL_RESULT"),
                                               ("pharma", "CLINICAL_RESULT", "CASE_HOLDING")])
@pytest.mark.parametrize("public", [False, True])
def test_classification_is_explicit_domain_scoped_and_versioned_without_rewriting_claim(signed, product, code, other, public):
    client, service, _, root, ids, _, _, _, _ = seed(signed, product=product, public=public)
    first = item(client, root, ids[0])
    assert "interpretation" not in first
    options = client.get(root + "/claim-reviews").json()["interpretation_options"]
    assert options["domain_pack_version"] == "1.3.0"
    assert code in {row["claim_type"] for row in options["types"]}
    assert other not in {row["claim_type"] for row in options["types"]}
    with service.db.session() as session:
        claim = session.get(DossierClaim, ids[0])
        original = copy.deepcopy((claim.statement, claim.status, claim.revision, claim.history))
    route = root + "/claim-reviews/review"
    data = body(first, interpretation=choice("SOURCE_STATEMENT", code), confirm_public=public)
    assert client.post(route, json=data).status_code == 403
    if public:
        assert post(client, route, {**data, "confirm_public": False}).status_code == 409
    saved = post(client, route, data)
    assert saved.status_code == 200, saved.text
    value = saved.json()
    assert value["interpretation"]["kind"] == "SOURCE_STATEMENT"
    assert value["interpretation"]["authority"] == "UNASSESSED"
    assert value["history"][0]["basis"]["interpretation"] == value["interpretation"]
    assert value["human_status"] == "ACCEPTED" and value["claim"]["evidence_status"] == "CONTESTED"
    assert post(client, route, data).json() == value
    assert post(client, route, body(value, confirm_public=public)).status_code == 409, "legacy client cannot silently clear the type"
    stale_request = body(first, interpretation=choice(), confirm_public=public)
    assert post(client, route, stale_request).status_code == 409
    changed = post(client, route, body(value, interpretation=choice(), confirm_public=public)).json()
    assert changed["revision"] == 2 and changed["interpretation"]["kind"] == "AI_INTERPRETATION"
    assert changed["history"][0]["basis"]["interpretation"]["claim_type"] == code
    assert post(client, route, data).json() == changed, "late replay cannot restore the old classification"
    reset = post(client, route, body(changed, interpretation=choice("UNKNOWN", "UNCLASSIFIED"), confirm_public=public)).json()
    assert reset["interpretation"]["kind"] == "UNKNOWN" and len(reset["history"]) == 3
    with service.db.session() as session:
        claim = session.get(DossierClaim, ids[0])
        assert (claim.statement, claim.status, claim.revision, claim.history) == original
    if public:
        client.cookies.clear()
        assert item(client, root, ids[0]) == reset
    else:
        export = client.get(root + "/export").json()
        assert next(row for row in export["claim_ledger"] if row["id"] == ids[0]) == reset
    assert signed[3].calls == []


@pytest.mark.parametrize("data,status", [
    (choice("SOURCE_STATEMENT", "CASE_HOLDING"), 422),
    (choice("USER_ASSERTION", "CLINICAL_RESULT"), 422),
    (choice(domain_pack_version="0.0.0"), 409),
    (choice(authority="PRIMARY_BINDING"), 422),
])
def test_invalid_or_unreviewed_authority_and_wrong_domain_types_are_rejected(signed, data, status):
    client, _, _, root, ids, _, _, _, _ = seed(signed, product="pharma")
    value = item(client, root, ids[0])
    response = post(client, root + "/claim-reviews/review", body(value, interpretation=data))
    assert response.status_code == status, response.text
    assert item(client, root, ids[0])["history"] == []


@pytest.mark.parametrize("public", [False, True])
def test_stale_and_hidden_related_evidence_never_present_current_classification(signed, public):
    client, service, doc, root, ids, sources, runs, _, evidence = seed(signed, public=public)
    with service.db.session() as session:
        link(session, runs, ids, evidence)
    saved = post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]),
        interpretation=choice("USER_ASSERTION", "USER_STATEMENT"), confirm_public=public)).json()
    with service.db.session() as session:
        session.get(DossierClaim, ids[0]).revision += 1
        session.commit()
    stale = item(client, root, ids[0])
    assert stale["stale"] and stale["human_status"] == "UNRESOLVED"
    assert stale["interpretation"] == saved["interpretation"]
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
    assert hidden["history_unavailable"] and not hidden["history"]
    assert "interpretation" not in hidden and hidden["decision"] is None


def test_legacy_retry_fingerprint_survives_optional_classification(signed):
    from sqlalchemy import select

    from helvetic_lens.product_claim_review_api import Review
    from helvetic_lens.product_entity_identity import digest
    from helvetic_lens.product_investigation_models import ClaimReview

    client, service, _, root, ids, _, _, _, _ = seed(signed)
    data = body(item(client, root, ids[0]))
    value = post(client, root + "/claim-reviews/review", data).json()
    legacy = Review(**data).model_dump(mode="json")
    legacy.pop("interpretation")
    with service.db.session() as session:
        review = session.scalar(select(ClaimReview).where(ClaimReview.claim_id == ids[0]))
        assert review.request_fingerprint == digest([review.reviewed_by_user_id, legacy])
    assert post(client, root + "/claim-reviews/review", data).json() == value


def test_classification_change_invalidates_search_and_synthesis_without_new_model_inputs(signed):
    from test_product_claim_synthesis import answer, preview, request, setup

    from helvetic_lens.product_search_review import snapshot

    values, path = setup(signed)
    client, service, doc, root, ids, _, _, _, _ = values
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
    changed = post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]), interpretation=choice()))
    assert changed.status_code == 200, changed.text
    with service.db.session() as session:
        after = snapshot(session, doc["id"], ids)
    assert before != after and after[ids[0]]["interpretation"]["kind"] == "AI_INTERPRETATION"
    fresh = preview(client, path)
    assert fresh["evidence_fingerprint"] != old["evidence_fingerprint"]
    assert all("interpretation" not in value["human_review"] for value in fresh["input"]["claims"])
    assert post(client, path + "/research", request(old)).status_code == 409
    thread = client.get(path).json()
    note = thread["accepted"]
    assert note["data"]["claim_freshness"]["status"] == "changed"
    assert thread["answer_needs_review"]
    assert post(client, path + "/accept", {"expected_revision": thread["revision"], "entry_id": note_id,
        "expected_review": thread["answer_review"]["fingerprint"]}).status_code == 409
    assert len(signed[3].calls) == 1
