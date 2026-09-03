import asyncio
from datetime import UTC, datetime

import httpx
from sqlalchemy import func, select

from helvetic_lens.broad_official_connector import FederalNewsConnector, FinmaNewsConnector
from helvetic_lens.fedlex_connector import FedlexConsultationConnector
from helvetic_lens.models import ConnectorReceipt, RegulatoryRelation, RegulatoryWork

NOW = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)


async def no_sleep(_):
    return None


def federal_item(identity="news-1", title="Consultation on data law"):
    return {
        "id": identity,
        "langGroupId": identity,
        "title": title,
        "description": "The Federal Council opened an official consultation.",
        "publishDate": "2026-09-02T08:00:00Z",
        "newsCategory": "Press release",
        "publishers": [{"name": "Federal Council"}],
        "topics": [{"id": 427, "name": "Consultations"}],
        "content": {"systemdata": {"updatedAt": "2026-09-02T08:05:00Z", "version": 2}},
    }


def federal_transport(items=None, total=None):
    items = [federal_item()] if items is None else items

    async def handler(request):
        if request.url.host == "d-nsbc-p.admin.ch":
            return httpx.Response(
                200,
                request=request,
                json={
                    "items": items,
                    "pageResults": len(items) if total is None else total,
                    "limit": 25,
                    "offset": int(request.url.params.get("offset", 0)),
                },
            )
        return httpx.Response(
            200,
            request=request,
            text="<html><main><h1>Official consultation</h1><p>The Federal Council opened a consultation about amendments to the data law. This is an official context publication.</p></main></html>",
            headers={"content-type": "text/html"},
        )

    return httpx.MockTransport(handler)


def finma_transport(valid=True):
    async def handler(request):
        if "/rss/news" in request.url.path:
            body = (
                """<rss><channel><title>FINMA</title><item><guid>finma-1</guid><title>FINMA publishes guidance</title><link>https://www.finma.ch/de/news/2026/guidance/</link><description>Official guidance for supervised institutions.</description><category>Guidance</category><pubDate>Wed, 02 Sep 2026 08:00:00 GMT</pubDate></item></channel></rss>"""
                if valid
                else "<rss><channel/></rss>"
            )
            return httpx.Response(200, request=request, text=body, headers={"content-type": "text/xml"})
        return httpx.Response(
            200,
            request=request,
            text="<html><main><h1>FINMA publishes guidance</h1><p>Official guidance for supervised institutions with sufficient detail for monitoring and review.</p></main></html>",
            headers={"content-type": "text/html"},
        )

    return httpx.MockTransport(handler)


def sparql_payload(rows):
    return {
        "head": {"vars": sorted({key for row in rows for key in row})},
        "results": {
            "bindings": [
                {
                    key: (
                        {"type": "literal", "value": value[0], "xml:lang": value[1]}
                        if isinstance(value, tuple)
                        else {
                            "type": "uri" if str(value).startswith("http") else "literal",
                            "value": str(value),
                        }
                    )
                    for key, value in row.items()
                }
                for row in rows
            ]
        },
    }


def consultation_transport():
    work = "https://fedlex.data.admin.ch/eli/dl/proj/2026/99/cons_1"
    impact = "https://fedlex.data.admin.ch/eli/cc/2022/491"

    async def handler(request):
        query = request.url.params.get("query", "")
        if "GROUP BY ?work" in query:
            rows = [
                {
                    "work": work,
                    "status": "https://fedlex.data.admin.ch/vocabulary/consultation-status/5",
                    "start": "2026-08-01",
                    "end": "2026-11-01",
                }
            ]
        elif "SELECT ?work" in query:
            rows = [{"work": work}]
        else:
            rows = [
                {
                    "title": ("Änderung des Datenschutzgesetzes", "de"),
                    "description": (
                        "Vernehmlassung zur Änderung des Datenschutzgesetzes mit ausführlicher Beschreibung.",
                        "de",
                    ),
                    "eventId": "2026-99",
                    "status": "https://fedlex.data.admin.ch/vocabulary/consultation-status/5",
                    "start": "2026-08-01",
                    "end": "2026-11-01",
                    "institution": "https://ld.admin.ch/office/1",
                    "impact": impact,
                },
                {
                    "title": ("Modification de la loi sur la protection des données", "fr"),
                    "description": (
                        "Consultation officielle concernant la modification de la loi et ses effets.",
                        "fr",
                    ),
                    "eventId": "2026-99",
                    "status": "https://fedlex.data.admin.ch/vocabulary/consultation-status/5",
                    "start": "2026-08-01",
                    "end": "2026-11-01",
                    "impact": impact,
                },
            ]
        return httpx.Response(
            200,
            request=request,
            json=sparql_payload(rows),
            headers={"content-type": "application/sparql-results+json"},
        )

    return httpx.MockTransport(handler)


