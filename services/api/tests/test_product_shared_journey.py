"""Fictional shared journey through acquisition, jobs, typed review and cited Ask.

These fixtures prove mechanics, not Semaglutide access or legal applicability.
Only transport/model responses are scripted; claims and evidence come from jobs.
"""
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from conftest import LAW_URL
from sqlalchemy import select
from test_auth import _register
from test_legal_profiles import config
from test_product_claim_interpretation import choice
from test_product_claim_review import body, item
from test_product_contributions import no_discovery
from test_product_domain_context import update
from test_product_dossiers import active, post
from test_product_dossiers import signed as signed
from test_product_investigations import complete
from test_product_monitoring_research import due, enable, model
from test_product_page_research import last_run
from test_product_research import question
from test_product_source_analysis import output, payload, separated
from test_product_source_authority import assessment, choices
from test_product_source_health import connect

from helvetic_lens.config import DomainError
from helvetic_lens.models import Version
from helvetic_lens.product_investigation_models import ClaimReview, DossierClaim, InvestigationEvent


def page(stage):
    return ("<html><head><title>Fictional administrative record</title></head><body><main>"
        f"<p>Fictional administrative record: demonstration review window is {stage} days.</p>"
        "<p>This synthetic page makes no drug, reimbursement or legal assertion.</p>"
        "</main></body></html>").encode()


def capture(client, service, root, law_id, stage):
    service.fetcher.values[LAW_URL] = page(stage)
    response = post(client, "/api/scans", {"law_ids": [law_id]})
    assert response.status_code == 202 and response.json()["status"] == "complete", response.text
    return client.get(root + "/documents/" + law_id + "/versions").json()["items"][0]["id"]


