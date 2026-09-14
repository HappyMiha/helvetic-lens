import copy
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select, update
from test_auth import _csrf, _register, _settings
from test_tender_matching import NOW, profile
from test_tender_repository import parsed, publication, revised

from helvetic_lens.main import create_app
from helvetic_lens.models import Job, OrganizationMembership
from helvetic_lens.tender_models import TenderDossierVersion, TenderMonitor, TenderPublicationSnapshot
from helvetic_lens.tender_observations import observe_publication

ROOT = "/api/tender-watch"


@pytest.fixture
def api(tmp_path):
    settings = _settings(tmp_path, tender_watch_enabled=True, simap_public_source_enabled=True)
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        identity = _register(client).json()
        yield client, app, settings, identity


def post(client, path, body):
    return client.post(ROOT + path, json=body, headers=_csrf(client))


def create(client, configuration=None):
    body = {"configuration": configuration or profile().model_dump(mode="json"), "request_key": str(uuid4())}
    response = post(client, "/monitors", body)
    assert response.status_code == 201, response.text
    return response.json()


def test_document_original_and_text_routes_enforce_current_private_access(api):
    from datetime import timedelta
    from uuid import UUID

    from helvetic_lens import tender_documents as documents
    from helvetic_lens.document_parsing import parse_document
    from helvetic_lens.tender_models import TenderDocumentAccess

    client, app, _, identity = api
    monitor = transition(client, create(client), "start")
    raw = publication()
    dossier = ingest(app, identity, monitor, raw)[0]
    database = app.state.service.db
    body = b"5 references required"
    with database.organization_context(identity["organization"]["id"]), database.session() as session:
        grant = documents.record_access(session, identity["user"]["id"], dossier, source_id="simap",
                                        publication_id=raw["id"], account_reference="fixture-private-account",
                                        policy_reference="fixture-reviewed-policy", now=NOW,
                                        valid_until=NOW + timedelta(days=365), retain_until=NOW + timedelta(days=366))
        grant_id = grant.id
        parsed_doc, _ = parse_document(body, content_type="text/plain", snapshot_id=uuid4(),
                                       access_scope_id=UUID(grant_id), source_id="simap", dossier_id=dossier,
                                       item_id="requirements", language="en")
        snapshot = documents.store(session, identity["user"]["id"], dossier, parsed_doc, body,
                                   content_type="text/plain", now=NOW)
        session.commit()
    path = ROOT + f"/dossiers/{dossier}/documents"
    listing = client.get(path)
    assert listing.status_code == 200 and listing.json()["items"][0]["id"] == snapshot
    assert "fixture-private-account" not in listing.text
    original = client.get(path + f"/{snapshot}/original")
    assert original.status_code == 200 and original.content == body
    assert original.headers["cache-control"] == "no-store"
    assert original.headers["content-disposition"].startswith("attachment;")
    assert original.headers["x-content-type-options"] == "nosniff"
    projection = client.get(path + f"/{snapshot}/text")
    assert projection.status_code == 200 and projection.json()["passages"][0]["text"] == body.decode()
    assert "access_scope_id" not in projection.json()
    from helvetic_lens import tender_document_observations as observations
    from helvetic_lens.document_sets import DocumentItem, Manifest

    def manifest_item(parsed):
        return DocumentItem(item_id="requirements", kind="document", title="Requirements",
                            official_url="https://www.simap.ch/en/project-detail/fixture",
                            access="available", snapshot_id=parsed.snapshot_id,
                            content_sha256=parsed.content_sha256, text_sha256=parsed.text_sha256,
                            parse_status="complete")

    baseline = Manifest(observation_id=uuid4(), source_id="simap", dossier_id=dossier,
                        access_scope_id=UUID(grant_id), observed_at=NOW, coverage="complete",
                        items=(manifest_item(parsed_doc),))
    with database.organization_context(identity["organization"]["id"]), database.session() as session:
        observations.observe(session, identity["user"]["id"], dossier, baseline, now=NOW)
        revised_body = b"7 references required"
        revised_doc, _ = parse_document(revised_body, content_type="text/plain", snapshot_id=uuid4(),
                                        access_scope_id=UUID(grant_id), source_id="simap", dossier_id=dossier,
                                        item_id="requirements", language="en")
        documents.store(session, identity["user"]["id"], dossier, revised_doc, revised_body,
                        content_type="text/plain", now=NOW)
        observed_id = str(uuid4())
        revised = baseline.model_copy(update={"observation_id": UUID(observed_id),
                                             "observed_at": NOW + timedelta(seconds=1),
                                             "items": (manifest_item(revised_doc),)})
        observations.observe(session, identity["user"]["id"], dossier, revised, now=NOW + timedelta(seconds=1))
        session.commit()
    observed_path = ROOT + f"/dossiers/{dossier}/document-observations/{observed_id}"
    observed_response = client.get(observed_path)
    assert observed_response.status_code == 200 and observed_response.headers["cache-control"] == "no-store"
    assert observed_response.json()["items"][0]["title"] == "Requirements"
    comparison_path = observed_path + "/comparison?item_id=requirements"
    comparison = client.get(comparison_path)
    assert comparison.status_code == 200 and comparison.json()["status"] == "changed"
    assert comparison.json()["changes"][0]["before"][0]["text"] == "5 references required"
    assert comparison.json()["changes"][0]["after"][0]["text"] == "7 references required"
    with TestClient(app) as peer:
        _register(peer, email="private-doc-peer@example.test")
        for suffix in ("", f"/{snapshot}/original", f"/{snapshot}/text"):
            assert peer.get(path + suffix).status_code == 404
        assert peer.get(observed_path).status_code == 404
        assert peer.get(comparison_path).status_code == 404
    with database.organization_context(identity["organization"]["id"]), database.session() as session:
        session.get(TenderDocumentAccess, grant_id).revoked_at = NOW
        session.commit()
    assert client.get(path).json()["items"] == []
    for suffix in ("original", "text"):
        denied = client.get(path + f"/{snapshot}/{suffix}")
        assert denied.status_code == 404 and denied.headers["cache-control"] == "no-store"
        assert "references" not in denied.text
    for denied_path in (observed_path, comparison_path):
        denied = client.get(denied_path)
        assert denied.status_code == 404 and denied.headers["cache-control"] == "no-store"
        assert "references" not in denied.text


