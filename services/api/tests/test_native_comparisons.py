"""Native baseline ownership, complete comparison and real brief-runner path."""

import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import delete, func, inspect, select
from test_interest_admission import model_identity, setup
from test_interest_execution import artifacts as artifacts_fixture
from test_interest_execution import execution as execution_fixture

from alembic import command
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.interest_admission import current_key
from helvetic_lens.models import (
    NativeDocumentComparison,
    NativeEventComparisonSelection,
    Organization,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryExpression,
    RegulatoryWork,
)
from helvetic_lens.native_comparisons import select_baseline

artifacts = artifacts_fixture
execution = execution_fixture


def baseline(service, event_id, *, altered=True, grant=True):
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, event_id)
        after = session.get(RegulatoryDocumentVersion, event.document_version_id)
        rows = copy.deepcopy(after.passages)
        if altered:
            rows[-1]["text"] += " Earlier synthetic wording."
        before = RegulatoryDocumentVersion(expression_id=after.expression_id, version_key=str(uuid4()),
            artifact_key="b" * 64 + ".html", extractor="synthetic", source_url="https://example.test/baseline",
            text="\n\n".join(row["text"] for row in rows), passages=rows,
            # Deliberately imported AFTER the event version. No timestamp guessing.
            created_at=utcnow() + timedelta(days=2))
        session.add(before)
        session.flush()
        if grant:
            earlier = RegulatoryEvent(work_id=event.work_id, expression_id=event.expression_id,
                document_version_id=before.id, authority=event.authority, event_type="new_version",
                dedupe_key=str(uuid4()), detected_at=utcnow(), source_url=before.source_url,
                provenance_method="official_metadata", evidence_json={"synthetic": True})
            session.add(earlier)
            session.flush()
            session.add(RegulatoryEventState(event_id=earlier.id))
        session.commit()
        return before.id, after.id


def choose(service, event_id, before_id, after_id, revision=0):
    with service.db.session() as session:
        row = select_baseline(session, service.organization_id, event_id,
            before_version_id=before_id, after_version_id=after_id, expected_revision=revision)
        session.commit()
        return row


def read(service, event_id):
    with service.db.session() as session:
        return current_key(session, service.organization_id, event_id, model=model_identity())


def test_complete_large_native_pair_persists_and_reuses_without_import_order_guess(harness):
    service, event_id, _, _ = setup(harness, units=400)
    before, after = baseline(service, event_id)
    with pytest.raises(DomainError) as error:
        read(service, event_id)
    assert error.value.code == "interest_context_exceeded"  # no implicit baseline
    selected = choose(service, event_id, before, after)
    value, key = read(service, event_id)
    assert len(value.evidence) == 2
    assert value.source_comparison.old_passage_count == value.source_comparison.new_passage_count == 400
    assert value.source_comparison.basis == "organization_selected"
    assert value.source_comparison.before_version_id == before
    assert value.source_comparison.after_version_id == after
    assert {row.side for row in value.evidence} == {"before", "after"}
    assert "does not establish legal effective dates" in value.event.limitations[0]
    assert read(service, event_id)[1] == key
    repeated = choose(service, event_id, before, after, selected.revision)
    assert repeated.comparison_id == selected.comparison_id and repeated.revision == 1
    assert read(service, event_id)[1] == key  # no token-burning invalidation on an unchanged save
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(NativeDocumentComparison)) == 1
        comparison = session.get(NativeDocumentComparison, repeated.comparison_id)
        assert len(comparison.diff["items"]) == 400
    assert not harness[3].calls


def test_baseline_changes_and_clear_preserve_history_and_revision_tombstone(harness):
    service, event_id, _, _ = setup(harness)
    old, after = baseline(service, event_id)
    another, _ = baseline(service, event_id, altered=False)
    first = choose(service, event_id, old, after)
    first_key = read(service, event_id)[1]
    second = choose(service, event_id, another, after, 1)
    assert first.comparison_id != second.comparison_id
    assert read(service, event_id)[1] != first_key
    assert read(service, event_id)[0].source_comparison.changes == []
    cleared = choose(service, event_id, None, after, 2)
    assert cleared.revision == 3 and cleared.comparison_id is None
    assert read(service, event_id)[0].source_comparison is None
    with pytest.raises(DomainError) as error:
        choose(service, event_id, old, after, 0)
    assert error.value.code == "native_selection_conflict"
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(NativeDocumentComparison)) == 2
        assert session.scalar(select(func.count()).select_from(NativeEventComparisonSelection)) == 1


