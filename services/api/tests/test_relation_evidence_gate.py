"""Adversarial regression cases, not independently labelled semantic acceptance."""

from copy import deepcopy

import pytest
from test_relation_analysis import relation_delivery

from helvetic_lens.config import DomainError
from helvetic_lens.models import RelationImpactAnalysis
from helvetic_lens.relation_analysis import evidence_row, finalize_result
from helvetic_lens.relation_candidates import score_candidate


@pytest.mark.parametrize(("source", "target"), [
    ("Verordnung über den Klimaschutz", "Verordnung über die Direktzahlungen"),
    ("Ordonnance fédérale sur le climat", "Ordonnance fédérale sur les paiements directs"),
    ("Ordinanza federale sul clima", "Ordinanza federale sui pagamenti diretti"),
    ("Ordinaziun federala davart il clima", "Ordinaziun federala davart ils pajaments directs"),
    ("Federal Ordinance concerning Climate", "Federal Ordinance concerning Direct Payments"),
    ("Verordnung 2026 über Landwirtschaft", "Verordnung 2026 über Telekommunikation"),
])
def test_instrument_authority_year_overlap_cannot_deliver_an_impact_lead(source, target):
    kwargs = dict(source_authority="fedlex", target_authority="fedlex",
                  source_kind="act", target_kind="act")
    assert score_candidate(source, target, **kwargs) is None
    # Exact references remain retrievable even without matching subject words.
    assert score_candidate(source, target, shared_norms=1, **kwargs) is not None


def dossier():
    rows = [
        evidence_row(source_kind="candidate_fact", label="Retrieval reason",
                     text="Shared normalized title terms: uber, verordnung", source_url=None),
        evidence_row(source_kind="regulatory_event", label="Publisher metadata",
                     text='{"type":"created"}', source_url=None, authoritative=True),
        evidence_row(source_kind="target_lifecycle", label="Lifecycle",
                     text='{"lifecycle_status":"in_force"}', source_url=None, authoritative=True),
        evidence_row(source_kind="event_source_passage", label="Proposed rule",
                     text="The proposal requires a documented review of retention periods.",
                     source_url="https://example.test/proposal", work_id="source",
                     version_id="source-v1", passage_id="s1"),
        evidence_row(source_kind="monitored_work_passage", label="Current rule",
                     text="Processing organizations must retain records for 30 days.",
                     source_url="https://example.test/act", work_id="target",
                     version_id="target-v1", passage_id="t1"),
        evidence_row(source_kind="official_relation", label="Official amendment",
                     text="The publisher explicitly names the amended act.",
                     source_url="https://example.test/relation", authoritative=True,
                     metadata={"relation_id": "official-1"}),
    ]
    return [{**row, "row_number": index} for index, row in enumerate(rows, 1)]


def draft():
    return {
        "supported": True, "proposed_relation_type": "potentially_impacts",
        "potential_severity": "high", "evidence_grade": "supported",
        "explanation": "The proposal introduces a documented retention review, while the saved act sets a 30-day retention period. Its applicability needs organizational review.",
        "business_areas": ["Operations"], "citation_rows": [4, 5],
        "actions": [{
            "title": "Review the proposed retention procedure", "rationale": "Compare the review requirement with the saved retention rule.",
            "owner_role": "Legal operations", "affected_area": "Record retention",
            "priority": "medium", "due_basis": "No source deadline established.", "due_date": None,
            "applicability_condition": "If the organization processes the affected records.",
            "evidence_grade": "possible", "citation_rows": [4, 5],
        }],
    }


def finish(value, rows=None, official=None, locale="en-CH"):
    return finalize_result(value, rows or dossier(), analysis_id="analysis-1",
                           official_relation=official, coverage={"limited": False},
                           source_work={"id": "source", "title": "New proposal"},
                           target_work={"id": "target", "title": "Monitored act"},
                           candidate={"why": ["ORIGINAL RETRIEVAL REASON"]}, output_locale=locale)


@pytest.mark.parametrize("citations", [[1], [2], [3], [1, 2, 3], [4], [5], [6]])
def test_valid_ids_are_not_sufficient_for_positive_impact(citations):
    value = draft()
    value["citation_rows"] = citations
    report = finish(value)
    assert not report["supported"]
    assert report["potential_severity"] == "none"
    assert report["assessment_status"] == "needs_review"
    assert report["evidence_grade"] == "needs_review"
    assert report["proposed_relation_type"] is None
    assert report["actions"] == []
    assert "missing_substantive_bridge" in report["validation_issues"]


def test_action_evidence_is_checked_per_action_not_borrowed_from_conclusion():
    value = draft()
    invalid_action = deepcopy(value["actions"][0])
    invalid_action.update(title="Unsubstantiated additional action", citation_rows=[1])
    value["actions"].insert(0, invalid_action)
    report = finish(value)
    assert report["supported"]
    assert [action["title"] for action in report["actions"]] == [value["actions"][1]["title"]]
    assert report["validation_issues"] == ["action_missing_substantive_bridge"]


