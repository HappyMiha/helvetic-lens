"""Synthetic source contracts/polls; lifecycle never obtains native rights."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select, update
from test_hazard_cap import NOW, info, message
from test_hazard_events import GeometryFixture
from test_hazard_repository import CONFIG, create
from test_hazard_sources import accept, grant, revised
from test_tender_repository import db as db
from test_tender_repository import template as template

from helvetic_lens import hazard_jobs as worker
from helvetic_lens import hazard_lifecycle as lifecycle
from helvetic_lens import hazard_readiness as readiness
from helvetic_lens import hazard_repository as repository
from helvetic_lens import hazard_sources as sources
from helvetic_lens import jobs
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.hazard_models import HazardDevelopment, HazardEventRevision, HazardMonitorAction
from helvetic_lens.hazard_source_models import HazardSourceSelection
from helvetic_lens.models import Job, OrganizationMembership


class ScopeFixture(GeometryFixture):
    scope_available = True

    def verify_source_scope(self, location, cantons, *, now):
        return {"state": "verified" if self.scope_available and location.canton in cantons else "unavailable",
                "version": self.version, "sha256": self.sha256}


@pytest.fixture
def store():
    return ScopeFixture()


def coverage(hazard="storm", **changes):
    return sources.HazardCoverage(hazard=hazard, cantons=("BS",), evidence_reference="Synthetic publisher jurisdiction",
        evidence_sha256="a" * 64, checked_at=NOW - timedelta(hours=1), valid_until=NOW + timedelta(days=2), **changes)


def complete_poll(db, permission, *, cursor=0, second=0):
    with db.session() as session:
        readiness.record_completed_poll(session, permission, generation=1, cursor=cursor,
            request_url="https://example.invalid/cap", evidence_sha256="b" * 64, now=NOW + timedelta(seconds=second))
        session.commit()


def setup(db, store, *, with_message=True):
    saved = create(db, {**CONFIG, "hazards": ["storm"]})
    permission = grant(db, private_decisions_allowed=True, coverage=(coverage(),))
    if with_message:
        accept(db, permission)
    complete_poll(db, permission, cursor=int(with_message))
    settings = Settings(_env_file=None, hazard_watch_enabled=True, hazard_source_enabled=True,
                        hazard_source_permission_id=permission)
    return saved, permission, settings


def command(db, store, settings, saved, action, *, second=0):
    with db.session() as session:
        result = lifecycle.command(session, "owner", saved["id"], saved["version"], action,
            settings=settings, store=store, now=NOW + timedelta(seconds=second))
        session.commit()
        return result


def test_explicit_start_process_pause_resume_archive_history_and_cancel_old_jobs(db, store):
    saved, _, settings = setup(db, store)
    active = command(db, store, settings, saved, "start")
    assert active["status"] == "active" and active["health"] == "waiting" and active["version"] == 2
    result = worker.refresh(db, settings, monitor_id=active["id"], version=2, store=store, now=NOW)
    assert result["changed"] == 1 and result["coverage_verified"] is False
    assert worker.refresh(db, settings, monitor_id=active["id"], version=2, store=store, now=NOW)["changed"] == 0
    paused = command(db, store, settings, active, "pause")
    assert paused["status"] == "paused" and paused["next_poll_at"] is None
    assert worker.refresh(db, settings, monitor_id=active["id"], version=2, store=store, now=NOW)["state"] == "superseded"
    with db.session() as session:
        assert all(row.cancel_requested for row in session.scalars(select(Job)))
        assert session.scalar(select(func.count()).select_from(HazardDevelopment)) == 1
    resumed = command(db, store, settings, paused, "resume")
    archived = command(db, store, settings, resumed, "archive")
    with db.session() as session:
        actions = lifecycle.history(session, "owner", archived["id"], limit=2)
        assert [row["action"] for row in actions["items"]] == ["archive", "resume"]
        older = lifecycle.history(session, "owner", archived["id"], before=actions["next_cursor"])
        assert [row["action"] for row in older["items"]] == ["pause", "start"]
        assert "proof" not in str(actions) and "latitude" not in str(actions)
        repository.delete_monitor(session, "owner", archived["id"], archived["version"])
        session.commit()
        assert session.scalar(select(HazardMonitorAction)) is None


def test_empty_completed_poll_allows_covered_start_but_never_invents_warning_or_allclear(db, store):
    saved, _, settings = setup(db, store, with_message=False)
    active = command(db, store, settings, saved, "start")
    result = worker.refresh(db, settings, monitor_id=active["id"], version=2, store=store, now=NOW)
    assert result == {"state": "processed", "changed": 0, "unavailable": 0, "coverage_verified": False}
    with db.session() as session:
        assert session.scalar(select(HazardDevelopment)) is None


@pytest.mark.parametrize("cause", ["disabled", "geography", "radius", "poll_missing", "poll_stale", "rights", "unsupported_hazard", "coverage_expired", "new_unfinished_poll"])
def test_start_requires_current_source_scope_and_poll_and_leaves_no_action_or_job_on_failure(db, store, cause):
    saved, permission, settings = setup(db, store)
    second = 0
    if cause == "disabled":
        settings.hazard_source_enabled = False
    elif cause == "geography":
        store.available = False
    elif cause == "radius":
        store.scope_available = False
    elif cause in {"poll_stale", "coverage_expired"}:
        second = 301 if cause == "poll_stale" else 2 * 86400
        if cause == "coverage_expired":
            complete_poll(db, permission, cursor=1, second=second)
    elif cause == "unsupported_hazard":
        with db.session() as session:
            saved = repository.edit_monitor(session, "owner", saved["id"], 1, CONFIG)
            session.commit()
    elif cause == "new_unfinished_poll":
        accept(db, permission, revised(), cursor=1)
    else:
        with db.session() as session:
            if cause == "rights":
                sources.revoke_permission(session, permission, now=NOW)
            else:
                session.execute(update(HazardSourceSelection).values(last_poll_at=None))
            session.commit()
    with pytest.raises(DomainError):
        command(db, store, settings, saved, "start", second=second)
    with db.session() as session:
        assert repository.get_monitor(session, "owner", saved["id"])["status"] == "draft"
        assert session.scalar(select(Job)) is None and session.scalar(select(HazardMonitorAction)) is None


def test_receipt_and_license_without_jurisdiction_do_not_prove_coverage(db, store):
    saved = create(db, {**CONFIG, "hazards": ["storm"]})
    permission = grant(db, private_decisions_allowed=True)
    accept(db, permission)
    complete_poll(db, permission, cursor=1)
    settings = Settings(_env_file=None, hazard_watch_enabled=True, hazard_source_enabled=True, hazard_source_permission_id=permission)
    with pytest.raises(DomainError) as failure:
        command(db, store, settings, saved, "start")
    assert failure.value.code == "hazard_selected_type_coverage_unverified"


def test_rights_expiry_cannot_prevent_pause_archive_or_preserve_stale_background_work(db, store, monkeypatch):
    saved, permission, settings = setup(db, store)
    active = command(db, store, settings, saved, "start")
    with db.session() as session:
        sources.revoke_permission(session, permission, now=NOW)
        session.commit()
    assert worker.refresh(db, settings, monitor_id=active["id"], version=2, store=store, now=NOW)["state"] == "unavailable"
    settings.hazard_source_enabled = False
    store.available = False
    monkeypatch.setattr(lifecycle, "MAX_ACTIONS", 1)
    paused = command(db, store, settings, active, "pause")
    archived = command(db, store, settings, paused, "archive")
    assert archived["status"] == "archived"


def test_version_state_owner_and_membership_checks_protect_commands_and_audit(db, store):
    saved, _, settings = setup(db, store)
    with db.session() as session:
        for actor in ("peer", "viewer"):
            with pytest.raises(DomainError):
                lifecycle.command(session, actor, saved["id"], 1, "start", settings=settings, store=store, now=NOW)
            with pytest.raises(DomainError):
                lifecycle.history(session, actor, saved["id"])
    active = command(db, store, settings, saved, "start")
    with pytest.raises(DomainError):
        command(db, store, settings, saved, "start")
    with pytest.raises(DomainError):
        command(db, store, settings, active, "resume")
    with db.session() as session:
        session.execute(update(OrganizationMembership).where(OrganizationMembership.user_id == "owner").values(role="revoked"))
        session.commit()
    with pytest.raises(DomainError):
        command(db, store, settings, active, "pause")
    assert worker.refresh(db, settings, monitor_id=active["id"], version=2, store=store, now=NOW)["state"] == "access_unavailable"


def test_start_rollback_and_final_geography_change_roll_back_status_job_and_action(db, store, monkeypatch):
    saved, _, settings = setup(db, store)
    with db.session() as session:
        lifecycle.command(session, "owner", saved["id"], 1, "start", settings=settings, store=store, now=NOW)
        session.rollback()
    original, calls = store.verify_source_scope, []
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(1)
        if len(calls) > 1:
            result["sha256"] = "c" * 64
        return result
    monkeypatch.setattr(store, "verify_source_scope", changed)
    with pytest.raises(DomainError):
        command(db, store, settings, saved, "start")
    with db.session() as session:
        assert repository.get_monitor(session, "owner", saved["id"])["status"] == "draft"
        assert session.scalar(select(Job)) is None and session.scalar(select(HazardMonitorAction)) is None


def test_scheduler_deduplicates_and_demoted_owner_cancels_work(db, store):
    saved, _, settings = setup(db, store)
    active = command(db, store, settings, saved, "start")
    assert worker.enqueue_due(db, settings, now=NOW)["enqueued"] == 0
    assert worker.enqueue_due(db, settings, now=NOW)["enqueued"] == 0
    with db.session() as session:
        session.execute(update(OrganizationMembership).where(OrganizationMembership.user_id == "owner").values(role="viewer"))
        session.commit()
    assert worker.enqueue_due(db, settings, now=NOW + timedelta(minutes=1))["enqueued"] == 0
    with db.session() as session:
        assert all(row.cancel_requested for row in session.scalars(select(Job)))
        assert repository.get_monitor(session, "owner", active["id"])["health"] == "access_unavailable"


def test_cancelled_or_lost_job_lease_cannot_publish_projected_events(db, store):
    saved, _, settings = setup(db, store)
    active = command(db, store, settings, saved, "start")
    with db.session() as session:
        job = session.scalar(select(Job))
        identifier = job.id
    with pytest.raises(jobs.JobCancelled):
        worker.refresh(db, settings, monitor_id=active["id"], version=2, store=store, now=NOW,
                       job_id=identifier, lease_owner="not-the-worker")
    with db.session() as session:
        assert session.scalar(select(HazardDevelopment)) is None


def test_new_instructions_require_completed_poll_then_publish_once(db, store):
    saved, permission, settings = setup(db, store)
    active = command(db, store, settings, saved, "start")
    assert worker.refresh(db, settings, monitor_id=active["id"], version=2, store=store, now=NOW)["changed"] == 1
    accept(db, permission, revised(infos=info(instruction="Evacuate.")), cursor=1, second=1)
    assert worker.refresh(db, settings, monitor_id=active["id"], version=2, store=store, now=NOW + timedelta(seconds=1))["state"] == "unavailable"
    complete_poll(db, permission, cursor=2, second=1)
    assert worker.refresh(db, settings, monitor_id=active["id"], version=2, store=store, now=NOW + timedelta(seconds=1))["changed"] == 1


def test_one_stale_warning_does_not_prevent_processing_an_independent_current_warning(db, store):
    saved, permission, settings = setup(db, store)
    active = command(db, store, settings, saved, "start")
    accept(db, permission, message(identifier="fresh-other"), cursor=1, second=301)
    complete_poll(db, permission, cursor=2, second=301)
    result = worker.refresh(db, settings, monitor_id=active["id"], version=2, store=store, now=NOW + timedelta(seconds=301))
    assert result["changed"] == 1 and result["unavailable"] == 1 and result["state"] == "processed"
    with db.session() as session:
        assert repository.get_monitor(session, "owner", active["id"])["health"] == "unavailable"
        assert session.scalar(select(func.count()).select_from(HazardDevelopment)) == 1


def test_scheduled_cleanup_erases_retained_derived_content_without_acquisition_or_processing(db, store):
    saved, _, settings = setup(db, store)
    active = command(db, store, settings, saved, "start")
    worker.refresh(db, settings, monitor_id=active["id"], version=2, store=store, now=NOW)
    settings.hazard_source_enabled = False
    result = worker.cleanup(db, now=NOW + timedelta(days=2))
    assert result["raw_rows"] == result["normalized_rows"] == result["private_rows"] == 1
    with db.session() as session:
        revision = session.scalar(select(HazardEventRevision))
        assert revision.decision == {} and revision.proof == {}
        assert session.scalar(select(HazardMonitorAction)).action == "start"
