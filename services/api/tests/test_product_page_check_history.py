"""Connected native scans, retained versions and dossier research; fictional sources."""
from datetime import timedelta
from uuid import uuid4

import pytest
from conftest import LAW_URL, ScriptedModel, policy
from sqlalchemy import select
from test_auth import _register
from test_law_history_metadata import recording
from test_product_document_history import setup
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_investigations import complete
from test_product_monitoring_research import due, enable, model
from test_product_page_research import changed, last_run

from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.models import DocumentWatch, Organization, OrganizationMembership, Scan, ScanItem, Version
from helvetic_lens.product_models import DossierEntry, ProductDossier


def route(root, law_id):
    return root + "/documents/" + law_id + "/checks"


def read(client, root, law_id, **params):
    response = client.get(route(root, law_id), params=params)
    assert response.status_code == 200, response.text
    assert "no-store" in response.headers["cache-control"]
    return response.json()


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_connected_page_to_checks_versions_research_and_visible_failure(signed, monkeypatch, product):
    client, service, _, target = signed
    _, root, law_id, baseline, versions = setup(client, product)
    assert read(client, root, law_id)["total"] == 0  # Attachment baseline is not an invented scan.
    assert post(client, "/api/scans", {"law_ids": [law_id]}).json()["status"] == "complete"
    unchanged = read(client, root, law_id)["items"][0]
    assert unchanged["outcome"] == "unchanged" and unchanged["research"] is None
    assert len(unchanged["versions"]) == 1 and unchanged["versions"][0]["id"] == baseline
    assert unchanged["started_at"] <= unchanged["finished_at"]
    enable(client, root, include_page_changes=True)
    current = changed(client, service, law_id, "Alpine Research publishes a revised fictional register entry.")
    calls = model(monkeypatch, target)
    assert due(service)["started"] == 1
    run = complete(client, service, root + "/investigations", last_run(client, root))
    before = (len(service.fetcher.calls), len(calls))
    with recording(service) as (_, loaded):
        history = read(client, root, law_id)
        assert loaded == []  # Native version text is not loaded for history metadata.
    entry = history["items"][0]
    assert entry["outcome"] == "changed" and entry["research"]["state"] == "completed"
    assert entry["research"]["investigation_id"] == run["id"]
    quote = entry["research"]["finding"]["evidence"]["quote"]
    assert "Alpine Research publishes a revised fictional register entry." in quote
    with service.db.session() as session:
        assert quote in session.get(Version, current).text
    assert [v["id"] for v in entry["versions"]] == [baseline, current]
    for version in entry["versions"]:
        saved = client.get(versions + "/" + version["id"], params={"expected_revision": version["evidence_revision"]})
        assert saved.status_code == 200 and saved.json()["document"]["id"] == law_id
    assert read(client, root, law_id)["items"] == history["items"]
    assert (len(service.fetcher.calls), len(calls)) == before
    last_success = client.get(root).json()["documents"][0]["last_success_at"]
    service.fetcher.values[LAW_URL] = DomainError("PRIVATE SOURCE ERROR", 502, "unavailable")
    assert post(client, "/api/scans", {"law_ids": [law_id]}).json()["status"] == "partial"
    failed = read(client, root, law_id)
    assert failed["items"][0]["outcome"] == "failed" and failed["items"][0]["finished_at"]
    assert failed["items"][0]["research"] is None and "PRIVATE" not in str(failed)
    assert client.get(root).json()["documents"][0]["last_success_at"] == last_success
    service.fetcher.values[LAW_URL] = policy("Alpine Research publishes a revised fictional register entry.")
    assert post(client, "/api/scans", {"law_ids": [law_id]}).json()["status"] == "complete"
    recovery = read(client, root, law_id)["items"][0]
    assert recovery["outcome"] == "unchanged" and recovery["research"] is None
    assert len(calls) == before[1]  # Neither same-content scan nor reader repeats dossier analysis.


