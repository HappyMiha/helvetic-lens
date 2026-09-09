"""Offline history uses exact old context, never today's profile or a new model."""

import asyncio
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, select
from test_brief_feedback import prepared
from test_interest_execution import artifacts, execution

from helvetic_lens import brief_history
from helvetic_lens.config import DomainError
from helvetic_lens.models import (
    InterestEventAssessment,
    Profile,
    RegulatoryDocumentVersion,
    RegulatoryEventState,
)

__all__ = ["artifacts", "execution"]


def test_old_profile_and_offline_model_do_not_regenerate_saved_history(execution, harness):
    service, saved, _ = prepared(execution)
    before_calls = len(execution[4]["requests"])
    with service.db.session() as session:
        record = session.get(InterestEventAssessment, saved["id"])
        original = deepcopy(record.result)
        assert all(
            "text" not in row and "source_url" not in row for row in record.history_context["evidence"]
        )
        session.scalar(select(Profile)).revision += 1
        session.commit()
    execution[4]["runtime"] = {}
    response = harness[0].get(f"/api/interest-briefs/{saved['id']}/history")
    assert response.status_code == 200, response.text
    history = response.json()
    assert history["status"] == "historical" and history["result"] == original
    assert history["provenance"]["profile_revision"] == 1 and history["ai_calls"] == 0
    assert len(execution[4]["requests"]) == before_calls
    for link in history["evidence_links"].values():
        assert link.startswith(("/corpus-evidence/", "/evidence/")) and "?passage=" in link


def test_metadata_pagination_is_scoped_and_does_not_load_prose(execution, harness):
    service, saved, _ = prepared(execution)
    with service.db.session() as session:
        original = session.get(InterestEventAssessment, saved["id"])
        for index in range(24):
            session.add(
                InterestEventAssessment(
                    organization_id=service.organization_id,
                    event_id=original.event_id,
                    input_fingerprint=uuid4().hex,
                    input_manifest={**original.input_manifest, "locale": "fr" if index % 2 else "en"},
                    status="failed",
                    error_code="synthetic_failure",
                    created_at=original.created_at + timedelta(seconds=index + 1),
                )
            )
        session.commit()
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(service.db.engine, "before_cursor_execute", capture)
    try:
        path = f"/api/interest-feed/events/{execution[2]}/brief/history"
        first = harness[0].get(path, params={"locale": "fr", "limit": 5}).json()
        second = (
            harness[0].get(path, params={"locale": "fr", "limit": 5, "cursor": first["next_cursor"]}).json()
        )
    finally:
        event.remove(service.db.engine, "before_cursor_execute", capture)
    assert first["has_more"] and second["has_more"] and len(first["items"]) == len(second["items"]) == 5
    assert not {row["id"] for row in first["items"]} & {row["id"] for row in second["items"]}
    assert all(row["locale"] == "fr" for row in first["items"])
    assert all(
        "interest_event_assessments.result" not in sql
        and "interest_event_assessments.history_context" not in sql
        for sql in statements
    )
    assert harness[0].get(path, params={"locale": "en", "cursor": first["next_cursor"]}).status_code == 422
    assert harness[0].get(path, params={"limit": 51}).status_code == 422


@pytest.mark.parametrize("damage", ["text", "artifact", "url", "citation", "context", "legacy"])
def test_changed_or_missing_historical_evidence_withholds_prose(execution, harness, damage):
    service, saved, _ = prepared(execution)
    with service.db.session() as session:
        record = session.get(InterestEventAssessment, saved["id"])
        if damage in {"text", "artifact", "url"}:
            source = session.get(
                RegulatoryDocumentVersion, record.input_manifest["evidence"][0]["version_id"]
            )
            if damage == "text":
                passages = deepcopy(source.passages)
                passages[0]["text"] = "Changed source wording"
                source.passages = passages
            elif damage == "artifact":
                source.artifact_key = "0" * 64
            else:
                source.source_url = "https://example.invalid/different-source"
        elif damage == "citation":
            result = deepcopy(record.result)
            result["what_happened"]["evidence_ids"] = ["foreign"]
            record.result = result
        elif damage == "context":
            context = deepcopy(record.history_context)
            context["profile_revision"] += 1
            record.history_context = context
        else:
            record.history_context = None
        session.commit()
    response = harness[0].get(f"/api/interest-briefs/{saved['id']}/history").json()
    assert response["status"] == (
        "legacy_context_missing" if damage == "legacy" else "historical_unavailable"
    )
    assert response["result"] is None and "evidence_links" not in response