def test_wrong_work_or_missing_passage_identity_cannot_supply_the_second_side():
    for field, replacement in [("work_id", "unrelated-work"), ("passage_id", None), ("version_id", None)]:
        rows = dossier()
        rows[4][field] = replacement
        assert not finish(draft(), rows)["supported"]


def test_mixed_valid_and_invalid_citations_are_rejected_not_silently_trimmed():
    value = draft()
    value["citation_rows"].append(999)
    with pytest.raises(DomainError) as exc:
        finish(value)
    assert exc.value.code == "invalid_citation"


@pytest.mark.parametrize("locale", ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"])
def test_generic_high_fallback_is_unassessed_and_keeps_actual_candidate_reason(locale):
    value = draft()
    value["explanation"] = "The evidence is clear and authoritative."
    report = finish(value, locale=locale)
    assert not report["supported"] and report["actions"] == []
    assert report["potential_severity"] == "none"
    assert report["assessment_status"] == "needs_review"
    assert "ORIGINAL RETRIEVAL REASON" in report["explanation"]
    assert "unusable_explanation" in report["validation_issues"]


def test_only_matching_confirmed_official_relation_can_be_used_without_passage_pair():
    value = draft()
    value["citation_rows"] = value["actions"][0]["citation_rows"] = [6]
    official = {"id": "official-1", "state": "confirmed", "type": "amends"}
    report = finish(value, official=official)
    assert report["supported"] and report["actions"]
    assert report["official_relation"] == official
    assert not finish(value, official={**official, "id": "unrelated-relation"})["supported"]
    assert not finish(value, official={**official, "state": "proposed"})["supported"]
    value["explanation"] = "The evidence grade is high because it is not supported by any evidence."
    report = finish(value, official=official)
    assert not report["supported"]
    assert report["official_relation"] == official


def test_legacy_high_result_is_history_only_and_reanalysis_reuses_delivery(harness, monkeypatch):
    client, _, service, model = harness
    delivery_id, _ = relation_delivery(harness)
    service.settings.apertus_base_url = "https://model.example/v1"
    from helvetic_lens import relation_analysis
    with monkeypatch.context() as old_rules:
        old_rules.setattr(relation_analysis, "SCHEMA_VERSION", "relation-impact-v2")
        first = client.post(f"/api/relation-candidates/{delivery_id}/analyse-jobs").json()
    original_id = first["result"]["data"]["id"]
    with service.db.session() as session:
        record = session.get(RelationImpactAnalysis, original_id)
        legacy_result = {**record.result, "schema_version": "relation-impact-v2", "potential_severity": "high"}
        record.result = legacy_result
        session.commit()
    history = client.get(f"/api/relation-candidates/{delivery_id}/analyses").json()
    assert history["current"] is None
    assert history["items"][0]["stale"] is True
    assert history["items"][0]["result"] == legacy_result
    inbox = client.get("/api/impact-inbox").json()
    item = inbox["items"][0]["items"][0]
    assert item["status"] == "stale" and item["severity"] == "unknown"
    assert item["current_analysis_id"] is None
    second = client.post(f"/api/relation-candidates/{delivery_id}/analyse-jobs").json()
    assert second["state"] == "succeeded"
    assert second["result"]["data"]["id"] != original_id
    history = client.get(f"/api/relation-candidates/{delivery_id}/analyses").json()
    assert history["total"] == 2 and history["current"]["stale"] is False
    assert next(row for row in history["items"] if row["id"] == original_id)["result"] == legacy_result
    assert len(model.calls) == 2
    inbox = client.get("/api/impact-inbox").json()
    assert inbox["total_events"] == inbox["total_impacts"] == 1


def test_official_urgency_survives_unassessed_ai(harness):
    client, _, service, model = harness
    delivery_id, _ = relation_delivery(harness, confirmed=True)
    service.settings.apertus_base_url = "https://model.example/v1"
    model.relation_compact = True
    from helvetic_lens.models import OrganizationRelationCandidate, RegulatoryEvent, RelationCandidate
    with service.db.session() as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        candidate = session.get(RelationCandidate, delivery.candidate_id)
        session.get(RegulatoryEvent, candidate.event_id).impact = "high"
        session.commit()
    job = client.post(f"/api/relation-candidates/{delivery_id}/analyse-jobs").json()
    assert not job["result"]["data"]["result"]["supported"]
    item = client.get("/api/impact-inbox").json()["items"][0]["items"][0]
    assert item["status"] == "confirmed_relation"
    assert item["severity"] == "high" and item["official_relation"]
