"""Full saved-diff planning and current DB admission, not model/legal quality."""

import asyncio
import copy
import json
from types import SimpleNamespace

import pytest
from conftest import add_law, import_old
from pydantic import ValidationError
from sqlalchemy import select
from test_interest_admission import draft_for, model_identity
from test_interest_assessment import Model, run
from test_interest_execution import artifacts as artifacts_fixture
from test_interest_execution import execution as execution_fixture

from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.diffing import compare_passages
from helvetic_lens.interest_admission import assemble, current_key
from helvetic_lens.interest_assessment import Dossier
from helvetic_lens.interest_assessment_store import AssessmentStore
from helvetic_lens.interest_material import plan
from helvetic_lens.models import (
    Comparison,
    DocumentWatch,
    Law,
    LegacyDocumentMapping,
    Organization,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryEventState,
    Version,
)

artifacts = artifacts_fixture
execution = execution_fixture


def passages(texts, prefix):
    return [{"id": f"{prefix}{i}", "text": text, "position": i + 1} for i, text in enumerate(texts)]


def inputs(old, new):
    before = SimpleNamespace(id="before", passages=passages(old, "o"), artifact_key="a" * 64 + ".pdf",
                             source_url="https://example.test/old.pdf")
    after = SimpleNamespace(id="after", passages=passages(new, "n"), artifact_key="b" * 64 + ".pdf",
                            source_url="https://example.test/new.pdf")
    comparison = SimpleNamespace(id="comparison", old_version_id=before.id, new_version_id=after.id,
                                 diff=compare_passages(before.passages, after.passages))
    return comparison, before, after


def test_inserted_article_renumbering_and_wraps_do_not_become_repeated_duties():
    values = inputs(["Art. 1 Purpose", "Art. 2 Scope", "Art. 3 Procedure", "Personengesell-\nschaft"],
                    ["Art. 1 Purpose", "Art. 2 New reporting duty", "Art. 3 Scope", "Art. 4 Procedure", "Personengesellschaft"])
    evidence, context = plan(*values)
    assert len(context.changes) == 1 and context.changes[0].classification == "added"
    assert context.presentation_only_count == 3
    assert [row.text for row in evidence] == ["Art. 2 New reporting duty"]
    assert evidence[0].side == "after" and evidence[0].role == "material_change"
    assert context.old_passage_count == 4 and context.new_passage_count == 5


def test_long_documents_send_all_changes_without_unchanged_bulk():
    old = [f"Unique unchanged provision {i} remains in force." for i in range(400)]
    new = old.copy()
    new[213] = "Unique unchanged provision 213 now requires 14 days notice."
    evidence, context = plan(*inputs(old, new))
    assert len(context.changes) == 1 and len(evidence) == 2
    assert context.old_passage_count == context.new_passage_count == 400
    assert evidence[0].text == old[213] and evidence[1].text == new[213]
    assert {row.side for row in evidence} == {"before", "after"}


@pytest.mark.parametrize("old,new", [
    (["Retention period is 10 days."], ["Retention period is 30 days."]),
    (["Article deleted entirely", "Art. 2 Scope"], ["Art. 2 Scope"]),
    (["Art. 2 Scope"], ["Art. 2 Scope", "New records requirement"]),
])
def test_changed_evidence_is_complete_on_both_present_sides(old, new):
    values = inputs(old, new)
    evidence, context = plan(*values)
    expected = {(side, row[side]["text"]) for row in values[0].diff["items"] if row["material"]
                for side in ("old", "new") if row[side]}
    assert {("old" if row.side == "before" else "new", row.text) for row in evidence if row.role == "material_change"} == expected
    assert len(context.changes) == values[0].diff["material_count"]


def test_no_material_changes_has_explicit_context_anchor_not_fabricated_changes():
    evidence, context = plan(*inputs(["Art. 1 Same wording"], ["Art. 2 Same wording"]))
    assert context.changes == [] and context.presentation_only_count == 1
    assert len(evidence) == 1 and evidence[0].role == "context"


@pytest.mark.parametrize("change", ["partial", "schema", "count", "text", "position", "duplicate", "flag", "pair"])
def test_corrupt_or_stale_persisted_comparison_is_not_used(change):
    comparison, before, after = inputs(["A duty", "Another duty"], ["A duty", "Another revised duty"])
    if change == "partial":
        comparison.diff["items"].pop(0)
    elif change == "schema":
        comparison.diff["schema_version"] = 1
    elif change == "count":
        comparison.diff["counts"]["modified"] += 1
    elif change == "text":
        after.passages = copy.deepcopy(after.passages)
        after.passages[0]["text"] = "Corrected after saving diff"
    elif change == "position":
        comparison.diff["items"][0]["new_position"] = True
    elif change == "duplicate":
        comparison.diff["items"].append(copy.deepcopy(comparison.diff["items"][0]))
    elif change == "flag":
        comparison.diff["items"][-1]["material"] = False
    else:
        comparison.old_version_id = "different-baseline"
    with pytest.raises(DomainError) as error:
        plan(comparison, before, after)
    assert error.value.code == "interest_comparison_unavailable"


