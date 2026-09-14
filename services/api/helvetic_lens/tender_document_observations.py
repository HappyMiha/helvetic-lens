"""Private manifest history and document-only dossier revisions, worker boundary."""

from copy import deepcopy

from sqlalchemy import func, select, update

from . import tender_documents as documents
from .config import DomainError
from .document_comparison import compare_documents
from .document_sets import DocumentDelta, Manifest, ManifestState, reconcile
from .monitoring_subjects import _savepoint
from .simap_sources import aware
from .tender_evidence import digest
from .tender_models import (
    TenderDocumentObservation,
    TenderDossier,
    TenderDossierVersion,
    TenderMonitor,
    TenderVersionSection,
)
from .tender_repository import owned_dossier, source_readable
from .tender_storage import StorageLimits, check_version_capacity, payload_size


def canonical(manifest):
    value = manifest.model_dump(mode="json")
    value["items"] = sorted(value["items"], key=lambda item: item["item_id"])
    return value


def latest(session, grant_id):
    return session.scalar(select(TenderDocumentObservation).where(
        TenderDocumentObservation.access_id == grant_id,
    ).order_by(TenderDocumentObservation.sequence.desc()).limit(1))


def state_of(row):
    if row is None:
        return None
    if row.purged_at is not None or row.state is None or row.deltas is None:
        raise documents.unavailable()
    if digest({"state": row.state, "deltas": row.deltas}) != row.fingerprint:
        raise DomainError("Document history integrity failed.", 503, "tender_document_invalid")
    state = ManifestState.model_validate(row.state)
    if (str(state.observation.observation_id) != row.id
            or str(state.observation.access_scope_id) != row.access_id
            or state.observation.dossier_id != row.dossier_id):
        raise DomainError("Document history scope failed.", 503, "tender_document_invalid")
    return state


def denied_items(session, access_id):
    state = state_of(latest(session, access_id))
    return {item.item_id for item in state.documents if item.access == "denied"} if state else set()


def item_permitted(session, access_id, item_id):
    """Explicit per-file denial also closes old retained downloads."""
    return item_id not in denied_items(session, access_id)


def require_current_changes(session, user_id, dossier_id, observation_id, *, now):
    row, _ = read_observation(session, user_id, dossier_id, observation_id, now=now)
    denied = denied_items(session, row.access_id)
    if any(delta["material"] and delta["item_id"] in denied for delta in row.deltas):
        raise documents.unavailable()


def comparison(session, user_id, dossier_id, observation_id, item_id, *, now):
    row, state = read_observation(session, user_id, dossier_id, observation_id, now=now)
    delta = next((DocumentDelta.model_validate(item) for item in row.deltas
                  if item["item_id"] == item_id and item["kind"] == "replaced"), None)
    if delta is None:
        raise documents.unavailable()

    def load(snapshot_id):
        try:
            return documents.read(session, user_id, dossier_id, str(snapshot_id), now=now)[1]
        except DomainError as error:
            if error.status == 404:
                return None
            raise

    return compare_documents(delta, state.observation, load).model_dump(mode="json")


def view(session, user_id, dossier_id, observation_id, *, now, limit=20, after_item=None):
    from .tender_repository import limit_value

    limit_value(limit)
    row, state = read_observation(session, user_id, dossier_id, observation_id, now=now)
    current = state_of(latest(session, row.access_id))
    denied = {item.item_id for item in current.documents if item.access == "denied"}
    selected = [item for item in state.documents if after_item is None or item.item_id > after_item]
    items = []
    for item in selected[:limit]:
        restricted = item.item_id in denied
        original = item.current or item.last_available
        items.append({"item_id": item.item_id, "kind": item.kind, "access": "denied" if restricted else item.access,
                      "lifecycle": item.lifecycle,
                      "title": original.title if original and not restricted else None,
                      "snapshot_id": str(item.last_available.snapshot_id) if item.last_available and not restricted else None,
                      "changes": [delta["kind"] for delta in row.deltas if delta["item_id"] == item.item_id],
                      "comparison_available": not restricted and any(delta["item_id"] == item.item_id
                                                                        and delta["kind"] == "replaced" for delta in row.deltas)})
    return {"id": row.id, "observed_at": documents.utc(row.observed_at).isoformat(),
            "coverage": state.observation.coverage, "items": items,
            "next_cursor": selected[limit - 1].item_id if len(selected) > limit else None}


def read_observation(session, user_id, dossier_id, observation_id, *, now):
    dossier = owned_dossier(session, user_id, dossier_id, personal_only=True)
    row = session.scalar(select(TenderDocumentObservation).where(
        TenderDocumentObservation.id == observation_id,
        TenderDocumentObservation.dossier_id == dossier.id,
        TenderDocumentObservation.organization_id == dossier.organization_id,
    ))
    if row is None:
        raise documents.unavailable()
    _, grant = documents.access(session, user_id, dossier.id, row.access_id, aware(now))
    state = state_of(row)
    if state.observation.source_id != grant.source_id:
        raise DomainError("Document history source mismatch.", 503, "tender_document_invalid")
    return row, state