@pytest.mark.parametrize("withdrawal", ["exclude", "unlink", "law_corpus", "version_corpus", "prior_corpus", "prior_url", "team", "product"])
def test_history_rechecks_source_link_corpus_audience_and_product(signed, withdrawal):
    client, service, _, _ = signed
    doc, root, law_id, baseline, _ = setup(client)
    current = changed(client, service, law_id, "Fictional revised source material.")
    assert read(client, root, law_id)["items"][0]["versions"]
    with service.db.session() as session:
        if withdrawal in {"exclude", "prior_url"}:
            url = LAW_URL if withdrawal == "exclude" else "https://example.org/withdrawn-original"
            if withdrawal == "prior_url":
                session.get(Version, baseline).source_url = url
            session.add(DossierEntry(dossier_id=doc["id"], request_key=str(uuid4()), kind="source_review", url=url,
                body="PRIVATE EXCLUSION", data_json={"decision": "exclude", "revision": 1}))
        elif withdrawal == "unlink":
            session.delete(session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == doc["id"], DossierEntry.kind == "monitor")))
        elif withdrawal == "team":
            session.get(ProductDossier, doc["id"]).monitoring_audience = "team"
        elif withdrawal != "product":
            other = Organization(name="Other corpus", slug="other-corpus")
            session.add(other)
            session.flush()
            if withdrawal == "law_corpus":
                from helvetic_lens.models import Law
                session.get(Law, law_id).owner_organization_id = other.id
            else:
                session.get(Version, baseline if withdrawal == "prior_corpus" else current).owner_organization_id = other.id
        session.commit()
    url = route(root, law_id).replace("pharma", "legal") if withdrawal == "product" else route(root, law_id)
    response = client.get(url)
    if withdrawal in {"version_corpus", "prior_corpus", "prior_url"}:
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["outcome"] == "evidence_unavailable" and not item["versions"] and not item["research"]
    else:
        assert response.status_code == 404
    assert "PRIVATE" not in response.text and "Fictional revised" not in response.text


def test_history_pagination_is_bounded_and_cutoff_does_not_include_later_checks(signed):
    client, service, _, target = signed
    _, root, law_id, _, _ = setup(client)
    with service.db.session() as session:
        scan = Scan(total=25, status="complete")
        session.add(scan)
        session.flush()
        for i in range(25):
            session.add(ScanItem(scan_id=scan.id, law_id=law_id, stage="complete", result="skipped", analysis_status="not_run"))
        session.commit()
    before = (len(service.fetcher.calls), len(target.calls))
    with recording(service) as (_, loaded):
        first = read(client, root, law_id)
        seen = [v["id"] for v in first["items"]]
        assert first["total"] == 25 and len(seen) == first["page_size"] == 10
        offset = first["next_offset"]
        while offset is not None:
            page = read(client, root, law_id, offset=offset, as_of=first["as_of"])
            seen.extend(v["id"] for v in page["items"])
            offset = page["next_offset"]
        assert len(set(seen)) == 25 and not loaded
    post(client, "/api/scans", {"law_ids": [law_id]})
    assert read(client, root, law_id, as_of=first["as_of"])["total"] == 25
    assert read(client, root, law_id)["total"] == 26
    assert len(target.calls) == before[1]
    for params in ({"offset": 10}, {"offset": -1}, {"as_of": "2026-01-01T00:00:00"}, {"as_of": (utcnow()+timedelta(days=1)).isoformat()}):
        assert client.get(route(root, law_id), params=params).status_code == 422


@pytest.mark.parametrize("stage,result,expected", [("queued", None, "pending"), ("interrupted", "cancelled", "interrupted"), ("complete", "skipped", "skipped")])
def test_unknown_attempt_times_are_not_reconstructed_from_scan_completion(signed, stage, result, expected):
    client, service, _, _ = signed
    _, root, law_id, _, _ = setup(client)
    with service.db.session() as session:
        scan = Scan(total=1, status="complete", finished_at=utcnow())
        session.add(scan)
        session.flush()
        session.add(ScanItem(scan_id=scan.id, law_id=law_id, stage=stage, result=result, events=[]))
        session.commit()
    item = read(client, root, law_id)["items"][0]
    assert item["outcome"] == expected and item["finished_at"] is None and item["started_at"] is None


