"""Exact native business versions for the permissioned evidence-download feature.

No endpoint or download authorization lives here. Callers must recheck the whole
packet at download time. A missing old source state is an error, never permission
to replace historical evidence with the current head.
"""

from copy import deepcopy

from sqlalchemy import select

from .business_item_work import _target
from .config import DomainError


def fail(code="monitoring_export_evidence_unavailable", status=409):
    raise DomainError("The selected evidence cannot be exported. Review its source access and version.", status, code)


def configuration(session, domain, monitor, revision):
    if domain == "tenders":
        from .tender_contracts import TenderProfile as Contract
        from .tender_models import TenderProfileRevision as Revision
    elif domain == "ip":
        from .trademark_contracts import TrademarkPortfolio as Contract
        from .trademark_models import TrademarkConfigurationRevision as Revision
    else:
        from .auction_contracts import AuctionProfile as Contract
        from .auction_models import AuctionConfigurationRevision as Revision
    row = session.scalar(select(Revision).where(Revision.monitor_id == monitor.id,
        Revision.organization_id == monitor.organization_id, Revision.revision == revision))
    if row is None:
        fail("monitoring_export_configuration_unavailable", 503)
    try:
        value = Contract.model_validate(row.configuration)
        if value.fingerprint() != row.configuration_hash:
            fail("monitoring_export_configuration_unavailable", 503)
    except ValueError:
        fail("monitoring_export_configuration_unavailable", 503)
    return {"revision": revision, "sha256": row.configuration_hash, "value": value.model_dump(mode="json")}


def _tender_snapshot(session, user_id, row, now):
    from .tender_repository import source_readable

    if row is None:
        return None
    # Personal authenticated originals and document-derived revisions require
    # their separate source contract. Never turn an owned private body into a
    # public SIMAP export merely because its parent publication is public.
    if row.document_observation_id:
        fail("monitoring_export_authenticated_documents_excluded", 403)
    source_readable(row, now, user_id=user_id)
    source = deepcopy(row.evidence)
    source.pop("original", None)
    return {"revision_id": row.id, "sequence": row.sequence, "profile_revision": row.profile_revision,
        "observed_at": row.observed_at, "source_sha256": row.source_hash,
        "publication_id": row.publication_id, "facts": source, "material": deepcopy(row.material)}


def tender(session, user_id, monitor_id, item_id, *, revision_id=None, now):
    from .tender_models import TenderDossierVersion

    monitor, dossier = _target(session, user_id, "tenders", monitor_id, item_id)
    versions = select(TenderDossierVersion).where(TenderDossierVersion.dossier_id == dossier.id,
        TenderDossierVersion.organization_id == monitor.organization_id)
    selected = session.scalar(versions.where(TenderDossierVersion.id == revision_id) if revision_id else
        versions.order_by(TenderDossierVersion.sequence.desc()).limit(1))
    if selected is None:
        fail("monitoring_export_version_not_found", 404)
    previous = session.scalar(versions.where(TenderDossierVersion.sequence == selected.sequence - 1))
    if selected.sequence > 1 and previous is None:
        fail()
    return {"selected_revision_id": selected.id, "sequence": selected.sequence,
        "profile_revision": selected.profile_revision, "change_codes": deepcopy(selected.changes),
        "configuration": configuration(session, "tenders", monitor, selected.profile_revision),
        "after": _tender_snapshot(session, user_id, selected, now),
        "before": _tender_snapshot(session, user_id, previous, now),
        "newer_available": selected.sequence < dossier.latest_sequence,
        "current_configuration": selected.profile_revision == monitor.revision}


def _licensed_source(session, domain, item, revision_id, *, now):
    if revision_id is None:
        return None
    if domain == "ip":
        from . import trademark_sources as sources
        from .trademark_source_models import TrademarkRegisterRevision as Revision
    else:
        from . import auction_sources as sources
        from .auction_source_models import AuctionSourceRecordRevision as Revision
    row = session.get(Revision, revision_id, populate_existing=True)
    if row is None or row.record_key != item.record_key:
        fail()
    _, policy = sources.require_permission(session, row.permission_id, now=now, purpose="export")
    facts = sources.read_revision(session, row.permission_id, row.id, now=now, purpose="display")
    return {"revision_id": row.id, "sequence": row.sequence, "permission_id": row.permission_id,
        "received_at": row.received_at, "attribution": policy.attribution, "source_sha256": row.normalized_hash,
        "facts": facts.model_dump(mode="json")}


def licensed(session, user_id, domain, monitor_id, item_id, *, revision_id=None, now):
    if domain not in {"ip", "auctions"}:
        fail("monitoring_export_domain_invalid", 422)
    monitor, item = _target(session, user_id, domain, monitor_id, item_id)
    if domain == "ip":
        from .trademark_history import event_detail
        from .trademark_workflow_models import TrademarkCandidateEvent as Event
        versions = select(Event).where(Event.candidate_id == item.id, Event.organization_id == monitor.organization_id)
    else:
        from .auction_today import detail
        from .auction_workflow_models import AuctionItemEvent as Event
        versions = select(Event).where(Event.item_id == item.id, Event.organization_id == monitor.organization_id)
    event = session.scalar(versions.where(Event.id == revision_id) if revision_id else
        versions.order_by(Event.sequence.desc()).limit(1))
    if event is None:
        fail("monitoring_export_version_not_found", 404)
    # Native readers validate the selected historical profile and its calculation
    # context. Their current-head convenience projection is intentionally omitted.
    selected = (event_detail(session, user_id, monitor.id, item.id, event.id, now=now) if domain == "ip" else
        detail(session, user_id, monitor.id, event.id, now=now))
    if domain == "ip" and selected["assessment"] is None:
        fail("monitoring_export_rule_evidence_unavailable", 409)
    after = _licensed_source(session, domain, item, event.source_revision_id, now=now)
    before = _licensed_source(session, domain, item, event.previous_revision_id, now=now)
    return {"selected_revision_id": event.id, "sequence": event.sequence,
        "profile_revision": event.profile_revision, "change_codes": deepcopy(event.change_codes),
        "configuration": configuration(session, domain, monitor, event.profile_revision),
        "after": after, "before": before,
        "detected_at": event.created_at,
        "evaluation_hash": event.evaluation_hash if domain == "ip" else None,
        "calibration_ids": deepcopy(event.calibration_ids) if domain == "ip" else [],
        "newer_available": selected["newer_available"], "current_configuration": selected["current_configuration"],
        "assessment": selected.get("assessment"), "deadline_context": selected.get("deadline_context")}
