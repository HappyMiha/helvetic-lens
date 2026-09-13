from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
import test_tender_repository as persistence
from sqlalchemy import select, update
from test_simap_sources import header_publication, page
from test_tender_matching import LOT_A, LOT_B, NOW, PROJECT, PUBLICATION, profile
from test_tender_repository import create, decide, publication, read, revised

from helvetic_lens import tender_jobs
from helvetic_lens import tender_scan as scan
from helvetic_lens.models import Job, OrganizationMembership
from helvetic_lens.simap_sources import SourceUnavailable, parse_cpv_ancestry
from helvetic_lens.tender_models import (
    TenderCollection,
    TenderDossier,
    TenderDossierVersion,
    TenderMonitor,
    TenderSourceLease,
)

db = persistence.db
template = persistence.template


def settings():
    return SimpleNamespace(tender_watch_enabled=True, simap_public_source_enabled=True)


class Source:
    def __init__(self, raw=None):
        self.raw = raw or publication()
        self.records = {self.raw["id"]: self.raw}
        self.search_pages = {
            None: page(
                {
                    "id": PROJECT,
                    "publicationId": self.raw["id"],
                    "publicationDate": "2026-09-12",
                    "pubType": "tender",
                    "lots": [],
                }
            )
        }
        self.past = {"pastPublications": []}
        self.header = {
            "id": PROJECT,
            "lotsType": "without",
            "latestPublication": header_publication(self.raw["id"]),
        }
        self.calls, self.hook, self.error = [], None, None

    def reply(self, kind, value):
        self.calls.append(kind)
        if self.hook:
            self.hook()
        if self.error:
            raise self.error
        return deepcopy(value)

    def search(self, **kwargs):
        assert kwargs["newest_from"] == "2026-06-14"
        assert kwargs["newest_until"] == "2026-09-12"
        return self.reply("search", self.search_pages[kwargs.get("last_item")])

    def publication(self, project, publication_id):
        assert project == PROJECT
        return self.reply("publication", self.records[publication_id])

    def project_header(self, project):
        assert project == PROJECT
        return self.reply("header", self.header)

    def publication_history(self, publication_id, *, lot_id=None):
        assert publication_id in self.records
        return self.reply("history", self.past)

    def cpv_ancestry(self, code):
        tree = {"codes": [{"code": "72000000", "codes": [{"code": "72212000", "codes": []}]}]}
        self.reply("taxonomy", {})
        return parse_cpv_ancestry(tree, requested_code=code)


def step(db, monitor, source, *, at=NOW, config=None):
    return tender_jobs.refresh(
        db, config or settings(), monitor_id=monitor["id"], version=monitor["version"], now=at, client=source
    )


def cycle(db, monitor, source, *, at=NOW, max_steps=50):
    results = []
    for index in range(max_steps):
        result = step(db, monitor, source, at=at + timedelta(seconds=15 * index))
        results.append(result)
        if result["status"] == "inactive_or_waiting":
            return results
    raise AssertionError("Collector failed to reach a bounded cycle boundary")


def test_capacity_keeps_buffer_and_retry_applies_same_publication(db):
    monitor, source = create(db, active=True), Source()
    config = settings()
    config.tender_public_storage_max_bytes = 1
    step(db, monitor, source, config=config)
    step(db, monitor, source, at=NOW + timedelta(seconds=15), config=config)
    with db.session() as session:
        before = deepcopy(session.get(TenderCollection, monitor["id"]).state)
    assert (
        step(db, monitor, source, at=NOW + timedelta(seconds=30), config=config)["status"]
        == "storage_capacity"
    )
    with db.session() as session:
        assert session.get(TenderCollection, monitor["id"]).state == before
        assert not list(session.scalars(select(TenderDossier)))
        assert session.get(TenderMonitor, monitor["id"]).health == "storage_capacity"
    # Operator increases capacity; the exact buffered original is retried.
    config.tender_public_storage_max_bytes = 1024**2
    result = step(db, monitor, source, at=NOW + timedelta(hours=6), config=config)
    assert result == {"status": "collecting_public", "changed_dossiers": 1}
    assert source.calls == ["search", "publication"]


