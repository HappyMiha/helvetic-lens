import copy
import shutil
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import delete, inspect, select, update
from sqlalchemy.exc import IntegrityError
from test_tender_matching import NOW, PROJECT, profile, record, source

from alembic import command
from helvetic_lens import tender_repository as tenders
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.db import Database
from helvetic_lens.models import Organization, OrganizationMembership, User
from helvetic_lens.tender_models import (
    TenderDecision,
    TenderDossier,
    TenderDossierVersion,
    TenderMonitor,
    TenderProfileRevision,
)
from helvetic_lens.tender_observations import observe_publication


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    root = tmp_path_factory.mktemp("tender-template")
    path = root / "baseline.db"
    db = Database(
        Settings(_env_file=None, database_url=f"sqlite:///{path.as_posix()}", data_dir=root / "data"),
        organization_id="org-a",
    )
    db.migrate()
    with db.session(include_all_organizations=True) as session:
        session.add_all(
            [Organization(id="org-a", name="A", slug="a"), Organization(id="org-b", name="B", slug="b")]
        )
        session.add_all(
            [
                User(id=user, name=user, email=f"{user}@example.test", password_hash="synthetic-unused")
                for user in ("owner", "peer", "viewer")
            ]
        )
        session.flush()
        session.add_all(
            [
                OrganizationMembership(organization_id=org, user_id=user, role=role)
                for org, user, role in (
                    ("org-a", "owner", "organization_admin"),
                    ("org-a", "peer", "organization_admin"),
                    ("org-a", "viewer", "viewer"),
                    ("org-b", "owner", "organization_admin"),
                )
            ]
        )
        session.commit()
    db.engine.dispose()
    return path


@pytest.fixture
def db(template, tmp_path):
    path = tmp_path / "tenders.db"
    shutil.copyfile(template, path)
    database = Database(
        Settings(_env_file=None, database_url=f"sqlite:///{path.as_posix()}", data_dir=tmp_path / "data"),
        organization_id="org-a",
    )
    yield database
    database.engine.dispose()


def create(db, *, active=False, key="create-a"):
    with db.session() as session:
        row = tenders.create_profile(session, "owner", profile().model_dump(mode="json"), key)
        if active:
            # Only a fixture: production activation will require source acceptance.
            session.execute(
                update(TenderMonitor).where(TenderMonitor.id == row["id"]).values(status="active")
            )
        session.commit()
    return row


def publication(*, ordinal=1, lots=False):
    raw = source(lots=lots)
    raw["base"].update(publicationNumber=f"42058-{ordinal:02d}", projectNumber="42058")
    raw["terms"] = {
        "termsType": "in_publication",
        "termsCriteria": [{"id": "refs", "description": {"en": "3 references required"}}],
    }
    return raw


def revised(raw, ordinal=2):
    result = copy.deepcopy(raw)
    result["id"] = result["base"]["id"] = str(uuid4())
    result["base"]["publicationNumber"] = f"42058-{ordinal:02d}"
    return result


def parsed(raw):
    from helvetic_lens.simap_sources import parse_publication

    return parse_publication(raw, project_id=PROJECT, publication_id=raw["id"], now=NOW)


def ingest(db, monitor, raw):
    with db.session() as session:
        ids = observe_publication(session, monitor["id"], parsed(raw), now=NOW)
        session.commit()
        return ids


def read(db, dossier):
    with db.session() as session:
        return tenders.get_dossier(session, "owner", dossier, now=NOW)


def decide(db, item, key="decision-1"):
    with db.session() as session:
        result = tenders.record_decision(
            session,
            "owner",
            item["id"],
            version=item["version"],
            sequence=item["sequence"],
            decision="bid",
            key=key,
            now=NOW,
        )
        session.commit()
        return result


def test_profiles_persist_idempotently_and_revisions_do_not_rewrite_history(db):
    initial = create(db)
    changed = profile(company_name="Changed company").model_dump(mode="json")
    with db.session() as session:
        row = tenders.revise_profile(session, "owner", initial["id"], 1, changed)
        session.commit()
    db.migrate()
    with db.session() as session:
        assert tenders.get_monitor(session, "owner", initial["id"]) == row
        assert (
            tenders.create_profile(session, "owner", profile().model_dump(mode="json"), "create-a")[
                "revision"
            ]
            == 2
        )
        history = tenders.profile_history(session, "owner", row["id"], limit=1)
        assert history["items"][0]["configuration"]["company_name"] == "Changed company"
        assert history["next_cursor"] == 2
        older = tenders.profile_history(session, "owner", row["id"], before_revision=2)
        assert older["items"][0]["configuration"]["company_name"] == "Example GmbH"
        with pytest.raises(DomainError, match="different settings"):
            tenders.create_profile(session, "owner", changed, "create-a")


