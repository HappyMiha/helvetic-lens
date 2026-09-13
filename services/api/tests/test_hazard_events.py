"""Synthetic private warning workflow; active monitors here bypass no live gate."""

from copy import deepcopy
from dataclasses import asdict
from datetime import timedelta

import pytest
from sqlalchemy import func, select, update
from test_hazard_cap import NOW, info, message
from test_hazard_repository import CONFIG, create
from test_hazard_sources import accept, grant, revised
from test_tender_repository import db as _database_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import hazard_events as events
from helvetic_lens import hazard_sources as sources
from helvetic_lens.config import DomainError
from helvetic_lens.hazard_geometry import match_radius
from helvetic_lens.hazard_models import (
    HazardDevelopment,
    HazardEventRevision,
    HazardMonitor,
    HazardReviewAction,
)
from helvetic_lens.models import OrganizationMembership

db = _database_fixture
template = _template_fixture


class GeometryFixture:
    """Real CAP geometry matching with separately synthetic municipality proof."""
    version = "2026-01"
    sha256 = "a" * 64
    available = True

    def verify_location(self, location, *, now):
        return {"state": "verified" if self.available else "unavailable", "version": self.version, "sha256": self.sha256}

    def match_warning(self, areas, location, *, geocode_version, now):
        match = match_radius(areas, latitude=location.latitude, longitude=location.longitude, radius_km=location.radius_km)
        return {**asdict(match), "basis": "explicit_geometry", "boundary_version": self.version, "boundary_sha256": self.sha256}


@pytest.fixture
def store():
    return GeometryFixture()


def active_fixture(db, *, config=None, actor="owner", key="home"):
    saved = create(db, payload=config, actor=actor, key=key)
    # No production activation function is called: native coverage/access remains
    # an independent unfinished gate. This fixture isolates event behavior.
    with db.session() as session:
        session.execute(update(HazardMonitor).where(HazardMonitor.id == saved["id"]).values(status="active", version=2))
        session.commit()
    return saved["id"]


def project(db, monitor, permission, receipt, store, *, actor="owner", second=0, version=2):
    with db.session() as session:
        result = events.project_message(session, actor, monitor, permission, receipt["evidence_id"], monitor_version=version,
            source_generation=receipt["generation"], source_cursor=receipt["cursor_version"], store=store,
            now=NOW + timedelta(seconds=second))
        session.commit()
        return result


def read(db, monitor, development, store, *, actor="owner", second=0, revision=None):
    with db.session() as session:
        return events.read_event(session, actor, monitor, development, store=store, now=NOW + timedelta(seconds=second), revision=revision)


def review(db, monitor, development, store, version, *, second=0, action="reviewed"):
    with db.session() as session:
        revision = session.get(HazardDevelopment, development).revision
        result = events.set_review(session, "owner", monitor, development, version=version,
            expected_revision=revision, action=action, store=store, now=NOW + timedelta(seconds=second))
        session.commit()
        return result


def setup(db, store):
    monitor = active_fixture(db)
    permission = grant(db, private_decisions_allowed=True)
    receipt = accept(db, permission)
    projected = project(db, monitor, permission, receipt, store)
    return monitor, permission, receipt, projected["development_id"]


def test_inside_receives_private_warning_outside_does_not_and_replay_is_idempotent(db, store):
    monitor, permission, receipt, development = setup(db, store)
    outside = deepcopy(CONFIG)
    outside["location"].update(latitude=47.0, longitude=7.0)
    other = active_fixture(db, config=outside, key="outside")
    assert project(db, other, permission, receipt, store)["development_id"] is None
    assert project(db, monitor, permission, receipt, store) == {"changed": False, "development_id": development, "revision": 1}
    db.engine.dispose()
    event = read(db, monitor, development, store)
    assert event["state"] == "active" and event["needs_review"]
    assert event["source"]["message"]["infos"][0]["instruction"] == "Stay indoors."
    assert event["source"]["attribution"] == "Fixture authority"
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(HazardDevelopment)) == 1


