"""Workspace retrieval must be useful without hiding limits or leaking records."""
from datetime import timedelta
from uuid import uuid4

from test_product_dossiers import create
from test_product_dossiers import signed as signed

from helvetic_lens.db import utcnow
from helvetic_lens.legal_profile_models import LegalMonitoringProfile
from helvetic_lens.product_models import DossierEntry, ResearchThread


def entry(session, dossier_id, title, body, age=0):
    row = DossierEntry(dossier_id=dossier_id, kind="note", request_key=str(uuid4()), title=title, body=body,
                       created_at=utcnow() - timedelta(days=age))
    session.add(row)
    session.flush()
    return row.id


def test_all_words_cross_fields_reordered_terms_and_phrase_title_relevance(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    with service.db.session() as session:
        profile = session.get(LegalMonitoringProfile, doc["profile"]["id"])
        profile.config_json = {**profile.config_json, "name": "Medicine programme", "goal": "Follow safety updates"}
        session.add(ResearchThread(dossier_id=doc["id"], creation_key=str(uuid4()), creation_fingerprint="test",
            title="Safety status", body="Review medicine evidence"))
        title_hit = entry(session, doc["id"], "Medicine safety review", "Earlier reviewed reference", age=10)
        entry(session, doc["id"], "Recent observations", "New medicine safety evidence")
        entry(session, doc["id"], "Medicine programme", "Follow the safety evidence")
        session.commit()
    response = client.get("/api/products/pharma/discover", params={"q": "medicine safety"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 5 and len(data["items"]) == 5 and data["match_mode"] == "all"
    assert {hit["kind"] for hit in data["items"]} == {"topic", "question", "note"}
    assert [hit for hit in data["items"] if hit["kind"] == "note"][0]["id"] == title_hit
    reordered = client.get("/api/products/pharma/discover", params={"q": "SAFETY medicine"}).json()
    assert {hit["id"] for hit in reordered["items"]} == {hit["id"] for hit in data["items"]}
    exact = client.get("/api/products/pharma/discover", params={"q": "medicine safety", "mode": "phrase"}).json()
    assert exact["total"] == 2 and exact["match_mode"] == "phrase"
    assert exact["items"][0]["id"] == title_hit


def test_literal_wildcards_bounded_words_and_trimmed_minimum(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    with service.db.session() as session:
        exact = entry(session, doc["id"], "trial_a", "The observed value is 50%")
        entry(session, doc["id"], "trialXa", "The observed value is 500")
        session.commit()
    for phrase in ("trial_a", "50%"):
        result = client.get("/api/products/pharma/discover", params={"q": phrase}).json()
        assert result["total"] == 1 and result["items"][0]["id"] == exact
    many = " ".join("word" + str(i) for i in range(13))
    assert client.get("/api/products/pharma/discover", params={"q": many}).status_code == 422
    assert client.get("/api/products/pharma/discover", params={"q": many, "mode": "phrase"}).status_code == 200
    assert client.get("/api/products/pharma/discover", params={"q": " a "}).status_code == 422


def test_totals_explain_group_cap_and_repeated_order_is_stable(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    with service.db.session() as session:
        for number in range(25):
            entry(session, doc["id"], f"Capillary evidence {number}", "Saved source observations")
        session.commit()
    first = client.get("/api/products/pharma/discover?q=capillary").json()
    second = client.get("/api/products/pharma/discover?q=capillary").json()
    assert first["total"] == 25 and len(first["items"]) == 20
    assert [hit["id"] for hit in first["items"]] == [hit["id"] for hit in second["items"]]
    other_product = client.get("/api/products/loyer/discover?q=capillary").json()
    assert other_product["total"] == 0 and other_product["items"] == []
