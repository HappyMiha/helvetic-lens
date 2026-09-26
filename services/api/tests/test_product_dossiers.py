import json
from uuid import uuid4

import pytest
from conftest import LAW_URL, FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_auth import _csrf, _register, _settings
from test_legal_profiles import config

from helvetic_lens import monitoring_topics
from helvetic_lens.main import create_app
from helvetic_lens.models import OrganizationMembership
from helvetic_lens.product_models import DossierEntry

ROOT = "/api/products/pharma/dossiers"


class TopicModel(ScriptedModel):
    responses: list[str]

    async def complete(self, system, user, **kwargs):
        self.calls.append((system, user))
        return self.responses.pop(0)


@pytest.fixture
def signed(tmp_path):
    model = TopicModel()
    app = create_app(_settings(tmp_path), fetcher=FakeFetcher(), model_client=model)
    with TestClient(app) as client:
        identity = _register(client).json()
        with app.state.service.db.organization_context(identity["organization"]["id"]):
            yield client, app.state.service, identity, model


def post(client, path, body):
    return client.post(path, headers=_csrf(client), json=body)


def create(client):
    body = {"creation_key": str(uuid4()), "config": config()}
    result = post(client, ROOT, body)
    assert result.status_code == 201, result.text
    return result.json(), body


def active(client, dossier):
    profile = dossier["profile"]
    result = post(client, f"/api/monitoring-profiles/{profile['id']}/activate", {"expected_revision": profile["revision"]})
    assert result.status_code == 200, result.text
    return result.json()


def test_persistence_retry_notes_export_and_product_boundary(signed):
    client, _, _, _ = signed
    doc, body = create(client)
    assert post(client, ROOT, body).json()["id"] == doc["id"]
    assert client.get(ROOT).json()["total"] == 1
    assert client.get(ROOT.replace("pharma", "loyer")).json()["total"] == 0
    route = ROOT + "/" + doc["id"]
    assert client.get(route.replace("pharma", "loyer")).status_code == 404
    entry = {"request_key": str(uuid4()), "kind": "note", "body": "Review before the next safety meeting."}
    saved = post(client, route + "/entries", entry)
    assert saved.status_code == 201, saved.text
    assert post(client, route + "/entries", entry).json()["id"] == saved.json()["id"]
    assert post(client, route + "/entries", {**entry, "body": "different"}).status_code == 409
    read = client.get(route).json()
    assert read["entry_count"] == 1 and read["entries"][0]["body"] == entry["body"]
    exported = client.get(route + "/export")
    assert exported.status_code == 200 and exported.json()["file_bytes_included"] is False
    assert exported.json()["entries"][0]["author"] == "Ada Example"
    assert "no-store" in exported.headers["cache-control"]
    assert post(client, route + "/entries", {**entry, "request_key": str(uuid4()), "kind": "reference", "url": "javascript:alert(1)"}).status_code == 422


def test_files_download_integrity_tenant_denial_and_csrf(signed):
    client, _, _, _ = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    upload = client.post(route + "/files", headers=_csrf(client), files={"file": ("../../report.txt", b"Evidence from a primary source.", "text/plain")})
    assert upload.status_code == 201, upload.text
    file = upload.json()
    assert file["title"] == "report.txt" and len(file["sha256"]) == 64
    path = route + "/files/" + file["id"]
    assert client.get(path).content == b"Evidence from a primary source."
    assert "attachment" in client.get(path).headers["content-disposition"]
    assert client.post(route + "/files", files={"file": ("x", b"x")}).status_code == 403
    assert client.post(route + "/files", headers=_csrf(client), files={"file": ("x", b"")}).status_code == 413
    other, _ = create(client)
    assert client.get(ROOT + "/" + other["id"] + "/files/" + file["id"]).status_code == 404
    assert _register(client, "second@example.ch", "Other organization").status_code == 201
    for p in (route, path, route + "/export"):
        response = client.get(p)
        assert response.status_code == 404 and "no-store" in response.headers["cache-control"]
    assert client.get(ROOT).json()["items"] == []


def test_viewer_readonly_and_author_private_draft(signed):
    client, service, identity, _ = signed
    draft, _ = create(client)
    activated, _ = create(client)
    active(client, activated)
    member = _register(client, "reader@example.ch").json()
    with service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=member["user"]["id"], organization_id=identity["organization"]["id"], role="viewer"))
        session.commit()
    selected = post(client, "/api/auth/session/organization", {"organization_id": identity["organization"]["id"]})
    assert selected.status_code == 200, selected.text
    assert client.get(ROOT + "/" + draft["id"]).status_code == 404
    assert client.get(ROOT + "/" + activated["id"]).status_code == 200
    assert post(client, ROOT + "/" + activated["id"] + "/entries", {"request_key": str(uuid4()), "kind": "note", "body": "not permitted"}).status_code == 403
    assert post(client, ROOT, {"creation_key": str(uuid4()), "config": config()}).status_code == 403