def test_too_many_changes_are_not_sampled():
    with pytest.raises(DomainError) as error:
        plan(*inputs([f"Legacy alpha requirement {i}" for i in range(80)],
                     [f"Modern omega provision {i}" for i in range(80)]))
    assert error.value.code == "interest_context_exceeded"


def setup_saved(harness, count=100):
    client, _, service, _ = harness
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    with service.db.session() as session:
        before, after = session.get(Version, old["id"]), session.get(Version, law["current_version_id"])
        before.source_url = after.source_url  # Synthetic publisher baseline URL, not a production attachment.
        before.passages = passages([f"Unique unchanged provision {i} remains in force." for i in range(count)], "o")
        after.passages = passages([f"Unique unchanged provision {i} remains in force." for i in range(count)], "n")
        after.passages[count // 2]["text"] = f"Unique unchanged provision {count // 2} requires 14 days notice."
        before.text, after.text = ("\n\n".join(p["text"] for p in row.passages) for row in (before, after))
        comparison = service.ensure_comparison(session, before, after, "saved_versions")
        mapping = session.scalar(select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == law["id"]))
        native = session.scalar(select(RegulatoryDocumentVersion).where(RegulatoryDocumentVersion.legacy_version_id == after.id))
        event = RegulatoryEvent(work_id=mapping.work_id, expression_id=native.expression_id,
            document_version_id=native.id, authority="synthetic", event_type="amended", dedupe_key="material-event",
            detected_at=utcnow(), source_url=after.source_url, provenance_method="text_diff", evidence_json={})
        session.add(event)
        session.flush()
        session.add(RegulatoryEventState(event_id=event.id))
        session.commit()
        return service, event.id, comparison.id, before.id, after.id


def test_saved_comparison_reaches_current_admission_generation_and_fenced_storage(harness):
    service, event_id, comparison_id, _, _ = setup_saved(harness, count=400)
    store = AssessmentStore(service.organization_id)
    with service.db.session() as session:
        record, _, value = store.prepare_current(session, event_id, model=model_identity(), context_char_limit=40000)
        token = store.claim(session, record.id, record.input_fingerprint)
        session.commit()
    assert len(value.evidence) == 2 and len(value.source_comparison.changes) == 1
    assert value.source_comparison.id == comparison_id and value.source_comparison.old_passage_count == 400
    model = Model(draft_for(value))
    result, usage = run(model, value)
    assert len(model.calls) == 1 and result["source_comparison"]["id"] == comparison_id
    assert model.calls[0][1]["source_comparison"]["complete"]
    assert "not a before/after" not in " ".join(result["input_limitations"])
    with service.db.session() as session:
        assert store.finish_current(session, record.id, token, value, result, model=model_identity(), provider_calls=usage["provider_calls"])
        session.commit()
        assert store.get(session, record.id).result == result


def test_unchanged_source_correction_invalidates_material_dossier(harness):
    service, event_id, _, _, after_id = setup_saved(harness)
    with service.db.session() as session:
        value, first = current_key(session, service.organization_id, event_id, model=model_identity())
        after = session.get(Version, after_id)
        after.passages = copy.deepcopy(after.passages)
        after.passages[0]["text"] = "Correction outside the previously selected material evidence."
        session.commit()
    with service.db.session() as session, pytest.raises(DomainError) as error:
        current_key(session, service.organization_id, event_id, model=model_identity())
    assert error.value.code == "interest_comparison_unavailable"


def test_conflicting_baselines_require_selection_not_import_time_guess(harness):
    service, event_id, comparison_id, before_id, after_id = setup_saved(harness, count=3)
    with service.db.session() as session:
        before = session.get(Version, before_id)
        second = Version(**{column.name: getattr(before, column.name) for column in Version.__table__.columns
                            if column.name not in {"id", "content_hash", "created_at"}}, content_hash="f" * 64)
        session.add(second)
        session.flush()
        service.regulatory_corpus.map_legacy_document(session, session.get(Law, before.law_id), second)
        service.ensure_comparison(session, second, session.get(Version, after_id), "saved_versions")
        session.commit()
    with service.db.session() as session, pytest.raises(DomainError) as error:
        assemble(session, service.organization_id, event_id, model=model_identity())
    assert error.value.code == "interest_comparison_ambiguous"
    with service.db.session() as session:
        watch = session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == before.law_id))
        watch.selected_baseline_version_id = before_id
        session.commit()
    with service.db.session() as session:
        value = assemble(session, service.organization_id, event_id, model=model_identity())
        assert value.source_comparison.id == comparison_id


