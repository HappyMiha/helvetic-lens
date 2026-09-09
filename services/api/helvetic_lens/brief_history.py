"""Offline organization history, bound to immutable context and accessible sources."""
from copy import deepcopy
from urllib.parse import quote

from pydantic import ValidationError
from sqlalchemy import or_, select

from .config import DomainError
from .corpus_access import accessible_versions, visible
from .interest_assessment import BriefDraft, BriefExecution, Dossier, finalize, fingerprint, manifest
from .interest_brief_reader import authorize
from .models import InterestEventAssessment as Assessment
from .models import Law, RegulatoryDocumentVersion, Version
from .topic_matching import _iso


def scope(organization, event_id, locale):
    return (Assessment.organization_id == organization, Assessment.event_id == event_id,
            Assessment.input_manifest["locale"].as_string() == locale)


def page(session, organization, event_id, *, locale="en", cursor="", limit=20):
    authorize(session, organization, event_id)
    if locale not in {"de", "fr", "it", "rm", "en"} or not 1 <= limit <= 50:
        raise DomainError("Choose a supported history language and page size.", 422, "invalid_brief_history_page")
    # Scalar columns only: a list never loads result, private profile facts or passages.
    query = select(Assessment.id, Assessment.status, Assessment.created_at, Assessment.finished_at,
        Assessment.attempts, Assessment.error_code,
        Assessment.input_manifest["locale"].as_string().label("locale"),
        Assessment.input_manifest["model"]["model"].as_string().label("model"),
        Assessment.input_manifest["model"]["route"].as_string().label("route"),
        Assessment.input_manifest["profile_revision"].as_integer().label("profile_revision"),
    ).where(*scope(organization, event_id, locale))
    if cursor:
        position = session.execute(select(Assessment.created_at, Assessment.id)
            .where(*scope(organization, event_id, locale), Assessment.id == cursor)).first()
        if position is None:
            raise DomainError("Reload this event's history.", 422, "invalid_brief_history_page")
        query = query.where(or_(Assessment.created_at < position.created_at,
            (Assessment.created_at == position.created_at) & (Assessment.id < position.id)))
    rows = list(session.execute(query.order_by(Assessment.created_at.desc(), Assessment.id.desc()).limit(limit + 1)).mappings())
    items = [{**row, "created_at": _iso(row["created_at"]), "finished_at": _iso(row["finished_at"])} for row in rows[:limit]]
    return {"event_id": event_id, "locale": locale, "items": items, "has_more": len(rows) > limit,
            "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None, "ai_calls": 0}


def _dossier(session, organization, record):
    data = deepcopy(record.history_context)
    if not isinstance(data, dict) or data.get("organization_id") != organization or data.get("event", {}).get("id") != record.event_id:
        raise ValueError("Historical context is absent or mismatched")
    evidence = data.get("evidence")
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 64:
        raise ValueError("Invalid historical evidence set")
    ids = {row["version_id"] for row in evidence}
    native = {row.id: row for row in session.scalars(accessible_versions(organization)
        .with_only_columns(RegulatoryDocumentVersion).where(RegulatoryDocumentVersion.id.in_(ids)))}
    legacy = {row.id: row for row in session.scalars(select(Version).join(Law, Law.id == Version.law_id)
        .where(Version.id.in_(ids), visible(Version, organization), visible(Law, organization)))}
    versions = {**native, **legacy}
    if set(versions) != ids:
        raise ValueError("Historical source access was revoked")
    units = {}
    for identity, version in versions.items():
        passages = version.passages
        if not isinstance(passages, list) or len({row["id"] for row in passages}) != len(passages):
            raise ValueError("Saved passage identities are ambiguous")
        units[identity] = {row["id"]: row["text"] for row in passages}
    for row in evidence:
        version = versions[row["version_id"]]
        if version.artifact_key != row["artifact_id"]:
            raise ValueError("Historical artifact changed")
        row["text"] = units[version.id][row["unit_id"]]
        row["source_url"] = version.source_url
    dossier = Dossier.model_validate(data)
    rebuilt = manifest(dossier)
    # The exact instructions are not duplicated into history; their immutable hash is.
    rebuilt["prompt_fingerprint"] = record.input_manifest["prompt_fingerprint"]
    if rebuilt != record.input_manifest or fingerprint(rebuilt) != record.input_fingerprint:
        raise ValueError("Historical evidence or context no longer matches the saved input")
    links = {row.id: f"/{'evidence' if row.version_id in legacy else 'corpus-evidence'}/{quote(row.version_id, safe='')}?passage={quote(row.unit_id, safe='')}" for row in dossier.evidence}
    return dossier, links


def detail(session, organization, identity):
    record = session.scalar(select(Assessment).where(Assessment.organization_id == organization, Assessment.id == identity))
    if record is None:
        raise DomainError("This saved assessment is unavailable.", 404, "not_found")
    authorize(session, organization, record.event_id)
    response = {"assessment_id": record.id, "event_id": record.event_id, "locale": record.input_manifest.get("locale"),
        "saved_at": _iso(record.finished_at or record.created_at), "status": "historical_unavailable",
        "assessment_status": record.status, "result": None, "ai_calls": 0}
    if record.status != "succeeded":
        return response
    if record.history_context is None:
        return {**response, "status": "legacy_context_missing"}
    try:
        dossier, links = _dossier(session, organization, record)
        proof = BriefExecution.model_validate(record.provenance.get("execution"))
        calls = record.provenance.get("provider_calls")
        if proof.runtime_fingerprint != dossier.model.runtime_fingerprint or type(calls) is not int or calls not in {1, 2}:
            raise ValueError("Historical execution proof mismatch")
        draft = {key: record.result[key] for key in BriefDraft.model_fields}
        draft["why_in_radar"] = [{key: value for key, value in row.items()
            if key not in {"interest_kind", "legal_relationship_status"}} for row in draft["why_in_radar"]]
        result = finalize(draft, dossier)
        if result != record.result:
            raise ValueError("Historical result failed validation")
    except (KeyError, TypeError, ValueError, AttributeError, ValidationError, DomainError):
        return response
    from .brief_reviews import current
    return {**response, "status": "historical", "result": result, "evidence_links": links,
        "interest_names": {row.id: row.name for row in dossier.interests}, "review": current(session, organization, record),
        "provenance": {"input_fingerprint": record.input_fingerprint, "profile_revision": dossier.profile_revision,
            "model": dossier.model.model_dump(mode="json"), "provider_calls": calls,
            "execution": proof.model_dump(mode="json")}}