def test_docx_originals_and_text_round_trip_through_private_http_routes(api):
    from datetime import timedelta
    from uuid import UUID

    from docx_fixture import docx, paragraph

    from helvetic_lens import tender_documents as documents
    from helvetic_lens.document_parsing import parse_document
    from helvetic_lens.docx_reader import DOCX_MIME

    client, app, _, identity = api
    monitor = transition(client, create(client), "start")
    raw = publication()
    dossier = ingest(app, identity, monitor, raw)[0]
    database = app.state.service.db
    bodies = [(docx("5 references required"), "complete", "docx"),
              (docx(content=paragraph("Unnumbered text") + '<w:p><w:pPr><w:numPr/></w:pPr></w:p>'), "partial", "docx"),
              (b"PK\x03\x04malformed original", "failed", "bin")]
    stored = []
    with database.organization_context(identity["organization"]["id"]), database.session() as session:
        grant = documents.record_access(session, identity["user"]["id"], dossier, source_id="simap",
                                        publication_id=raw["id"], account_reference="fixture-docx-account",
                                        policy_reference="fixture-docx-policy", now=NOW,
                                        valid_until=NOW + timedelta(days=365), retain_until=NOW + timedelta(days=366))
        for index, (body, state, extension) in enumerate(bodies):
            parsed_doc, _ = parse_document(body, content_type=DOCX_MIME, snapshot_id=uuid4(),
                                           access_scope_id=UUID(grant.id), source_id="simap", dossier_id=dossier,
                                           item_id=f"attachment-{index}", language="en")
            snapshot = documents.store(session, identity["user"]["id"], dossier, parsed_doc, body,
                                       content_type=DOCX_MIME, now=NOW)
            stored.append((snapshot, body, state, extension))
        session.commit()
    for snapshot, body, state, extension in stored:
        path = ROOT + f"/dossiers/{dossier}/documents/{snapshot}"
        original = client.get(path + "/original")
        assert original.status_code == 200 and original.content == body
        assert original.headers["content-disposition"].endswith(f'.{extension}"')
        assert original.headers["cache-control"] == "no-store"
        text = client.get(path + "/text")
        assert text.status_code == 200 and text.json()["parse_status"] == state
        if state == "complete":
            assert text.json()["passages"][0]["text"] == "5 references required"
            assert text.json()["passages"][0]["locator"].startswith("part:word/document.xml/")
            assert text.json()["passages"][0]["page"] is None
        with TestClient(app) as peer:
            _register(peer, email=f"docx-peer-{snapshot}@example.test")
            assert peer.get(path + "/original").status_code == 404
            assert peer.get(path + "/text").status_code == 404


