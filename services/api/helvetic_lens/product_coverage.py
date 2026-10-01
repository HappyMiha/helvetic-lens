"""Dossier-scoped saved coverage, without fetching sources or claiming a scan."""
from datetime import datetime

from fastapi import Query, Request
from sqlalchemy import select

from .db import utcnow
from .legal_profile_models import LegalMonitoringProfile
from .models import MonitoringTopic, MonitoringTopicRevision
from .product_api import Product
from .product_investigation_models import Investigation, WebResearchPolicy, WebResearchTrigger
from .product_investigations import access
from .product_sources import document_statuses
from .topic_coverage import _iso, snapshot


def selection(session, parent):
    profile = session.get(LegalMonitoringProfile, parent.profile_id)
    topics, pack_ids = [], []
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
    return profile, topics, pack_ids


def payload(session, parent):
    profile, topics, pack_ids = selection(session, parent)
    now = utcnow()
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
    @router.get("/research-capabilities")
    def capabilities(product: Product, request: Request):
        from .domain_packs import REGISTRY, for_product
        from .product_provenance import principal

        identity = actor(request)
        with service.db.session() as session:
            principal(session, identity, utcnow())
            return {"contract": "research-capabilities/v1", "selected": for_product(product).id,
                "packs": [pack.descriptor() for pack in REGISTRY.values()]}

    @router.get("/dossiers/{dossier_id}/knowledge")
    def knowledge(product: Product, dossier_id: str, request: Request,
                  offset: int = Query(default=0, ge=0, le=100000)):
        from .research_knowledge import ledger_page

        identity = actor(request)
        with service.db.session() as session:
            return ledger_page(session, access(session, identity, product, dossier_id), offset=offset)

    @router.get("/dossiers/{dossier_id}/coverage/research")
    def research_history(product: Product, dossier_id: str, request: Request,
                         offset: int = Query(default=0, ge=0, le=100000)):
        from .product_exploration import adaptive_current
        from .product_public_research import sources_visible
        from .research_coverage import project

        identity = actor(request)
        with service.db.session() as session:
            parent = access(session, identity, product, dossier_id)
            query = select(Investigation).where(Investigation.dossier_id == parent.id,
                Investigation.publication_id.is_(None), sources_visible()).order_by(
                    Investigation.created_at.desc(), Investigation.id).offset(offset).limit(11)
            runs = list(session.scalars(query))
            return {"items": [project(session, run) if adaptive_current(session, run) else {
                "investigation_id": run.id, "status": "evidence_changed", "recorded": False} for run in runs[:10]],
                "offset": offset, "next_offset": offset + 10 if len(runs) > 10 else None}

    @router.get("/dossiers/{dossier_id}/coverage")
    def read(product: Product, dossier_id: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            parent = access(session, identity, product, dossier_id)
            return payload(session, parent)

    @router.get("/dossiers/{dossier_id}/coverage/history")
    def history(product: Product, dossier_id: str, request: Request,
                pack_id: str = Query(max_length=120), connector: str = Query(max_length=80),
                stream: str = Query(max_length=200), offset: int = Query(default=0, ge=0, le=100000),
                as_of: datetime | None = None):
        from .product_feed_check_history import payload as checks

        identity = actor(request)
        with service.db.session() as session:
            parent = access(session, identity, product, dossier_id)
            return checks(session, parent, pack_id, connector, stream, offset=offset, as_of=as_of)