def test_stale_profile_writer_and_caller_rollback_preserve_winner(db):
    initial = create(db)
    with db.session() as stale:
        tenders.get_monitor(stale, "owner", initial["id"])
        with db.session() as writer:
            tenders.revise_profile(
                writer, "owner", initial["id"], 1, profile(name="Winner").model_dump(mode="json")
            )
            writer.commit()
        with pytest.raises(DomainError, match="changed"):
            tenders.revise_profile(
                stale, "owner", initial["id"], 1, profile(name="Stale").model_dump(mode="json")
            )
        stale.rollback()
    with db.session() as session:
        tenders.create_profile(session, "owner", profile().model_dump(mode="json"), "rolled-back")
        session.rollback()
        rows = tenders.list_monitors(session, "owner")["items"]
        assert len(rows) == 1 and rows[0]["configuration"]["name"] == "Winner"


def test_owner_and_tenant_scope_apply_to_dossiers_history_evidence_and_decisions(db):
    monitor = create(db, active=True)
    (dossier,) = ingest(db, monitor, publication())
    item = read(db, dossier)
    with db.session() as session:
        assert tenders.list_monitors(session, "peer")["items"] == []
        for operation in (
            lambda: tenders.get_monitor(session, "peer", monitor["id"]),
            lambda: tenders.profile_history(session, "peer", monitor["id"]),
            lambda: tenders.get_dossier(session, "peer", dossier),
            lambda: tenders.dossier_history(session, "peer", dossier),
            lambda: tenders.evidence_version(session, "peer", dossier, item["evidence_version_id"]),
            lambda: tenders.record_decision(
                session, "peer", dossier, version=item["version"], sequence=1, decision="bid", key="x"
            ),
        ):
            with pytest.raises(DomainError) as denied:
                operation()
            assert denied.value.status == 404
    with db.organization_context("org-b"), db.session() as session:
        for model in (
            TenderMonitor,
            TenderProfileRevision,
            TenderDossier,
            TenderDossierVersion,
            TenderDecision,
        ):
            assert list(session.scalars(select(model))) == []
        with pytest.raises(DomainError) as denied:
            tenders.get_dossier(session, "owner", dossier)
        assert denied.value.status == 404


def test_membership_revocation_and_viewer_role_are_rechecked(db):
    monitor = create(db)
    with db.session() as session:
        with pytest.raises(DomainError) as denied:
            tenders.create_profile(session, "viewer", profile().model_dump(mode="json"), "viewer")
        assert denied.value.status == 403
        tenders.get_monitor(session, "owner", monitor["id"])
        session.execute(
            delete(OrganizationMembership).where(
                OrganizationMembership.user_id == "owner", OrganizationMembership.organization_id == "org-a"
            )
        )
        session.commit()
        with pytest.raises(DomainError) as denied:
            tenders.get_monitor(session, "owner", monitor["id"])
        assert denied.value.status == 403


def test_deadline_and_requirement_update_reopens_review_without_losing_internal_decision(db):
    monitor = create(db, active=True)
    raw = publication()
    (dossier,) = ingest(db, monitor, raw)
    before = read(db, dossier)
    reviewed = decide(db, before)
    assert reviewed["review_state"] == "reviewed" and reviewed["following"]
    changed = revised(raw)
    changed["dates"]["offerDeadline"] = "2026-10-23T15:00:00+02:00"
    changed["terms"]["termsCriteria"][0]["description"]["en"] = "5 references required"
    assert ingest(db, monitor, changed) == [dossier]
    item = read(db, dossier)
    assert item["id"] == before["id"] and item["decision"] == "bid" and item["reviewed_sequence"] == 1
    assert item["review_state"] == "needs_review" and item["sequence"] == 2
    assert {change["field"] for change in item["changes"]} == {"deadline", "terms"}
    assert item["decision_scope"] == "internal_only"
    # Retrying the first saved decision never reviews the changed requirements.
    assert decide(db, before)["review_state"] == "needs_review"
    with pytest.raises(DomainError, match="changed"):
        decide(db, before, key="stale-new-request")
    assert decide(db, item, key="review-v2")["review_state"] == "reviewed"
    with db.session() as session:
        history = tenders.dossier_history(session, "owner", dossier, now=NOW)
        assert [row["sequence"] for row in history["items"]] == [2, 1]
        original = tenders.evidence_version(session, "owner", dossier, before["evidence_version_id"], now=NOW)
        assert (
            original["original"]["terms"]["termsCriteria"][0]["description"]["en"] == "3 references required"
        )


def test_duplicates_and_presentation_only_revision_do_not_reopen_review(db):
    monitor = create(db, active=True)
    raw = publication()
    (dossier,) = ingest(db, monitor, raw)
    decide(db, read(db, dossier))
    assert ingest(db, monitor, raw) == []
    changed = revised(raw)
    changed["terms"]["termsCriteria"][0]["description"]["en"] = "<p>3   references <b>required</b></p>"
    assert ingest(db, monitor, changed) == [dossier]
    item = read(db, dossier)
    assert item["review_state"] == "reviewed" and item["kind"] == "source_update" and item["changes"] == []