def test_http_email_consent_requires_verified_owner_and_csrf_and_stays_private(api):
    from helvetic_lens.models import User

    client, app, _, identity = api
    monitor = create(client)
    path = ROOT + f"/monitors/{monitor['id']}/email"
    before = client.get(path)
    assert before.status_code == 200 and not before.json()["consent_active"]
    body = {
        "expected_version": 1,
        "configuration": {"delivery": {"email": "daily_digest", "digest_at": "08:00"}},
        "consent": True,
    }
    assert client.patch(path, json=body).status_code == 403
    denied = client.patch(path, json=body, headers=_csrf(client))
    assert denied.status_code == 409 and denied.json()["code"] == "email_verification_required"
    with app.state.service.db.session() as session:
        session.get(User, identity["user"]["id"]).email_verified_at = NOW
        session.commit()
    enabled = client.patch(path, json=body, headers=_csrf(client))
    assert enabled.status_code == 200 and enabled.json()["consent_active"]
    assert enabled.headers["cache-control"] == "no-store"
    assert client.patch(path, json=body, headers=_csrf(client)).status_code == 409
    assert client.get(path.replace("/email", "/email-preview")).json()["items"] == []
    with TestClient(app) as peer:
        _register(peer, email="private-email-peer@example.test")
        assert peer.get(path).status_code == 404
        assert peer.get(path.replace("/email", "/email-preview")).status_code == 404
    body.update(
        expected_version=enabled.json()["monitor_version"],
        configuration={"delivery": {"email": "off"}},
        consent=False,
    )
    assert not client.patch(path, json=body, headers=_csrf(client)).json()["consent_active"]


@pytest.mark.asyncio
@pytest.mark.parametrize("age", [timedelta(0), timedelta(days=2), timedelta(days=2, seconds=1)])
async def test_tender_email_uses_the_actual_private_job_dispatcher_with_fake_smtp(api, monkeypatch, age):
    from test_tender_delivery import Mailer

    from helvetic_lens import tender_delivery as email
    from helvetic_lens import tender_email_preferences as preferences
    from helvetic_lens.models import User

    client, app, settings, identity = api
    monitor = transition(client, create(client), "start")
    database, organization = app.state.service.db, identity["organization"]["id"]
    sender = Mailer()
    monkeypatch.setattr(email, "AuthMailer", lambda _settings: sender)
    class DeliveryClock(datetime):
        @classmethod
        def now(cls, tz=None):
            value = NOW + age
            return value.astimezone(tz) if tz is not None else value.replace(tzinfo=None)

    # The real worker omits `now`; control its clock rather than ageing a fixed
    # synthetic publication against the date on which the release suite runs.
    monkeypatch.setattr(email, "datetime", DeliveryClock)
    settings.auth_email_mode = "smtp"
    with database.organization_context(organization), database.session() as session:
        user_id = identity["user"]["id"]
        session.get(User, user_id).email_verified_at = NOW
        session.flush()
        preferences.configure(
            session,
            user_id,
            monitor["id"],
            expected_version=monitor["version"],
            configuration={"delivery": {"email": "immediate"}},
            consent=True,
            now=NOW,
        )
        session.commit()
    ingest(app, identity, monitor, publication())
    assert email.enqueue_due(database, settings, now=NOW) == {"enqueued": 1}
    with database.organization_context(organization), database.session() as session:
        job_id = session.scalar(select(Job.id).where(Job.type == "tender_email"))
    with database.organization_context(organization):
        result = await app.state.service.execute_job(job_id)
        assert result["state"] == "succeeded", result
    expected = int(age <= email.MAX_AGE)
    assert len(sender.calls) == expected
    if expected:
        assert sender.calls[0][0][0] == identity["user"]["email"]
    with database.organization_context(organization), database.session() as session:
        assert session.get(Job, job_id).result_json["status"] == (
            "sent" if expected else "no_eligible_changes"
        )
    assert client.get(f"/api/jobs/{job_id}").status_code == 200