def observe(session, user_id, dossier_id, manifest, *, now, storage_limits=StorageLimits()):
    """Caller commits snapshots and manifest atomically after permitted collection.

    Full listings only, never a raw pagination page. Source identity/rights and
    capture leases remain the source worker's responsibility. No HTTP write route.
    """
    now = aware(now)
    manifest = Manifest.model_validate(manifest.model_dump())
    if manifest.observed_at > now:
        raise ValueError("Future document observation")
    dossier = owned_dossier(session, user_id, dossier_id, write=True, personal_only=True)
    with _savepoint(session):
        session.execute(update(TenderMonitor).where(TenderMonitor.id == dossier.monitor_id)
                        .values(version=TenderMonitor.version))
        monitor = session.scalar(select(TenderMonitor).where(TenderMonitor.id == dossier.monitor_id)
                                 .execution_options(populate_existing=True).with_for_update())
        if monitor.status != "active":
            raise DomainError("Monitor is not active.", 409, "tender_monitor_inactive")
        session.execute(update(TenderDossier).where(TenderDossier.id == dossier.id)
                        .values(version=TenderDossier.version))
        dossier, grant = documents.access(session, user_id, dossier_id, str(manifest.access_scope_id), now, write=True)
        if manifest.source_id != grant.source_id or manifest.dossier_id != dossier.id:
            raise ValueError("Manifest source and private dossier must match its grant")
        original = session.scalar(select(TenderDossierVersion).where(
            TenderDossierVersion.dossier_id == dossier.id,
            TenderDossierVersion.sequence == dossier.latest_sequence,
        ))
        if original is None or original.publication_id != grant.publication_id:
            raise ValueError("Document observation does not match the current publication")
        # Always check the authoritative public original; earlier private grants
        # may have expired and must not prevent a newly approved baseline.
        source_readable(original, now, include_documents=False)
        previous = latest(session, grant.id)
        previous_state = state_of(previous)
        incoming = canonical(manifest)
        request_hash = digest(incoming)
        if grant.last_observation_id == str(manifest.observation_id):
            if grant.last_observation_hash != request_hash:
                raise ValueError("Conflicting repeated manifest identity")
            return previous.id if previous else None
        if grant.last_observed_at is not None and manifest.observed_at <= documents.utc(grant.last_observed_at):
            raise ValueError("Document observations must advance; stale polls cannot replace current evidence")
        for item in manifest.items:
            if item.access != "available":
                continue
            # Incoming source proof can restore an explicitly denied item. This
            # trusted ingestion flag is never available in an HTTP request.
            _, parsed = documents.read(session, user_id, dossier.id, str(item.snapshot_id), now=now,
                                       check_item_access=False)
            if (str(parsed.access_scope_id) != grant.id or parsed.item_id != item.item_id
                    or parsed.content_sha256 != item.content_sha256
                    or (parsed.parse_status == "complete") != (item.parse_status == "complete")
                    or (item.parse_status == "complete" and parsed.text_sha256 != item.text_sha256)):
                raise ValueError("Manifest item does not match its exact stored projection")
        result = reconcile(previous_state, manifest)
        grant.last_observed_at = manifest.observed_at
        grant.last_observation_id = str(manifest.observation_id)
        grant.last_observation_hash = request_hash
        if previous_state:
            old = canonical(previous_state.observation)
            for key in ("observation_id", "observed_at"):
                old.pop(key)
                incoming.pop(key)
            if old == incoming:
                session.flush()
                return previous.id
        data = result.state.model_dump(mode="json")
        deltas = [item.model_dump(mode="json") for item in result.deltas]
        size = payload_size({"state": data, "deltas": deltas})
        used = documents.used_bytes(session, dossier.id)
        count = session.scalar(select(func.count()).select_from(TenderDocumentObservation)
                               .where(TenderDocumentObservation.dossier_id == dossier.id))
        if used + size > documents.MAX_DOSSIER_BYTES or count >= documents.MAX_DOSSIER_SNAPSHOTS:
            raise DomainError("Document history capacity reached.", 409, "tender_document_capacity")
        observation = TenderDocumentObservation(
            id=str(manifest.observation_id), organization_id=dossier.organization_id,
            dossier_id=dossier.id, access_id=grant.id, sequence=previous.sequence + 1 if previous else 1,
            fingerprint=digest({"state": data, "deltas": deltas}), state=data, deltas=deltas,
            previous_id=previous.id if previous else None, stored_bytes=size, observed_at=manifest.observed_at,
        )
        session.add(observation)
        session.flush()
        material = any(item.material for item in result.deltas)
        renewed = previous is None and bool(original.observation_key)
        if not material and not renewed:
            # Baselines/access/parse metadata have their own immutable history.
            # They must not supersede an unreviewed public opportunity or its mail.
            return observation.id
        check_version_capacity(session, monitor, storage_limits)
        sequence = (session.scalar(select(func.max(TenderDossierVersion.sequence))
                                   .where(TenderDossierVersion.dossier_id == dossier.id)) or 0) + 1
        version = TenderDossierVersion(
            organization_id=dossier.organization_id, dossier_id=dossier.id, sequence=sequence,
            publication_id=original.publication_id, publication_ordinal=original.publication_ordinal,
            profile_revision=original.profile_revision, source_hash=original.source_hash,
            observation_key=observation.id, document_observation_id=observation.id,
            publish_after=original.publish_after, material_keys=deepcopy(original.material_keys),
            summary=deepcopy(original.summary), match=deepcopy(original.match),
            changes=[{"field": "documents", "kind": "field_changed" if material else "coverage_changed"}],
            kind="material_update" if material else "source_update", observed_at=now,
        )
        session.add(version)
        session.flush()
        for section in original.sections:
            session.add(TenderVersionSection(version_id=version.id, organization_id=dossier.organization_id,
                                             name=section.name, section_id=section.section_id, locator=section.locator))
        dossier.latest_sequence = sequence
        dossier.version += 1
        dossier.updated_at = now
        if (material or renewed) and dossier.review_state == "reviewed":
            dossier.review_state = "needs_review"
        # The previous internal decision and reviewed_sequence remain immutable.
        session.flush()
        from .tender_delivery import record_intent

        record_intent(session, monitor, dossier, version, now)
        return observation.id