def test_pausing_retains_authorized_history_but_viewer_and_session_boundaries_remain(signed):
    client, service, identity, _ = signed
    _, root, law_id, _, _ = setup(client)
    post(client, "/api/scans", {"law_ids": [law_id]})
    with service.db.session() as session:
        session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law_id)).active = False
        session.commit()
    assert read(client, root, law_id)["items"]
    viewer = _register(client, "source-history-viewer@example.ch").json()
    assert client.get(route(root, law_id)).status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=viewer["user"]["id"], organization_id=identity["organization"]["id"], role="viewer"))
        session.commit()
    post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]})
    assert read(client, root, law_id)["items"]
    assert post(client, route(root, law_id), {}).status_code in {403, 405}
    client.cookies.clear()
    assert client.get(route(root, law_id)).status_code == 401


@pytest.mark.parametrize("failed", [False, True])
def test_native_analysis_result_is_distinct_from_successful_page_capture(signed, monkeypatch, failed):
    client, service, _, target = signed
    _, root, law_id, _, _ = setup(client)
    service.environment_settings.apertus_base_url = "https://model.example/v1"
    service.environment_settings.apertus_model = "fixture"
    target.fail = failed
    monkeypatch.setattr(target, "complete", ScriptedModel.complete.__get__(target))
    service.fetcher.values[LAW_URL] = policy(60)
    response = post(client, "/api/scans", {"law_ids": [law_id]})
    assert response.status_code == 202
    assert response.json()["status"] == ("partial" if failed else "complete"), response.text
    item = read(client, root, law_id)["items"][0]
    assert item["outcome"] == "changed" and len(item["versions"]) == 2
    assert item["analysis_status"] == ("failed" if failed else "succeeded")
    assert item["research"] is None and item["finished_at"] and target.calls
    assert client.get(root).json()["documents"][0]["last_success_at"]


@pytest.mark.parametrize("case", ["synthetic", "import", "prior_revision", "current_revision"])
def test_retained_research_never_uses_an_example_or_corrected_version(signed, monkeypatch, case):
    client, service, _, target = signed
    _, root, law_id, baseline, _ = setup(client)
    enable(client, root, include_page_changes=True)
    current = changed(client, service, law_id, "Fictional changed text for the new research.")
    calls = model(monkeypatch, target)
    assert due(service)["started"] == 1
    complete(client, service, root + "/investigations", last_run(client, root))
    assert read(client, root, law_id)["items"][0]["research"]["finding"]
    with service.db.session() as session:
        version = session.get(Version, baseline if case == "prior_revision" else current)
        if case == "synthetic":
            version.synthetic = True
        elif case == "import":
            version.origin = "import"
        else:
            version.evidence_revision += 1
        session.commit()
    before = (len(service.fetcher.calls), len(calls))
    item = read(client, root, law_id)["items"][0]
    if case in {"synthetic", "import"}:
        assert item["outcome"] == "example_or_import" and item["research"] is None
    else:
        assert not item["research"] or (item["research"]["state"] == "unavailable" and not item["research"]["finding"])
    assert (len(service.fetcher.calls), len(calls)) == before


def test_selected_historical_baseline_does_not_claim_a_fresh_page_change(signed):
    client, service, _, _ = signed
    _, root, law_id, baseline, _ = setup(client)
    current = changed(client, service, law_id, "Fictional historical comparison text.")
    response = post(client, "/api/scans", {"law_ids": [law_id], "baseline_version_id": baseline})
    assert response.status_code == 202, response.text
    native = response.json()["items"][0]
    assert native["live_result"] == "unchanged" and native["mode"] == "historical", response.text
    item = read(client, root, law_id)["items"][0]
    assert item["outcome"] == "historical_comparison"
    assert [v["id"] for v in item["versions"]] == [baseline, current]
    assert item["research"] is None