@pytest.mark.parametrize("change", ["before", "after", "passage_metadata", "artifact", "url", "diff", "grant", "event", "language"])
def test_source_corrections_and_revocations_invalidate_selection_without_fallback(harness, change):
    service, event_id, _, _ = setup(harness)
    before, after = baseline(service, event_id)
    selected = choose(service, event_id, before, after)
    with service.db.session() as session:
        old = session.get(RegulatoryDocumentVersion, before)
        if change in {"before", "after"}:
            version = old if change == "before" else session.get(RegulatoryDocumentVersion, after)
            version.text += " Corrected."
        elif change == "passage_metadata":
            old.passages = [{**row, "page": 99} for row in old.passages]
        elif change == "artifact":
            old.artifact_key = "c" * 64 + ".pdf"
        elif change == "url":
            old.source_url = "https://example.test/corrected-source"
        elif change == "diff":
            comparison = session.get(NativeDocumentComparison, selected.comparison_id)
            comparison.diff = {**comparison.diff, "items": comparison.diff["items"][:-1]}
        elif change == "grant":
            earlier_id = session.scalar(select(RegulatoryEvent.id).where(RegulatoryEvent.document_version_id == before))
            session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == earlier_id))
        elif change == "event":
            session.get(RegulatoryEvent, event_id).document_version_id = before
        else:
            session.get(RegulatoryExpression, old.expression_id).language = "und"
        session.commit()
    with pytest.raises(DomainError) as error:
        read(service, event_id)
    assert error.value.code in {"interest_comparison_unavailable", "interest_evidence_unavailable", "interest_not_current"}


@pytest.mark.parametrize("failure", ["same", "ungranted", "language", "work", "malformed", "missing", "unknown_language", "retarget"])
def test_invalid_pair_cannot_be_selected_or_written(harness, failure):
    service, event_id, _, _ = setup(harness)
    before, after = baseline(service, event_id, grant=failure != "ungranted")
    with service.db.session() as session:
        old = session.get(RegulatoryDocumentVersion, before)
        if failure in {"language", "work"}:
            original = session.get(RegulatoryExpression, old.expression_id)
            work_id = original.work_id
            if failure == "work":
                work = RegulatoryWork(authority="fedlex", kind="act", canonical_key="native-other-work", title="Other work")
                session.add(work)
                session.flush()
                work_id = work.id
            expression = RegulatoryExpression(work_id=work_id, language="fr", expression_key="other")
            session.add(expression)
            session.flush()
            old.expression_id = expression.id
        elif failure == "malformed":
            old.passages = [{"id": "bad", "text": ""}]
        elif failure == "missing":
            old.artifact_key = None
        elif failure == "unknown_language":
            session.get(RegulatoryExpression, old.expression_id).language = "und"
        session.commit()
    with pytest.raises(DomainError):
        choose(service, event_id, after if failure == "same" else before,
               before if failure == "retarget" else after)
    with service.db.session() as session:
        assert not list(session.scalars(select(NativeDocumentComparison)))
        assert not list(session.scalars(select(NativeEventComparisonSelection)))


def test_tenant_selection_never_leaks_into_another_admitted_organization(harness):
    service, event_id, _, _ = setup(harness)
    before, after = baseline(service, event_id)
    chosen = choose(service, event_id, before, after)
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Other", slug="native-other")
        session.add(other)
        session.flush()
        with pytest.raises(DomainError) as error:
            select_baseline(session, other.id, event_id, before_version_id=before,
                            after_version_id=after, expected_revision=0)
        assert error.value.code == "not_found"
        event = session.get(RegulatoryEvent, event_id)
        session.add(RegulatoryEventState(organization_id=other.id, event_id=event.id))
        session.flush()
        from helvetic_lens.native_comparisons import event_material
        assert event_material(session, other.id, event) is None
        # Even a corrupted cross-tenant selection pointer is refused in a privileged worker.
        session.add(NativeEventComparisonSelection(organization_id=other.id, event_id=event.id,
                    comparison_id=chosen.comparison_id, revision=1))
        session.flush()
        with pytest.raises(DomainError) as error:
            event_material(session, other.id, event)
        assert error.value.code == "interest_comparison_unavailable"
        session.rollback()


def test_local_runner_uses_native_pair_once_and_persists_exact_comparison(execution):
    service, runner, event_id = execution[:3]
    before, after = baseline(service, event_id)
    chosen = choose(service, event_id, before, after)
    result = asyncio.run(runner.run(event_id))
    assert result["status"] == "succeeded"
    comparison = result["result"]["source_comparison"]
    assert comparison["id"] == chosen.comparison_id and comparison["basis"] == "organization_selected"
    assert comparison["before_version_id"] == before and comparison["after_version_id"] == after
    assert len(execution[4]["generated"]) == 1
    again = asyncio.run(runner.run(event_id))
    assert again["cached"] and len(execution[4]["generated"]) == 1