def test_hierarchy_context_is_exact_and_excludes_sibling_articles():
    old = ["Chapter 1 Reports", "Art. 1 Timing", "Reports are due in 10 days.",
           "Art. 2 Recipients", "Public authority receives the report."]
    new = old.copy()
    new[2] = "Reports are due in 30 days."
    evidence, context = plan(*inputs(old, new))
    refs = context.changes[0].context_ids
    assert len(refs) == 4
    assert {row.text for row in evidence if row.id in refs} == {"Chapter 1 Reports", "Art. 1 Timing"}
    assert all("Recipients" not in row.text for row in evidence)


@pytest.mark.parametrize("change", ["version", "side", "missing", "context", "coverage", "counts", "omitted_change"])
def test_dossier_refuses_cross_side_or_missing_material_references(harness, change):
    service, event_id, _, _, _ = setup_saved(harness, count=3)
    with service.db.session() as session:
        value = assemble(session, service.organization_id, event_id, model=model_identity()).model_dump(mode="json")
    if change == "version":
        value["source_comparison"]["before_version_id"] = "another-version"
    elif change == "side":
        value["evidence"][0]["side"] = "current"
    elif change == "missing":
        value["source_comparison"]["changes"][0]["before_ids"] = ["not-supplied"]
    elif change == "context":
        value["source_comparison"]["changes"][0]["context_ids"] = ["not-supplied"]
    elif change == "coverage":
        value["source_comparison"]["old_passage_count"] += 1
    elif change == "counts":
        value["source_comparison"]["counts"]["added"] = False
    else:
        value["source_comparison"]["changes"] = []
    with pytest.raises(ValidationError):
        Dossier.model_validate(value)


@pytest.mark.parametrize("change", ["owner", "language", "malformed", "identity", "duplicate_ids"])
def test_invalid_baseline_never_enters_comparison_dossier(harness, change):
    service, event_id, _, before_id, _ = setup_saved(harness, count=3)
    with service.db.session(include_all_organizations=True) as session:
        before = session.get(Version, before_id)
        if change == "owner":
            other = Organization(name="Foreign baseline owner", slug="material-foreign")
            session.add(other)
            session.flush()
            before.owner_organization_id = other.id
        elif change == "language":
            after = session.scalar(select(Version).where(Version.id != before.id))
            before.identity_json = {**before.identity_json, "language": "de"}
            after.identity_json = {**after.identity_json, "language": "fr"}
        elif change == "malformed":
            before.passages = [{"text": "no id"}]
        elif change == "identity":
            before.identity_json = {**before.identity_json, "title": "An entirely unrelated law on railway construction"}
        else:
            before.passages = [before.passages[0], before.passages[0]]
        session.commit()
    with service.db.session() as session, pytest.raises(DomainError):
        assemble(session, service.organization_id, event_id, model=model_identity())


def test_stale_comparison_during_generation_supersedes_without_publishing(harness):
    service, event_id, comparison_id, _, _ = setup_saved(harness)
    store = AssessmentStore(service.organization_id)
    with service.db.session() as session:
        record, _, value = store.prepare_current(session, event_id, model=model_identity(), context_char_limit=40000)
        token = store.claim(session, record.id, record.input_fingerprint)
        session.commit()
    result, usage = run(Model(draft_for(value)), value)
    with service.db.session() as session:
        comparison = session.get(Comparison, comparison_id)
        changed = copy.deepcopy(comparison.diff)
        changed["items"].pop(0)
        comparison.diff = changed
        session.commit()
    with service.db.session() as session:
        assert not store.finish_current(session, record.id, token, value, result, model=model_identity(), provider_calls=usage["provider_calls"])
        session.commit()
        assert store.get(session, record.id).status == "superseded"
        assert store.get(session, record.id).result is None


def test_material_plan_is_measured_and_generated_once_by_real_local_gateway(execution, harness):
    _, event_id, comparison_id, _, _ = setup_saved(harness, count=400)
    result = asyncio.run(execution[1].run(event_id))
    assert result["status"] == "succeeded"
    assert result["result"]["source_comparison"]["id"] == comparison_id
    assert result["provenance"]["provider_calls"] == 1
    wire = execution[4]["generated"]
    assert len(wire) == 1 and wire[0] == execution[4]["counts"][0]
    data = json.loads(wire[0]["messages"][-1]["content"])
    assert len(data["evidence"]) == 2 and data["source_comparison"]["old_passage_count"] == 400
    assert len(data["source_comparison"]["changes"]) == 1
    assert {row["side"] for row in data["evidence"]} == {"before", "after"}


def test_old_comparison_mode_does_not_hide_complete_saved_pair(harness):
    service, event_id, comparison_id, before_id, after_id = setup_saved(harness)
    with service.db.session() as session:
        current = session.get(Comparison, comparison_id)
        session.add(Comparison(id="00000000-0000-0000-0000-000000000000", law_id=current.law_id,
            owner_organization_id=current.owner_organization_id, old_version_id=before_id, new_version_id=after_id,
            mode="historical", diff={"schema_version": 1, "complete": False}, identity_json={}))
        session.commit()
    with service.db.session() as session:
        value = assemble(session, service.organization_id, event_id, model=model_identity())
        assert value.source_comparison.id == comparison_id
