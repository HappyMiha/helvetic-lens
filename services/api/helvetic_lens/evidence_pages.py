"""Bound saved evidence transfer; original versions and legacy full APIs remain intact."""

import json
from datetime import UTC

from sqlalchemy import Integer, case, cast, func, select, true

from .config import DomainError
from .corpus_access import accessible_versions, visible
from .corpus_evidence import artifact_path
from .models import Law, RegulatoryDocumentVersion, RegulatoryExpression, RegulatoryWork, Version

TEXT_PAGE_SIZE = 16000


def detail(session, organization_id, version_id, settings, *, native=False, offset=0, limit=50, passage=""):
    if not 0 <= offset <= 2147483647 or not 1 <= limit <= 50 or len(passage) > 200:
        raise DomainError("Choose a valid evidence page.", 422, "invalid_evidence_page")
    model = RegulatoryDocumentVersion if native else Version
    base = (
        accessible_versions(organization_id).where(model.id == version_id)
        if native
        else select(Version)
        .join(Law, Law.id == Version.law_id)
        .where(Version.id == version_id, visible(Version, organization_id), visible(Law, organization_id))
    )
    postgres = session.bind.dialect.name == "postgresql"
    count = (
        case((func.json_typeof(model.passages) == "array", func.json_array_length(model.passages)), else_=0)
        if postgres
        else func.coalesce(func.json_array_length(model.passages), 0)
    )
    fields = [
        model.id,
        model.content_type,
        model.filename,
        model.source_url,
        model.created_at,
        model.artifact_key,
        func.coalesce(func.length(model.text), 0).label("characters"),
        count.label("passage_count"),
    ]
    fields += (
        [
            RegulatoryWork.title.label("law_name"),
            RegulatoryExpression.language,
            model.metadata_json["synthetic"].as_string().label("synthetic"),
        ]
        if native
        else [
            Law.name.label("law_name"),
            Version.law_id,
            Version.origin,
            Version.synthetic,
            Version.declared_date,
            Version.date_provenance,
            Version.identity_json,
        ]
    )
    row = session.execute(base.with_only_columns(*fields)).mappings().first()
    if row is None:
        raise DomainError("The saved source evidence is unavailable in this organization.", 404, "not_found")
    total = row["passage_count"]
    target_found = None
    if total:
        # Expand once in SQL; do not repeatedly extract every index from a large JSON array.
        if postgres:
            parts = (
                func.json_array_elements(model.passages)
                .table_valued("value", with_ordinality="ordinal")
                .render_derived()
            )
            ordinal = parts.c.ordinal - 1
            identifier = parts.c.value.op("->>")("id")
        else:
            parts = func.json_each(model.passages).table_valued("key", "value")
            ordinal = cast(parts.c.key, Integer)
            identifier = func.json_extract(parts.c.value, "$.id")
        page_query = base.join(parts, true())
    if passage:
        position = (
            session.scalar(
                page_query.with_only_columns(ordinal, maintain_column_froms=True)
                .where(identifier == passage)
                .order_by(ordinal)
                .limit(1)
            )
            if total
            else None
        )
        target_found = position is not None
        if target_found:
            offset = (position // limit) * limit
    mode = "passages" if total else "text"
    size = limit if total else TEXT_PAGE_SIZE
    length = total if total else row["characters"]
    if offset >= length and offset:
        raise DomainError(
            "This page is outside the saved document. Open its first page.", 422, "invalid_evidence_page"
        )
    end = min(offset + size, length)
    if total:
        values = list(
            session.scalars(
                page_query.with_only_columns(parts.c.value, maintain_column_froms=True)
                .where(ordinal >= offset, ordinal < end)
                .order_by(ordinal)
                .limit(limit)
            )
        )
        if not values:
            raise DomainError("The saved evidence is no longer accessible.", 404, "not_found")
        passages = [json.loads(value) if isinstance(value, str) else value for value in values]
        plain_text = None
    else:
        plain_text = (
            session.scalar(base.with_only_columns(func.substr(model.text, offset + 1, TEXT_PAGE_SIZE))) or ""
        )
        passages = []

    def iso(value):
        return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()

    route = "regulatory-versions" if native else "versions"
    return {
        "id": row["id"],
        "law_id": None if native else row["law_id"],
        "law_name": row["law_name"],
        "native": native,
        "origin": "official_connector" if native else row["origin"],
        "synthetic": row["synthetic"] in (True, 1, "true"),
        "content_type": row["content_type"] or "unknown",
        "filename": row["filename"],
        "source_url": row["source_url"],
        "created_at": iso(row["created_at"]),
        "declared_date": None if native else row["declared_date"],
        "date_provenance": None if native else row["date_provenance"],
        "identity_json": {"language": row["language"]} if native else row["identity_json"],
        "characters": row["characters"],
        "passage_count": total,
        "passages": passages,
        "plain_text": plain_text,
        "artifact_url": f"/api/{route}/{version_id}/artifact"
        if artifact_path(settings, row["artifact_key"])
        else None,
        "pagination": {
            "offset": offset,
            "end": end,
            "total": length,
            "size": size,
            "mode": mode,
            "next_offset": end if end < length else None,
            "previous_offset": max(0, offset - size) if offset else None,
            "target_found": target_found,
        },
    }
