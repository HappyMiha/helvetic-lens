"""Brief provenance, complete-interest coverage and the fixed inference budget."""

import asyncio
import copy
import json

import pytest
from pydantic import ValidationError

from helvetic_lens.config import DomainError
from helvetic_lens.interest_assessment import Dossier, finalize, fingerprint, generate, manifest


def dossier(*, organization_id="org-a", event_id="event-a", count=2, locale="en", kind="proposal"):
    return Dossier.model_validate({
        "organization_id": organization_id,
        "event": {"id": event_id, "title": "Retention consultation", "kind": kind,
                  "official_status": "consultation", "status_evidence_ids": ["source"],
                  "official_dates": [{"kind": "published", "value": "2026-09-01", "evidence_ids": ["source"]}]},
        "profile_revision": 1,
        "profile_facts": [{"id": "profile-description", "field": "description", "text": "We run a retail bakery."},
                          {"id": "area-operations", "field": "business_area", "text": "Operations"}],
        "interests": [{"id": f"match-{i}", "kind": "topic", "revision": f"topic-revision-{i}",
                       "fingerprint": str(i % 10) * 64, "name": f"Retention topic {i}",
                       "reason_signals": ["retention"], "evidence_ids": ["source"]} for i in range(count)],
        "evidence": [{"id": "source", "version_id": "source-v1", "artifact_id": "artifact-1",
                      "unit_id": "article-2", "source_url": "https://example.test/original.pdf#page=2",
                      "source_kind": "event", "primary_source": True,
                      "text": "Consultation proposes record retention for banks; no effective date has been adopted."},
                     {"id": "target", "version_id": "target-v1", "artifact_id": "artifact-2",
                      "unit_id": "article-8", "source_url": "https://example.test/law.html#art8",
                      "source_kind": "monitored_law", "primary_source": True,
                      "text": "The existing banking rule governs record retention."}],
        "model": {"route": "local", "provider": "docker", "model": "local-apertus",
                  "runtime_fingerprint": "a" * 64, "configuration_fingerprint": "b" * 64},
        "locale": locale,
    })


def draft_for(value):
    claim = {"text": "A banking retention consultation was published; it does not change the rule yet.",
             "evidence_ids": ["source"]}
    return {"what_happened": copy.deepcopy(claim),
            "why_in_radar": [{**copy.deepcopy(claim), "interest_id": row.id} for row in value.interests],
            "importance": {"text": "Low priority for a retail bakery; the proposal concerns banking records.",
                           "evidence_ids": ["source"], "level": "low", "profile_fact_ids": ["profile-description"]},
            "affected_area_ids": [],
            "next_step": {"text": "No action now: the organization is not a bank and this is only a consultation.",
                          "evidence_ids": ["source"], "kind": "no_action_now", "interest_id": None},
            "uncertainty": "The consultation may change; this is not a legal assessment."}


class Model:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, system, user, **kwargs):
        kwargs["budget"].claim()
        self.calls.append((system, json.loads(user), kwargs["response_schema"]))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result if isinstance(result, str) else json.dumps(result)


def run(model, value, **kwargs):
    return asyncio.run(generate(model, value, context_char_limit=40000, **kwargs))


@pytest.mark.parametrize("locale", ["de", "fr", "it", "rm", "en"])
@pytest.mark.parametrize("kind", ["law_changed", "proposal", "court_decision", "official_news"])
def test_one_brief_covers_all_interests_preserves_official_facts_and_low_importance(locale, kind):
    value = dossier(locale=locale, kind=kind, count=7)  # More than the feed's first five cards.
    model = Model(draft_for(value))
    result, provenance = run(model, value)
    assert len(model.calls) == provenance["provider_calls"] == 1
    assert len(model.calls[0][1]["interests"]) == len(result["why_in_radar"]) == 7
    assert f"in {locale}." in model.calls[0][0]
    assert result["official_status"] == "consultation"
    assert result["official_dates"] == [{"kind": "published", "value": "2026-09-01", "evidence_ids": ["source"]}]
    assert result["importance"]["level"] == "low"
    assert result["next_step"]["kind"] == "no_action_now"
    assert result["citations"][0]["artifact_id"] == "artifact-1"
    assert result["citations"][0]["source_url"].endswith("#page=2")
    assert "text" not in result["citations"][0]
    assert all(row["legal_relationship_status"] == "not_assessed" for row in result["why_in_radar"])
    assert "organization_id" not in model.calls[0][1] and "model" not in model.calls[0][1]