def test_feedback_to_real_ai_proposal_and_reviewed_native_revision(signed):
    client, service, _, model = signed
    doc, _ = create(client)
    profile = active(client, doc)
    route = ROOT + "/" + doc["id"]
    feedback = post(client, route + "/entries", {"request_key": str(uuid4()), "kind": "feedback", "body": "Focus on citizenship applications and avoid unrelated migration news.", "relevance": "not_relevant"})
    assert feedback.status_code == 201
    model.responses = [json.dumps({"topics": [{"name": "Citizenship applications", "description": "Follow procedure changes", "keywords": ["naturalisation", "citizenship application"]}]})]
    proposal = post(client, route + "/improve", {"expected_revision": profile["revision"], "feedback": "Narrow this topic"})
    assert proposal.status_code == 200, proposal.text
    entry = proposal.json()
    assert entry["data"]["feedback_ids"] == [feedback.json()["id"]]
    topic = profile["topics"][0]
    assert "Focus on citizenship" in str(model.calls)
    with service.db.session() as session:
        assert monitoring_topics.get_topic(session, topic["id"])["current_revision"] == topic["current_revision"]
    applied = post(client, route + "/improvements/apply", {"proposal_id": entry["id"], "topic_id": topic["id"], "suggestion": 0, "expected_revision": topic["current_revision"]})
    assert applied.status_code == 200, applied.text
    with service.db.session() as session:
        changed = monitoring_topics.get_topic(session, topic["id"])
        assert changed["current_revision"] == topic["current_revision"] + 1
        assert changed["plan"]["concepts"] == ["naturalisation", "citizenship application"]
        assert session.scalar(select(DossierEntry).where(DossierEntry.kind == "improvement")) is not None


def test_stale_proposal_and_foreign_topic_do_not_change_monitoring(signed):
    client, _, _, model = signed
    doc, _ = create(client)
    profile = active(client, doc)
    route = ROOT + "/" + doc["id"]
    model.responses = [json.dumps({"topics": [{"name": "New topic", "description": "Narrower scope", "keywords": ["specific"]}]})]
    proposal = post(client, route + "/improve", {"expected_revision": profile["revision"]}).json()
    values = {"proposal_id": proposal["id"], "topic_id": str(uuid4()), "suggestion": 0, "expected_revision": 1}
    assert post(client, route + "/improvements/apply", values).status_code == 404
    topic = profile["topics"][0]
    paused = post(client, f"/api/monitoring-profiles/{profile['id']}/status", {"expected_revision": profile["revision"], "status": "paused"})
    assert paused.status_code == 200
    values["topic_id"] = topic["id"]
    assert post(client, route + "/improvements/apply", values).status_code == 409


def test_primary_page_watch_uses_native_fetch_evidence_and_scheduler(signed):
    client, service, _, _ = signed
    doc, _ = create(client)
    route = ROOT + "/" + doc["id"]
    ref = post(client, route + "/entries", {"request_key": str(uuid4()), "kind": "reference", "title": "Official page", "url": LAW_URL}).json()
    watch_path = route + "/sources/" + ref["id"] + "/monitor"
    assert post(client, watch_path, {}).status_code == 422
    active(client, doc)
    result = post(client, watch_path, {})
    assert result.status_code == 200, result.text
    assert post(client, watch_path, {}).json()["id"] == result.json()["id"]
    saved = client.get(route).json()
    assert len(saved["documents"]) == 1 and saved["documents"][0]["auto_check_enabled"]
    assert saved["documents"][0]["last_checked"]
    assert service.fetcher.calls[0][0] == LAW_URL
    from helvetic_lens.document_monitoring import enqueue_due
    queued = enqueue_due(service.db, service.environment_settings)
    assert queued["documents"] == 1
    assert enqueue_due(service.db, service.environment_settings)["documents"] == 0


def test_source_guidance_uses_real_catalogue_and_rejects_invented_sources(signed):
    client, _, _, model = signed
    doc, _ = create(client)
    path = ROOT + "/" + doc["id"] + "/source-advice"
    model.responses = [json.dumps({"recommendations": [{"source_id": "fedlex-legislation", "reason": "Official Swiss legislation for the requested scope."}]})]
    result = post(client, path, {"expected_revision": 1})
    assert result.status_code == 200, result.text
    assert result.json()["recommendations"][0]["source_id"] == "fedlex-legislation"
    assert "catalogue" in model.calls[-1][1]
    model.responses = [json.dumps({"recommendations": [{"source_id": "invented-pharma-feed", "reason": "Unverified coverage"}]})]
    assert post(client, path, {"expected_revision": 1}).status_code == 502


def test_retention_preserves_referenced_files_and_erasure_collects_them(signed):
    import os
    from datetime import timedelta

    from helvetic_lens.account_erasure_store import select_private_rows
    from helvetic_lens.db import utcnow
    from helvetic_lens.maintenance import cleanup_operational_data
    from helvetic_lens.models import User

    client, service, identity, _ = signed
    doc, _ = create(client)
    result = client.post(ROOT + "/" + doc["id"] + "/files", headers=_csrf(client), files={"file": ("audit.txt", b"retained evidence")})
    assert result.status_code == 201
    with service.db.session() as session:
        entry = session.get(DossierEntry, result.json()["id"])
        key = entry.artifact_key
    file = service.environment_settings.storage_path / "artifacts" / key
    old = (utcnow() - timedelta(days=100)).timestamp()
    os.utime(file, (old, old))
    cleanup_operational_data(service.db, service.environment_settings)
    assert file.read_bytes() == b"retained evidence"
    with service.db.session(include_all_organizations=True) as session:
        user = session.get(User, identity["user"]["id"])
        selection = select_private_rows(session, user, [identity["organization"]["id"]])
        assert key in selection.artifacts
        assert selection.counts["product_dossiers"] == 1
        assert selection.counts["product_dossier_entries"] == 1
