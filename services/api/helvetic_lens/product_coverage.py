"""Dossier-scoped saved coverage, without fetching sources or claiming a scan."""
from fastapi import Request
from sqlalchemy import select

from .db import utcnow
from .legal_profile_models import LegalMonitoringProfile
from .models import MonitoringTopic, MonitoringTopicRevision
from .product_api import Product
from .product_investigation_models import Investigation, WebResearchPolicy, WebResearchTrigger
from .product_investigations import access
from .product_sources import document_statuses
from .topic_coverage import _iso, snapshot


def payload(session, parent):
    profile = session.get(LegalMonitoringProfile, parent.profile_id)
    now, topics, pack_ids = utcnow(), [], []
    # Never reuse the original profile selection after a topic has been revised.
    for identifier in dict.fromkeys(profile.topic_ids_json):
        topic = session.get(MonitoringTopic, identifier)
        revision = session.scalar(select(MonitoringTopicRevision).where(
            MonitoringTopicRevision.topic_id == identifier,
            MonitoringTopicRevision.organization_id == parent.organization_id,
            MonitoringTopicRevision.revision == topic.current_revision,
        )) if topic and topic.organization_id == parent.organization_id else None
        if not revision:
            topics.append({"id": identifier, "name": "Unavailable monitoring topic",
                           "status": "missing", "revision": None, "pack_ids": []})
            continue
        selected = list(revision.source_pack_ids_json)
        topics.append({"id": identifier, "name": revision.name, "status": topic.status,
                       "revision": topic.current_revision, "pack_ids": selected})
        pack_ids.extend(selected)
    if profile.status == "draft":
        pack_ids.extend(profile.config_json.get("source_pack_ids", []))
    pack_ids = list(dict.fromkeys(pack_ids))
    packs = []
    for offset in range(0, len(pack_ids), 20):
        packs.extend(snapshot(session, pack_ids[offset:offset + 20], now=now,
                              organization_id=parent.organization_id)["items"])
    policy = session.scalar(select(WebResearchPolicy).where(WebResearchPolicy.dossier_id == parent.id))
    latest = session.execute(select(WebResearchTrigger, Investigation).join(
        Investigation, Investigation.id == WebResearchTrigger.investigation_id).where(
        WebResearchTrigger.dossier_id == parent.id,
        Investigation.dossier_id == parent.id,
    ).order_by(WebResearchTrigger.created_at.desc(), WebResearchTrigger.id.desc()).limit(1)).first()
    return {
        "schema_id": "dossier-coverage/v1", "dossier_id": parent.id, "captured_at": _iso(now),
        "scope": "saved_operational_state", "profile_status": profile.status,
        "documents": document_statuses(session, parent), "topics": topics, "packs": packs,
        "web_research": {
            "enabled": bool(policy and policy.enabled), "revision": policy.revision if policy else 0,
            "last_scheduler_check_at": _iso(policy.checked_at) if policy else None,
            "next_run_at": _iso(policy.next_run_at) if policy and policy.enabled else None,
            "reason": policy.reason if policy else "Recurring public search is off.",
            "latest_run": {"id": latest[1].id, "status": latest[1].status,
                           "created_at": _iso(latest[0].created_at),
                           "policy_revision": latest[0].policy_revision} if latest else None,
        },
        "limitations": [
            "Saved source state, not a completed dossier-wide scan or exhaustive coverage.",
            "Shared feed collection does not prove that a dossier topic has checked every document.",
            "References and uploaded files are not monitored unless explicitly connected.",
            "Recurring search outcomes describe their own bounded investigations, not the whole internet.",
        ], "ai_calls": 0,
    }


def routes(router, service, actor):
    @router.get("/dossiers/{dossier_id}/coverage")
    def read(product: Product, dossier_id: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            parent = access(session, identity, product, dossier_id)
            return payload(session, parent)