def test_revoked_and_foreign_event_history_is_not_readable(execution, harness):
    service, saved, _ = prepared(execution)
    with service.db.session(include_all_organizations=True) as session:
        with pytest.raises(DomainError) as error:
            brief_history.detail(session, str(uuid4()), saved["id"])
        assert error.value.status == 404
        session.execute(
            delete(RegulatoryEventState).where(
                RegulatoryEventState.organization_id == service.organization_id
            )
        )
        session.commit()
    assert harness[0].get(f"/api/interest-briefs/{saved['id']}/history").status_code == 404
    assert harness[0].get(f"/api/interest-feed/events/{execution[2]}/brief/history").status_code == 404


def test_still_queued_history_returns_no_partial_result(execution, harness):
    service = execution[0]
    saved = asyncio.run(execution[1].run(execution[2]))
    with service.db.session() as session:
        session.get(InterestEventAssessment, saved["id"]).status = "running"
        session.commit()
    result = harness[0].get(f"/api/interest-briefs/{saved['id']}/history").json()
    assert result["assessment_status"] == "running" and result["result"] is None


def test_legacy_material_history_rechecks_both_saved_sides(execution, harness):
    from test_interest_material import setup_saved

    from helvetic_lens.models import Version
    service, event_id, comparison_id, before_id, _ = setup_saved(harness, count=400)
    saved = asyncio.run(execution[1].run(event_id))
    assert saved["status"] == "succeeded"
    with service.db.session() as session:
        result = brief_history.detail(session, service.organization_id, saved["id"])
        assert result["status"] == "historical" and result["result"]["source_comparison"]["id"] == comparison_id
        assert all(link.startswith("/evidence/") for link in result["evidence_links"].values())
        old = session.get(Version, before_id)
        old.owner_organization_id = str(uuid4())
        # Use a real foreign organization for PostgreSQL foreign-key enforcement.
        from helvetic_lens.models import Organization
        session.add(Organization(id=old.owner_organization_id, name="Foreign history organization", slug="foreign-history"))
        session.commit()
    with service.db.session(include_all_organizations=True) as session:
        result = brief_history.detail(session, service.organization_id, saved["id"])
        assert result["status"] == "historical_unavailable" and result["result"] is None


def test_history_migration_preserves_existing_reviews_and_bindings(execution):
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import func
    from test_brief_reviews import request

    from alembic import command
    from helvetic_lens import brief_reviews
    from helvetic_lens.models import InterestAssessmentBinding, InterestBriefReview
    service, saved, _ = prepared(execution)
    with service.db.session() as session:
        review = brief_reviews.save(session, service.organization_id, saved["id"], None,
            brief_reviews.ReviewInput(**request(brief_reviews.read(session, service.organization_id, saved["id"]))))
        bindings = session.scalar(select(func.count()).select_from(InterestAssessmentBinding))
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    with service.db.engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "dc2e367d90fa")
        command.upgrade(cfg, "head")
    with service.db.session() as session:
        record = session.get(InterestEventAssessment, saved["id"])
        assert record.result == saved["result"] and record.history_context is None
        assert session.scalar(select(func.count()).select_from(InterestAssessmentBinding)) == bindings
        assert session.get(InterestBriefReview, review["review"]["id"]).decision == "confirmed"
