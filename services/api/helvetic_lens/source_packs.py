"""Organization subscriptions over the shared official regulatory corpus."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from . import jobs as durable_jobs
from .config import DomainError
from .db import utcnow
from .models import (
    Job,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryWork,
    SourcePackChangeRequest,
    SourcePackDefinition,
    SourcePackSubscription,
)
from .source_capabilities import SOURCE_CAPABILITY_INDEX

SOURCE_PACK_CATALOGUE_REVISION = "2026-09-04.1"
STARTER_ID = "swiss-federal-starter"
BACKFILL_LIMIT = 500
LOCALES = ("de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH")


def _localized(en: str, de: str, fr: str, it: str, rm: str) -> dict[str, str]:
    return {"en-CH": en, "de-CH": de, "fr-CH": fr, "it-CH": it, "rm-CH": rm}


PACK_DEFINITIONS = (
    {
        "id": STARTER_ID,
        "parent_id": None,
        "position": 0,
        "name_json": _localized(
            "Swiss Federal Starter",
            "Schweizer Bundes-Starter",
            "Pack fédéral suisse de départ",
            "Pacchetto federale svizzero iniziale",
            "Pachet federal svizzer da partenza",
        ),
        "description_json": _localized(
            "A transparent starter assembled from five independently controllable official-source packs.",
            "Ein transparenter Einstieg aus fünf einzeln steuerbaren amtlichen Quellenpaketen.",
            "Un point de départ transparent composé de cinq packs de sources officielles contrôlables séparément.",
            "Un avvio trasparente composto da cinque pacchetti di fonti ufficiali controllabili separatamente.",
            "In punct da partenza transparent cun tschintg pachets da funtaunas uffizialas controllabels separadamain.",
        ),
        "expected_first_data_json": _localized(
            "Existing shared records appear first; bounded historical discovery continues in the background.",
            "Zuerst erscheinen vorhandene gemeinsame Einträge; die begrenzte historische Suche läuft im Hintergrund weiter.",
            "Les données partagées existantes apparaissent d’abord; la recherche historique limitée continue en arrière-plan.",
            "Prima compaiono i dati condivisi esistenti; la ricerca storica limitata continua in background.",
            "Ils records communabels existents cumparan l’emprim; la tschertga istorica limitada cuntinuescha en il fund.",
        ),
        "filters_json": {"children": []},
    },
    {
        "id": "fedlex-legislation",
        "parent_id": STARTER_ID,
        "position": 10,
        "name_json": _localized("Fedlex legislation", "Fedlex-Recht", "Législation Fedlex", "Legislazione Fedlex", "Legislaziun Fedlex"),
        "description_json": _localized(
            "Federal acts, ordinances, and official publications from Fedlex.",
            "Bundesgesetze, Verordnungen und amtliche Veröffentlichungen aus Fedlex.",
            "Lois fédérales, ordonnances et publications officielles de Fedlex.",
            "Leggi federali, ordinanze e pubblicazioni ufficiali da Fedlex.",
            "Leschas federalas, ordinaziuns e publicaziuns uffizialas da Fedlex.",
        ),
        "expected_first_data_json": _localized(
            "Saved corpus matches appear immediately; reconciliation fills bounded catalogue pages.",
            "Gespeicherte Treffer erscheinen sofort; der Abgleich ergänzt begrenzte Katalogseiten.",
            "Les correspondances enregistrées apparaissent immédiatement; le rapprochement complète des pages limitées.",
            "Le corrispondenze salvate appaiono subito; la riconciliazione completa pagine limitate.",
            "Ils resultats memorisads cumparan immediat; la reconciliaziun cumplettescha paginas limitadas.",
        ),
        "filters_json": {"streams": [["fedlex", value] for value in ("rss-de", "rss-fr", "rss-it", "reconcile-cc", "reconcile-oc", "reconcile-fga")]},
    },
    {
        "id": "fedlex-consultations",
        "parent_id": STARTER_ID,
        "position": 20,
        "name_json": _localized("Federal consultations", "Vernehmlassungen", "Consultations fédérales", "Consultazioni federali", "Consultaziuns federalas"),
        "description_json": _localized(
            "Federal consultations, drafts, and explanatory material before enactment.",
            "Vernehmlassungen, Entwürfe und Erläuterungen vor dem Inkrafttreten.",
            "Consultations, projets et documents explicatifs avant leur adoption.",
            "Consultazioni, progetti e documenti esplicativi prima dell’adozione.",
            "Consultaziuns, sbozs e documents explicativs avant l’adopziun.",
        ),
        "expected_first_data_json": _localized(
            "Current saved consultations appear first; catalogue discovery is bounded.",
            "Zuerst erscheinen gespeicherte laufende Vernehmlassungen; die Katalogsuche ist begrenzt.",
            "Les consultations enregistrées apparaissent d’abord; la découverte du catalogue est limitée.",
            "Le consultazioni salvate appaiono per prime; la scoperta del catalogo è limitata.",
            "Las consultaziuns memorisadas cumparan l’emprim; la tschertga dal catalog è limitada.",
        ),
        "filters_json": {"streams": [["fedlex", "consultations"]]},
    },
    {
        "id": "swiss-parliament",
        "parent_id": STARTER_ID,
        "position": 30,
        "name_json": _localized("Swiss Parliament", "Schweizer Parlament", "Parlement suisse", "Parlamento svizzero", "Parlament svizzer"),
        "description_json": _localized(
            "Parliamentary affairs, initiatives, bills, and official notices.",
            "Parlamentsgeschäfte, Initiativen, Vorlagen und amtliche Mitteilungen.",
            "Objets parlementaires, initiatives, projets et communications officielles.",
            "Oggetti parlamentari, iniziative, disegni e comunicati ufficiali.",
            "Fatschentas parlamentaras, iniziativas, projects e communicaziuns uffizialas.",
        ),
        "expected_first_data_json": _localized(
            "Recent and already saved affairs appear first; the full catalogue advances in pages.",
            "Aktuelle und gespeicherte Geschäfte erscheinen zuerst; der Gesamtkatalog wächst seitenweise.",
            "Les objets récents et enregistrés apparaissent d’abord; le catalogue complet avance par pages.",
            "Gli oggetti recenti e salvati appaiono per primi; il catalogo completo avanza per pagine.",
            "Fatschentas actualas e memorisadas cumparan l’emprim; il catalog cumplet progredescha per paginas.",
        ),
        "filters_json": {"streams": [["swiss-parliament", value] for value in ("recent", "active", "catalogue", "notices")]},
    },
    {
        "id": "federal-courts",
        "parent_id": STARTER_ID,
        "position": 40,
        "name_json": _localized("Federal courts", "Bundesgerichte", "Tribunaux fédéraux", "Tribunali federali", "Tribunals federals"),
        "description_json": _localized(
            "Published decisions from the Federal Supreme Court and Federal Criminal Court.",
            "Veröffentlichte Entscheide des Bundesgerichts und Bundesstrafgerichts.",
            "Décisions publiées du Tribunal fédéral et du Tribunal pénal fédéral.",
            "Decisioni pubblicate del Tribunale federale e del Tribunale penale federale.",
            "Decisiuns publitgadas dal Tribunal federal e dal Tribunal penal federal.",
        ),
        "expected_first_data_json": _localized(
            "Latest saved decisions appear first; discovery does not promise a complete historical archive.",
            "Neueste gespeicherte Entscheide erscheinen zuerst; die Suche verspricht kein vollständiges historisches Archiv.",
            "Les dernières décisions enregistrées apparaissent d’abord; la découverte ne promet pas des archives complètes.",
            "Le ultime decisioni salvate appaiono per prime; la scoperta non promette un archivio storico completo.",
            "Las ultimas decisiuns memorisadas cumparan l’emprim; la tschertga na garantescha betg in archiv istoric cumplet.",
        ),
        "filters_json": {"streams": [["federal-supreme-court", "latest"], ["federal-supreme-court", "reconcile"], ["federal-criminal-court", "latest"]]},
    },
    {
        "id": "federal-policy-regulators",
        "parent_id": STARTER_ID,
        "position": 50,
        "name_json": _localized("Official policy and regulators", "Amtliche Politik und Aufsicht", "Politique et autorités officielles", "Politica e autorità ufficiali", "Politica ed autoritads uffizialas"),
        "description_json": _localized(
            "Official federal policy notices plus FINMA guidance, enforcement, and sanctions news.",
            "Amtliche Bundesmitteilungen sowie FINMA-Nachrichten zu Wegleitungen, Enforcement und Sanktionen.",
            "Communications fédérales officielles et actualités FINMA sur orientations, enforcement et sanctions.",
            "Comunicati federali ufficiali e notizie FINMA su orientamenti, enforcement e sanzioni.",
            "Communicaziuns federalas uffizialas e novitads FINMA davart directivas, enforcement e sancziuns.",
        ),
        "expected_first_data_json": _localized(
            "Recent saved notices appear first; these signals remain context and are never presented as enacted law.",
            "Zuerst erscheinen aktuelle gespeicherte Mitteilungen; diese Signale bleiben Kontext und gelten nie als Recht.",
            "Les avis récents enregistrés apparaissent d’abord; ces signaux restent contextuels et ne sont jamais du droit.",
            "Gli avvisi recenti salvati appaiono per primi; restano segnali contestuali e non sono mai diritto vigente.",
            "Las communicaziuns actualas memorisadas cumparan l’emprim; quests signals restan context e n’èn mai dretg vertent.",
        ),
        "filters_json": {"streams": [[connector, f"news-{language}"] for connector, languages in (("federal-news", ("de", "fr", "it", "rm", "en")), ("finma-news", ("de", "fr", "it", "en"))) for language in languages]},
    },
)


def seed_definitions(session: Session) -> None:
    now = utcnow()
    children = [item["id"] for item in PACK_DEFINITIONS if item["parent_id"] == STARTER_ID]
    for item in PACK_DEFINITIONS:
        values = dict(item)
        if values["id"] == STARTER_ID:
            values["filters_json"] = {"children": children}
        record = session.get(SourcePackDefinition, values["id"])
        if not record:
            record = SourcePackDefinition(id=values["id"], created_at=now)
            session.add(record)
        record.parent_id = values["parent_id"]
        record.revision = SOURCE_PACK_CATALOGUE_REVISION
        record.name_json = values["name_json"]
        record.description_json = values["description_json"]
        record.expected_first_data_json = values["expected_first_data_json"]
        record.filters_json = values["filters_json"]
        record.position = values["position"]
        record.active = True
        record.updated_at = now
    session.commit()


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()


def _targets(session: Session, pack_id: str) -> list[SourcePackDefinition]:
    definition = session.get(SourcePackDefinition, pack_id)
    if not definition or not definition.active:
        raise DomainError("The requested source pack was not found.", 404, "source_pack_not_found")
    if definition.parent_id is None:
        return list(
            session.scalars(
                select(SourcePackDefinition)
                .where(SourcePackDefinition.parent_id == definition.id, SourcePackDefinition.active.is_(True))
                .order_by(SourcePackDefinition.position)
            )
        )
    return [definition]


def _stream_keys(definition: SourcePackDefinition) -> set[tuple[str, str]]:
    return {tuple(item) for item in (definition.filters_json or {}).get("streams", [])}


def _subscription_payload(record: SourcePackSubscription | None) -> dict:
    if not record:
        return {
            "enabled": False,
            "state": "inactive",
            "progress_current": 0,
            "progress_total": 1,
            "included_event_count": 0,
            "failed_count": 0,
            "last_error": None,
            "activated_at": None,
            "deactivated_at": None,
        }
    return {
        "id": record.id,
        "enabled": record.enabled,
        "state": record.state,
        "progress_current": record.progress_current,
        "progress_total": record.progress_total,
        "included_event_count": record.included_event_count,
        "failed_count": record.failed_count,
        "last_error": record.last_error,
        "activated_at": _iso(record.activated_at),
        "deactivated_at": _iso(record.deactivated_at),
    }


def catalogue(session: Session, schedule_items: list[dict]) -> dict:
    schedules = {(item["connector"], item["stream"]): item for item in schedule_items}
    subscriptions = {item.pack_id: item for item in session.scalars(select(SourcePackSubscription))}
    requests = list(
        session.scalars(
            select(SourcePackChangeRequest)
            .where(SourcePackChangeRequest.status == "pending")
            .order_by(SourcePackChangeRequest.created_at.desc())
        )
    )
    request_by_pack = {item.pack_id: item for item in requests}
    definitions = list(
        session.scalars(
            select(SourcePackDefinition)
            .where(SourcePackDefinition.parent_id == STARTER_ID, SourcePackDefinition.active.is_(True))
            .order_by(SourcePackDefinition.position)
        )
    )
    items = []
    for definition in definitions:
        keys = _stream_keys(definition)
        capabilities = [SOURCE_CAPABILITY_INDEX[key].serialize() for key in keys]
        current_schedules = [schedules[key] for key in keys if key in schedules]
        gaps = list(dict.fromkeys(gap for item in capabilities for gap in item["known_gaps"]))
        successful = [item.get("last_success_at") for item in current_schedules if item.get("last_success_at")]
        pending = request_by_pack.get(definition.id)
        items.append(
            {
                "id": definition.id,
                "parent_id": definition.parent_id,
                "revision": definition.revision,
                "name": definition.name_json,
                "description": definition.description_json,
                "expected_first_data": definition.expected_first_data_json,
                "filters": definition.filters_json,
                "authorities": sorted({item["authority"] for item in capabilities}),
                "document_kinds": sorted({kind for item in capabilities for kind in item["document_kinds"]}),
                "languages": sorted({language for item in capabilities for language in item["languages"]}),
                "cadences": sorted({item["cadence"] for item in capabilities}),
                "historical_windows": list(dict.fromkeys(item["historical_window"] for item in capabilities)),
                "known_gaps": gaps,
                "capabilities": capabilities,
                "last_success_at": max(successful) if successful else None,
                "partial": any(item["catalogue_state"] == "partial" for item in capabilities)
                or any(item.get("availability") in {"partial", "degraded", "unavailable"} for item in current_schedules),
                "subscription": _subscription_payload(subscriptions.get(definition.id)),
                "pending_request": (
                    {"id": pending.id, "action": pending.requested_action, "created_at": _iso(pending.created_at)}
                    if pending
                    else None
                ),
            }
        )
    root = session.get(SourcePackDefinition, STARTER_ID)
    active_count = sum(item["subscription"]["enabled"] for item in items)
    starter_state = "active" if items and active_count == len(items) else "partial" if active_count else "inactive"
    return {
        "catalogue_revision": SOURCE_PACK_CATALOGUE_REVISION,
        "starter": {
            "id": root.id,
            "revision": root.revision,
            "name": root.name_json,
            "description": root.description_json,
            "expected_first_data": root.expected_first_data_json,
            "state": starter_state,
            "active_subpack_count": active_count,
            "subpack_count": len(items),
        },
        "items": items,
    }


def activate(
    session: Session, pack_id: str, *, organization_id: str, actor_user_id: str | None
) -> dict:
    now = utcnow()
    jobs = []
    all_reused = True
    for definition in _targets(session, pack_id):
        subscription = session.scalar(
            select(SourcePackSubscription).where(SourcePackSubscription.pack_id == definition.id)
        )
        if not subscription:
            subscription = SourcePackSubscription(pack_id=definition.id)
            session.add(subscription)
            session.flush()
        if subscription.enabled and subscription.state in {"queued", "backfilling", "active"}:
            existing = session.scalar(
                select(Job).where(
                    Job.organization_id == organization_id,
                    Job.target_id == subscription.id,
                    Job.type == "source_pack_backfill",
                    Job.state.in_(["queued", "dispatched", "running", "retrying"]),
                )
            )
            if existing:
                jobs.append(durable_jobs.serialize(session, existing))
            continue
        subscription.enabled = True
        subscription.state = "queued"
        subscription.revision += 1
        subscription.progress_current = 0
        subscription.progress_total = 1
        subscription.failed_count = 0
        subscription.last_error = None
        subscription.activated_by_user_id = actor_user_id
        subscription.activated_at = now
        subscription.deactivated_at = None
        subscription.updated_at = now
        all_reused = False
        job, _ = durable_jobs.enqueue(
            session,
            job_type="source_pack_backfill",
            target_type="source_pack",
            target_id=subscription.id,
            queue="ingest",
            idempotency_key=f"source-pack:{subscription.id}:{subscription.revision}",
            payload={"pack_id": definition.id},
            priority=5,
            progress_total=1,
            steps=[("Reuse saved shared-corpus events", {"limit": BACKFILL_LIMIT})],
            organization_id=organization_id,
        )
        jobs.append(durable_jobs.serialize(session, job))
        for request in session.scalars(
            select(SourcePackChangeRequest).where(
                SourcePackChangeRequest.pack_id == definition.id,
                SourcePackChangeRequest.status == "pending",
                SourcePackChangeRequest.requested_action == "activate",
            )
        ):
            request.status, request.resolved_at = "fulfilled", now
    session.commit()
    return {"pack_id": pack_id, "jobs": jobs, "reused": all_reused}


def deactivate(session: Session, pack_id: str) -> dict:
    now = utcnow()
    changed = 0
    for definition in _targets(session, pack_id):
        subscription = session.scalar(
            select(SourcePackSubscription).where(SourcePackSubscription.pack_id == definition.id)
        )
        if subscription and (subscription.enabled or subscription.state != "inactive"):
            subscription.enabled = False
            subscription.state = "inactive"
            subscription.revision += 1
            subscription.deactivated_at = now
            subscription.updated_at = now
            changed += 1
        for request in session.scalars(
            select(SourcePackChangeRequest).where(
                SourcePackChangeRequest.pack_id == definition.id,
                SourcePackChangeRequest.status == "pending",
                SourcePackChangeRequest.requested_action == "deactivate",
            )
        ):
            request.status, request.resolved_at = "fulfilled", now
    session.commit()
    return {"pack_id": pack_id, "deactivated": changed, "reused": changed == 0}


def request_change(
    session: Session,
    pack_id: str,
    action: str,
    *,
    requested_by_user_id: str | None,
) -> dict:
    if action not in {"activate", "deactivate"}:
        raise DomainError("Choose activate or deactivate.", 422, "source_pack_action_invalid")
    targets = _targets(session, pack_id)
    if len(targets) != 1:
        raise DomainError("Request a change for one visible subpack.", 422, "source_pack_request_granularity")
    existing = session.scalar(
        select(SourcePackChangeRequest).where(
            SourcePackChangeRequest.pack_id == pack_id,
            SourcePackChangeRequest.requested_action == action,
            SourcePackChangeRequest.status == "pending",
        )
    )
    if existing:
        return {"id": existing.id, "pack_id": pack_id, "action": action, "status": existing.status, "reused": True}
    record = SourcePackChangeRequest(
        pack_id=pack_id,
        requested_by_user_id=requested_by_user_id,
        requested_action=action,
    )
    session.add(record)
    session.commit()
    return {"id": record.id, "pack_id": pack_id, "action": action, "status": record.status, "reused": False}


def definition_matches(definition: SourcePackDefinition, connector: str, stream: str) -> bool:
    return (connector, stream) in _stream_keys(definition)


def enabled_organizations_for_stream(
    session: Session, connector: str, stream: str
) -> set[str]:
    result = set()
    for subscription, definition in session.execute(
        select(SourcePackSubscription, SourcePackDefinition)
        .join(SourcePackDefinition, SourcePackDefinition.id == SourcePackSubscription.pack_id)
        .where(SourcePackSubscription.enabled.is_(True))
        .execution_options(include_all_organizations=True)
    ):
        if definition_matches(definition, connector, stream):
            result.add(subscription.organization_id)
    return result


def run_backfill(session: Session, subscription_id: str, *, limit: int = BACKFILL_LIMIT) -> dict:
    subscription = session.get(SourcePackSubscription, subscription_id)
    if not subscription:
        raise DomainError("The source-pack subscription was not found.", 404, "source_pack_subscription_not_found")
    if not subscription.enabled:
        return {"status": "cancelled", "included": 0, "remaining": 0}
    definition = session.get(SourcePackDefinition, subscription.pack_id)
    if not definition:
        raise DomainError("The source-pack definition was not found.", 409, "source_pack_definition_missing")
    subscription.state = "backfilling"
    subscription.updated_at = utcnow()
    keys = _stream_keys(definition)
    stream_match = or_(
        *(
            and_(
                RegulatoryEvent.connector == connector,
                RegulatoryEvent.evidence_json["stream"].as_string() == stream,
            )
            for connector, stream in keys
        )
    )
    existing = select(RegulatoryEventState.id).where(
        RegulatoryEventState.organization_id == subscription.organization_id,
        RegulatoryEventState.event_id == RegulatoryEvent.id,
    ).exists()
    candidates = list(
        session.execute(
            select(RegulatoryEvent, RegulatoryWork)
            .join(RegulatoryWork, RegulatoryWork.id == RegulatoryEvent.work_id)
            .where(
                stream_match,
                ~existing,
            )
            .order_by(RegulatoryEvent.detected_at.desc(), RegulatoryEvent.id.desc())
            .limit(max(1, limit) + 1)
        )
    )
    matches = [event for event, _work in candidates]
    has_more = len(matches) > limit
    selected = matches[:limit]
    for event in selected:
        session.add(
            RegulatoryEventState(
                organization_id=subscription.organization_id,
                event_id=event.id,
            )
        )
    subscription.included_event_count += len(selected)
    subscription.progress_current = len(selected)
    subscription.progress_total = len(selected) + int(has_more)
    subscription.state = "partial" if has_more else "active"
    subscription.failed_count = 0
    subscription.last_error = None
    subscription.updated_at = utcnow()
    session.flush()
    return {
        "status": subscription.state,
        "pack_id": subscription.pack_id,
        "included": len(selected),
        "total_included": subscription.included_event_count,
        "remaining": 1 if has_more else 0,
        "shared_documents_created": 0,
        "shared_events_created": 0,
    }


def fail_backfill(session: Session, subscription_id: str, detail: str) -> None:
    subscription = session.get(SourcePackSubscription, subscription_id)
    if subscription:
        subscription.state = "failed"
        subscription.failed_count += 1
        subscription.last_error = detail[:2000]
        subscription.updated_at = utcnow()