def test_late_backfill_and_replayed_old_content_cannot_rewind_current_dossier(db):
    monitor = create(db, active=True)
    raw = publication(ordinal=2)
    (dossier,) = ingest(db, monitor, raw)
    late = revised(raw, ordinal=1)
    late["dates"]["offerDeadline"] = "2026-10-09T15:00:00+02:00"
    assert ingest(db, monitor, late) == [dossier]
    assert read(db, dossier)["sequence"] == 1
    with db.session() as session:
        versions = tenders.dossier_history(session, "owner", dossier, now=NOW)["items"]
        assert versions[0]["kind"] == "late_evidence" and versions[0]["changes"] == []
    assert ingest(db, monitor, raw) == [] and ingest(db, monitor, late) == []


def test_award_updates_followed_dossier_even_though_it_is_excluded_from_discovery(db):
    monitor = create(db, active=True)
    raw = publication(lots=True)
    (dossier,) = ingest(db, monitor, raw)  # Catering lot is irrelevant.
    decide(db, read(db, dossier))
    award = revised(raw)
    award["type"] = award["base"]["type"] = "award"
    award["lot"] = award.pop("lots")[0]
    assert ingest(db, monitor, award) == [dossier]
    result = read(db, dossier)
    assert result["match"]["verdict"] == "excluded" and result["review_state"] == "needs_review"
    assert result["material"]["phase"]["value"] == "awarded"


def test_paused_monitor_and_revoked_membership_do_not_ingest(db):
    monitor = create(db)
    assert ingest(db, monitor, publication()) == []
    with db.session() as session:
        session.execute(
            update(TenderMonitor).where(TenderMonitor.id == monitor["id"]).values(status="active")
        )
        session.execute(update(User).where(User.id == "owner").values(active=False))
        session.commit()
    with pytest.raises(DomainError) as denied:
        ingest(db, monitor, publication())
    assert denied.value.status == 403


def test_publication_gate_is_rechecked_for_saved_evidence_and_history(db):
    monitor = create(db, active=True)
    (dossier,) = ingest(db, monitor, publication())
    item = read(db, dossier)
    early = NOW - timedelta(seconds=1)
    with db.session() as session:
        assert tenders.dossier_history(session, "owner", dossier, now=early)["items"] == []
        for operation in (
            lambda: tenders.get_dossier(session, "owner", dossier, now=early),
            lambda: tenders.evidence_version(
                session, "owner", dossier, item["evidence_version_id"], now=early
            ),
        ):
            with pytest.raises(DomainError) as denied:
                operation()
            assert denied.value.status == 404


def test_observation_rollback_removes_all_new_evidence(db):
    monitor = create(db, active=True)
    with db.session() as session:
        assert observe_publication(session, monitor["id"], record(publication()), now=NOW)
        session.rollback()
        assert list(session.scalars(select(TenderDossier))) == []
        assert list(session.scalars(select(TenderDossierVersion))) == []


def test_conflicting_later_lot_rolls_back_earlier_lot_in_the_same_observation(db):
    monitor = create(db, active=True)
    initial = publication(lots=True)
    initial["lots"][1]["title"]["en"] = "More software development"
    first, second = ingest(db, monitor, initial)
    award = revised(initial)
    award["type"] = award["base"]["type"] = "award"
    award["lot"] = award.pop("lots")[1]
    assert ingest(db, monitor, award) == [second]
    conflict = revised(initial)
    conflict["dates"]["offerDeadline"] = "2026-10-23T15:00:00+02:00"
    with db.session() as session:
        with pytest.raises(ValueError, match="same sequence"):
            observe_publication(session, monitor["id"], parsed(conflict), now=NOW)
        # The caller can still commit unrelated work; partial lot writes were
        # rolled back by the observation's own savepoint.
        session.commit()
        assert tenders.get_dossier(session, "owner", first, now=NOW)["sequence"] == 1
        history = tenders.dossier_history(session, "owner", first, now=NOW)["items"]
        assert len(history) == 1


def test_reader_detects_a_mutated_original_instead_of_presenting_it_as_saved_evidence(db):
    monitor = create(db, active=True)
    dossier, = ingest(db, monitor, publication())
    item = read(db, dossier)
    with db.session() as session:
        saved = session.get(TenderDossierVersion, item["evidence_version_id"])
        changed = copy.deepcopy(saved.evidence)
        changed["original"]["terms"]["termsCriteria"][0]["description"]["en"] = "Altered"
        saved.snapshot.evidence = changed
        session.commit()
        with pytest.raises(DomainError) as failure:
            tenders.evidence_version(session, "owner", dossier, saved.id, now=NOW)
        assert failure.value.code == "tender_evidence_invalid"


def test_schema_prevents_dossier_link_to_other_tenant_monitor(db):
    monitor = create(db)
    with db.session() as session:
        session.add(TenderDossier(organization_id="org-b", monitor_id=monitor["id"], project_id=PROJECT))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_additive_migration_preserves_accounts_and_existing_monitoring(db):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "d4a6be15f87c")
        tables = inspect(connection).get_table_names()
        assert "tender_monitors" not in tables
        assert {"air_monitors", "river_monitors", "monitoring_subjects", "users"}.issubset(tables)
        command.upgrade(config, "head")
        assert "tender_decisions" in inspect(connection).get_table_names()
    with db.session() as session:
        assert session.get(User, "owner").email == "owner@example.test"
