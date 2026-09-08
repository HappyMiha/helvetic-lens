"""Exact-current saved briefs; no scheduling, tokenization or inference."""

from urllib.parse import quote

from pydantic import ValidationError
from sqlalchemy import select

from .config import DomainError
from .corpus_access import visible
from .interest_admission import current_key
from .interest_assessment import BriefDraft, BriefExecution, finalize
from .models import (
    InterestEventAssessment,
    Law,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryWork,
    Version,
)
from .topic_matching import _iso


def authorize(session, organization_id, event_id):
    event = session.scalar(select(RegulatoryEvent.id).join(RegulatoryWork,
        RegulatoryWork.id == RegulatoryEvent.work_id).join(RegulatoryEventState,
        RegulatoryEventState.event_id == RegulatoryEvent.id).where(
        RegulatoryEvent.id == event_id, RegulatoryEventState.organization_id == organization_id,
        visible(RegulatoryWork, organization_id)))
    if event is None:
        raise DomainError("This event is not available to the organization.", 404, "not_found")


def latest(session, organization_id, event_id, locale):
    authorize(session, organization_id, event_id)
    # A history existence check does not require reading result/source payloads.
    return session.execute(select(InterestEventAssessment.id, InterestEventAssessment.status,
        InterestEventAssessment.created_at, InterestEventAssessment.finished_at).where(
        InterestEventAssessment.organization_id == organization_id,
        InterestEventAssessment.event_id == event_id,
        InterestEventAssessment.input_manifest["locale"].as_string() == locale,
    ).order_by(InterestEventAssessment.created_at.desc(), InterestEventAssessment.id.desc()).limit(1)).first()


def read(session, organization_id, event_id, *, locale="en", model=None):
    if locale not in {"de", "fr", "it", "rm", "en"}:
        raise DomainError("Unsupported brief language.", 422, "invalid_locale")
    recorded = latest(session, organization_id, event_id, locale)
    response = {"event_id": event_id, "locale": locale, "status": "not_scheduled",
                "assessment_id": None, "saved_at": None, "result": None,
                "provenance": None, "error_code": None, "ai_calls": 0}
    if recorded is None:
        return response
    if model is None:
        return {**response, "status": "runtime_unverified"}
    try:
        dossier, key = current_key(session, organization_id, event_id, model=model, locale=locale)
    except DomainError as error:
        if error.status == 404:
            raise
        return {**response, "status": "not_current"}
    record = session.scalar(select(InterestEventAssessment).where(
        InterestEventAssessment.organization_id == organization_id,
        InterestEventAssessment.event_id == event_id,
        InterestEventAssessment.input_fingerprint == key))
    if record is None or record.status == "superseded":
        return {**response, "status": "stale"}
    response.update(assessment_id=record.id, saved_at=_iso(record.finished_at or record.created_at))
    if record.status in {"queued", "running", "failed"}:
        return {**response, "status": "pending" if record.status != "failed" else "failed",
                "error_code": record.error_code if record.status == "failed" else None}
    try:
        proof = BriefExecution.model_validate(record.provenance.get("execution"))
        if proof.runtime_fingerprint != dossier.model.runtime_fingerprint:
            raise ValueError("Runtime proof mismatch")
        draft = {key: record.result[key] for key in BriefDraft.model_fields}
        draft["why_in_radar"] = [{key: value for key, value in row.items()
            if key not in {"interest_kind", "legal_relationship_status"}} for row in draft["why_in_radar"]]
        verified = finalize(draft, dossier)
        if verified != record.result:
            raise ValueError("Saved result no longer matches its evidence")
        calls = record.provenance.get("provider_calls")
        if type(calls) is not int or calls not in {1, 2}:
            raise ValueError("Invalid measured call count")
    except (KeyError, TypeError, ValueError, AttributeError, ValidationError, DomainError):
        return {**response, "status": "unavailable"}
    legacy_ids = set(session.scalars(select(Version.id).join(Law, Law.id == Version.law_id).where(
        Version.id.in_({item.version_id for item in dossier.evidence}),
        visible(Version, organization_id), visible(Law, organization_id))))
    links = {item.id: f"/{'evidence' if item.version_id in legacy_ids else 'corpus-evidence'}/{quote(item.version_id, safe='')}?passage={quote(item.unit_id, safe='')}"
             for item in dossier.evidence}
    return {**response, "status": "available", "result": verified, "evidence_links": links,
            "interest_names": {item.id: item.name for item in dossier.interests},
            "provenance": {"provider_calls": calls, "execution": proof.model_dump(mode="json")}}