@pytest.mark.parametrize("problem", ["json", "missing_interest", "duplicate_interest", "extra_interest",
                                     "unknown_citation", "wrong_interest_citation", "wrong_event_source",
                                     "unknown_profile", "unknown_area", "invented_date", "invented_status",
                                     "review_without_interest", "review_wrong_citation", "blank_text"])
def test_one_repair_covers_schema_and_semantic_reference_errors(problem):
    value = dossier()
    broken = draft_for(value)
    if problem == "json":
        broken = "{broken"
    elif problem == "missing_interest":
        broken["why_in_radar"].pop()
    elif problem == "duplicate_interest":
        broken["why_in_radar"][1]["interest_id"] = "match-0"
    elif problem == "extra_interest":
        broken["why_in_radar"][1]["interest_id"] = "somebody-elses-topic"
    elif problem == "unknown_citation":
        broken["what_happened"]["evidence_ids"] = ["source", "invented"]
    elif problem == "wrong_interest_citation":
        broken["why_in_radar"][0]["evidence_ids"] = ["target"]
    elif problem == "wrong_event_source":
        broken["what_happened"]["evidence_ids"] = ["target"]
    elif problem == "unknown_profile":
        broken["importance"]["profile_fact_ids"] = ["invented-bank-profile"]
    elif problem == "unknown_area":
        broken["affected_area_ids"] = ["Invented compliance team"]
    elif problem == "invented_date":
        broken["official_dates"] = [{"effective": "2027-01-01"}]
    elif problem == "invented_status":
        broken["official_status"] = "in_force"
    elif problem == "review_without_interest":
        broken["next_step"]["kind"] = "review"
    elif problem == "review_wrong_citation":
        broken["next_step"].update(kind="review", interest_id="match-0", evidence_ids=["target"])
    elif problem == "blank_text":
        broken["what_happened"]["text"] = "   "
    model = Model(broken, draft_for(value))
    result, provenance = run(model, value)
    assert provenance["provider_calls"] == len(model.calls) == 2
    assert "repair" in model.calls[1][1]
    assert result["importance"]["level"] == "low"


def test_second_invalid_answer_is_rejected_without_third_call_or_unverified_result():
    value = dossier()
    bad = draft_for(value)
    bad["what_happened"]["evidence_ids"] = ["source", "not-supplied"]
    model = Model(bad, bad, draft_for(value))
    with pytest.raises(DomainError, match="primary evidence") as error:
        run(model, value)
    assert error.value.code == "invalid_citation" and len(model.calls) == 2


def test_empty_profile_is_explicitly_undetermined_not_invented_relevance():
    value = dossier().model_copy(update={"profile_facts": []})
    good = draft_for(value)
    good["importance"].update(level="undetermined", profile_fact_ids=[], text="Add an organization description to assess importance.")
    model = Model(draft_for(value), good)
    result, _ = run(model, value)
    assert result["importance"]["level"] == "undetermined" and len(model.calls) == 2


def test_context_overflow_never_calls_model_or_samples_interests():
    value = dossier(count=64)
    model = Model(draft_for(value))
    with pytest.raises(DomainError) as error:
        asyncio.run(generate(model, value, context_char_limit=1000))
    assert error.value.code == "interest_context_exceeded" and model.calls == []


def test_cloud_is_opt_in_and_transport_timeout_is_not_a_json_repair():
    value = dossier()
    cloud = value.model_copy(update={"model": value.model.model_copy(update={"route": "cloud"})})
    model = Model(draft_for(value))
    with pytest.raises(DomainError) as error:
        run(model, cloud)
    assert error.value.code == "cloud_not_approved" and model.calls == []
    approved = cloud.model_copy(update={"model": cloud.model.model_copy(update={"cloud_fallback_approved": True})})
    assert run(model, approved)[0]["importance"]["level"] == "low"
    timed_out = Model(DomainError("Timed out", 504, "model_timeout"))
    with pytest.raises(DomainError) as error:
        run(timed_out, value)
    assert error.value.code == "model_timeout" and len(timed_out.calls) == 1


