"""Synthetic official-contract fixtures; never used as product fallback data."""
import asyncio
from dataclasses import replace

import httpx
import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_source_packs import _auth_settings

from helvetic_lens.auth import CSRF_COOKIE
from helvetic_lens.basel_stadt_connector import BaselStadtConnector, fingerprint
from helvetic_lens.basel_stadt_pilot import PACK_ID
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.main import create_app
from helvetic_lens.models import (
    ConnectorSchedule,
    Organization,
    OrganizationMembership,
    RegulatoryDocumentVersion,
    RegulatoryWork,
)


def row(version=300, **overrides):
    return {
        "id": "123", "v_id": version, "systematic_number": "153.260",
        "title_de": "Synthetic Datenschutz Gesetz", "category_name": "Gesetz",
        "is_active": "True", "info_badge": "current", "version_active_since": "2020-01-01",
        "version_inactive_since": None, "version_found_at": "2026-09-09",
        "version_url_de": f"https://www.gesetzessammlung.bs.ch/app/de/texts_of_law/153.260/versions/{version}",
        "gesetzestext_html": "<html><body><main><h1>Synthetic Datenschutz Gesetz</h1><p>Datenschutz und Information. This fictional fixture is not law. Organisations protect personal information and document their procedures.</p></main></body></html>",
        **overrides,
    }


def source(settings, rows, *, stream="starter-de", page_size=20, requests=None):
    def respond(request):
        if requests is not None:
            requests.append(str(request.url))
        where = request.url.params.get("where", "")
        selected = rows
        if "v_id < " in where:
            selected = [item for item in rows if item["v_id"] < int(where.split("v_id < ")[-1])]
        elif where.startswith("v_id = "):
            selected = [item for item in rows if item["v_id"] == int(where[7:])]
        return httpx.Response(200, json={"total_count": len(selected), "results": selected[:int(request.url.params["limit"])]})
    return BaselStadtConnector(settings, stream=stream, page_size=page_size, transport=httpx.MockTransport(respond))


@pytest.mark.asyncio
async def test_keyset_overlap_taxonomy_dedup_and_exact_recovery(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    rows = [row(300), row(300, index="other category"), row(200), row(100)]
    connector = source(settings, rows, stream="catalogue-de", page_size=2)
    first = await connector.discover_since(None, {})
    assert len(first.items) == 1 and not first.complete
    second = await connector.discover_since(first.next_cursor, {})
    assert len(second.items) == 2 and second.complete
    repeated = await connector.discover_since(second.next_cursor, {})
    assert repeated.items == first.items
    recovered = await source(settings, rows).fetch_metadata(first.items[0])
    assert recovered.metadata["jurisdiction"] == "CH-BS"
    assert [d.value for d in recovered.dates] == ["2020-01-01"]
    assert recovered.lifecycle_status == "active"
    with pytest.raises(DomainError):
        await connector.fetch_metadata(replace(first.items[0], canonical_url="https://www.gesetzessammlung.bs.ch/wrong"))
    with pytest.raises(DomainError):
        await source(settings, [row(300, title_de="Changed")]).fetch_metadata(first.items[0])
    assert fingerprint(row(300)) == fingerprint(row(300, index="taxonomy only"))


@pytest.mark.parametrize("override", [
    {"v_id": "300"}, {"is_active": True}, {"version_active_since": "yesterday"},
    {"version_url_de": "https://evil.example/texts/versions/3"}, {"title_de": None},
])
@pytest.mark.asyncio
async def test_schema_and_external_url_fail_closed(tmp_path, override):
    with pytest.raises(DomainError):
        await source(Settings(_env_file=None, data_dir=tmp_path), [row(**override)]).discover_since(None, {})


@pytest.mark.asyncio
async def test_missing_html_and_history_are_not_invented(tmp_path):
    connector = source(Settings(_env_file=None, data_dir=tmp_path), [row(gesetzestext_html=None, info_badge="not_current")])
    metadata = await connector.fetch_metadata((await connector.discover_since(None, {})).items[0])
    assert metadata.lifecycle_status == "active"  # historical version is not a repealed law
    expression = (await connector.list_expressions(metadata))[0]
    assert await connector.fetch_official_artifact(expression) is None
    assert await connector.extract_relations(metadata) == ()


def plan():
    return {"name": "Basel privacy", "goal": "Follow Datenschutz", "concepts": ["Datenschutz"],
            "synonyms": [], "exclusions": [], "jurisdictions": ["CH-BS"], "languages": ["de"],
            "source_pack_ids": [PACK_ID], "document_kinds": ["act", "ordinance", "unclassified_document"],
            "event_kinds": ["created", "new_version", "amended", "repealed", "replaced", "status_changed"],
            "importance_floor": "low"}


def test_first_material_journey_reopens_exact_artifact_and_saves_once(harness, monkeypatch):
    client, _, service, model = harness
    assert client.post("/api/onboarding/basel-stadt/collect").status_code == 409
    activated = client.post(f"/api/source-packs/{PACK_ID}/activate")
    assert activated.status_code == 202, activated.text
    for job in activated.json()["jobs"]:
        assert asyncio.run(service.execute_job(job["id"], worker="basel-test"))["state"] == "succeeded"
    async def sync(stream):
        result = await service.connector_runner.run_page(source(service.settings, [row()], stream=stream), stream=stream)
        return {key: getattr(result, key) for key in ("connector", "stream", "status", "page_id", "persisted", "total", "next_cursor", "error")}
    monkeypatch.setattr(service, "sync_basel_stadt", sync)
    queued = service.enqueue_connector_sync(PACK_ID, "starter-de")
    result = asyncio.run(service.execute_job(queued["job"]["id"], worker="basel-test"))
    assert result["state"] == "succeeded", result
    preview = client.post("/api/monitoring-topics/preview", json=plan())
    assert preview.status_code == 200, preview.text
    items = preview.json()["items"]
    assert items and items[0]["evidence_url"].startswith("/corpus-evidence/"), preview.json()
    version_id = items[0]["evidence_url"].rsplit("/", 1)[-1]
    evidence = client.get(f"/api/regulatory-versions/{version_id}")
    assert evidence.status_code == 200, evidence.text
    assert "Datenschutz" in evidence.text
    artifact = client.get(f"/api/regulatory-versions/{version_id}/artifact")
    assert artifact.status_code == 200
    assert artifact.content == row()["gesetzestext_html"].encode()
    first = client.post("/api/monitoring-topics", json={**plan(), "idempotency_key": "basel-first-save"})
    second = client.post("/api/monitoring-topics", json={**plan(), "idempotency_key": "basel-first-save"})
    assert first.status_code == 201, first.text
    assert first.json()["id"] == second.json()["id"]
    duplicated = client.post("/api/monitoring-topics/preview", json=plan()).json()
    assert duplicated["matching_topics"]["items"][0]["id"] == first.json()["id"]
    again = asyncio.run(service.connector_runner.run_page(source(service.settings, [row()]), stream="starter-de"))
    assert again.status == "persisted", again.error
    with service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(RegulatoryWork)) == 1
        assert session.scalar(select(func.count()).select_from(RegulatoryDocumentVersion)) == 1
    assert model.calls == []
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Unsubscribed Basel organization", slug="basel-unsubscribed")
        session.add(other)
        session.commit()
        other_id = other.id
    from helvetic_lens.basel_onboarding import collect
    from helvetic_lens.monitoring_topics import preview as preview_topic
    with service.db.organization_context(other_id):
        with pytest.raises(DomainError) as error:
            collect(service)
        assert error.value.code == "source_pack_inactive"
        with service.db.session() as session:
            assert preview_topic(session, plan())["items"] == []


