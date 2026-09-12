"""Cross-domain inventory against real auth and tenant-scoped SQL sessions."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from test_auth import _csrf, _register, _settings

from helvetic_lens.air_models import AirMonitor
from helvetic_lens.main import create_app
from helvetic_lens.models import Job, MonitoringSubject, OrganizationMembership, OutboxMessage
from helvetic_lens.monitoring_contracts import MonitoringRollout, public_pollen_rollout
from helvetic_lens.monitoring_live_models import MonitoringRuntime
from helvetic_lens.river_models import RiverMonitor

URL = "/api/monitoring-centre"


@pytest.fixture
def centre(tmp_path):
    settings = _settings(tmp_path)
    settings.monitoring_rollout = public_pollen_rollout()
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        identity = _register(client).json()
        yield client, app, settings, identity


def seed(app, identity, kind="air", *, clock=None, status="active", health="waiting", state=None):
    model = AirMonitor if kind == "air" else RiverMonitor
    identifier = str(uuid4())
    with app.state.service.db.session(include_all_organizations=True) as session:
        session.add(
            model(
                id=identifier,
                owner_user_id=identity["user"]["id"],
                organization_id=identity["organization"]["id"],
                request_key=identifier,
                request_hash="0" * 64,
                configuration={
                    "name": f"Private {kind}",
                    "station_id": "BAS" if kind == "air" else "2289",
                    "metrics": ["O3"] if kind == "air" else ["W"],
                    "rules": [],
                },
                status=status,
                health=health,
                state=state or {},
                created_at=clock or datetime.now(UTC),
                next_poll_at=datetime.now(UTC) + timedelta(minutes=10),
                last_poll_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        session.commit()
    return identifier


def pollen(client):
    response = client.post(
        "/api/monitoring-subjects",
        headers=_csrf(client),
        json={
            "request_key": str(uuid4()),
            "configuration": {"station_id": "PBS", "selections": [{"allergen": "birch"}]},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_nine_honest_choices_no_customs_no_implicit_activation(centre):
    client, app, _, _ = centre
    with app.state.service.db.session(include_all_organizations=True) as session:
        before = [session.scalar(select(func.count()).select_from(model)) for model in (Job, OutboxMessage)]
    response = client.get(URL)
    assert response.status_code == 200 and "no-store" in response.headers["cache-control"]
    payload = response.json()
    assert payload["items"] == [] and payload["next_cursor"] is None
    templates = payload["templates"]
    assert {row["id"] for row in templates} == {
        "warnings",
        "commute",
        "traffic",
        "pollen",
        "river",
        "air",
        "tenders",
        "ip",
        "auctions",
    }
    assert sum(row["group"] == "personal" for row in templates) == 6
    assert {row["id"] for row in templates if row["href"]} == {"pollen", "river", "air"}
    assert all(row["availability"] == "blocked" for row in templates if not row["href"])
    with app.state.service.db.session(include_all_organizations=True) as session:
        assert before == [
            session.scalar(select(func.count()).select_from(model)) for model in (Job, OutboxMessage)
        ]


def test_bounded_pagination_with_cross_domain_ties_and_insert(centre):
    client, app, _, identity = centre
    clock = datetime.now(UTC) - timedelta(hours=1)
    ids = {seed(app, identity, kind, clock=clock) for kind in ("air", "river") for _ in range(32)}
    pid = pollen(client)
    with app.state.service.db.session(include_all_organizations=True) as session:
        session.get(MonitoringSubject, pid).created_at = clock
        session.commit()
    ids.add(pid)
    seen, cursor = [], None
    while True:
        page = client.get(URL, params={"limit": 7, **({"cursor": cursor} if cursor else {})}).json()
        assert 0 < len(page["items"]) <= 7
        seen.extend(row["id"] for row in page["items"])
        if not cursor:
            seed(app, identity)
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 65 and set(seen) == ids
    rows = client.get(URL, params={"domain": "river", "limit": 50}).json()["items"]
    assert len(rows) == 32 and all(row["domain"] == "river" for row in rows)


def test_owner_workspace_and_cursor_privacy_and_revocation(centre):
    owner, app, _, identity = centre
    mine = seed(app, identity)
    with TestClient(app) as peer:
        foreign = _register(peer, "peer@example.ch", "Foreign").json()
        secret = seed(app, foreign)
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.add(
                OrganizationMembership(
                    user_id=foreign["user"]["id"],
                    organization_id=identity["organization"]["id"],
                    role="organization_admin",
                )
            )
            session.commit()
        sibling = {**foreign, "organization": identity["organization"]}
        sibling_id = seed(app, sibling, "river")
        assert {row["id"] for row in owner.get(URL).json()["items"]} == {mine}
        for identifier, kind in ((secret, "air"), (sibling_id, "river")):
            response = owner.get(URL, params={"cursor": f"{kind}:{identifier}"})
            assert response.status_code == 422 and identifier not in response.text
        assert {row["id"] for row in peer.get(URL).json()["items"]} == {secret}
    with app.state.service.db.session(include_all_organizations=True) as session:
        session.execute(
            delete(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])
        )
        session.commit()
    response = owner.get(URL)
    assert response.status_code in {401, 403} and mine not in response.text


def test_viewer_reads_only_own_saved_monitors(centre):
    client, app, _, identity = centre
    identifier = seed(app, identity)
    with app.state.service.db.session(include_all_organizations=True) as session:
        member = session.scalar(
            select(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])
        )
        member.role = "viewer"
        session.commit()
    assert client.get(URL).json()["items"][0]["id"] == identifier
    response = client.post(
        f"/api/air-watch/monitors/{identifier}/command",
        headers=_csrf(client),
        json={"action": "pause", "expected_version": 1},
    )
    assert response.status_code == 403


def test_disabled_keeps_only_private_inventory_metadata_and_no_runtime_read(centre, monkeypatch):
    client, app, settings, identity = centre
    seed(app, identity, health="ready")
    seed(app, identity, "river", health="ready")
    pollen(client)
    settings.air_watch_enabled = settings.river_watch_enabled = False
    settings.monitoring_rollout = MonitoringRollout()

    def forbidden(*args, **kwargs):
        pytest.fail("Disabled inventory must not read source evidence")

    monkeypatch.setattr("helvetic_lens.monitoring_centre.air_runtime.view", forbidden)
    monkeypatch.setattr("helvetic_lens.monitoring_centre.river_runtime.view", forbidden)
    monkeypatch.setattr("helvetic_lens.monitoring_centre.monitoring_runtime.state", forbidden)
    payload = client.get(URL).json()
    assert len(payload["items"]) == 3
    assert all(
        item["health"] == "disabled"
        and item["href"] is None
        and item["last_observation_at"] is None
        and item["next_check_at"] is None
        and item["last_check_at"] is None
        for item in payload["items"]
    )
    assert all(item["href"] is None for item in payload["templates"])


@pytest.mark.parametrize("kind,hours", [("air", 7), ("river", 2)])
def test_freshness_is_rechecked_without_source_collection(centre, kind, hours):
    client, app, _, identity = centre
    now = datetime.now(UTC)
    state = {"coverage": {"metric": {"status": "current", "sample": {"timestamp": now.isoformat()}}}}
    identifier = seed(app, identity, kind, state=state, health="ready")
    row = client.get(URL).json()["items"][0]
    assert row["health"] == "ready" and row["last_observation_at"] == now.isoformat()
    with app.state.service.db.session(include_all_organizations=True) as session:
        model = AirMonitor if kind == "air" else RiverMonitor
        session.get(model, identifier).state = {
            "coverage": {
                "metric": {
                    "status": "current",
                    "sample": {"timestamp": (now - timedelta(hours=hours)).isoformat()},
                }
            }
        }
        session.commit()
    row = client.get(URL).json()["items"][0]
    assert row["health"] == "partial_unknown" and row["last_observation_at"] is None
    assert row["last_check_at"] and row["next_check_at"]


def test_lifecycle_filters_and_exact_links_persist(centre):
    client, app, _, identity = centre
    aid = seed(app, identity)
    rid = seed(app, identity, "river", status="archived")
    pid = pollen(client)
    response = client.post(
        f"/api/air-watch/monitors/{aid}/command",
        headers=_csrf(client),
        json={"action": "pause", "expected_version": 1},
    )
    assert response.status_code == 200, response.text
    for _ in range(2):
        page = client.get(URL, params={"status": "paused"}).json()
        assert [row["id"] for row in page["items"]] == [aid]
        assert page["items"][0]["next_check_at"] is None
    rows = {row["id"]: row for row in client.get(URL).json()["items"]}
    assert rows[aid]["href"] == f"/air-watch?monitor={aid}"
    assert rows[rid]["href"] == f"/river-watch?monitor={rid}"
    assert rows[pid]["href"] == f"/pollen-watch#draft={pid}"
    assert rows[pid]["health"] == "not_started"
    assert client.get(URL, params={"status": "archived"}).json()["items"][0]["id"] == rid


@pytest.mark.parametrize(
    "params",
    [
        {"cursor": "bad"},
        {"cursor": "air:not-a-uuid"},
        {"limit": 51},
        {"domain": "customs"},
        {"status": "deleted"},
    ],
)
def test_invalid_filters_fail_closed(centre, params):
    assert centre[0].get(URL, params=params).status_code == 422


def test_anonymous_never_reads_inventory(centre):
    with TestClient(centre[1]) as anonymous:
        assert anonymous.get(URL).status_code == 401


def test_pollen_rechecks_source_approval_instead_of_trusting_saved_ready(centre):
    client, app, _, identity = centre
    identifier = pollen(client)
    now = datetime.now(UTC)
    with app.state.service.db.session(include_all_organizations=True) as session:
        session.get(MonitoringSubject, identifier).status = "active"
        session.add(
            MonitoringRuntime(
                subject_id=identifier,
                organization_id=identity["organization"]["id"],
                version=1,
                run_id=str(uuid4()),
                configuration_revision=1,
                started_at=now,
                next_poll_at=now,
                last_poll_at=now,
                health="ready",
                current_stream_ids=[],
            )
        )
        session.commit()
    row = client.get(URL).json()["items"][0]
    assert row["health"] == "source_not_approved" and row["last_observation_at"] is None


def test_pollen_forecast_is_never_labelled_as_latest_observation(centre, monkeypatch):
    client, app, _, _ = centre
    identifier = pollen(client)
    with app.state.service.db.session(include_all_organizations=True) as session:
        session.get(MonitoringSubject, identifier).status = "active"
        session.commit()

    def current(*args, **kwargs):
        return {
            "runtime": {"health": "ready"},
            "current": [
                {
                    "availability": "usable",
                    "sample": {
                        "valid_at": "2026-09-12T15:00:00Z",
                        "series": {"period": "observation_hourly"},
                    },
                },
                {
                    "availability": "usable",
                    "sample": {"valid_at": "2026-09-13T15:00:00Z", "series": {"period": "forecast_instant"}},
                },
            ],
        }

    monkeypatch.setattr("helvetic_lens.monitoring_centre.monitoring_runtime.state", current)
    assert client.get(URL).json()["items"][0]["last_observation_at"] == "2026-09-12T15:00:00Z"


def test_shadow_and_exact_workspace_revocation_are_honest(centre):
    client, _, settings, identity = centre
    settings.monitoring_rollout = MonitoringRollout.model_validate(
        {
            "enabled": True,
            "grants": [
                {
                    "workspace_id": "*",
                    "template_id": "pollen-watch",
                    "template_version": 1,
                    "mode": "enabled",
                },
                {
                    "workspace_id": identity["organization"]["id"],
                    "template_id": "pollen-watch",
                    "template_version": 1,
                    "mode": "shadow",
                },
            ],
        }
    )
    choice = next(row for row in client.get(URL).json()["templates"] if row["id"] == "pollen")
    assert choice["availability"] == "preview_only" and choice["href"] == "/pollen-watch"
    payload = settings.monitoring_rollout.model_dump()
    payload["grants"][1]["mode"] = "legacy"
    settings.monitoring_rollout = MonitoringRollout.model_validate(payload)
    choice = next(row for row in client.get(URL).json()["templates"] if row["id"] == "pollen")
    assert choice["availability"] == "disabled" and choice["href"] is None
