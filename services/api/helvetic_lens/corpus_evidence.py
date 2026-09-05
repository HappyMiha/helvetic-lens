"""Read saved native-connector evidence without creating a legacy law or model job."""
import re
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import load_only

from .config import DomainError
from .inbox_context import visible
from .models import (
    DocumentWatch,
    Law,
    LegacyDocumentMapping,
    OrganizationRelationCandidate,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryExpression,
    RegulatoryWork,
    RelationCandidate,
    Version,
)
from .topic_matching import _iso


def authorized_version(session, organization_id, version_id, *, body=True):
    admitted = (select(RegulatoryEventState.id)
        .join(RegulatoryEvent, RegulatoryEvent.id == RegulatoryEventState.event_id)
        .where(RegulatoryEventState.organization_id == organization_id,
               RegulatoryEvent.document_version_id == RegulatoryDocumentVersion.id,
               RegulatoryEvent.work_id == RegulatoryWork.id).exists())
    delivered = (select(OrganizationRelationCandidate.id)
        .join(RelationCandidate, RelationCandidate.id == OrganizationRelationCandidate.candidate_id)
        .join(RegulatoryEvent, RegulatoryEvent.id == RelationCandidate.event_id)
        .where(OrganizationRelationCandidate.organization_id == organization_id,
               RegulatoryEvent.document_version_id == RegulatoryDocumentVersion.id,
               RegulatoryEvent.work_id == RegulatoryWork.id).exists())
    watched = (select(DocumentWatch.id)
        .join(Law, Law.id == DocumentWatch.law_id)
        .join(LegacyDocumentMapping, LegacyDocumentMapping.law_id == Law.id)
        .where(DocumentWatch.organization_id == organization_id,
               LegacyDocumentMapping.work_id == RegulatoryWork.id,
               visible(Law, organization_id), visible(LegacyDocumentMapping, organization_id)).exists())
    query = (select(RegulatoryDocumentVersion, RegulatoryExpression.language, RegulatoryWork.title)
        .join(RegulatoryExpression, RegulatoryExpression.id == RegulatoryDocumentVersion.expression_id)
        .join(RegulatoryWork, RegulatoryWork.id == RegulatoryExpression.work_id)
        .where(RegulatoryDocumentVersion.id == version_id, visible(RegulatoryWork, organization_id),
               or_(admitted, delivered, watched)))
    if not body:
        query = query.options(load_only(RegulatoryDocumentVersion.id, RegulatoryDocumentVersion.legacy_version_id,
                                         RegulatoryDocumentVersion.artifact_key, RegulatoryDocumentVersion.content_type,
                                         RegulatoryDocumentVersion.filename, raiseload=True))
    row = session.execute(query).first()
    if row is None:
        raise DomainError("The saved source evidence is unavailable in this organization.", 404, "not_found")
    version, language, title = row
    if version.legacy_version_id:
        linked = session.scalar(select(Version.id).join(Law, Law.id == Version.law_id)
            .where(Version.id == version.legacy_version_id, visible(Version, organization_id), visible(Law, organization_id)))
        if not linked:
            raise DomainError("The saved source evidence is unavailable in this organization.", 404, "not_found")
    return version, language, title


def artifact_path(settings, key):
    if not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{64}(?:\.[a-z0-9]{1,12})?", key):
        return None
    folder = (settings.storage_path / "artifacts").resolve()
    path = (folder / key).resolve()
    return path if path.parent == folder and path.is_file() else None


def detail(session, organization_id, version_id, settings):
    version, language, title = authorized_version(session, organization_id, version_id)
    passages = version.passages or []
    path = artifact_path(settings, version.artifact_key)
    return {"id": version.id, "law_id": None, "law_name": title, "title": title,
            "origin": "official_connector", "synthetic": (version.metadata_json or {}).get("synthetic") is True, "native": True,
            "content_type": version.content_type or "unknown", "filename": version.filename,
            "created_at": _iso(version.created_at), "fetched_at": _iso(version.fetched_at),
            "declared_date": None, "date_provenance": None,
            "source_url": version.source_url, "content_hash": version.content_hash,
            "characters": len(version.text or ""), "passages": passages, "passage_count": len(passages),
            "plain_text": version.text if not passages else None,
            "page_count": max((p.get("page") or 0 for p in passages), default=0),
            "identity_json": {"language": language}, "evidence_url": f"/corpus-evidence/{version.id}",
            "artifact_url": f"/api/regulatory-versions/{version.id}/artifact" if path else None}


def artifact(session, organization_id, version_id, settings):
    version, _, _ = authorized_version(session, organization_id, version_id, body=False)
    path = artifact_path(settings, version.artifact_key)
    if path is None:
        raise DomainError("The saved artifact is unavailable. Extracted evidence remains accessible.", 404, "artifact_missing")
    mime = "application/pdf" if version.content_type == "application/pdf" else "text/plain"
    filename = Path((version.filename or path.name).replace("\\", "/")).name
    return path, mime, filename