def test_restriction_during_fetch_prevents_retaining_result(db):
    from helvetic_lens.tender_rights import restrict

    monitor, source = create(db, active=True), Source()
    step(db, monitor, source)

    def withdraw():
        with db.session() as session:
            restrict(
                session, scope="project", target_id=PROJECT, policy_reference="withdraw-during-io", now=NOW
            )
            session.commit()

    source.hook = withdraw
    assert step(db, monitor, source, at=NOW + timedelta(seconds=15))["status"] == "source_rights_unavailable"
    with db.session() as session:
        state = session.get(TenderCollection, monitor["id"]).state
        assert state["buffer"] is None and state["pending"][0]["kind"] == "publication"
        assert not list(session.scalars(select(TenderDossier)))
    calls = list(source.calls)
    step(db, monitor, source, at=NOW + timedelta(hours=6))
    assert source.calls == calls


def test_durable_checkpoint_survives_new_sessions_and_observes_once(db):
    monitor = create(db, active=True)
    source = Source()
    assert step(db, monitor, source)["status"] == "collecting_public"
    with db.session() as session:
        state = session.get(TenderCollection, monitor["id"]).state
        assert state["query"] == 1 and state["pending"][0]["kind"] == "publication"
    result = cycle(db, monitor, source, at=NOW + timedelta(seconds=15))
    assert source.calls == ["search", "publication", "history"]
    assert sum(item.get("changed_dossiers", 0) for item in result) == 1
    with db.session() as session:
        assert len(list(session.scalars(select(TenderDossier)))) == 1
        assert len(list(session.scalars(select(TenderDossierVersion)))) == 1
        row = session.get(TenderMonitor, monitor["id"])
        assert row.health == "public_cycle_complete"
        state = session.get(TenderCollection, monitor["id"]).state
        assert state["cycle_complete"] and state["buffer"] is None
    before = list(source.calls)
    assert step(db, monitor, source, at=NOW + timedelta(hours=1))["status"] == "inactive_or_waiting"
    assert source.calls == before


def test_source_retry_after_does_not_advance_cursor_or_report_an_empty_success(db):
    monitor = create(db, active=True)
    source = Source()
    source.error = SourceUnavailable("rate_limited", 172800, status_code=429)
    assert step(db, monitor, source)["status"] == "rate_limited"
    with db.session() as session:
        state = session.get(TenderCollection, monitor["id"]).state
        assert state["query"] == 0 and state["cursor"] is None
        assert not list(session.scalars(select(TenderDossier)))
        lease = session.get(TenderSourceLease, "simap_public")
        assert tender_jobs.utc(lease.next_request_at) == NOW + timedelta(days=2)
    assert step(db, monitor, source, at=NOW + timedelta(minutes=1))["status"] == "source_budget_wait"
    assert source.calls == ["search"]


def test_empty_permitted_page_keeps_paging_and_rereads_at_publication_gate(db):
    monitor = create(db, active=True)
    source = Source()
    source.search_pages = {
        None: page(
            {
                "id": PROJECT,
                "publicationId": PUBLICATION,
                "publicationDate": "2026-09-12",
                "pubType": "tender",
                "lots": [],
            },
            last_item="20260912|42058",
        ),
        "20260912|42058": page(),
    }
    before_gate = NOW - timedelta(minutes=2)
    results = cycle(db, monitor, source, at=before_gate)
    assert [item["status"] for item in results] == [
        "collecting_public",
        "collecting_public",
        "inactive_or_waiting",
    ]
    assert source.calls == ["search", "search"]
    with db.session() as session:
        state = session.get(TenderCollection, monitor["id"]).state
        assert scan.aware_from_text(state["restart_at"]) == NOW
    cycle(db, monitor, source, at=NOW)
    with db.session() as session:
        assert len(list(session.scalars(select(TenderDossier)))) == 1


