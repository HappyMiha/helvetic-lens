"""Authority-aware, idempotent persistence for the shared regulatory corpus."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .config import DomainError
from .db import utcnow
from .models import (
    Law,
    LegacyDocumentMapping,
    RegulatoryDate,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryExpression,
    RegulatoryIdentifier,
    RegulatoryRelation,
    RegulatoryWork,
)

WORK_KINDS = {
    "act",
    "ordinance",
    "parliamentary_business",
    "initiative",
    "bill",
    "court_decision",
    "official_notice",
    "consultation",
    "unclassified_document",
}
DATE_KINDS = {
    "detected_at",
    "published_at",
    "version_date",
    "effective_from",
    "effective_to",
    "decision_date",
    "fetched_at",
}
DATE_PRECISIONS = {"instant", "day", "month", "year", "unknown"}
EVENT_TYPES = {
    "created",
    "new_version",
    "amended",
    "repealed",
    "replaced",
    "status_changed",
    "decided",
    "notice_published",
}
CONNECTOR_HEALTH_STATES = {"healthy", "degraded", "error", "unknown"}
ANALYSIS_STATES = {"pending", "queued", "running", "complete", "failed", "not_required"}
IMPACT_STATES = {"high", "medium", "low", "none", "unknown"}
RELATION_TYPES = {
    "amends",
    "repeals",
    "replaces",
    "implements",
    "cites",
    "interprets",
    "potentially_impacts",
}
RELATION_STATES = {"confirmed", "proposed", "rejected"}
PROVENANCE_METHODS = {
    "official_metadata",
    "exact_identifier",
    "text_rule",
    "model_proposal",
    "human_review",
    "legacy_mapping",
}
IDENTIFIER_PRIORITY = {
    "eli_uri": 0,
    "sr_rs": 1,
    "parliamentary_business_id": 2,
    "court_docket": 3,
    "official_url": 4,
    "legacy_canonical_identity": 9,
}


def _clean(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if not parsed.scheme or not parsed.netloc:
        raise DomainError("The official URL is invalid.", 422, "invalid_official_url")
    host = (parsed.hostname or "").lower()
    port = f":{parsed.port}" if parsed.port else ""
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), host + port, path, parsed.query, ""))


def normalize_identifier(scheme: str, value: str) -> str:
    scheme = scheme.strip().lower()
    value = _clean(value)
    if not value:
        raise DomainError("An identifier value is required.", 422, "identifier_required")
    if scheme in {"eli_uri", "official_url", "legacy_canonical_identity"} and value.lower().startswith(
        ("http://", "https://")
    ):
        return normalize_url(value)
    if scheme == "sr_rs":
        return re.sub(r"[^0-9A-Za-z.]", "", value).upper()
    if scheme in {"parliamentary_business_id", "court_docket"}:
        return re.sub(r"\s+", "", value).upper()
    return value.casefold()


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class IdentifierInput:
    scheme: str
    value: str
    source_url: str | None = None


@dataclass(frozen=True)
class DateInput:
    target: str
    kind: str
    value: str
    precision: str
    provenance: str
    source_url: str | None = None
    evidence: dict = field(default_factory=dict)


@dataclass(frozen=True)
class VersionInput:
    key: str
    content_hash: str | None = None
    artifact_key: str | None = None
    extractor: str | None = None
    text: str | None = None
    passages: tuple[dict, ...] = ()
    content_type: str | None = None
    filename: str | None = None
    source_url: str | None = None
    fetched_at: datetime | None = None
    legacy_version_id: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ExpressionInput:
    language: str
    key: str
    title: str = ""
    official_url: str | None = None
    metadata: dict = field(default_factory=dict)
    version: VersionInput | None = None


@dataclass(frozen=True)
class DocumentInput:
    kind: str
    authority: str
    identifiers: tuple[IdentifierInput, ...]
    expression: ExpressionInput
    title: str = ""
    stable_official_url: str | None = None
    lifecycle_status: str | None = None
    metadata: dict = field(default_factory=dict)
    dates: tuple[DateInput, ...] = ()
    legacy_law_id: str | None = None
    owner_organization_id: str | None = None


@dataclass(frozen=True)
class EventInput:
    work_id: str
    authority: str
    event_type: str
    detected_at: datetime
    provenance_method: str
    source_url: str
    evidence: dict
    external_key: str | None = None
    expression_id: str | None = None
    document_version_id: str | None = None
    connector: str | None = None
    connector_health: str = "healthy"
    analysis_state: str = "pending"
    impact: str = "unknown"


@dataclass(frozen=True)
class RelationInput:
    subject_work_id: str
    object_work_id: str
    authority: str
    relation_type: str
    state: str
    provenance_method: str
    evidence: dict
    source_version_id: str | None = None
    confidence: float | None = None
    rule_or_model_revision: str | None = None
    supersedes_relation_id: str | None = None


@dataclass(frozen=True)
class MergeResult:
    work: RegulatoryWork
    expression: RegulatoryExpression
    version: RegulatoryDocumentVersion | None
    created_work: bool
    created_expression: bool
    created_version: bool
    previous_lifecycle_status: str | None = None
    lifecycle_changed: bool = False


class RegulatoryCorpus:
    """The only write boundary used by catalogue connectors and reconciliation jobs."""

    @staticmethod
    def bind_legacy_official_identity(
        session: Session,
        *,
        authority: str,
        scheme: str,
        value: str,
        kind: str,
        stable_official_url: str,
    ) -> None:
        """Bind a previously added official URL to its catalogue identity before merge."""

        normalized = normalize_identifier(scheme, value)
        existing = session.scalar(
            select(RegulatoryIdentifier).where(
                RegulatoryIdentifier.authority == _clean(authority).lower(),
                RegulatoryIdentifier.scheme == scheme,
                RegulatoryIdentifier.normalized_value == normalized,
            )
        )
        if existing:
            return
        mapping = session.scalar(
            select(LegacyDocumentMapping)
            .join(Law, Law.id == LegacyDocumentMapping.law_id)
            .where(Law.canonical_identity == value)
            .order_by(LegacyDocumentMapping.created_at)
            .limit(1)
        )
        if not mapping:
            return
        work = session.get(RegulatoryWork, mapping.work_id)
        if not work:
            return
        session.add(
            RegulatoryIdentifier(
                work_id=work.id,
                authority=_clean(authority).lower(),
                scheme=scheme,
                value=_clean(value),
                normalized_value=normalized,
                source_url=normalize_url(stable_official_url),
            )
        )
        work.authority = _clean(authority).lower()
        if work.kind == "unclassified_document":
            work.kind = kind
        work.stable_official_url = normalize_url(stable_official_url)
        mapping.mapping_status = "matched"
        mapping.canonical_hint = f"{scheme}:{normalized}"
        mapping.reason = "Matched to the catalogue by its stable official identity."
        session.flush()

    def merge_document(self, session: Session, data: DocumentInput) -> MergeResult:
        authority = _clean(data.authority).lower()
        if data.kind not in WORK_KINDS:
            raise DomainError("Unknown regulatory work kind.", 422, "invalid_work_kind")
        if not authority:
            raise DomainError("An authority is required.", 422, "authority_required")

        supplied = list(data.identifiers)
        if data.stable_official_url:
            stable = normalize_url(data.stable_official_url)
            if not any(item.scheme.strip().lower() == "official_url" for item in supplied):
                supplied.append(IdentifierInput("official_url", stable, stable))
        if not supplied:
            raise DomainError(
                "At least one authority-scoped identifier is required.",
                422,
                "regulatory_identifier_required",
            )

        normalized = [
            (item, item.scheme.strip().lower(), normalize_identifier(item.scheme, item.value))
            for item in supplied
        ]
        matching_ids = session.scalars(
            select(RegulatoryIdentifier).where(
                RegulatoryIdentifier.authority == authority,
                or_(
                    *(
                        (RegulatoryIdentifier.scheme == scheme)
                        & (RegulatoryIdentifier.normalized_value == value)
                        for _, scheme, value in normalized
                    )
                ),
            )
        ).all()
        matched_work_ids = {item.work_id for item in matching_ids}
        if len(matched_work_ids) > 1:
            raise DomainError(
                "The supplied identifiers resolve to different canonical works.",
                409,
                "regulatory_identity_conflict",
            )

        mapping = None
        if data.legacy_law_id:
            mapping = session.scalar(
                select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == data.legacy_law_id)
            )
        work = session.get(RegulatoryWork, next(iter(matched_work_ids))) if matched_work_ids else None
        previous_lifecycle_status = work.lifecycle_status if work else None
        created_work = work is None
        if work is None:
            canonical = min(
                normalized,
                key=lambda item: (IDENTIFIER_PRIORITY.get(item[1], 8), item[1], item[2]),
            )
            work = RegulatoryWork(
                owner_organization_id=data.owner_organization_id,
                kind=data.kind,
                authority=authority,
                canonical_key=f"{canonical[1]}:{canonical[2]}",
                title=_clean(data.title or data.expression.title),
                stable_official_url=normalize_url(data.stable_official_url)
                if data.stable_official_url
                else None,
                lifecycle_status=data.lifecycle_status,
                metadata_json=dict(data.metadata),
            )
            session.add(work)
            session.flush()
        else:
            if work.kind == "unclassified_document" and data.kind != work.kind:
                work.kind = data.kind
            if not work.title and (data.title or data.expression.title):
                work.title = _clean(data.title or data.expression.title)
            if not work.stable_official_url and data.stable_official_url:
                work.stable_official_url = normalize_url(data.stable_official_url)
            if data.lifecycle_status:
                work.lifecycle_status = data.lifecycle_status
            work.metadata_json = {**(work.metadata_json or {}), **data.metadata}
            work.updated_at = utcnow()

        existing_by_value = {(item.scheme, item.normalized_value): item for item in matching_ids}
        for item, scheme, value in normalized:
            existing = existing_by_value.get((scheme, value))
            if not existing:
                existing = session.scalar(
                    select(RegulatoryIdentifier).where(
                        RegulatoryIdentifier.work_id == work.id,
                        RegulatoryIdentifier.scheme == scheme,
                        RegulatoryIdentifier.normalized_value == value,
                    )
                )
            if existing and existing.work_id != work.id:
                raise DomainError(
                    "An identifier already belongs to another canonical work.",
                    409,
                    "regulatory_identifier_conflict",
                )
            if existing and existing.authority != authority and work.authority == authority:
                existing.authority = authority
            if not existing:
                session.add(
                    RegulatoryIdentifier(
                        work_id=work.id,
                        authority=authority,
                        scheme=scheme,
                        value=_clean(item.value),
                        normalized_value=value,
                        source_url=normalize_url(item.source_url) if item.source_url else None,
                    )
                )

        language = _clean(data.expression.language).lower() or "und"
        expression_key = (
            normalize_identifier("official_url", data.expression.key)
            if "://" in data.expression.key
            else _clean(data.expression.key)
        )
        expression = session.scalar(
            select(RegulatoryExpression).where(
                RegulatoryExpression.work_id == work.id,
                RegulatoryExpression.language == language,
                RegulatoryExpression.expression_key == expression_key,
            )
        )
        created_expression = expression is None
        if expression is None:
            expression = RegulatoryExpression(
                work_id=work.id,
                language=language,
                expression_key=expression_key,
                title=_clean(data.expression.title),
                official_url=normalize_url(data.expression.official_url)
                if data.expression.official_url
                else None,
                metadata_json=dict(data.expression.metadata),
            )
            session.add(expression)
            session.flush()
        else:
            expression.title = _clean(data.expression.title) or expression.title
            expression.metadata_json = {
                **(expression.metadata_json or {}),
                **data.expression.metadata,
            }
            expression.updated_at = utcnow()

        version = None
        created_version = False
        if data.expression.version:
            version_data = data.expression.version
            version_key = _clean(version_data.key)
            version = session.scalar(
                select(RegulatoryDocumentVersion).where(
                    RegulatoryDocumentVersion.expression_id == expression.id,
                    RegulatoryDocumentVersion.version_key == version_key,
                )
            )
            created_version = version is None
            if version is None:
                version = RegulatoryDocumentVersion(
                    expression_id=expression.id,
                    version_key=version_key,
                    legacy_version_id=version_data.legacy_version_id,
                    content_hash=version_data.content_hash,
                    artifact_key=version_data.artifact_key,
                    extractor=version_data.extractor,
                    text=version_data.text,
                    passages=list(version_data.passages),
                    content_type=version_data.content_type,
                    filename=version_data.filename,
                    source_url=normalize_url(version_data.source_url) if version_data.source_url else None,
                    fetched_at=version_data.fetched_at,
                    metadata_json=dict(version_data.metadata),
                )
                session.add(version)
                session.flush()
            else:
                if version_data.content_hash and version.content_hash not in {
                    None,
                    version_data.content_hash,
                }:
                    raise DomainError(
                        "The same official version key returned different content.",
                        409,
                        "regulatory_version_content_conflict",
                    )
                version.content_hash = version.content_hash or version_data.content_hash
                version.artifact_key = version.artifact_key or version_data.artifact_key
                version.extractor = version.extractor or version_data.extractor
                version.text = version.text or version_data.text
                version.passages = version.passages or list(version_data.passages)
                version.content_type = version.content_type or version_data.content_type
                version.filename = version.filename or version_data.filename
                version.metadata_json = {
                    **(version.metadata_json or {}),
                    **version_data.metadata,
                }

        targets = {"work": work.id, "expression": expression.id}
        if version:
            targets["version"] = version.id
        for date in data.dates:
            if date.target not in targets:
                raise DomainError("A date target is unavailable.", 422, "invalid_date_target")
            self.record_date(session, targets[date.target], date.target, date)

        if data.legacy_law_id and mapping is None:
            mapping = LegacyDocumentMapping(
                owner_organization_id=data.owner_organization_id,
                law_id=data.legacy_law_id,
                work_id=work.id,
                mapping_status="provisional",
                canonical_hint=work.canonical_key,
                reason="Awaiting an authority-scoped identifier from an official connector.",
            )
            session.add(mapping)
        elif mapping:
            mapping.work_id = work.id
            mapping.mapping_status = "matched"
            mapping.canonical_hint = work.canonical_key
            mapping.reason = "Matched by an authority-scoped connector identifier."

        session.flush()
        return MergeResult(
            work=work,
            expression=expression,
            version=version,
            created_work=created_work,
            created_expression=created_expression,
            created_version=created_version,
            previous_lifecycle_status=previous_lifecycle_status,
            lifecycle_changed=(
                not created_work
                and bool(data.lifecycle_status)
                and previous_lifecycle_status != data.lifecycle_status
            ),
        )

    def map_legacy_document(self, session: Session, law, version) -> MergeResult:
        """Create an explicit provisional corpus mapping without changing legacy reads."""

        dates = ()
        if version.declared_date:
            dates = (
                DateInput(
                    target="version",
                    kind="version_date",
                    value=version.declared_date,
                    precision="day",
                    provenance=version.date_provenance or "legacy_record",
                    source_url=version.source_url,
                ),
            )
        language = (version.identity_json or {}).get("language") or "und"
        if language == "unknown":
            language = "und"
        owner = law.owner_organization_id
        legacy_identity = f"{owner}:{law.canonical_identity}" if owner else law.canonical_identity
        return self.merge_document(
            session,
            DocumentInput(
                kind="unclassified_document",
                authority=law.provider or "direct_url",
                identifiers=(IdentifierInput("legacy_canonical_identity", legacy_identity, law.url),),
                title=law.name,
                stable_official_url=law.url if owner is None else None,
                expression=ExpressionInput(
                    language=language,
                    key=law.canonical_identity,
                    title=version.title or law.name,
                    official_url=version.source_url or law.url,
                    version=VersionInput(
                        key=f"{version.content_hash}:{version.extractor}",
                        content_hash=version.content_hash,
                        artifact_key=version.artifact_key,
                        source_url=version.source_url,
                        fetched_at=version.created_at or utcnow(),
                        legacy_version_id=version.id,
                    ),
                ),
                dates=dates,
                legacy_law_id=law.id,
                owner_organization_id=owner,
            ),
        )

    @staticmethod
    def record_date(session: Session, entity_id: str, entity_type: str, data: DateInput) -> RegulatoryDate:
        if data.kind not in DATE_KINDS or data.precision not in DATE_PRECISIONS:
            raise DomainError("The regulatory date is invalid.", 422, "invalid_regulatory_date")
        value = _clean(data.value)
        record = session.scalar(
            select(RegulatoryDate).where(
                RegulatoryDate.entity_type == entity_type,
                RegulatoryDate.entity_id == entity_id,
                RegulatoryDate.kind == data.kind,
                RegulatoryDate.date_value == value,
                RegulatoryDate.precision == data.precision,
                RegulatoryDate.provenance == data.provenance,
            )
        )
        if record:
            return record
        record = RegulatoryDate(
            entity_type=entity_type,
            entity_id=entity_id,
            kind=data.kind,
            date_value=value,
            precision=data.precision,
            provenance=_clean(data.provenance),
            source_url=normalize_url(data.source_url) if data.source_url else None,
            evidence_json=dict(data.evidence),
        )
        session.add(record)
        session.flush()
        return record

    @staticmethod
    def record_event(session: Session, data: EventInput) -> RegulatoryEvent:
        if data.event_type not in EVENT_TYPES:
            raise DomainError("Unknown regulatory event type.", 422, "invalid_event_type")
        if not data.source_url or not data.evidence:
            raise DomainError(
                "A regulatory event requires source evidence.",
                422,
                "regulatory_event_evidence_required",
            )
        if data.provenance_method not in PROVENANCE_METHODS:
            raise DomainError("Unknown provenance method.", 422, "invalid_provenance_method")
        if (
            data.connector_health not in CONNECTOR_HEALTH_STATES
            or data.analysis_state not in ANALYSIS_STATES
            or data.impact not in IMPACT_STATES
        ):
            raise DomainError("The registry event state is invalid.", 422, "invalid_event_state")
        authority = _clean(data.authority).lower()
        key = (
            f"{data.event_type}:{data.external_key}"
            if data.external_key
            else _fingerprint(
                {
                    "work": data.work_id,
                    "expression": data.expression_id,
                    "version": data.document_version_id,
                    "type": data.event_type,
                    "source": normalize_url(data.source_url),
                    "evidence": data.evidence,
                }
            )
        )
        record = session.scalar(
            select(RegulatoryEvent).where(
                RegulatoryEvent.authority == authority,
                RegulatoryEvent.dedupe_key == key,
            )
        )
        if record:
            return record
        record = RegulatoryEvent(
            work_id=data.work_id,
            expression_id=data.expression_id,
            document_version_id=data.document_version_id,
            authority=authority,
            event_type=data.event_type,
            dedupe_key=key,
            detected_at=data.detected_at,
            source_url=normalize_url(data.source_url),
            provenance_method=data.provenance_method,
            connector=_clean(data.connector or authority).lower(),
            connector_health=data.connector_health,
            analysis_state=data.analysis_state,
            impact=data.impact,
            evidence_json=dict(data.evidence),
        )
        session.add(record)
        session.flush()
        return record

    @staticmethod
    def record_relation(session: Session, data: RelationInput) -> RegulatoryRelation:
        if data.relation_type not in RELATION_TYPES or data.state not in RELATION_STATES:
            raise DomainError("The regulatory relation is invalid.", 422, "invalid_relation")
        if data.provenance_method not in PROVENANCE_METHODS or not data.evidence:
            raise DomainError(
                "A regulatory relation requires supported provenance and evidence.",
                422,
                "regulatory_relation_evidence_required",
            )
        evidence_fingerprint = _fingerprint(data.evidence)
        authority = _clean(data.authority).lower()
        key = _fingerprint(
            {
                "subject": data.subject_work_id,
                "object": data.object_work_id,
                "version": data.source_version_id,
                "type": data.relation_type,
                "state": data.state,
                "method": data.provenance_method,
                "evidence": evidence_fingerprint,
                "supersedes": data.supersedes_relation_id,
                "revision": data.rule_or_model_revision,
            }
        )
        record = session.scalar(
            select(RegulatoryRelation).where(
                RegulatoryRelation.authority == authority,
                RegulatoryRelation.dedupe_key == key,
            )
        )
        if record:
            return record
        record = RegulatoryRelation(
            subject_work_id=data.subject_work_id,
            object_work_id=data.object_work_id,
            source_version_id=data.source_version_id,
            supersedes_relation_id=data.supersedes_relation_id,
            authority=authority,
            relation_type=data.relation_type,
            state=data.state,
            provenance_method=data.provenance_method,
            dedupe_key=key,
            evidence_fingerprint=evidence_fingerprint,
            confidence=data.confidence,
            evidence_json=dict(data.evidence),
            rule_or_model_revision=data.rule_or_model_revision,
        )
        session.add(record)
        session.flush()
        return record