@pytest.mark.parametrize("product,template", [("legal", "legal-question"), ("pharma", "market-access")])
def test_saved_source_change_to_reviewed_claim_and_cited_ask(signed, monkeypatch, product, template):
    client, service, identity, target = signed
    base = f"/api/products/{product}"
    setup = config(name="Fictional shared journey", sector="Pharmaceutical research" if product == "pharma" else "Legal research",
        goal="Monitor changes to a fictional administrative record; do not infer real status.",
        topics=[{"id": str(uuid4()), "name": "Fictional administrative record", "description": "Follow retained demonstration revisions",
                 "keywords": ["fictional", "administrative", "record"]}])
    # Fedlex is an existing selected catalogue pack, not a verified Market Access feed.
    result = post(client, base + "/dossiers", {"creation_key": str(uuid4()), "config": setup,
        "template": {"id": template, "version": "1.0.0"}})
    assert result.status_code == 201, result.text
    doc = result.json()
    root = base + "/dossiers/" + doc["id"]
    context = ({"active_substances": ["Semaglutide"], "countries": ["Switzerland"], "tags": ["Fictional mechanics only"]}
               if product == "pharma" else {"jurisdictions": ["Switzerland"], "tags": ["Fictional mechanics only"]})
    saved, _ = update(client, root, context)
    assert saved.status_code == 200, saved.text
    assert client.get(root + "/domain-context").json()["values"] == saved.json()["values"]
    assert client.get(root).json()["template"]["selection"]["id"] == template
    active(client, client.get(root).json())
    service.fetcher.values[LAW_URL] = page(10)
    law_id = connect(client, root)
    history = root + "/documents/" + law_id + "/versions"
    baseline = client.get(history).json()["items"][0]["id"]
    enable(client, root, include_page_changes=True)
    external = no_discovery(monkeypatch)
    runs, versions = [], []
    with monkeypatch.context() as inference:
        calls = model(inference, target)
        assert due(service)["started"] == 0
        for days in (20, 30):
            versions.append(capture(client, service, root, law_id, days))
            assert due(service)["started"] == 1
            fetched = len(service.fetcher.calls)
            run = complete(client, service, root + "/investigations", last_run(client, root))
            assert run["status"] == "completed" and len(run["claims"]) == 1, run
            assert len(service.fetcher.calls) == fetched
            assert run["sources"][0]["snapshot"]["saved_page"]["version_id"] == versions[-1]
            runs.append(run)
        assert len(calls) == 3 and external == []  # Two extractions and the paired comparison.
        assert capture(client, service, root, law_id, 30) == versions[-1]
        assert due(service)["started"] == 0 and len(calls) == 3
    assert client.get(history).json()["total"] == 3
    changes = client.get(root + "/evidence-changes").json()
    assert changes["total"] == 1 and changes["items"][0]["kind"] == "UPDATES"
    ids = [run["claims"][0]["id"] for run in runs]
    with service.db.session() as session:
        original = {identifier: deepcopy((row.statement, row.status, row.revision, row.history))
                    for identifier in ids if (row := session.get(DossierClaim, identifier))}
        for version_id, days in zip([baseline, *versions], [10, 20, 30], strict=True):
            version = session.get(Version, version_id)
            assert f"{days} days" in version.text and version.artifact_key and version.content_hash
            assert version.source_url == LAW_URL and version.origin == "live"
            assert client.get(history + "/" + version_id).status_code == 200
    for index, decision in ((0, "dismissed"), (1, "accepted")):
        finding = item(client, root, ids[index])
        assert finding["human_status"] == "PROPOSED" and finding["reviewable"]
        citations = finding["evidence"] + finding["comparisons"][0]["evidence"]
        # A paired comparison also contains the claim's own citation.
        distinct_sources = {c["source"]["id"]: c for c in citations}
        request = body(finding, decision=decision, interpretation=choice(),
            source_assessments=choices(*(assessment(c["source"]["id"], c["id"], "USER_DOCUMENT") for c in distinct_sources.values())),
            reason="PRIVATE reviewer rationale for this fictional administrative record.")
        route = root + "/claim-reviews/review"
        reviewed = post(client, route, request)
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()["human_status"] == ("ACCEPTED" if index else "REJECTED")
        assert post(client, route, request).json() == reviewed.json()
        assert post(client, route, {**request, "request_key": str(uuid4())}).status_code == 409
    with service.db.session() as session:
        claims = list(session.scalars(select(DossierClaim).where(DossierClaim.dossier_id == doc["id"])))
        assert {c.id: (c.statement, c.status, c.revision, c.history) for c in claims} == original
        reviews = list(session.scalars(select(ClaimReview).where(ClaimReview.dossier_id == doc["id"])))
        assert len(reviews) == 2 and all(r.reviewed_by_user_id == identity["user"]["id"] for r in reviews)
        events = list(session.scalars(select(InvestigationEvent).where(
            InvestigationEvent.dossier_id == doc["id"], InvestigationEvent.kind == "claim_reviewed")))
        assert len(events) == 2
    thread, _ = question(client, root, "What changed in the fictional administrative record?")
    path = root + "/discussion/" + thread["id"]
    preview = separated(client, path)
    proposed = preview["input"]["claims"]
    assert proposed[0]["id"] == ids[1] and proposed[0]["human_review"]["human_status"] == "ACCEPTED"
    assert proposed[0]["comparisons"][0]["human_review"]["human_status"] == "REJECTED"
    citations = [s for s in preview["input"]["sources"] if s["kind"] == "investigation_quote"]
    assert {s["saved_version"]["id"] for s in citations} == set(versions)
    assert all(s["saved_version"]["recorded_revision"] == s["saved_version"]["current_revision"] for s in citations)
    assert "PRIVATE reviewer rationale" not in json.dumps(preview)
    target.responses = [json.dumps(output(preview))]
    response = post(client, path + "/research", payload(preview))
    assert response.status_code == 200, response.text
    note = response.json()
    assert note["data"]["findings"] == output(preview)["findings"]
    assert json.loads(target.calls[0][1]) == preview["input"] and len(target.calls) == 1
    assert note["data"]["claim_freshness"]["status"] == "current"
    assert client.get(path).json()["accepted"] is None
    assert post(client, path + "/accept", {"expected_revision": client.get(path).json()["revision"], "entry_id": note["id"]}).status_code == 200
    assert "Quoted saved text" in client.get(root + "/brief").text
    before = client.get(root + "/coverage").json()["documents"][0]
    service.fetcher.values[LAW_URL] = DomainError("Fictional source unavailable", 502, "source_unavailable")
    assert post(client, "/api/scans", {"law_ids": [law_id]}).json()["status"] == "partial"
    coverage = client.get(root + "/coverage").json()
    failed = coverage["documents"][0]
    assert coverage["limitations"] and failed["last_result"] == "failed" and failed["last_error"]
    assert failed["last_success_at"] == before["last_success_at"] < failed["last_checked"]
    assert failed["saved_version_at"] == before["saved_version_at"]
    assert client.get(history + "/" + versions[0]).status_code == 200
    assert capture(client, service, root, law_id, 30) == versions[-1]
    recovered = client.get(root + "/coverage").json()["documents"][0]
    assert recovered["last_result"] == "unchanged" and recovered["last_success_at"] > failed["last_success_at"]
    assert due(service)["started"] == 0 and len(target.calls) == 1 and external == []
    export = client.get(root + "/export").json()
    assert len(export["claim_ledger"]) == 2 and len(export["monitoring_research"]["items"]) == 2
    assert any(e["id"] == note["id"] for e in export["entries"])
    client.cookies.clear()
    assert client.get(base + "/public-dossiers").json()["total"] == 0
    for route in (root, root + "/export", root + "/coverage", path, history + "/" + versions[0]):
        assert client.get(route).status_code == 401
    assert _register(client, f"foreign-{product}-journey@example.ch").status_code == 201
    for route in (root, root + "/export", root + "/claim-reviews", path, history + "/" + versions[0]):
        assert client.get(route).status_code == 404
