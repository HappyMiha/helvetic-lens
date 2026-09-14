"""Versioned private evidence packets from exact native history, without writes."""

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from . import monitoring_evidence_versions as business
from . import monitoring_personal_evidence as personal
from .business_item_models import BusinessItemWorkEvent
from .business_item_work import TARGETS
from .monitoring_evidence_ask import LOCALES, Record
from .monitoring_evidence_versions import fail
from .river_contracts import utc

FORMAT = "helvetic-lens-monitoring-evidence-v1"
MAX_BYTES = 2_000_000
MAX_ACTIONS = 1000


def canonical(value):
    def encode(item):
        if isinstance(item, datetime):
            return utc(item).isoformat()
        if isinstance(item, date):
            return item.isoformat()
        if isinstance(item, Decimal) and item.is_finite():
            return str(item)
        raise TypeError("Unsupported evidence value")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False, default=encode)


def actions(session, domain, record, selected):
    """Return only private actions actually bound to the selected evidence.

    Actor IDs are nullable after erasure; no email, credential or current-person
    lookup is required to reproduce an action recorded in the private history.
    """
    organization = session.info.get("organization_id")
    after = selected["after"]
    if domain == "tenders":
        from .tender_models import TenderDecision as Decision
        query = select(Decision).where(Decision.dossier_id == record.item_id,
            Decision.sequence == selected["sequence"])
        fields = ("id", "sequence", "decision", "created_at", "user_id")
    elif domain == "ip":
        from .trademark_workflow_models import TrademarkReview as Decision
        query = select(Decision).where(Decision.candidate_id == record.item_id,
            Decision.source_revision_id == after["revision_id"], Decision.profile_revision == selected["profile_revision"],
            Decision.sequence == selected["sequence"], Decision.evaluation_hash == selected["evaluation_hash"])
        fields = ("id", "candidate_version", "sequence", "source_revision_id", "profile_revision",
            "evaluation_hash", "decision", "created_at", "actor_user_id")
    else:
        from .auction_workflow_models import AuctionDecision as Decision
        query = select(Decision).where(Decision.item_id == record.item_id,
            Decision.source_revision_id == after["revision_id"], Decision.material_sequence == selected["sequence"])
        # This legacy native action records its source/material sequence, but
        # not a profile revision. Preserve that limitation rather than invent it.
        fields = ("id", "item_version", "material_sequence", "source_revision_id", "decision",
            "following", "created_at", "actor_user_id")
    rows = list(session.scalars(query.where(Decision.organization_id == organization)
        .order_by(Decision.created_at, Decision.id).limit(MAX_ACTIONS + 1)))
    if len(rows) > MAX_ACTIONS:
        fail("monitoring_export_too_large", 413)
    native_reviews = [{name: getattr(row, name) for name in fields} for row in rows]
    column = getattr(BusinessItemWorkEvent, TARGETS[domain])
    binding = BusinessItemWorkEvent.evidence_binding
    query = select(BusinessItemWorkEvent).where(column == record.item_id,
        BusinessItemWorkEvent.organization_id == organization,
        binding["revision_id"].as_string() == after["revision_id"],
        binding["profile_revision"].as_integer() == selected["profile_revision"],
        binding["sequence"].as_integer() == selected["sequence"])
    if domain in {"ip", "tenders"}:
        fingerprint = selected["evaluation_hash"] if domain == "ip" else after["source_sha256"]
        query = query.where(binding["fingerprint"].as_string() == fingerprint)
    work = list(session.scalars(query.order_by(BusinessItemWorkEvent.item_version).limit(MAX_ACTIONS + 1)))
    if len(work) > MAX_ACTIONS:
        fail("monitoring_export_too_large", 413)
    return {"scope": "actions_bound_to_selected_source", "native_reviews": native_reviews,
        "native_profile_binding_recorded": domain != "auctions",
        "work_history": [{name: getattr(row, name) for name in ("id", "item_version", "actor_user_id",
            "assigned_user_id", "decision", "comment", "evidence_binding", "created_at")} for row in work]}


def packet(session, settings, user_id, record: Record, *, locale, prepared_at, now, revision_id=None):
    if locale not in LOCALES or record.domain not in personal.DOMAINS | set(TARGETS):
        fail("monitoring_export_request_invalid", 422)
    if record.domain in personal.DOMAINS:
        if revision_id is not None:
            fail("monitoring_export_request_invalid", 422)
        selected = personal.selected(session, settings, user_id, record, now=now)
        decisions = {"scope": "selected_record_with_current_review_state",
            "review": selected.pop("private_review")}
    else:
        if record.sequence is not None:
            fail("monitoring_export_request_invalid", 422)
        flag = {"tenders": "tender_watch_enabled", "ip": "trademark_watch_enabled", "auctions": "auction_watch_enabled"}[record.domain]
        if not getattr(settings, flag):
            fail("monitoring_evidence_not_found", 404)
        selected = (business.tender(session, user_id, record.monitor_id, record.item_id,
            revision_id=revision_id, now=now) if record.domain == "tenders" else
            business.licensed(session, user_id, record.domain, record.monitor_id, record.item_id,
                revision_id=revision_id, now=now))
        decisions = actions(session, record.domain, record, selected)
    selection = {"domain": record.domain, "monitor_id": record.monitor_id, "item_id": record.item_id,
        "sequence": selected["sequence"], "revision_id": selected["selected_revision_id"]}
    evidence = {"native_evidence": selected, "private_decisions": decisions}
    try:
        payload = canonical(evidence)
        manifest = {"format": FORMAT, "prepared_at": prepared_at, "locale": locale,
            "scope": {"organization_id": session.info.get("organization_id"), "user_id": user_id},
            "selection": selection, "configuration_revision": selected["profile_revision"],
            "payload_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            "payload_bytes": len(payload.encode("utf-8")), "raw_provider_payload_included": False,
            "limits": ["private_copy_no_redistribution_grant", "current_access_rechecked_on_download",
                "native_attribution_and_source_limits_apply", "authenticated_source_documents_excluded"]}
        encoded = canonical({"manifest": manifest, "payload": json.loads(payload)})
    except (ValueError, TypeError):
        fail("monitoring_export_evidence_invalid", 503)
    size = len(encoded.encode("utf-8"))
    if size > MAX_BYTES:
        fail("monitoring_export_too_large", 413)
    return {"canonical_json": encoded, "sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "bytes": size, "manifest": json.loads(canonical(manifest)),
        "filename": f"helvetic-lens-{record.domain}-{record.item_id}-{selected['sequence']}.json"}
