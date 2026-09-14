"""Default selection respects stored operator decisions; no live source calls."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from test_hazard_lifecycle import ScopeFixture
from test_hazard_meteoalarm_store import snapshot
from test_hazard_repository import CONFIG
from test_hazard_sources import db as _database_fixture
from test_hazard_sources import grant
from test_hazard_sources import template as _template_fixture

from helvetic_lens import hazard_acquisition as acquisition
from helvetic_lens import hazard_native_source as native
from helvetic_lens import hazard_readiness as readiness
from helvetic_lens import hazard_sources as sources
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.hazard_contracts import HazardConfiguration
from helvetic_lens.hazard_source_models import (
    HazardMessageEvidence,
    HazardSourcePermission,
    HazardSourceSelection,
)

db = _database_fixture
template = _template_fixture
NOW = native.REVIEWED_AT + timedelta(hours=1)


def settings(**kwargs):
    return Settings(_env_file=None, hazard_watch_enabled=True, hazard_source_enabled=True, **kwargs)


def test_default_public_contract_needs_a_complete_poll_and_only_enables_reviewed_types(db):
    config = settings()
    assert native.initialize(db, config, now=NOW) == {"state": "installed"}
    assert native.initialize(db, config, now=NOW) == {"state": "existing_selection"}
    saved = HazardConfiguration.model_validate({**CONFIG, "hazards": ["storm"]})
    with db.session() as session:
        identifier = native.permission_id(session, config)
        _, policy = sources.require_permission(session, identifier, now=NOW)
        assert policy.reference.endswith(native.TERMS_SHA256)
        assert policy.coverage[0].hazard == "storm" and len(policy.coverage[0].cantons) == 26
        with pytest.raises(DomainError) as error:
            readiness.ready(session, config, saved, store=ScopeFixture(), now=NOW)
        assert error.value.code == "hazard_source_poll_not_current"
        assert readiness.source_summary(session, config, now=NOW)["state"] == "unavailable"
    preparations = []

    def prepare(guard):
        guard()
        preparations.append(True)

    result = acquisition.collect(db, config, downloader=lambda **_: snapshot(when=NOW), now=lambda: NOW, prepare=prepare)
    assert result["state"] == "published" and preparations == [True]
    with db.session() as session:
        proof = readiness.ready(session, config, saved, store=ScopeFixture(), now=NOW)
        assert proof["permission_id"] == identifier and proof["cursor"] == 1
        summary = readiness.source_summary(session, config, now=NOW)
        assert summary["state"] == "current" and summary["supported_hazards"] == ["storm"]
        assert "permission_id" not in summary and "reference" not in summary
        assert readiness.source_summary(session, config, now=NOW + timedelta(minutes=6))["state"] == "unavailable"
        assert session.scalar(select(func.count()).select_from(HazardMessageEvidence)) == 0
        for hazard in ("heavy_snow", "flood", "forest_fire", "power_outage", "civil_protection_warning"):
            unverified = saved.model_copy(update={"hazards": (hazard,)})
            with pytest.raises(DomainError) as error:
                readiness.ready(session, config, unverified, store=ScopeFixture(), now=NOW)
            assert error.value.code == "hazard_selected_type_coverage_unverified"


@pytest.mark.parametrize("change", ["revoked", "deselected", "expired"])
def test_default_never_recreates_or_renews_a_prior_source_decision(db, change):
    config = settings()
    native.initialize(db, config, now=NOW)
    when = NOW
    with db.session() as session:
        identifier = native.permission_id(session, config)
        if change == "revoked":
            sources.revoke_permission(session, identifier, now=NOW)
        elif change == "deselected":
            session.delete(session.get(HazardSourceSelection, native.SOURCE_KEY))
        else:
            when = native.VALID_UNTIL
        session.commit()
    native.initialize(db, config, now=when)
    calls = []
    result = acquisition.collect(db, config, downloader=lambda **_: calls.append(True), now=lambda: when)
    assert result["state"] in {"unconfigured", "permission_unavailable"} and calls == []
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(HazardSourcePermission)) == 1


def test_explicit_or_unselected_existing_custom_contract_is_never_replaced(db):
    identifier = grant(db)
    config = settings(hazard_source_permission_id=identifier)
    assert native.initialize(db, config, now=NOW)["state"] == "unchanged"
    config.hazard_source_permission_id = ""
    assert native.initialize(db, config, now=NOW)["state"] == "operator_selection_required"
    with db.session() as session:
        assert native.permission_id(session, config) == ""
        assert session.scalar(select(func.count()).select_from(HazardSourcePermission)) == 1


def test_disabled_source_does_not_install_a_public_permission(db):
    config = settings()
    config.hazard_source_enabled = False
    assert native.initialize(db, config, now=NOW)["state"] == "unchanged"
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(HazardSourcePermission)) == 0


def test_normal_worker_installs_default_collects_and_uses_guarded_geometry_preparation(db, monkeypatch):
    from helvetic_lens import celery_app as task
    from helvetic_lens import hazard_native_boundaries as geometry

    config = settings()
    collected = acquisition.collect
    checks = []

    def prepare(path, *, now, checkpoint):
        assert path == config.storage_path and now == NOW
        checkpoint()
        checks.append(True)
        return {"state": "installed"}

    def collect(database, settings, **kwargs):
        return collected(database, settings, downloader=lambda **_: snapshot(when=NOW), now=lambda: NOW, **kwargs)

    monkeypatch.setattr(task, "settings", config)
    monkeypatch.setattr(task, "Database", lambda _: db)
    monkeypatch.setattr(acquisition, "clock", lambda: NOW)
    monkeypatch.setattr(acquisition, "collect", collect)
    monkeypatch.setattr(geometry, "ensure", prepare)
    assert task.collect_hazard_source()["state"] == "published"
    assert checks == [True]
    with db.session() as session:
        assert readiness.source_summary(session, config, now=NOW)["state"] == "current"
