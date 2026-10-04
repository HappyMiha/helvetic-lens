"""Scripted readings verify provenance/transport, never semantic accuracy."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_document_source_context import OBSERVATION, original, reading
from test_research_original_context import source

from helvetic_lens import product_document_analysis as analysis
from helvetic_lens.product_exploration import Briefing
from helvetic_lens.product_investigation_models import InvestigationBranch
from helvetic_lens.product_operations import fingerprint
from helvetic_lens.product_research_mission import schema as mission_schema
from helvetic_lens.research_model_transport import EvidenceWire
from helvetic_lens.research_reading_context import provider_notes, stamp, validated_notes


def wire_for(sources):
    return EvidenceWire({"phase": "brief", "run_id": "run", "input": {
        "original_question": "Compare the scope and period.", "sources": sources, "research_mission": {}}},
        mission_schema(Briefing), "", shared_answer=True)


def annotated_sources():
    sources = [source("s", [("page-1-text-1", "The retained observation applies to the enrolled group."),
        ("page-1-text-2", "This is additional original context on the same physical page."),
        ("page-7-text-1", "The effect is conditional on continued exposure."),
        ("page-7-text-2", "The qualification has its own original page context.")])]
    def binding(index):
        return {"source_id": "s", "sha256": sources[0]["sha256"],
            "locator": sources[0]["excerpts"][index]["passage"], "quote": sources[0]["excerpts"][index]["text"]}
    sources[0]["reading_context"] = {**stamp("Compare the scope and period.", "run"), "notes": [
        {"interpretation": "A fallible interpretation with a necessary condition.", "role": "counterevidence",
            "level": "document", "original": binding(0), "anchors": [{"kind": "condition", **binding(2)}]}]}
    return sources


@pytest.mark.parametrize("mutation", ["question", "run", "no_current_run", "sha", "quote", "anchor_sha", "foreign", "withdrawn", "legacy"])
def test_invalid_optional_interpretations_are_omitted_without_changing_originals(mutation):
    sources = annotated_sources()
    expected_question, expected_run = "Compare the scope and period.", "run"
    if mutation == "question":
        expected_question = "A different current question."
    elif mutation == "run":
        expected_run = "another-run"
    elif mutation == "no_current_run":
        expected_run = None
    elif mutation == "sha":
        sources[0]["sha256"] = "b" * 64
    elif mutation == "quote":
        sources[0]["reading_context"]["notes"][0]["original"]["quote"] = "Invented quote."
    elif mutation == "anchor_sha":
        sources[0]["reading_context"]["notes"][0]["anchors"][0]["sha256"] = "b" * 64
    elif mutation in {"foreign", "withdrawn"}:
        anchor = sources[0]["reading_context"]["notes"][0]["anchors"][0]
        anchor["source_id"] = "foreign"
        if mutation == "foreign":
            sources.append(source("foreign", [(anchor["locator"], anchor["quote"])], url="https://other.test/report"))
    else:
        sources[0]["reading_context"].pop("question")
    before = deepcopy(sources)
    assert not validated_notes(sources, expected_question, investigation_id=expected_run)
    assert sources == before


def test_complete_original_context_required_and_local_ids_rebound_without_citable_interpretation():
    sources = annotated_sources()
    wire = wire_for(sources)
    notes = provider_notes(wire, wire.references)["s"]
    assert len(notes) == 1 and "role" not in notes[0]
    assert notes[0]["original_citation_refs"] == [1]
    assert notes[0]["context_anchors"] == [{"kind": "condition", "citation_refs": [3]}]
    assert "scope" not in notes[0]  # The provider source group labels all its notes once.
    assert "interpretation" not in notes[0]
    assert all(ref["quote"] != wire.reading_context["s"][0]["interpretation"] for ref in wire.references.values())
    assert "reading_context" not in wire.input["sources"][0]
    for missing in (1, 2, 3, 4):
        assert not provider_notes(wire, {key: value for key, value in wire.references.items() if key != missing})
    local = {key + 20: value for key, value in wire.references.items()}
    rebound = provider_notes(wire, local)["s"][0]
    assert rebound["original_citation_refs"] == [21]
    assert rebound["context_anchors"][0]["citation_refs"] == [23]
    wire.reading_context = json.loads(json.dumps(wire.reading_context))
    assert provider_notes(wire, local)["s"][0] == rebound


def test_literal_copy_and_paraphrase_share_only_exact_original_pointer():
    sources = annotated_sources()
    raw = sources[0]["reading_context"]["notes"][0]
    another = deepcopy(raw)
    sources[0]["reading_context"]["notes"].append(another)
    raw["interpretation"] = raw["original"]["quote"]
    another["role"] = "support"
    wire = wire_for(sources)
    assert wire.reading_anchor_refs == [1]
    assert wire.reading_context["s"][0]["anchors"] == [{"kind": "condition", "citation_refs": [3]}]
    assert len(wire.reading_context["s"]) == 2
    assert provider_notes(wire, wire.references) == {"s": [{"level": "document", "original_citation_refs": [1],
        "context_anchors": [{"kind": "condition", "citation_refs": [3]}]}]}
    assert wire.references[1]["quote"] == raw["original"]["quote"]


def test_erroneous_reading_prose_and_support_label_never_reach_provider_input():
    from helvetic_lens.research_evidence_pack import provider_input

    sources = annotated_sources()
    # This exact erroneous interpretation occurred in native98563, reading10.
    # The assertion tests non-projection, not an automated legal truth verdict.
    poison = ("You are not required to publish the source code to the public unless you are redistributing "
        "the modified library itself as a standalone product; redistribution of the modified library "
        "requires distribution of the source code to downstream recipients.")
    quote = "You must give any other recipients of the Work or Derivative Works a copy of this License; and"
    sources[0]["excerpts"][0]["text"] = quote
    raw = sources[0]["reading_context"]["notes"][0]
    raw.update(interpretation=poison, role="support")
    raw["original"]["quote"] = quote
    wire = wire_for(sources)
    payload = provider_input(wire, wire.references)
    assert poison == wire.reading_context["s"][0]["interpretation"]
    assert wire.reading_context["s"][0]["role"] == "support"
    assert poison not in json.dumps(payload)
    assert wire.reading_anchor_refs == [1]
    assert payload["sources"][0]["reading_notes"] == [{"level": "document", "original_citation_refs": [1],
        "context_anchors": [{"kind": "condition", "citation_refs": [3]}]}]
    assert payload["sources"][0]["excerpts"][0]["text"] == quote
    assert "not proof of an assertion" in payload["sources"][0]["reading_scope"]


def test_projection_caches_only_exact_current_structural_closure(monkeypatch):
    from helvetic_lens import research_original_context as originals

    wire = wire_for(annotated_sources())
    calls, actual = [], originals.reference_units

    def counted(wire):
        calls.append(True)
        return actual(wire)

    monkeypatch.setattr(originals, "reference_units", counted)
    assert provider_notes(wire, wire.references)
    assert provider_notes(wire, {key + 20: value for key, value in wire.references.items()})
    assert len(calls) == 1
    wire.input["sources"][0]["original_context"] = {"policy": "changed"}
    provider_notes(wire, wire.references)
    assert len(calls) == 2
    wire.source_context = []
    provider_notes(wire, wire.references)
    assert len(calls) == 3
    wire.references[99] = {"source_id": "s", "locator": "page-1-text-3", "quote": "Another complete original line."}
    assert not provider_notes(wire, {key: value for key, value in wire.references.items() if key != 99})
    assert len(calls) == 4
    wire.input["sources"][0]["sha256"] = "c" * 64
    provider_notes(wire, wire.references)
    assert len(calls) == 5
    wire.input["sources"][0]["excerpts"].append({"passage": "page-1-text-0", "text": "Scope"})
    provider_notes(wire, wire.references)
    assert len(calls) == 6
    wire.input["sources"][0]["excerpts"][-1]["text"] = "Appendix"
    provider_notes(wire, wire.references)
    assert len(calls) == 7


def test_new_section_stamp_binds_question_and_original_without_projecting_summary(monkeypatch):
    run = SimpleNamespace(id="run", question="Compare the scope and period.")
    point = {"statement": "The reading records a fallible contextual interpretation.", "role": "context",
        "locator": "page-1-text-1", "quote": OBSERVATION, "context_anchors": []}
    row = original(run, [(point["locator"], point["quote"])], [point])
    work = {"input": {"question": run.question, "source": {}}}
    analysis.prepare_section(work, row)
    review = analysis.SectionReview.model_validate({key: row.snapshot["section_review"][key]
        for key in ("coverage_fingerprint", "summary", "observations", "cross_references", "limitations")})
    row.snapshot["section_review"] = analysis.validate_section(row, work, SimpleNamespace(section_review=review))
    monkeypatch.setattr(analysis, "rows", lambda *args: [])
    monkeypatch.setattr("helvetic_lens.product_investigations.rows", lambda *args: [])
    values = analysis.compact_sources(None, run, [row], retain_originals=True)
    envelope = values[0]["reading_context"]
    assert envelope["question"] == run.question and envelope["investigation_id"] == run.id
    assert envelope["notes"][0]["role"] == "context"
    assert set(envelope["notes"][0]) == {"interpretation", "role", "level", "original", "anchors"}
    assert "summary" not in envelope and "limitations" not in envelope
    assert "reading_binding" not in values[0]["section_review"]
    run.question = "Another question."
    assert "reading_context" not in analysis.compact_sources(None, run, [row])[0]
    assert row.snapshot["section_review"]["observations"] == [point]


@pytest.mark.parametrize("tree_review", [False, True])
def test_current_small_and_tree_findings_survive_compaction_with_dependency_fences(monkeypatch, tree_review):
    run, sources, session, state, work, result = reading(monkeypatch, tree_review=tree_review)
    branch = SimpleNamespace(query=run.question, checkpoint=state)
    monkeypatch.setattr(analysis, "rows", lambda session, model, run: [branch] if model is InvestigationBranch else [])
    monkeypatch.setattr("helvetic_lens.product_investigations.rows",
        lambda session, model, run: [branch] if model is InvestigationBranch else [])
    analysis.apply(session, run, state, work, result)
    if tree_review:
        analysis.prepare(session, run, state, {})
    before = deepcopy(state)
    values = analysis.compact_sources(session, run, sources, retain_originals=True)
    note = values[0]["reading_context"]["notes"][0]
    assert note["level"] == "document" and note["original"]["quote"] == OBSERVATION
    assert len(note["anchors"]) == 4
    assert state == before
    assert "reading_context" not in analysis.compact_sources(session, run, sources[:1])[0]
    sources[1].snapshot["unrelated_revision"] = True
    assert "reading_context" not in analysis.compact_sources(session, run, sources)[0]


def test_legacy_small_review_requires_exact_completed_execution_not_same_run(monkeypatch):
    run, sources, session, state, work, result = reading(monkeypatch)
    branch = SimpleNamespace(query=run.question, checkpoint=state)
    monkeypatch.setattr(analysis, "rows", lambda session, model, run: [branch] if model is InvestigationBranch else [])
    monkeypatch.setattr("helvetic_lens.product_investigations.rows",
        lambda session, model, run: [branch] if model is InvestigationBranch else [])
    analysis.apply(session, run, state, work, result)
    state["document_reads"]["0"].pop("reading_context_binding")
    assert not analysis.compact_sources(session, run, sources)[0].get("reading_context")
    state["steps"] = [{"phase": "document_review", "document_index": "0", "status": "completed",
        "execution": {"input_fingerprint": fingerprint({"input": work["input"], "query": branch.query})}}]
    before = deepcopy(state)
    assert analysis.compact_sources(session, run, sources)[0]["reading_context"]["notes"][0]["level"] == "document"
    assert state == before
    state["document_reads"]["0"]["reading_context_binding"] = stamp(run.question, "different-run")
    assert not analysis.compact_sources(session, run, sources)[0].get("reading_context")
    state["document_reads"]["0"].pop("reading_context_binding")
    run.question = "A changed full question."
    assert not analysis.compact_sources(session, run, sources)[0].get("reading_context")