def test_review_translation_preserves_review_then_instruction_change_reopens_then_allclear(db, store):
    monitor, permission, first, development = setup(db, store)
    assert review(db, monitor, development, store, 1)["reviewed"]
    translated = accept(db, permission, revised(infos=info() + info(language="fr-CH", instruction="Restez.")), second=1, cursor=1)
    project(db, monitor, permission, translated, store, second=1)
    event = read(db, monitor, development, store, second=1)
    assert event["revision"] == 2 and event["material_sequence"] == 1 and event["reviewed"]
    changed = accept(db, permission, revised(identifier="third", previous="second", previous_sent="2026-09-13T09:30:00+00:00",
        sent="2026-09-13T09:40:00+00:00", infos=info(instruction="Evacuate now.")), second=2, cursor=2)
    project(db, monitor, permission, changed, store, second=2)
    event = read(db, monitor, development, store, second=2)
    assert event["material_sequence"] == 2 and event["needs_review"]
    assert read(db, monitor, development, store, second=2, revision=1)["source"]["message"]["infos"][0]["instruction"] == "Stay indoors."
    clear = accept(db, permission, revised(identifier="clear", previous="third", previous_sent="2026-09-13T09:40:00+00:00",
        sent="2026-09-13T09:50:00+00:00", infos=info(level="Minor", extra="<responseType>AllClear</responseType>")), second=3, cursor=3)
    project(db, monitor, permission, clear, store, second=3)
    assert read(db, monitor, development, store, second=3)["state"] == "resolved"


def test_cancel_updates_only_existing_private_lineage_without_claiming_allclear(db, store):
    monitor, permission, _, development = setup(db, store)
    cancel = accept(db, permission, revised(kind="Cancel", infos=""), second=1, cursor=1)
    project(db, monitor, permission, cancel, store, second=1)
    assert read(db, monitor, development, store, second=1)["state"] == "cancelled"
    other = active_fixture(db, key="later")
    assert project(db, other, permission, cancel, store, second=1)["development_id"] is None


def test_unknown_classification_or_below_threshold_never_creates_an_affected_event(db, store):
    monitor = active_fixture(db)
    permission = grant(db, private_decisions_allowed=True)
    low = accept(db, permission, message(infos=info(level="Minor")))
    assert project(db, monitor, permission, low, store)["development_id"] is None
    unknown = accept(db, permission, message(identifier="unknown").replace("<value>storm</value>", "<value>unknown</value>"), cursor=1)
    assert project(db, monitor, permission, unknown, store)["development_id"] is None


def test_geography_moving_warning_outside_marks_not_relevant_without_allclear(db, store):
    monitor, permission, _, development = setup(db, store)
    away = accept(db, permission, revised(infos=info(geometry="<circle>46.5,6.5 1</circle>")), cursor=1, second=1)
    project(db, monitor, permission, away, store, second=1)
    event = read(db, monitor, development, store, second=1)
    assert event["state"] == "not_relevant" and event["needs_review"]


@pytest.mark.parametrize("actor", ["peer", "viewer"])
def test_other_users_cannot_read_project_or_review_a_private_place(db, store, actor):
    monitor, permission, receipt, development = setup(db, store)
    with pytest.raises(DomainError) as failure:
        read(db, monitor, development, store, actor=actor)
    assert failure.value.status == 404
    with pytest.raises(DomainError):
        project(db, monitor, permission, receipt, store, actor=actor)
    with db.session() as session, pytest.raises(DomainError):
        events.set_review(session, actor, monitor, development, version=1, expected_revision=1, action="reviewed", store=store, now=NOW)


def test_membership_loss_denies_even_previously_loaded_event(db, store):
    monitor, _, _, development = setup(db, store)
    read(db, monitor, development, store)
    with db.session() as session:
        session.execute(update(OrganizationMembership).where(OrganizationMembership.user_id == "owner").values(role="revoked"))
        session.commit()
    with pytest.raises(DomainError) as failure:
        read(db, monitor, development, store)
    assert failure.value.status == 403


def test_current_source_update_redacts_until_reprojected_but_exact_history_is_readable(db, store):
    monitor, permission, _, development = setup(db, store)
    receipt = accept(db, permission, revised(infos=info(level="Extreme")), second=1, cursor=1)
    current = read(db, monitor, development, store, second=1)
    assert current["state"] == "unavailable" and "source" not in current and "decision" not in current
    assert read(db, monitor, development, store, second=1, revision=1)["state"] == "active"
    project(db, monitor, permission, receipt, store, second=1)
    assert read(db, monitor, development, store, second=1)["decision"]["importance"] == "alarm"


def test_stale_source_and_expired_or_changed_geography_redact_current_facts(db, store):
    monitor, _, _, development = setup(db, store)
    assert read(db, monitor, development, store, second=301)["state"] == "unavailable"
    store.sha256 = "b" * 64
    assert "source" not in read(db, monitor, development, store)
    store.available = False
    assert "decision" not in read(db, monitor, development, store, revision=1)


def test_revocation_erases_derived_content_and_prevents_review(db, store):
    monitor, permission, _, development = setup(db, store)
    with db.session() as session:
        sources.revoke_permission(session, permission, now=NOW)
        session.commit()
    assert read(db, monitor, development, store)["state"] == "unavailable"
    with db.session() as session:
        row = session.scalar(select(HazardEventRevision))
        assert row.decision == {} and row.proof == {}
    with pytest.raises(DomainError):
        review(db, monitor, development, store, 1)


