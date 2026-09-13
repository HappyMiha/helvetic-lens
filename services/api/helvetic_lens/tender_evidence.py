"""Deduplicated public snapshots behind strictly private dossier references."""

import hashlib
import json
from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .config import DomainError
from .monitoring_subjects import _savepoint
from .tender_models import TenderMaterialSection, TenderPublicationSnapshot, TenderVersionSection
from .tender_storage import StorageLimits, payload_size, reserve, storage_lock


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def existing_or_insert(session, model, identifier, *, limits, **fields):
    storage_lock(session)
    row = session.scalar(select(model).where(model.id == identifier).with_for_update())
    if row is not None:
        return row
    try:
        with _savepoint(session):
            reserve(session, fields["payload_bytes"], limits)
            row = model(id=identifier, **fields)
            session.add(row)
            session.flush()
        return row
    except IntegrityError:
        row = session.scalar(select(model).where(model.id == identifier).with_for_update())
        if row is None:
            raise
        return row


def store_snapshot(session, record, now, *, limits=StorageLimits()):
    row = existing_or_insert(
        session,
        TenderPublicationSnapshot,
        record["evidence_sha256"],
        limits=limits,
        payload_bytes=payload_size(record),
        publication_id=record["publication_id"],
        project_id=record["project_id"],
        evidence=deepcopy(record),
        created_at=now,
    )
    if (
        row.publication_id != record["publication_id"]
        or row.project_id != record["project_id"]
        or row.evidence != record
    ):
        raise DomainError(
            "Stored tender evidence conflicts with its fingerprint.", 503, "tender_evidence_invalid"
        )
    return row.id


def store_material(session, version, material, now, *, cache=None, limits=StorageLimits()):
    for name, value in material.items():
        cached = cache.get(id(value)) if cache is not None else None
        if cached is not None and cached[0] is value:
            hashed = cached[1]
        else:
            data = {"value": value["value"], "coverage": value["coverage"]}
            hashed = digest(data)
            row = existing_or_insert(
                session,
                TenderMaterialSection,
                hashed,
                data=deepcopy(data),
                created_at=now,
                payload_bytes=payload_size(data),
                limits=limits,
            )
            if row.data != data:
                raise DomainError(
                    "Stored tender field conflicts with its fingerprint.", 503, "tender_evidence_invalid"
                )
            if cache is not None:
                # Retain the object as well as its id; ids can be reused after GC.
                # The cache belongs only to this atomic observation.
                cache[id(value)] = (value, hashed)
        session.add(
            TenderVersionSection(
                version_id=version.id,
                organization_id=version.organization_id,
                name=name,
                section_id=hashed,
                locator=value["locator"],
            )
        )
    session.flush()
    session.expire(version, ["sections"])


def resolve_material(version):
    references = version.sections
    names = [item.name for item in references]
    if len(set(names)) != len(names) or set(names) != set(version.material_keys):
        raise DomainError("Tender field evidence is incomplete.", 503, "tender_evidence_invalid")
    result = {}
    for item in references:
        if item.section is None or digest(item.section.data) != item.section_id:
            raise DomainError(
                "Tender field evidence no longer matches its fingerprint.", 503, "tender_evidence_invalid"
            )
        result[item.name] = {**deepcopy(item.section.data), "locator": item.locator}
    return result
