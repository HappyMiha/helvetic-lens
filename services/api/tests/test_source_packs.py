import asyncio
from datetime import UTC, datetime

from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from helvetic_lens.auth import CSRF_COOKIE
from helvetic_lens.config import Settings
from helvetic_lens.main import create_app
from helvetic_lens.models import (
    Job,
    OrganizationMembership,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryWork,
    SourcePackChangeRequest,
    SourcePackDefinition,
    SourcePackSubscription,
)
from helvetic_lens.regulatory_corpus import DocumentInput, EventInput, ExpressionInput, IdentifierInput
from helvetic_lens.source_packs import STARTER_ID, enabled_organizations_for_stream


def _fedlex_event(
    service,
    key: str = "pack-event",
    *,
    connector: str = "fedlex",
    stream: str = "rss-de",
) -> str:
    with service.db.session() as session:
        merged = service.regulatory_corpus.merge_document(
            session,
            DocumentInput(
                kind="act",
                authority="fedlex",
                identifiers=(IdentifierInput("eli", f"https://fedlex.data.admin.ch/eli/cc/{key}"),),
                title="Source-pack fixture act",
                expression=ExpressionInput(language="de", key=f"{key}:de"),
            ),
        )
        event = service.regulatory_corpus.record_event(
            session,
            EventInput(
                work_id=merged.work.id,
                authority="fedlex",
                event_type="created",
                detected_at=datetime.now(UTC),
                provenance_method="official_metadata",
                source_url="https://fedlex.data.admin.ch/eli/cc/pack-event",
                evidence={"stream": stream},
                external_key=key,
                connector=connector,
                connector_health="healthy",
            ),
        )
        session.commit()
        return event.id


def test_starter_catalogue_is_seeded_from_exact_capability_streams(harness):
    client, _, service, _ = harness
    response = client.get("/api/source-packs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["starter"]["id"] == STARTER_ID
    assert payload["starter"]["subpack_count"] == 5
    assert payload["starter"]["state"] == "inactive"
    assert {item["id"] for item in payload["items"]} == {
        "fedlex-legislation",
        "fedlex-consultations",
        "swiss-parliament",
        "federal-courts",
        "federal-policy-regulators",
    }
    assert all(set(item["name"]) == {"de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"} for item in payload["items"])
    assert sum(len(item["capabilities"]) for item in payload["items"]) == 23
    with service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(SourcePackDefinition)) == 6


def test_activation_backfills_shared_events_without_copying_the_corpus(harness):
    client, _, service, _ = harness
    event_id = _fedlex_event(service)
    with service.db.session(include_all_organizations=True) as session:
        before = (
            session.scalar(select(func.count()).select_from(RegulatoryWork)),
            session.scalar(select(func.count()).select_from(RegulatoryEvent)),
        )

    activated = client.post("/api/source-packs/fedlex-legislation/activate")
    assert activated.status_code == 202, activated.text
    job = activated.json()["jobs"][0]
    completed = asyncio.run(service.execute_job(job["id"], worker="source-pack-test"))
    assert completed["state"] == "succeeded"
    assert completed["result"]["data"]["included"] == 1
    assert completed["result"]["data"]["shared_documents_created"] == 0

    with service.db.session(include_all_organizations=True) as session:
        subscription = session.scalar(
            select(SourcePackSubscription).where(
                SourcePackSubscription.pack_id == "fedlex-legislation"
            )
        )
        assert subscription.enabled is True
        assert subscription.state == "active"
        assert subscription.included_event_count == 1
        assert session.scalar(
            select(RegulatoryEventState.id).where(RegulatoryEventState.event_id == event_id)
        )
        assert before == (
            session.scalar(select(func.count()).select_from(RegulatoryWork)),
            session.scalar(select(func.count()).select_from(RegulatoryEvent)),
        )
        assert enabled_organizations_for_stream(session, "fedlex", "rss-de") == {
            service.organization_id
        }

    repeated = client.post("/api/source-packs/fedlex-legislation/activate")
    assert repeated.status_code == 202
    assert repeated.json() == {
        "pack_id": "fedlex-legislation",
        "jobs": [],
        "reused": True,
    }
    with service.db.session(include_all_organizations=True) as session:
        assert session.scalar(
            select(func.count()).select_from(Job).where(Job.type == "source_pack_backfill")
        ) == 1

    disabled = client.post("/api/source-packs/fedlex-legislation/deactivate")
    assert disabled.status_code == 200
    assert disabled.json()["deactivated"] == 1
    with service.db.session(include_all_organizations=True) as session:
        assert enabled_organizations_for_stream(session, "fedlex", "rss-de") == set()
        assert session.scalar(
            select(RegulatoryEventState.id).where(RegulatoryEventState.event_id == event_id)
        ), "Disabling a pack must retain already saved organization evidence."