def test_federal_news_is_incremental_and_runner_deduplicates(harness):
    _, _, service, _ = harness
    connector = FederalNewsConnector(
        service.settings.model_copy(update={"allow_private_sources": True}),
        transport=federal_transport(),
        sleep=no_sleep,
        now=lambda: NOW,
    )
    page = asyncio.run(connector.discover_since(None, {}))
    assert page.complete and page.next_cursor["watermark"] == "2026-09-02T08:05:00Z"
    metadata = asyncio.run(connector.fetch_metadata(page.items[0]))
    assert metadata.kind == "official_notice" and metadata.metadata["notice_context_only"] is True
    first = asyncio.run(service.connector_runner.run_page(connector, stream=connector.stream))
    second = asyncio.run(service.connector_runner.run_page(connector, stream=connector.stream))
    assert first.persisted == 1 and second.status == "persisted"
    with service.db.session(include_all_organizations=True) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ConnectorReceipt)
                .where(ConnectorReceipt.connector == "federal-news")
            )
            == 1
        )


def test_federal_news_contract_drift_is_visible(harness):
    _, _, service, _ = harness
    connector = FederalNewsConnector(
        service.settings.model_copy(update={"allow_private_sources": True}),
        transport=federal_transport([{"title": "missing identity"}]),
        sleep=no_sleep,
        now=lambda: NOW,
    )
    try:
        asyncio.run(connector.discover_since(None, {}))
    except Exception as exc:
        assert getattr(exc, "code", None) == "connector_contract_drift"
    else:
        raise AssertionError("contract drift was accepted")


def test_finma_feed_preserves_notice_status_and_detects_drift(harness):
    _, _, service, _ = harness
    settings = service.settings.model_copy(update={"allow_private_sources": True})
    connector = FinmaNewsConnector(settings, transport=finma_transport(), sleep=no_sleep, now=lambda: NOW)
    page = asyncio.run(connector.discover_since(None, {}))
    metadata = asyncio.run(connector.fetch_metadata(page.items[0]))
    assert metadata.kind == "official_notice" and metadata.lifecycle_status == "published"
    report = asyncio.run(
        FinmaNewsConnector(
            settings, transport=finma_transport(False), sleep=no_sleep, now=lambda: NOW
        ).health()
    )
    assert report.status == "degraded" and report.source_contract["error_code"] == "connector_contract_drift"


def test_fedlex_consultation_preserves_json_and_exact_foreseen_impact(harness):
    _, _, service, _ = harness
    connector = FedlexConsultationConnector(
        service.settings.model_copy(update={"allow_private_sources": True}),
        page_size=5,
        transport=consultation_transport(),
        sleep=no_sleep,
        now=lambda: NOW,
    )
    page = asyncio.run(connector.discover_since(None, {}))
    metadata = asyncio.run(connector.fetch_metadata(page.items[0]))
    expressions = asyncio.run(connector.list_expressions(metadata))
    artifact = asyncio.run(connector.fetch_official_artifact(expressions[0]))
    relations = asyncio.run(connector.extract_relations(metadata))
    assert metadata.kind == "consultation"
    assert metadata.metadata["proposal_not_enacted_law"] is True
    assert artifact.content_type.startswith("application/sparql-results+json")
    assert {item.relation_type for item in relations} == {"potentially_impacts"}
    result = asyncio.run(service.connector_runner.run_page(connector, stream=connector.stream))
    assert result.persisted == 1
    with service.db.session(include_all_organizations=True) as session:
        work = session.scalar(select(RegulatoryWork).where(RegulatoryWork.kind == "consultation"))
        relation = session.scalar(
            select(RegulatoryRelation).where(RegulatoryRelation.subject_work_id == work.id)
        )
        assert relation.provenance_method == "official_metadata"