def test_following_runs_independently_of_new_discovery_matches(db):
    monitor = create(db, active=True)
    source = Source()
    cycle(db, monitor, source)
    with db.session() as session:
        dossier = session.scalar(select(TenderDossier.id))
    decide(db, read(db, dossier))
    changed = revised(source.raw)
    changed["dates"]["offerDeadline"] = "2026-10-23T15:00:00+02:00"
    source.records[changed["id"]] = changed
    source.header["latestPublication"] = header_publication(changed["id"])
    source.search_pages = {None: page()}
    source.calls = []
    cycle(db, monitor, source, at=NOW + timedelta(hours=6))
    assert source.calls[0] == "header" and "publication" in source.calls and source.calls[-1] == "search"
    assert read(db, dossier)["review_state"] == "needs_review"


def test_historical_open_notice_cannot_invent_a_new_opportunity_for_an_awarded_lot(db):
    monitor = create(db, active=True)
    initial = publication(lots=True)
    initial["lots"][1]["title"]["en"] = "Software development for the second lot"
    award = revised(initial)
    award["type"] = award["base"]["type"] = "award"
    award["lot"] = award.pop("lots")[0]
    source = Source(initial)
    source.records[award["id"]] = award
    source.search_pages = {
        None: page(
            {
                "id": PROJECT,
                "publicationId": award["id"],
                "publicationDate": "2026-09-12",
                "pubType": "award",
                "lots": [
                    {"lotId": LOT_A, "publicationId": award["id"], "publicationDate": "2026-09-12"},
                    {"lotId": LOT_B, "publicationId": initial["id"], "publicationDate": "2026-09-12"},
                ],
            }
        )
    }
    source.past = {
        "pastPublications": [{"id": initial["id"], "pubType": "tender", "publicationDate": "2026-09-12"}]
    }
    cycle(db, monitor, source)
    with db.session() as session:
        rows = list(session.scalars(select(TenderDossier)))
        assert len(rows) == 1 and rows[0].lot_key == LOT_B


@pytest.mark.parametrize("change", ["paused", "revoked", "policy"])
def test_inflight_access_or_policy_change_discards_network_result(db, change):
    monitor = create(db, active=True)
    source, config = Source(), settings()

    def revoke():
        if change == "policy":
            config.simap_public_source_enabled = False
            return
        with db.session() as session:
            if change == "paused":
                session.execute(
                    update(TenderMonitor)
                    .where(TenderMonitor.id == monitor["id"])
                    .values(status="paused", version=2)
                )
            else:
                member = session.scalar(
                    select(OrganizationMembership).where(
                        OrganizationMembership.user_id == "owner",
                        OrganizationMembership.organization_id == "org-a",
                    )
                )
                session.delete(member)
            session.commit()

    source.hook = revoke
    result = step(db, monitor, source, config=config)
    assert result["status"] in {"inactive_or_superseded", "access_unavailable"}
    with db.session() as session:
        assert not list(session.scalars(select(TenderDossier)))
        collection = session.get(TenderCollection, monitor["id"])
        assert collection.state["query"] == 0 and collection.lease_token is None
        assert session.get(TenderSourceLease, "simap_public").lease_token is None


def test_source_budget_is_shared_across_monitors_without_shared_private_queries(db):
    first, second = create(db, active=True), create(db, active=True, key="second")
    source = Source()
    assert step(db, first, source)["status"] == "collecting_public"
    assert step(db, second, source)["status"] == "source_budget_wait"
    assert source.calls == ["search"]
    with db.session() as session:
        lease = session.get(TenderSourceLease, "simap_public")
        assert not hasattr(lease, "state") and not hasattr(lease, "configuration")
    assert step(db, second, source, at=NOW + timedelta(seconds=15))["status"] == "collecting_public"


def test_simultaneous_workers_cannot_both_claim_the_initial_shared_source_lease(db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(2)

    def claim():
        barrier.wait(timeout=5)
        return tender_jobs._source_claim(db, str(uuid4()), NOW)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(claim), pool.submit(claim)
        results = [first.result(timeout=10), second.result(timeout=10)]
    assert sorted(results) == [False, True]


def test_tender_migration_matches_the_current_worker_models(db):
    from alembic.autogenerate import produce_migrations
    from alembic.migration import MigrationContext

    from helvetic_lens.db import Base

    with db.engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={
                "include_object": lambda obj, name, kind, reflected, compared: (
                    kind != "table" or name.startswith("tender_")
                )
            },
        )
        changes = produce_migrations(context, Base.metadata)
        assert changes.upgrade_ops.is_empty(), changes.upgrade_ops.as_diffs()