@pytest.mark.asyncio
async def test_latest_window_is_bounded_and_health_detects_empty_source(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    connector = source(settings, [row(n) for n in range(300, 240, -1)], stream="latest-de")
    cursor, seen = None, []
    for _ in range(3):
        page = await connector.discover_since(cursor, {})
        seen.extend(page.items)
        cursor = page.next_cursor
    assert len(seen) == 50 and page.complete and cursor == {"cycle": 1}
    assert (await connector.health()).status == "healthy"
    assert (await source(settings, []).health()).status == "degraded"


def test_collection_is_bounded_throttled_and_respects_disabled_schedule(harness):
    client, _, service, _ = harness
    client.post(f"/api/source-packs/{PACK_ID}/activate")
    response = client.post("/api/onboarding/basel-stadt/collect")
    assert response.status_code == 202, response.text
    assert response.json() == {"state": "queued"}
    assert client.post("/api/onboarding/basel-stadt/collect").json() == {"state": "recently_requested"}
    with service.db.session(include_all_organizations=True) as session:
        schedule = session.scalar(select(ConnectorSchedule).where(ConnectorSchedule.connector == PACK_ID, ConnectorSchedule.stream == "starter-de"))
        schedule.enabled = False
        session.commit()
    assert client.post("/api/onboarding/basel-stadt/collect").status_code == 409


@pytest.mark.asyncio
async def test_empty_catalogue_conflicting_version_and_ignored_boundary_fail(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    for rows in ([], [row(), row(title_de="Contradictory source copy")]):
        with pytest.raises(DomainError) as error:
            await source(settings, rows).discover_since(None, {})
        assert error.value.code == "connector_contract_drift"
    connector = BaselStadtConnector(settings, transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"total_count": 1, "results": [row()]})))
    with pytest.raises(DomainError):
        await connector.discover_since({"before": 200}, {})


def test_cross_stream_overlap_and_corrected_text_keep_immutable_versions(harness):
    _, _, service, _ = harness
    for stream, rows in (("starter-de", [row()]), ("catalogue-de", [row()]), ("latest-de", [row(gesetzestext_html=row()["gesetzestext_html"].replace("Datenschutz und", "Datenschutz, Transparenz und"))])):
        result = asyncio.run(service.connector_runner.run_page(source(service.settings, rows, stream=stream), stream=stream))
        assert result.status == "persisted", result.error
    with service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(RegulatoryWork)) == 1
        versions = session.scalars(select(RegulatoryDocumentVersion)).all()
        assert len(versions) == 2
        assert len({v.content_hash for v in versions}) == 2
        assert any("Transparenz" not in v.text for v in versions)


def test_collection_requires_csrf_admin_and_own_subscription(tmp_path):
    app = create_app(_auth_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        assert client.post("/api/onboarding/basel-stadt/collect").status_code == 401
        response = client.post("/api/auth/register", json={"email": "basel-admin@example.ch", "password": "correct horse battery staple", "name": "Basel tester", "organization_name": "Basel test"})
        assert response.status_code == 201, response.text
        assert client.post("/api/onboarding/basel-stadt/collect").status_code == 403
        headers = {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE)}
        assert client.post("/api/onboarding/basel-stadt/collect", headers=headers).status_code == 409
        assert client.post(f"/api/source-packs/{PACK_ID}/activate", headers=headers).status_code == 202
        with app.state.service.db.session(include_all_organizations=True) as session:
            membership = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == response.json()["user"]["id"]))
            membership.role = "viewer"
            session.commit()
        blocked = client.post("/api/onboarding/basel-stadt/collect", headers=headers)
        assert blocked.status_code == 403 and blocked.json()["code"] == "viewer_read_only"