def transition(client, monitor, action):
    response = post(
        client,
        f"/monitors/{monitor['id']}/command",
        {"action": action, "expected_version": monitor["version"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def ingest(app, identity, monitor, raw):
    database = app.state.service.db
    with database.organization_context(identity["organization"]["id"]), database.session() as session:
        ids = observe_publication(session, monitor["id"], parsed(raw), now=NOW)
        session.commit()
        return ids


def test_http_withdrawal_hides_cards_history_and_download_without_deleting_evidence(api):
    from helvetic_lens.tender_rights import restrict

    client, app, _, identity = api
    monitor = transition(client, create(client), "start")
    raw = publication()
    (dossier,) = ingest(app, identity, monitor, raw)
    item = client.get(ROOT + f"/dossiers/{dossier}").json()
    with app.state.service.db.session() as session:
        restrict(
            session, scope="publication", target_id=raw["id"], policy_reference="http-withdrawal", now=NOW
        )
        session.commit()
    assert client.get(ROOT + f"/monitors/{monitor['id']}/dossiers").json()["items"] == []
    assert client.get(ROOT + f"/dossiers/{dossier}/versions").json()["items"] == []
    for path in (
        f"/dossiers/{dossier}",
        f"/dossiers/{dossier}/versions/{item['evidence_version_id']}/evidence",
    ):
        response = client.get(ROOT + path)
        assert response.status_code == 404 and response.headers["cache-control"] == "no-store"
        assert "termsCriteria" not in response.text and "http-withdrawal" not in response.text


def test_http_private_discovery_follow_review_and_material_update(api):
    client, app, _, identity = api
    monitor = create(client)
    assert monitor["status"] == "draft"
    checked = post(client, "/profile-check", {"configuration": monitor["configuration"]}).json()
    assert checked["start_available"] and not checked["live_results_checked"]
    monitor = transition(client, monitor, "start")
    raw = publication()
    (dossier,) = ingest(app, identity, monitor, raw)
    cards = client.get(ROOT + f"/monitors/{monitor['id']}/dossiers")
    assert cards.status_code == 200 and cards.headers["cache-control"] == "no-store"
    assert [item["id"] for item in cards.json()["items"]] == [dossier]
    assert "original" not in cards.text and "termsCriteria" not in cards.text
    detail = client.get(ROOT + f"/dossiers/{dossier}").json()
    followed = post(
        client, f"/dossiers/{dossier}/follow", {"expected_version": detail["version"], "following": True}
    ).json()
    assert followed["following"] and followed["review_state"] == "new"
    decision_body = {
        "expected_version": followed["version"],
        "sequence": followed["sequence"],
        "decision": "bid",
        "request_key": str(uuid4()),
    }
    decision = post(client, f"/dossiers/{dossier}/decision", decision_body)
    assert decision.status_code == 200 and decision.json()["review_state"] == "reviewed"
    assert decision.json()["decision_scope"] == "internal_only"
    changed = revised(raw)
    changed["dates"]["offerDeadline"] = "2026-10-23T15:00:00+02:00"
    ingest(app, identity, monitor, changed)
    latest = client.get(ROOT + f"/dossiers/{dossier}").json()
    assert latest["sequence"] == 2 and latest["review_state"] == "needs_review"
    assert latest["decision"] == "bid" and latest["reviewed_sequence"] == 1
    window_path = ROOT + f"/dossiers/{dossier}/review-changes?through_sequence=2&reviewed_sequence=1"
    window = client.get(window_path)
    assert window.status_code == 200 and window.headers["cache-control"] == "no-store"
    assert window.json()["items"][0]["changes"] == [{"field": "deadline", "kind": "field_changed",
                                                    "before_locator": "/dates/offerDeadline",
                                                    "after_locator": "/dates/offerDeadline"}]
    invalid_window = client.get(window_path.replace("through_sequence=2", "through_sequence=1"))
    assert invalid_window.status_code == 409 and invalid_window.headers["cache-control"] == "no-store"
    with TestClient(app) as peer:
        _register(peer, email="review-window-peer@example.test")
        denied_window = peer.get(window_path)
        assert denied_window.status_code == 404 and denied_window.headers["cache-control"] == "no-store"
    assert (
        post(client, f"/dossiers/{dossier}/decision", decision_body).json()["review_state"] == "needs_review"
    )
    stale = {**decision_body, "request_key": str(uuid4())}
    assert post(client, f"/dossiers/{dossier}/decision", stale).status_code == 409
    versions = client.get(ROOT + f"/dossiers/{dossier}/versions?limit=1").json()
    assert versions["items"][0]["sequence"] == 2 and versions["next_cursor"] == 2
    older = client.get(ROOT + f"/dossiers/{dossier}/versions?before_sequence=2").json()
    assert [item["sequence"] for item in older["items"]] == [1]
    evidence = client.get(ROOT + f"/dossiers/{dossier}/versions/{detail['evidence_version_id']}/evidence")
    assert evidence.json()["original"] == raw
    off = post(
        client, f"/dossiers/{dossier}/follow", {"expected_version": latest["version"], "following": False}
    )
    assert off.status_code == 200 and off.json()["review_state"] == "needs_review"
    assert client.get(ROOT + f"/monitors/{monitor['id']}/dossiers?following=true").json()["items"] == []


def test_source_gate_pause_edit_resume_archive_delete_preserve_private_history(api):
    client, app, settings, identity = api
    monitor = create(client)
    settings.simap_public_source_enabled = False
    denied = post(client, f"/monitors/{monitor['id']}/command", {"expected_version": 1, "action": "start"})
    assert denied.status_code == 409 and denied.json()["code"] == "tender_source_not_ready"
    settings.simap_public_source_enabled = True
    monitor = transition(client, monitor, "start")
    raw = publication()
    ingest(app, identity, monitor, raw)
    changed = {
        "expected_version": monitor["version"],
        "configuration": {**monitor["configuration"], "name": "Updated"},
    }
    assert (
        client.patch(ROOT + f"/monitors/{monitor['id']}", json=changed, headers=_csrf(client)).status_code
        == 409
    )
    settings.simap_public_source_enabled = False
    monitor = transition(client, monitor, "pause")
    database = app.state.service.db
    with database.session(include_all_organizations=True) as session:
        job = session.scalar(select(Job).where(Job.target_id == monitor["id"]))
        assert job.cancel_requested
    changed["expected_version"] = monitor["version"]
    edited = client.patch(ROOT + f"/monitors/{monitor['id']}", json=changed, headers=_csrf(client))
    assert edited.status_code == 200 and edited.json()["revision"] == 2
    monitor = edited.json()
    history = client.get(ROOT + f"/monitors/{monitor['id']}/revisions").json()["items"]
    assert [item["revision"] for item in history] == [2, 1]
    settings.simap_public_source_enabled = True
    monitor = transition(client, monitor, "resume")
    monitor = transition(client, monitor, "archive")
    path = ROOT + f"/monitors/{monitor['id']}"
    assert (
        client.request(
            "DELETE", path, json={"expected_version": monitor["version"] - 1}, headers=_csrf(client)
        ).status_code
        == 409
    )
    assert client.get(path).status_code == 200
    assert (
        client.request(
            "DELETE", path, json={"expected_version": monitor["version"]}, headers=_csrf(client)
        ).status_code
        == 204
    )
    assert client.get(path).status_code == 404
    with database.session(include_all_organizations=True) as session:
        assert session.scalar(select(TenderMonitor).where(TenderMonitor.id == monitor["id"])) is None
        assert session.scalar(select(TenderDossierVersion)) is None
        assert session.scalar(select(TenderPublicationSnapshot)) is not None


def test_csrf_private_readers_and_revoked_membership(api):
    client, app, _, identity = api
    monitor = transition(client, create(client), "start")
    (dossier,) = ingest(app, identity, monitor, publication())
    detail = client.get(ROOT + f"/dossiers/{dossier}").json()
    assert (
        client.post(
            ROOT + f"/monitors/{monitor['id']}/command",
            json={"expected_version": monitor["version"], "action": "pause"},
        ).status_code
        == 403
    )
    with TestClient(app) as peer:
        assert peer.get(ROOT + "/monitors").status_code == 401
        outsider = _register(peer, email="tender-api-peer@example.test").json()
        paths = [
            f"/monitors/{monitor['id']}",
            f"/monitors/{monitor['id']}/revisions",
            f"/monitors/{monitor['id']}/dossiers",
            f"/dossiers/{dossier}",
            f"/dossiers/{dossier}/versions",
            f"/dossiers/{dossier}/versions/{detail['evidence_version_id']}/evidence",
        ]
        for same_org in (False, True):
            if same_org:
                with app.state.service.db.session(include_all_organizations=True) as session:
                    session.add(
                        OrganizationMembership(
                            organization_id=identity["organization"]["id"],
                            user_id=outsider["user"]["id"],
                            role="organization_admin",
                        )
                    )
                    session.commit()
                assert (
                    peer.post(
                        "/api/auth/session/organization",
                        json={"organization_id": identity["organization"]["id"]},
                        headers=_csrf(peer),
                    ).status_code
                    == 200
                )
            assert peer.get(ROOT + "/monitors").json()["items"] == []
            for path in paths:
                assert peer.get(ROOT + path).status_code == 404, path
            assert (
                post(
                    peer,
                    f"/dossiers/{dossier}/follow",
                    {"expected_version": detail["version"], "following": True},
                ).status_code
                == 404
            )
            assert (
                post(
                    peer,
                    f"/dossiers/{dossier}/decision",
                    {
                        "expected_version": detail["version"],
                        "sequence": 1,
                        "decision": "bid",
                        "request_key": str(uuid4()),
                    },
                ).status_code
                == 404
            )
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.execute(
                delete(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])
            )
            session.commit()
        assert client.get(ROOT + f"/dossiers/{dossier}").status_code in {401, 403}


def test_discovery_cards_are_paginated_filtered_and_do_not_hydrate_full_publications(api):
    client, app, _, identity = api
    monitor = transition(client, create(client), "start")
    raw = publication(lots=True)
    raw["lots"] = [
        {
            "id": str(uuid4()),
            "title": {"en": "Software development " + str(index)},
            "projectSubType": "service",
        }
        for index in range(7)
    ]
    dossiers = ingest(app, identity, monitor, raw)
    sql = []

    def query(_connection, _cursor, statement, _parameters, _context, _executemany):
        sql.append(statement)

    event.listen(app.state.service.db.engine, "before_cursor_execute", query)
    try:
        found, cursor = [], None
        while True:
            path = (
                ROOT
                + f"/monitors/{monitor['id']}/dossiers?limit=2"
                + (f"&after_id={cursor}" if cursor else "")
            )
            result = client.get(path)
            assert result.status_code == 200, result.text
            page = result.json()
            found.extend(item["id"] for item in page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
        assert len(found) == 7 and set(found) == set(dossiers)
        assert not any(
            "tender_publication_snapshots" in statement or "tender_material_sections" in statement
            for statement in sql
        )
    finally:
        event.remove(app.state.service.db.engine, "before_cursor_execute", query)
    assert (
        client.get(ROOT + f"/monitors/{monitor['id']}/dossiers?review_state=reviewed").json()["items"] == []
    )
    assert client.get(ROOT + f"/monitors/{monitor['id']}/dossiers?limit=101").status_code == 422
    with (
        app.state.service.db.organization_context(identity["organization"]["id"]),
        app.state.service.db.session() as session,
    ):
        session.execute(update(TenderDossierVersion).values(publish_after=NOW.replace(year=2030)))
        session.commit()
    assert client.get(ROOT + f"/monitors/{monitor['id']}/dossiers").json()["items"] == []


def test_feature_switch_invalid_inputs_and_short_phrase_only_activation(api):
    client, _, settings, _ = api
    config = profile(capabilities=[{"name": "C sharp", "phrases": ["C#"]}]).model_dump(mode="json")
    assert not post(client, "/profile-check", {"configuration": config}).json()["start_available"]
    monitor = create(client, config)
    response = post(client, f"/monitors/{monitor['id']}/command", {"expected_version": 1, "action": "start"})
    assert response.status_code == 422 and response.json()["code"] == "tender_discovery_query_required"
    invalid = copy.deepcopy(config)
    invalid["company_name"] = ""
    assert post(client, "/profile-check", {"configuration": invalid}).status_code == 422
    assert (
        post(
            client,
            "/monitors",
            {"configuration": config, "request_key": str(uuid4()), "owner_user_id": "injected"},
        ).status_code
        == 422
    )
    settings.tender_watch_enabled = False
    assert client.get(ROOT + "/monitors").status_code == 404
    assert post(client, "/profile-check", {"configuration": config}).status_code == 404


def test_profile_revision_reassesses_same_publication_without_rewriting_source_or_decision(api):
    client, app, _, identity = api
    monitor = transition(client, create(client), "start")
    raw = publication()
    (dossier,) = ingest(app, identity, monitor, raw)
    item = client.get(ROOT + f"/dossiers/{dossier}").json()
    assert (
        post(
            client,
            f"/dossiers/{dossier}/decision",
            {
                "expected_version": item["version"],
                "sequence": item["sequence"],
                "decision": "bid",
                "request_key": str(uuid4()),
            },
        ).status_code
        == 200
    )
    monitor = transition(client, monitor, "pause")
    config = {**monitor["configuration"], "excluded_phrases": ["software development"]}
    edited = client.patch(
        ROOT + f"/monitors/{monitor['id']}",
        headers=_csrf(client),
        json={
            "expected_version": monitor["version"],
            "configuration": config,
        },
    )
    assert edited.status_code == 200
    monitor = transition(client, edited.json(), "resume")
    assert ingest(app, identity, monitor, raw) == [dossier]
    assert ingest(app, identity, monitor, raw) == []
    latest = client.get(ROOT + f"/dossiers/{dossier}").json()
    assert latest["kind"] == "profile_reassessment" and latest["sequence"] == 2
    assert latest["changes"] == [] and latest["match"]["verdict"] == "excluded"
    assert (
        latest["review_state"] == "needs_review"
        and latest["decision"] == "bid"
        and latest["reviewed_sequence"] == 1
    )
    assert latest["source_hash"] == item["source_hash"]
    with app.state.service.db.session(include_all_organizations=True) as session:
        assert len(list(session.scalars(select(TenderPublicationSnapshot)))) == 1


def test_monitoring_centre_exposes_only_private_tender_metadata_and_honest_source_gate(api):
    client, app, settings, identity = api
    monitor = transition(client, create(client), "start")
    centre = client.get("/api/monitoring-centre?domain=tenders").json()
    assert len(centre["templates"]) == 9
    assert centre["items"][0]["id"] == monitor["id"]
    assert centre["items"][0]["station_id"] is None
    assert centre["items"][0]["href"] == f"/tender-watch?monitor={monitor['id']}"
    assert "company_name" not in str(centre) and "capabilities" not in str(centre)
    choice = next(item for item in centre["templates"] if item["id"] == "tenders")
    assert choice["availability"] == "available"
    settings.simap_public_source_enabled = False
    centre = client.get("/api/monitoring-centre?domain=tenders").json()
    assert (
        centre["items"][0]["health"] == "source_unavailable" and centre["items"][0]["next_check_at"] is None
    )
    assert (
        next(item for item in centre["templates"] if item["id"] == "tenders")["availability"]
        == "preview_only"
    )
    settings.tender_watch_enabled = False
    centre = client.get("/api/monitoring-centre?domain=tenders").json()
    assert centre["items"][0]["href"] is None and centre["items"][0]["health"] == "disabled"
    with TestClient(app) as peer:
        _register(peer, email="centre-tender-peer@example.test")
        assert peer.get("/api/monitoring-centre?domain=tenders").json()["items"] == []