def test_backfill_matches_exact_connector_and_stream_pair(harness):
    client, _, service, _ = harness
    matching_id = _fedlex_event(service, "matching-pair")
    nonmatching_id = _fedlex_event(
        service,
        "wrong-connector-pair",
        connector="swiss-parliament",
        stream="rss-de",
    )

    activated = client.post("/api/source-packs/fedlex-legislation/activate")
    job = activated.json()["jobs"][0]
    completed = asyncio.run(service.execute_job(job["id"], worker="source-pack-pair-test"))

    assert completed["result"]["data"]["included"] == 1
    with service.db.session(include_all_organizations=True) as session:
        included_ids = set(
            session.scalars(
                select(RegulatoryEventState.event_id).where(
                    RegulatoryEventState.event_id.in_([matching_id, nonmatching_id])
                )
            )
        )
    assert included_ids == {matching_id}


def test_starter_activation_queues_each_visible_subpack_once(harness):
    client, *_ = harness
    response = client.post(f"/api/source-packs/{STARTER_ID}/activate")
    assert response.status_code == 202
    assert len(response.json()["jobs"]) == 5
    assert len({item["target_id"] for item in response.json()["jobs"]}) == 5
    repeated = client.post(f"/api/source-packs/{STARTER_ID}/activate")
    assert repeated.status_code == 202
    assert repeated.json()["reused"] is True
    assert len(repeated.json()["jobs"]) == 5
    assert {item["id"] for item in repeated.json()["jobs"]} == {
        item["id"] for item in response.json()["jobs"]
    }


def _auth_settings(tmp_path):
    return Settings(
        _env_file=None,
        database_url="sqlite:///" + (tmp_path / "source-packs-auth.db").as_posix(),
        data_dir=tmp_path / "source-packs-auth-data",
        app_environment="test",
        allow_anonymous_dev=False,
        session_cookie_secure=False,
        job_execution_mode="inline",
        apertus_provider="custom",
        apertus_base_url="",
        apertus_api_key="",
        firecrawl_api_key="",
    )


def test_viewer_can_request_but_cannot_mutate_source_packs(tmp_path):
    app = create_app(_auth_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        registered = client.post(
            "/api/auth/register",
            json={
                "email": "viewer@example.ch",
                "password": "correct horse battery staple",
                "name": "Read Only",
                "organization_name": "Viewer organization",
            },
        )
        assert registered.status_code == 201
        user_id = registered.json()["user"]["id"]
        with app.state.service.db.session(include_all_organizations=True) as session:
            membership = session.scalar(
                select(OrganizationMembership).where(OrganizationMembership.user_id == user_id)
            )
            membership.role = "viewer"
            session.commit()
        headers = {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE)}
        blocked = client.post(
            "/api/source-packs/fedlex-legislation/activate", headers=headers
        )
        assert blocked.status_code == 403
        assert blocked.json()["code"] == "viewer_read_only"

        requested = client.post(
            "/api/source-pack-requests",
            json={"pack_id": "fedlex-legislation", "action": "activate"},
            headers=headers,
        )
        assert requested.status_code == 201, requested.text
        assert requested.json()["status"] == "pending"
        duplicate = client.post(
            "/api/source-pack-requests",
            json={"pack_id": "fedlex-legislation", "action": "activate"},
            headers=headers,
        )
        assert duplicate.status_code == 201
        assert duplicate.json()["reused"] is True
        with app.state.service.db.session(include_all_organizations=True) as session:
            assert session.scalar(select(func.count()).select_from(SourcePackChangeRequest)) == 1