def test_no_personal_history_or_credentials_in_internal_contract():
    for extra in ("user_id", "private_history", "api_key", "subscription"):
        with pytest.raises(ValidationError):
            Dossier.model_validate({**dossier().model_dump(), extra: "private"})


def test_manifest_is_order_independent_but_changes_for_every_material_binding():
    value = dossier()
    before = manifest(value)
    reordered = value.model_copy(update={"interests": list(reversed(value.interests)),
                                         "evidence": list(reversed(value.evidence)),
                                         "profile_facts": list(reversed(value.profile_facts))})
    assert manifest(reordered) == before
    variants = [value.model_copy(update={"profile_revision": 2}),
                value.model_copy(update={"locale": "rm"}),
                value.model_copy(update={"organization_id": "other"}),
                value.model_copy(update={"interests": value.interests[:1]}),
                value.model_copy(update={"event": value.event.model_copy(update={"official_status": "adopted"})}),
                value.model_copy(update={"model": value.model.model_copy(update={"runtime_fingerprint": "c" * 64})}),
                value.model_copy(update={"profile_facts": [value.profile_facts[0].model_copy(update={"text": "We run a bank."})]}),
                value.model_copy(update={"evidence": [value.evidence[0].model_copy(update={"text": "Corrected source."}), value.evidence[1]]})]
    assert all(fingerprint(manifest(item)) != fingerprint(before) for item in variants)
    assert manifest(value, "Changed prompt") != before
    serialized = json.dumps(before)
    assert value.evidence[0].text not in serialized and value.profile_facts[0].text not in serialized


def test_input_evidence_integrity_is_checked_before_generation():
    base = dossier().model_dump()
    for change in ("duplicate_id", "non_primary", "missing_ref", "status_without_evidence"):
        data = copy.deepcopy(base)
        if change == "duplicate_id":
            data["interests"][1]["id"] = data["interests"][0]["id"]
        elif change == "non_primary":
            data["evidence"][0]["primary_source"] = False
        elif change == "missing_ref":
            data["interests"][0]["evidence_ids"] = ["missing"]
        else:
            data["event"]["status_evidence_ids"] = []
        with pytest.raises(ValidationError):
            Dossier.model_validate(data)


def test_review_step_is_bound_to_exact_interest_and_does_not_create_obligations():
    value = dossier()
    draft = draft_for(value)
    draft["next_step"].update(kind="review", interest_id="match-1",
                             text="Review the consultation's banking scope before expanding this topic.")
    result = finalize(draft, value)
    assert result["next_step"]["interest_id"] == "match-1"
    assert "due_date" not in result["next_step"]


def test_hung_provider_is_cancelled_at_deadline():
    cancelled = []
    class HungModel:
        async def complete(self, *args, **kwargs):
            kwargs["budget"].claim()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)
    with pytest.raises(DomainError) as error:
        run(HungModel(), dossier(), max_seconds=0.01)
    assert error.value.code == "model_timeout" and cancelled == [True]


def test_external_cancellation_is_not_converted_into_repair_or_success():
    async def exercise():
        started = asyncio.Event()
        class Cancellable:
            async def complete(self, *args, **kwargs):
                kwargs["budget"].claim()
                started.set()
                await asyncio.Event().wait()
        task = asyncio.create_task(generate(Cancellable(), dossier(), context_char_limit=40000))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(exercise())


def test_caller_mutation_during_request_cannot_replace_saved_evidence():
    value = dossier()
    original = draft_for(value)
    class MutatingModel(Model):
        async def complete(self, *args, **kwargs):
            value.evidence.clear()
            value.interests.clear()
            return await super().complete(*args, **kwargs)
    result, _ = run(MutatingModel(original), value)
    assert len(result["why_in_radar"]) == 2 and result["citations"][0]["id"] == "source"