def test_disabled_feature_or_source_makes_no_requests_or_private_checkpoints(db):
    monitor = create(db, active=True)
    source, config = Source(), settings()
    config.simap_public_source_enabled = False
    assert step(db, monitor, source, config=config)["status"] == "disabled"
    config.simap_public_source_enabled, config.tender_watch_enabled = True, False
    assert step(db, monitor, source, config=config)["status"] == "disabled"
    assert source.calls == []
    with db.session() as session:
        assert session.get(TenderCollection, monitor["id"]) is None


def test_scheduler_uses_durable_outbox_without_duplicate_active_jobs(db):
    monitor = create(db, active=True)
    with db.session() as session:
        session.execute(
            update(TenderMonitor).where(TenderMonitor.id == monitor["id"]).values(next_poll_at=NOW)
        )
        session.commit()
    assert tender_jobs.enqueue_due(db, settings(), now=NOW) == {"enqueued": 1}
    assert tender_jobs.enqueue_due(db, settings(), now=NOW + timedelta(minutes=1)) == {"enqueued": 0}
    with db.session() as session:
        job = session.scalar(select(Job).where(Job.target_type == "tender_monitor"))
        assert job.payload == {"version": 1}
        assert "Software" not in str(job.payload)
        assert job.organization_id == "org-a"


def test_expired_worker_cannot_apply_or_release_replacement_lease(db):
    monitor = create(db, active=True)
    source = Source()
    replacement = str(uuid4())

    def replace():
        with db.session() as session:
            session.execute(
                update(TenderCollection)
                .where(TenderCollection.monitor_id == monitor["id"])
                .values(lease_token=replacement)
            )
            session.execute(
                update(TenderSourceLease).values(
                    lease_token=replacement, next_request_at=NOW + timedelta(days=1)
                )
            )
            session.commit()

    source.hook = replace
    assert step(db, monitor, source)["status"] == "inactive_or_superseded"
    with db.session() as session:
        assert session.get(TenderCollection, monitor["id"]).lease_token == replacement
        assert session.get(TenderSourceLease, "simap_public").lease_token == replacement
        assert not list(session.scalars(select(TenderDossier)))


def test_repeated_bad_query_does_not_freeze_following_cycles(db):
    monitor = create(db, active=True)
    source = Source()
    source.search_pages = {None: {"broken": "contract"}}
    for index in range(3):
        assert (
            step(db, monitor, source, at=NOW + timedelta(minutes=5 * index))["status"]
            == "invalid_source_contract"
        )
    assert step(db, monitor, source, at=NOW + timedelta(minutes=15))["status"] == "inactive_or_waiting"
    with db.session() as session:
        assert session.get(TenderMonitor, monitor["id"]).health == "partial_public_coverage"
        state = session.get(TenderCollection, monitor["id"]).state
        assert state["gaps"][0]["reason"] == "invalid_source_contract"


def test_verified_taxonomy_is_cached_and_used_before_cpv_candidate_assessment(db):
    monitor = create(db, active=True)
    with db.session() as session:
        session.execute(
            update(TenderMonitor)
            .where(TenderMonitor.id == monitor["id"])
            .values(configuration=profile(capabilities=[], cpv_codes=["72000000"]).model_dump(mode="json"))
        )
        session.commit()
    source = Source()
    source.raw["procurement"]["cpvCode"] = {"code": "72212000"}
    cycle(db, monitor, source)
    assert source.calls == ["search", "publication", "taxonomy", "history"]
    with db.session() as session:
        row = session.scalar(select(TenderDossierVersion))
        assert row.match["matches"][0]["code"] == "cpv_descendant"
        assert row.match["matches"][0]["taxonomy_sha256"]
    source.calls = []
    cycle(db, monitor, source, at=NOW + timedelta(hours=6))
    assert "taxonomy" not in source.calls


