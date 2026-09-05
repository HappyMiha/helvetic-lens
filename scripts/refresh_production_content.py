"""Operator-only content refresh. Never drops schema, accounts, or evidence files.

Run with the deployed API environment after a verified backup, holding the host
deployment lock and stopping public entry points and background writers. Prepare
fetches and validates ALL replacement artifacts before reset is allowed. Reset
is a single transaction with an explicit table allowlist and account invariants.
No initialize()/migrations, synthetic evidence, cloud credentials, or user edits.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from helvetic_lens import models as m
from helvetic_lens.config import Settings
from helvetic_lens.db import Base, utcnow
from helvetic_lens.extraction import Fetched, Fetcher, extract
from helvetic_lens.regulatory_corpus import EventInput
from helvetic_lens.service import HelveticLens
from sqlalchemy import delete, func, select

CONTENT_TABLES = frozenset(
    [
        "action_decisions",
        "analyses",
        "ask_records",
        "assistant_conversations",
        "comparisons",
        "connector_item_errors",
        "connector_pages",
        "connector_receipts",
        "connector_runs",
        "connector_states",
        "digest_deliveries",
        "document_watches",
        "feed_states",
        "identity_decisions",
        "integration_logs",
        "job_steps",
        "jobs",
        "laws",
        "legacy_document_mappings",
        "monitoring_topic_drafts",
        "monitoring_topic_revisions",
        "monitoring_topics",
        "observations",
        "organization_relation_candidates",
        "organization_relation_reviews",
        "outbox_messages",
        "regulatory_dates",
        "regulatory_document_versions",
        "regulatory_event_states",
        "regulatory_event_user_states",
        "regulatory_events",
        "regulatory_expressions",
        "regulatory_identifiers",
        "regulatory_relations",
        "regulatory_works",
        "relation_candidates",
        "relation_impact_analyses",
        "scan_items",
        "scans",
        "source_pack_change_requests",
        "source_pack_subscriptions",
        "sources",
        "topic_event_matches",
        "versions",
    ]
)
IDENTITY_TABLES = (
    "users",
    "organizations",
    "organization_memberships",
    "organization_invitations",
    "user_sessions",
    "account_tokens",
    "digest_preferences",
    "security_events",
    "administrative_audit",
    "apertus_configuration",
    "prompt_configuration",
    "prompt_revisions",
    "platform_prompt_configuration",
    "organization_quotas",
)
PACK = "lugano-ticino-tech"
DOCUMENTS = [
    {
        "key": "lpd",
        "name": "LPD · Protezione dei dati / AI e SaaS",
        "kind": "act",
        "jurisdiction": "CH",
        "url": "https://fedlex.admin.ch/eli/cc/2022/491/it/pdf-a",
        "historical": "https://fedlex.admin.ch/eli/cc/2022/491/20230901/it/pdf-a",
        "date": "2023-09-01",
    },
    {
        "key": "opda",
        "name": "OPDa · Privacy engineering e trasferimenti di dati",
        "kind": "ordinance",
        "jurisdiction": "CH",
        "url": "https://fedlex.admin.ch/eli/cc/2022/568/it/pdf-a",
        "historical": "https://fedlex.admin.ch/eli/cc/2022/568/20250401/it/pdf-a",
        "date": "2025-04-01",
    },
    {
        "key": "lsin",
        "name": "LSIn · Cibersicurezza e segnalazione degli incidenti",
        "kind": "act",
        "jurisdiction": "CH",
        "url": "https://fedlex.admin.ch/eli/cc/2022/232/it/pdf-a",
        "historical": "https://fedlex.admin.ch/eli/cc/2022/232/20240101/it/pdf-a",
        "date": "2024-01-01",
    },
    {
        "key": "ticino-privacy",
        "name": "Ticino · LPDP: dati personali nei servizi pubblici",
        "kind": "act",
        "jurisdiction": "CH-TI",
        "url": "https://m3.ti.ch/CAN/RLeggi/public/index.php/raccolta-leggi/legge-piatta/num/50",
    },
    {
        "key": "ticino-startup",
        "name": "Ticino · LInn: innovazione economica e startup",
        "kind": "act",
        "jurisdiction": "CH-TI",
        "url": "https://www3.ti.ch/CAN/RLeggi/public/raccolta-leggi/legge/numero/11.3.3.1",
    },
    {
        "key": "ticino-funding",
        "name": "Ticino · Incentivi per investimenti immateriali delle startup",
        "kind": "official_notice",
        "jurisdiction": "CH-TI",
        "url": "https://m4.ti.ch/fileadmin/DFE/DE-USE/LINN/investimenti_immateriali_materiali/USE_DIRETTIVA_investimenti_immateriali.pdf",
    },
    {
        "key": "lugano-digital",
        "name": "Lugano · Strategia digitale 2025–2030 (strategia, non legge)",
        "kind": "official_notice",
        "jurisdiction": "CH-TI",
        "url": "https://www.lugano.ch/dam/jcr:d5bf54aa-0870-4323-ae6e-4f8f52f2ba90/strategia-digitale-lvga-2025-2030.pdf",
    },
    {
        "key": "ticino-digital",
        "name": "Ticino · Strategia per la trasformazione digitale",
        "kind": "official_notice",
        "jurisdiction": "CH-TI",
        "url": "https://www.ti.ch/fileadmin/can/portale-trasformazione-digitale/Diginotizie/Strategia_trasformazione_digitale/Strategia_Digitale.pdf",
    },
    {
        "key": "swiss-ai",
        "name": "Svizzera · Regolamentazione IA: lavori preparatori (non legge vigente)",
        "kind": "official_notice",
        "jurisdiction": "CH",
        "url": "https://www.bj.admin.ch/it/intelligenza-artificiale",
    },
    {
        "key": "cyber-duty",
        "name": "UFCS · Obbligo di segnalare ciberattacchi: campo di applicazione",
        "kind": "official_notice",
        "jurisdiction": "CH",
        "url": "https://www.bacs.admin.ch/it/informazioni-sullobbligo-di-segnalare",
    },
]
TOPICS = [
    (
        "AI governance · Svizzera e Lugano",
        "Seguire le regole e le iniziative su IA per un prodotto SaaS locale; distinguere proposte, strategie e obblighi vigenti.",
        ["intelligenza artificiale", "AI", "governance", "trasparenza"],
        [
            "artificial intelligence",
            "intelligence artificielle",
            "künstliche Intelligenz",
        ],
    ),
    (
        "Privacy engineering · LPD, OPDa e Ticino",
        "Valutare i cambiamenti per account, log, fornitori e dati personali, senza presumere che le norme per enti pubblici si applichino a ogni startup.",
        ["protezione dei dati", "dati personali", "LPD", "OPDa", "LPDP"],
        ["data protection", "Datenschutz", "protection des données"],
    ),
    (
        "Cybersecurity · Incident response e fornitori",
        "Monitorare sicurezza delle informazioni e segnalazioni; verificare l'assoggettamento concreto prima di attribuire obblighi alla società.",
        ["cibersicurezza", "ciberattacchi", "sicurezza delle informazioni", "LSIn"],
        ["cybersecurity", "cyberattacks", "Informationssicherheit"],
    ),
    (
        "Startup Ticino · Innovazione e incentivi",
        "Individuare misure di innovazione e finanziamento per startup software; verificare sede, organico e requisiti, senza dare per certa l'ammissibilità.",
        ["startup", "start-up", "innovazione", "investimenti", "LInn"],
        ["innovation", "incentivi", "imprese"],
    ),
    (
        "Lugano · Servizi digitali e sovranità dei dati",
        "Seguire strategie digitali, opportunità di collaborazione e servizi pubblici in Ticino, separando indirizzi strategici da norme vincolanti.",
        ["Lugano", "Ticino", "digitale", "sovranità", "servizi pubblici"],
        ["digital", "digitalizzazione", "trasformazione digitale"],
    ),
]


def emit(value):
    print(json.dumps(value, ensure_ascii=False, default=str), flush=True)


def identity_digest(session):
    # Read through Core to include every tenant; emit only the digest, never secrets.
    records = {}
    for name in IDENTITY_TABLES:
        table = Base.metadata.tables[name]
        records[name] = [
            dict(row)
            for row in session.execute(
                select(table).order_by(*table.primary_key.columns)
            ).mappings()
        ]
    return hashlib.sha256(
        json.dumps(records, sort_keys=True, default=str).encode()
    ).hexdigest()


def reset_content(service, *, organization_id, expected_users, backup_id):
    if not backup_id or len(backup_id) != 16 or not backup_id.endswith("Z"):
        raise ValueError("A verified backup ID is required")
    with service.db.session(include_all_organizations=True) as session:
        user_count = session.scalar(select(func.count()).select_from(m.User))
        tenant_ids = set(
            session.scalars(select(m.OrganizationMembership.organization_id))
        )
        if user_count != expected_users or tenant_ids != {organization_id}:
            raise ValueError(
                "Account/tenant scope changed; refuse the global corpus refresh"
            )
        active = session.scalar(
            select(func.count())
            .select_from(m.Job)
            .where(m.Job.state.not_in(["succeeded", "failed", "cancelled"]))
        )
        if active:
            raise ValueError("Background jobs must finish before refresh")
        before = identity_digest(session)
        deleted = {}
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in CONTENT_TABLES:
                deleted[table.name] = session.execute(delete(table)).rowcount
        if identity_digest(session) != before:
            raise RuntimeError(
                "Protected account/configuration data changed; rolling back"
            )
        session.commit()
        return {
            "deleted": deleted,
            "identity_digest": before,
            "users_preserved": user_count,
            "backup_id": backup_id,
            "artifact_files_deleted": 0,
        }


async def prepare(settings, path):
    fetcher = Fetcher(settings)
    cache = {}
    for spec in DOCUMENTS:
        for key in ("url", "historical"):
            if key not in spec:
                continue
            url = spec[key]
            fetched = await fetcher.fetch(url)
            filename = urlsplit(fetched.url).path.rsplit("/", 1)[-1] or "document.html"
            doc = await asyncio.to_thread(
                extract, fetched.body, fetched.content_type, filename
            )
            if len(doc.text) < 500 or not doc.passages:
                raise ValueError(f"Insufficient extracted evidence: {spec['key']}")
            cache[url] = {
                "url": fetched.url,
                "body": base64.b64encode(fetched.body).decode(),
                "content_type": fetched.content_type,
                "metadata": fetched.metadata,
                "sha256": hashlib.sha256(fetched.body).hexdigest(),
            }
            emit(
                {
                    "prepared": spec["key"],
                    "version": key,
                    "characters": len(doc.text),
                    "passages": len(doc.passages),
                    "extractor": doc.extractor,
                    "resolved": fetched.url,
                }
            )
    path.write_text(json.dumps(cache))
    path.chmod(0o600)
    emit({"prepared_artifacts": len(cache), "cache": str(path)})


class PreparedFetcher:
    def __init__(self, path):
        self.cache = json.loads(path.read_text())

    async def fetch(self, url, provider="native", **kwargs):
        value = self.cache[url]
        body = base64.b64decode(value["body"])
        if hashlib.sha256(body).hexdigest() != value["sha256"]:
            raise ValueError("Prepared artifact checksum mismatch")
        return Fetched(value["url"], body, value["content_type"], value["metadata"])


def configure_schedules(service):
    enabled = {
        ("fedlex", stream) for stream in ("rss-de", "rss-fr", "rss-it", "consultations")
    }
    enabled |= {("swiss-parliament", stream) for stream in ("recent", "active")}
    enabled |= {
        (connector, stream)
        for connector in ("federal-news", "finma-news")
        for stream in ("news-it", "news-en")
    }
    with service.db.session(include_all_organizations=True) as session:
        for schedule in session.scalars(select(m.ConnectorSchedule)):
            schedule.enabled = (schedule.connector, schedule.stream) in enabled
            if schedule.enabled:
                schedule.next_run_at = utcnow()
            schedule.last_job_id = None
            schedule.updated_at = utcnow()
        session.commit()
    emit(
        {"scheduled_streams": sorted(enabled), "historical_catalogue_crawls": "paused"}
    )


async def seed(service, cache):
    service.fetcher = PreparedFetcher(cache)
    with service.db.session() as session:
        if session.scalar(select(func.count()).select_from(m.Law)):
            raise ValueError(
                "Seed requires an empty content corpus; no duplicate insertion"
            )
        profile = session.get(m.Profile, service.tenant_record_id)
        profile.name = "HelveticLens · Lugano–Ticino AI & Startup Monitor"
        # Retain the existing factual company description; reduce unreadable matrix width.
        profile.business_areas = [
            "AI & product",
            "Privacy & legal",
            "Security & operations",
            "Growth & partnerships",
        ]
        profile.revision += 1
        labels = {
            locale: "Lugano–Ticino · AI, privacy & startup"
            for locale in ["it-CH", "en-CH", "de-CH", "fr-CH", "rm-CH"]
        }
        pack = session.get(m.SourcePackDefinition, PACK)
        if not pack:
            pack = m.SourcePackDefinition(id=PACK)
            session.add(pack)
        pack.parent_id = "swiss-federal-starter"
        pack.revision = "2026-09-05.1"
        pack.position = 60
        pack.name_json = labels
        pack.description_json = {
            k: "Curated official Swiss, Ticino and Lugano documents. Strategies and preparatory work are not enacted law. This is a selected set, not exhaustive coverage."
            for k in labels
        }
        pack.expected_first_data_json = {
            k: "Verified saved originals, historical comparisons and topic matches; use Scan to check watched URLs again."
            for k in labels
        }
        pack.filters_json = {"streams": [["curated-official", "lugano-ticino-tech"]]}
        pack.active = True
        session.commit()
    for spec in DOCUMENTS:
        law = await service.add_law({"name": spec["name"], "url": spec["url"]})
        with service.db.session() as session:
            record = session.get(m.Law, law["id"])
            current = session.get(m.Version, record.current_version_id)
            metadata = service.fetcher.cache[spec["url"]]["metadata"]
            version_date = metadata.get("eli_version_date")
            if version_date:
                current.declared_date = version_date
                current.date_provenance = "official_metadata"
            mapping = service.regulatory_corpus.map_legacy_document(
                session, record, current
            )
            mapping.work.kind = spec["kind"]
            event = service.regulatory_corpus.record_event(
                session,
                EventInput(
                    work_id=mapping.work.id,
                    expression_id=mapping.expression.id,
                    document_version_id=mapping.version.id,
                    authority=urlsplit(spec["url"]).hostname,
                    event_type="created",
                    detected_at=utcnow(),
                    provenance_method="legacy_mapping",
                    source_url=current.source_url,
                    connector="curated-official",
                    analysis_state="not_required",
                    evidence={
                        "stream": "lugano-ticino-tech",
                        "jurisdiction": spec["jurisdiction"],
                        "title": spec["name"],
                        "excerpt": current.text[:12000],
                        "artifact_sha256": service.fetcher.cache[spec["url"]]["sha256"],
                        "note": "First monitored snapshot, not a claim of a newly enacted law or newly published notice.",
                    },
                ),
            )
            session.add(m.RegulatoryEventState(event_id=event.id))
            current_id = current.id
            session.commit()
        if spec.get("historical"):
            imported = await service.import_version(
                law["id"],
                body=None,
                filename="",
                text="",
                url=spec["historical"],
                declared_date=spec["date"],
                synthetic=False,
                preview=False,
            )
            comparison = service.create_comparison(
                imported["version"]["id"], current_id
            )
            emit({"comparison": spec["key"], "id": comparison["id"]})
        emit({"seeded": spec["key"], "law_id": law["id"]})
    for pack_id in (
        PACK,
        "fedlex-legislation",
        "fedlex-consultations",
        "swiss-parliament",
        "federal-policy-regulators",
    ):
        result = service.activate_source_pack(pack_id, None)
        emit({"activated_pack": pack_id, "state": result.get("state")})
    for index, (name, goal, concepts, synonyms) in enumerate(TOPICS):
        topic = service.create_monitoring_topic(
            {
                "name": name,
                "goal": goal,
                "concepts": concepts,
                "synonyms": synonyms,
                "exclusions": [],
                "jurisdictions": ["CH", "CH-TI"],
                "languages": ["it", "en", "de", "fr"],
                "source_pack_ids": [
                    PACK,
                    "fedlex-legislation",
                    "fedlex-consultations",
                    "swiss-parliament",
                    "federal-policy-regulators",
                ],
                "document_kinds": [
                    "act",
                    "ordinance",
                    "official_notice",
                    "consultation",
                    "initiative",
                    "parliamentary_business",
                ],
                "event_kinds": [
                    "created",
                    "new_version",
                    "amended",
                    "status_changed",
                    "notice_published",
                ],
                "importance_floor": "low",
            },
            idempotency_key=f"production-refresh-20260905-topic-{index}",
            actor_user_id=None,
        )
        emit({"topic": name, "id": topic["id"]})


async def refine_federal(service):
    """Prefer official structured HTML for legal diffs; retain every PDF original."""
    fetcher = Fetcher(service.settings)
    prepared = []
    for spec in DOCUMENTS[:3]:
        for side in ("historical", "url"):
            url = spec[side].removesuffix("/pdf-a")
            fetched = await fetcher.fetch(url)
            filename = urlsplit(fetched.url).path.rsplit("/", 1)[-1]
            document = await asyncio.to_thread(
                extract, fetched.body, fetched.content_type, filename
            )
            if document.content_type != "text/html" or len(document.text) < 10000:
                raise ValueError("Expected full official structured legal HTML")
            prepared.append((spec, side, url, fetched, document))
    # All six artifacts are fetched before any database update; one transaction.
    with service.db.session() as session:
        old_ids = {}
        for spec, side, url, fetched, document in prepared:
            law = session.scalar(
                select(m.Law).where(
                    m.Law.canonical_identity == service.canonical_document_identity(url)
                )
            )
            version, _ = service.save_snapshot(
                session,
                law,
                document,
                "historical_url" if side == "historical" else "live",
                fetched.url,
                fetched.metadata["eli_version_date"],
                metadata=fetched.metadata,
            )
            version.date_provenance = "official_metadata"
            if side == "historical":
                old_ids[spec["key"]] = version.id
            else:
                law.url = url
                law.current_version_id = version.id
                law.last_checked = utcnow()
                service.regulatory_corpus.map_legacy_document(session, law, version)
                old = session.get(m.Version, old_ids[spec["key"]])
                comparison = service.ensure_comparison(
                    session, old, version, "saved_versions"
                )
                watch = service.watch(session, law.id)
                watch.selected_baseline_version_id = old.id
                emit(
                    {
                        "structured_comparison": spec["key"],
                        "id": comparison.id,
                        "counts": comparison.diff.get("counts"),
                    }
                )
        session.commit()


async def sources(service):
    definitions = [
        (
            "Lugano · Strategia digitale e documentazione",
            "https://www.lugano.ch/news/20250905-strategia-digitale-2025-2030/",
        ),
        (
            "Ticino · Legge per l'innovazione economica",
            "https://www3.ti.ch/CAN/RLeggi/public/raccolta-leggi/legge/numero/11.3.3.1",
        ),
        (
            "UFG · Regolamentazione dell'intelligenza artificiale",
            "https://www.bj.admin.ch/it/intelligenza-artificiale",
        ),
    ]
    for name, url in definitions:
        with service.db.session() as session:
            source = session.scalar(select(m.Source).where(m.Source.url == url))
            if source is None:
                source = m.Source(name=name, url=url, section="/", provider="native")
                session.add(source)
                session.commit()
            source_id = source.id
        result = await service.discover(source_id)
        emit(
            {
                "source": name,
                "verified_documents": result.get("verified_count"),
                "errors": result.get("error_count"),
                "scope": "one listing page",
            }
        )


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "prepare",
            "rehearse",
            "reset",
            "seed",
            "refine-federal",
            "sources",
            "schedules",
            "analyse",
            "verify",
        ],
    )
    parser.add_argument("--organization", required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--backup-id")
    parser.add_argument("--expected-users", type=int, default=2)
    parser.add_argument("--confirm-content-reset", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    if args.command == "prepare":
        return await prepare(settings, args.cache)
    if args.command == "rehearse":
        from helvetic_lens.source_packs import seed_definitions

        with tempfile.TemporaryDirectory(
            prefix="helvetic-refresh-rehearsal-"
        ) as directory:
            isolated = settings.model_copy(
                update={
                    "database_url": "sqlite:///:memory:",
                    "data_dir": Path(directory),
                    "app_environment": "test",
                }
            )
            rehearsal = HelveticLens(isolated, organization_id=args.organization)
            Base.metadata.create_all(rehearsal.db.engine)
            with rehearsal.db.session() as session:
                session.add(
                    m.Organization(
                        id=args.organization, name="Rehearsal", slug="rehearsal"
                    )
                )
                session.flush()
                for index in range(args.expected_users):
                    user = m.User(
                        email=f"rehearsal-{index}@example.invalid",
                        name="Test",
                        password_hash="unchanged",
                    )
                    session.add(user)
                    session.flush()
                    session.add(
                        m.OrganizationMembership(
                            user_id=user.id, role="organization_admin"
                        )
                    )
                session.add(
                    m.Profile(
                        id=rehearsal.tenant_record_id,
                        description="Test software company",
                    )
                )
                session.commit()
                seed_definitions(session)
            await seed(rehearsal, args.cache)
            with rehearsal.db.session() as session:
                for job in session.scalars(select(m.Job)):
                    job.state = "succeeded"
                session.commit()
            result = reset_content(
                rehearsal,
                organization_id=args.organization,
                expected_users=args.expected_users,
                backup_id="20260905T000000Z",
            )
            assert result["users_preserved"] == args.expected_users
            assert result["deleted"]["laws"] == len(DOCUMENTS)
            assert result["deleted"]["versions"] == 13
            emit({"rehearsal": "passed", "reset": result})
            rehearsal.db.engine.dispose()
        return
    service = HelveticLens(settings, organization_id=args.organization)
    try:
        with service.organization_runtime():
            if args.command == "reset":
                if not args.confirm_content_reset:
                    raise ValueError("Explicit reset flag required")
                prepared = PreparedFetcher(args.cache)
                for spec in DOCUMENTS:
                    for key in ("url", "historical"):
                        if key in spec:
                            await prepared.fetch(spec[key])
                emit(
                    reset_content(
                        service,
                        organization_id=args.organization,
                        expected_users=args.expected_users,
                        backup_id=args.backup_id,
                    )
                )
            elif args.command == "seed":
                await seed(service, args.cache)
            elif args.command == "schedules":
                configure_schedules(service)
            elif args.command == "refine-federal":
                await refine_federal(service)
            elif args.command == "sources":
                await sources(service)
            elif args.command == "analyse":
                with service.db.session() as session:
                    ids = list(
                        session.scalars(
                            select(m.Comparison.id)
                            .join(m.Law, m.Law.id == m.Comparison.law_id)
                            .where(
                                m.Comparison.new_version_id == m.Law.current_version_id
                            )
                        )
                    )
                for comparison_id in ids:
                    job = service.enqueue_analysis(comparison_id, "en-CH")
                    emit(
                        {
                            "analysis_job": job["id"],
                            "comparison": comparison_id,
                            "state": job["state"],
                        }
                    )
            else:
                with service.db.session(include_all_organizations=True) as session:
                    emit(
                        {
                            "users": session.scalar(
                                select(func.count()).select_from(m.User)
                            ),
                            "identity_digest": identity_digest(session),
                        }
                    )
                emit(service.impact_matrix("en-CH"))
    finally:
        service.db.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