def test_review_cas_and_dismissal_do_not_hide_later_escalation(db, store):
    monitor, permission, _, development = setup(db, store)
    dismissed = review(db, monitor, development, store, 1, action="not_relevant")
    assert dismissed["dismissed"] and not dismissed["needs_review"]
    with pytest.raises(DomainError):
        review(db, monitor, development, store, 1)
    high = accept(db, permission, revised(infos=info(level="Extreme")), second=1, cursor=1)
    project(db, monitor, permission, high, store, second=1)
    assert read(db, monitor, development, store, second=1)["needs_review"]


def test_processing_requires_active_version_and_separate_derived_storage_right(db, store):
    monitor = create(db)["id"]
    permission = grant(db, private_decisions_allowed=True)
    receipt = accept(db, permission)
    with pytest.raises(DomainError) as failure:
        project(db, monitor, permission, receipt, store, version=1)
    assert failure.value.code == "hazard_event_monitor_inactive_or_changed"
    monitor = active_fixture(db, key="active")
    other = grant(db, expected_generation=1)
    receipt = accept(db, other, generation=2)
    with pytest.raises(DomainError) as failure:
        project(db, monitor, other, receipt, store)
    assert failure.value.code == "hazard_private_decisions_denied"


def test_projection_rollback_and_geography_change_during_write_are_atomic(db, store, monkeypatch):
    monitor = active_fixture(db)
    permission = grant(db, private_decisions_allowed=True)
    receipt = accept(db, permission)
    with db.session() as session:
        events.project_message(session, "owner", monitor, permission, receipt["evidence_id"], monitor_version=2,
            source_generation=1, source_cursor=1, store=store, now=NOW)
        session.rollback()
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(HazardDevelopment)) == 0
    original = store.verify_location
    calls = 0

    def changing(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            store.sha256 = "b" * 64
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "verify_location", changing)
    with pytest.raises(DomainError) as failure:
        project(db, monitor, permission, receipt, store)
    assert failure.value.code == "hazard_event_geography_changed"
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(HazardDevelopment)) == 0


def test_event_storage_limit_does_not_advance_private_revision(db, store, monkeypatch):
    monitor, permission, _, development = setup(db, store)
    receipt = accept(db, permission, revised(), second=1, cursor=1)
    monkeypatch.setattr(events, "MAX_REVISIONS", 1)
    with pytest.raises(DomainError) as failure:
        project(db, monitor, permission, receipt, store, second=1)
    assert failure.value.code == "hazard_event_storage_limit"
    with db.session() as session:
        assert session.get(HazardDevelopment, development).revision == 1


def test_review_audit_keeps_exact_revision_and_is_rolled_back_with_the_action(db, store):
    monitor, permission, _, development = setup(db, store)
    review(db, monitor, development, store, 1)
    high = accept(db, permission, revised(infos=info(level="Extreme")), second=1, cursor=1)
    project(db, monitor, permission, high, store, second=1)
    event = read(db, monitor, development, store, second=1)
    with db.session() as session:
        events.set_review(session, "owner", monitor, development, version=event["version"], action="reviewed",
                          expected_revision=event["revision"], store=store, now=NOW + timedelta(seconds=1))
        session.rollback()
    assert read(db, monitor, development, store, second=1)["needs_review"]
    with db.session() as session:
        actions = list(session.execute(select(HazardReviewAction, HazardEventRevision).join(
            HazardEventRevision, HazardEventRevision.id == HazardReviewAction.event_revision_id)))
        assert len(actions) == 1
        assert actions[0][0].action == "reviewed" and actions[0][1].revision == 1


def test_private_history_and_pages_have_bounded_owned_cursors_without_source_prose(db, store):
    monitor, permission, _, development = setup(db, store)
    second = accept(db, permission, revised(infos=info(level="Extreme")), second=1, cursor=1)
    project(db, monitor, permission, second, store, second=1)
    with db.session() as session:
        page = events.list_events(session, "owner", monitor, store=store, now=NOW + timedelta(seconds=1), limit=1)
        assert not page["coverage_verified"] and "source" not in page["items"][0]
        page = events.history(session, "owner", monitor, development, store=store, now=NOW + timedelta(seconds=1), limit=1)
        assert page["items"][0]["revision"] == 2 and page["next_cursor"] == 2
        older = events.history(session, "owner", monitor, development, store=store, now=NOW + timedelta(seconds=1), before=2)
        assert older["items"][0]["revision"] == 1 and "source" not in older["items"][0]
        with pytest.raises(DomainError):
            events.list_events(session, "peer", monitor, store=store, now=NOW, after_id=development)
        session.info["organization_id"] = "org-b"
        with pytest.raises(DomainError) as failure:
            events.read_event(session, "owner", monitor, development, store=store, now=NOW)
        assert failure.value.status == 404