def test_same_publication_can_be_applied_to_two_distinct_current_lot_scopes(db):
    monitor = create(db, active=True)
    raw = publication(lots=True)
    raw["lots"][1]["title"]["en"] = "Software development for another lot"
    source = Source(raw)
    source.search_pages = {
        None: page(
            {
                "id": PROJECT,
                "publicationId": raw["id"],
                "publicationDate": "2026-09-12",
                "pubType": "tender",
                "lots": [{"lotId": LOT_A, "publicationId": raw["id"], "publicationDate": "2026-09-12"}],
            },
            last_item="20260912|42058",
        ),
        "20260912|42058": page(
            {
                "id": PROJECT,
                "publicationId": raw["id"],
                "publicationDate": "2026-09-12",
                "pubType": "tender",
                "lots": [{"lotId": LOT_B, "publicationId": raw["id"], "publicationDate": "2026-09-12"}],
            }
        ),
    }
    cycle(db, monitor, source)
    with db.session() as session:
        assert set(session.scalars(select(TenderDossier.lot_key))) == {LOT_A, LOT_B}
        assert session.get(TenderCollection, monitor["id"]).state["buffer"] is None


def test_cancellation_releases_lease_and_preserves_work_for_retry(db):
    from helvetic_lens.jobs import JobCancelled

    monitor = create(db, active=True)
    source = Source()
    checks = []

    def checkpoint():
        checks.append(1)
        if len(checks) == 3:
            raise JobCancelled()

    with pytest.raises(JobCancelled):
        tender_jobs.refresh(
            db, settings(), monitor_id=monitor["id"], version=1, client=source, now=NOW, checkpoint=checkpoint
        )
    with db.session() as session:
        state = session.get(TenderCollection, monitor["id"])
        assert state.lease_token is None and state.state["query"] == 0
    assert step(db, monitor, source, at=NOW + timedelta(seconds=15))["status"] == "collecting_public"


@pytest.mark.asyncio
async def test_real_durable_dispatch_and_http_job_owner_guards(tmp_path, monkeypatch):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_auth import _csrf, _register, _settings

    from helvetic_lens.main import create_app
    from helvetic_lens.tender_repository import create_profile

    config = _settings(tmp_path, tender_watch_enabled=True, simap_public_source_enabled=True)
    app = create_app(config, fetcher=FakeFetcher(), model_client=ScriptedModel())
    source = Source()
    original_refresh = tender_jobs.refresh

    def refresh(*args, **kwargs):
        return original_refresh(*args, **kwargs, now=NOW, client=source)

    monkeypatch.setattr(tender_jobs, "refresh", refresh)
    with TestClient(app) as owner:
        identity = _register(owner).json()
        service = app.state.service
        organization = identity["organization"]["id"]
        with service.db.organization_context(organization), service.db.session() as session:
            saved = create_profile(
                session, identity["user"]["id"], profile().model_dump(mode="json"), "real-dispatch"
            )
            row = session.get(TenderMonitor, saved["id"])
            row.status, row.next_poll_at = "active", NOW
            assert tender_jobs.enqueue(session, row, NOW) == 1
            session.commit()
            job_id = session.scalar(select(Job.id).where(Job.target_id == row.id))
        assert owner.get(f"/api/jobs/{job_id}").status_code == 200
        with TestClient(app) as peer:
            outsider = _register(peer, email="tender-peer@example.test").json()
            with service.db.session(include_all_organizations=True) as session:
                session.add(
                    OrganizationMembership(
                        organization_id=organization,
                        user_id=outsider["user"]["id"],
                        role="organization_admin",
                    )
                )
                session.commit()
            assert (
                peer.post(
                    "/api/auth/session/organization",
                    json={"organization_id": organization},
                    headers=_csrf(peer),
                ).status_code
                == 200
            )
            assert peer.get(f"/api/jobs/{job_id}").status_code == 404
            assert saved["id"] not in str(peer.get("/api/jobs").json())
            assert peer.post(f"/api/jobs/{job_id}/cancel", headers=_csrf(peer)).status_code == 404
            assert peer.post(f"/api/jobs/{job_id}/retry", headers=_csrf(peer)).status_code == 404
        with service.db.organization_context(organization):
            result = await service.execute_job(job_id)
            assert result["state"] == "succeeded", result
            with service.db.session() as session:
                state = session.get(TenderCollection, saved["id"]).state
                assert state["query"] == 1 and state["pending"][0]["kind"] == "publication"
        assert source.calls == ["search"]