def test_native_selection_change_during_generation_cannot_publish(execution):
    service, runner, event_id = execution[:3]
    before, after = baseline(service, event_id)
    choose(service, event_id, before, after)

    def clear(phase):
        if phase == "generate":
            choose(service, event_id, None, after, 1)

    execution[4]["hook"] = clear
    result = asyncio.run(runner.run(event_id))
    assert result["status"] == "superseded" and result["result"] is None


def test_stale_pair_must_be_explicitly_rebuilt_and_old_history_survives(harness):
    service, event_id, _, _ = setup(harness)
    before, after = baseline(service, event_id)
    original = choose(service, event_id, before, after)
    with service.db.session() as session:
        version = session.get(RegulatoryDocumentVersion, before)
        version.passages = [{**row, "text": row["text"] + " Saved correction."} for row in version.passages]
        session.commit()
    renewed = choose(service, event_id, before, after, 1)
    assert renewed.comparison_id != original.comparison_id
    value, _ = read(service, event_id)
    assert value.source_comparison.id == renewed.comparison_id
    with service.db.session() as session:
        assert session.get(NativeDocumentComparison, original.comparison_id)


def test_concurrent_editors_cannot_overwrite_each_other(harness):
    service, event_id, _, _ = setup(harness)
    before, after = baseline(service, event_id)
    other, _ = baseline(service, event_id, altered=False)
    third, _ = baseline(service, event_id)
    choose(service, event_id, before, after)
    barrier = Barrier(2)

    def edit(baseline_id):
        barrier.wait(timeout=10)
        try:
            return choose(service, event_id, baseline_id, after, 1).comparison_id
        except DomainError as error:
            assert error.code == "native_selection_conflict"
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, (third, other)))
    assert results.count("conflict") == 1
    with service.db.session() as session:
        selected = session.scalar(select(NativeEventComparisonSelection))
        assert selected.revision == 2 and selected.comparison_id in results


def test_native_migration_roundtrip_preserves_saved_corpus(harness):
    service, event_id, after_id, _ = setup(harness)
    before, after = baseline(service, event_id)
    choose(service, event_id, before, after)
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "d7d9f1284ba5")
        assert "native_document_comparisons" not in inspect(connection).get_table_names()
        command.upgrade(config, "head")
        for model in (NativeDocumentComparison, NativeEventComparisonSelection):
            columns = {row["name"] for row in inspect(connection).get_columns(model.__tablename__)}
            assert columns == set(model.__table__.columns.keys())
    with service.db.session() as session:
        assert session.get(RegulatoryEvent, event_id)
        assert session.get(RegulatoryDocumentVersion, after_id)
        assert session.get(RegulatoryDocumentVersion, before)
        assert not list(session.scalars(select(NativeDocumentComparison)))


def test_complete_oversized_changes_are_saved_but_not_sampled_for_ai(harness):
    service, event_id, _, _ = setup(harness, units=70)
    before, after = baseline(service, event_id)
    with service.db.session() as session:
        version = session.get(RegulatoryDocumentVersion, before)
        version.passages = [{**row, "text": row["text"] + " Earlier."} for row in version.passages]
        session.commit()
    selected = choose(service, event_id, before, after)
    with service.db.session() as session:
        comparison = session.get(NativeDocumentComparison, selected.comparison_id)
        assert comparison.diff["old_passage_count"] == comparison.diff["new_passage_count"] == 70
    with pytest.raises(DomainError) as error:
        read(service, event_id)
    assert error.value.code == "interest_context_exceeded"
    assert not harness[3].calls


def test_selection_does_not_commit_callers_transaction(harness):
    service, event_id, _, _ = setup(harness)
    before, after = baseline(service, event_id)
    with service.db.session() as session:
        select_baseline(session, service.organization_id, event_id, before_version_id=before,
                        after_version_id=after, expected_revision=0)
        session.rollback()
    with service.db.session() as session:
        assert not list(session.scalars(select(NativeDocumentComparison)))
        assert not list(session.scalars(select(NativeEventComparisonSelection)))


@pytest.mark.parametrize("revision", [True, -1, "0", None])
def test_invalid_revision_cannot_mutate_selection(harness, revision):
    service, event_id, _, _ = setup(harness)
    before, after = baseline(service, event_id)
    with pytest.raises(DomainError) as error:
        choose(service, event_id, before, after, revision)
    assert error.value.code == "invalid_revision"