def test_source_retention_also_erases_private_decisions(db, store):
    monitor = active_fixture(db)
    permission = grant(db, private_decisions_allowed=True, raw_retention_seconds=0, normalized_retention_seconds=10)
    receipt = accept(db, permission)
    project(db, monitor, permission, receipt, store)
    with db.session() as session:
        sources.purge_content(session, now=NOW + timedelta(seconds=10), permission_id=permission)
        session.commit()
    with db.session() as session:
        row = session.scalar(select(HazardEventRevision))
        assert row.decision == row.proof == {}


def test_type_mute_is_owner_private_preserves_review_and_requires_fresh_monitor_version(db, store):
    monitor, permission, receipt, development = setup(db, store)
    with db.session() as session:
        muted = events.set_mute(session, "owner", monitor, "storm", version=2, muted=True, now=NOW)
        assert muted["version"] == 3 and muted["muted_hazards"] == ["storm"]
        session.commit()
    event = read(db, monitor, development, store)
    assert event["muted"] and event["needs_review"] and not event["reviewed"]
    with pytest.raises(DomainError):
        project(db, monitor, permission, receipt, store)
    with db.session() as session:
        with pytest.raises(DomainError):
            events.set_mute(session, "owner", monitor, "storm", version=2, muted=False, now=NOW)
        with pytest.raises(DomainError):
            events.mutes(session, "peer", monitor)
        events.set_mute(session, "owner", monitor, "storm", version=3, muted=False, now=NOW)
        session.commit()
    assert not read(db, monitor, development, store)["muted"]


def test_muting_one_hazard_cannot_silence_another_selected_hazard(db, store):
    monitor = active_fixture(db)
    permission = grant(db, private_decisions_allowed=True, rules=(
        sources.HazardRule(hazard="storm", value_name="fixture", value="storm"),
        sources.HazardRule(hazard="flood", value_name="fixture", value="flood")))
    xml = message(infos=info(extra="<eventCode><valueName>fixture</valueName><value>flood</value></eventCode>"))
    receipt = accept(db, permission, xml)
    development = project(db, monitor, permission, receipt, store)["development_id"]
    with db.session() as session:
        events.set_mute(session, "owner", monitor, "storm", version=2, muted=True, now=NOW)
        session.commit()
    assert not read(db, monitor, development, store)["muted"]
    with db.session() as session:
        events.set_mute(session, "owner", monitor, "flood", version=3, muted=True, now=NOW)
        session.commit()
    assert read(db, monitor, development, store)["muted"]


def test_review_action_bound_keeps_review_state_unchanged(db, store, monkeypatch):
    monitor, _, _, development = setup(db, store)
    monkeypatch.setattr(events, "MAX_REVIEW_ACTIONS", 0)
    with pytest.raises(DomainError) as failure:
        review(db, monitor, development, store, 1)
    assert failure.value.code == "hazard_review_history_limit"
    assert read(db, monitor, development, store)["needs_review"]


def test_shared_source_revocation_purges_private_derived_content_in_every_organization(db, store):
    _, permission, receipt, _ = setup(db, store)
    with db.organization_context("org-b"):
        other_monitor = active_fixture(db, key="other-organization")
        project(db, other_monitor, permission, receipt, store)
    with db.session() as session:
        sources.revoke_permission(session, permission, now=NOW)
        session.commit()
    with db.session(include_all_organizations=True) as session:
        rows = list(session.scalars(select(HazardEventRevision)))
        assert len(rows) == 2 and {row.organization_id for row in rows} == {"org-a", "org-b"}
        assert all(row.decision == row.proof == {} for row in rows)


def test_historical_reader_cannot_review_unseen_new_instructions_even_with_current_version(db, store):
    monitor, permission, _, development = setup(db, store)
    newer = accept(db, permission, revised(infos=info(instruction="Evacuate.")), second=1, cursor=1)
    project(db, monitor, permission, newer, store, second=1)
    historical = read(db, monitor, development, store, second=1, revision=1)
    with db.session() as session, pytest.raises(DomainError) as failure:
        events.set_review(session, "owner", monitor, development, version=historical["version"],
                          expected_revision=historical["revision"], action="reviewed", store=store, now=NOW + timedelta(seconds=1))
    assert failure.value.code == "hazard_event_review_conflict"
    assert read(db, monitor, development, store, second=1)["needs_review"]
