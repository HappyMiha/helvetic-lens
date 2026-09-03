import asyncio
from datetime import UTC, datetime

import httpx
import pytest
from conftest import policy
from sqlalchemy import func, select

from helvetic_lens.config import DomainError, Settings
from helvetic_lens.fedlex_connector import FedlexConnector, fedlex_connectors
from helvetic_lens.models import (
    ConnectorReceipt,
    ConnectorState,
    LegacyDocumentMapping,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryExpression,
    RegulatoryIdentifier,
    RegulatoryRelation,
    RegulatoryWork,
)

WORK = "https://fedlex.data.admin.ch/eli/cc/1999/404"
BASE_ACT = "https://fedlex.data.admin.ch/eli/oc/1999/404"
AMENDING_ACT = "https://fedlex.data.admin.ch/eli/oc/2024/1"
CURRENT_VERSION = WORK + "/20240303"
CURRENT_DE = CURRENT_VERSION + "/de"
CURRENT_FR = CURRENT_VERSION + "/fr"
FUTURE_DE = WORK + "/20290101/de"


def sparql(rows):
    return httpx.Response(200, json={"head": {"vars": []}, "results": {"bindings": rows}})


def binding(value, *, language=None):
    result = {"type": "uri" if value.startswith("http") else "literal", "value": value}
    if language:
        result["xml:lang"] = language
    return result


def rss(*items):
    entries = "".join(
        "<item>"
        f"<title>{title}</title><description>{title}</description>"
        f"<pubDate>{published}</pubDate><link>{url}</link>"
        f"<guid isPermaLink='false'>{url}</guid></item>"
        for title, published, url in items
    )
    return (
        "<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel>"
        "<title>Fedlex</title><link>https://fedlex.data.admin.ch</link>"
        "<lastBuildDate>Thu, 03 Sep 2026 03:42:12 GMT</lastBuildDate>"
        f"{entries}</channel></rss>"
    ).encode()


def metadata_rows():
    common = {
        "identifier": binding("19995395"),
        "historicalLegalId": binding("101"),
        "documentDate": binding("1999-04-18"),
        "entryInForce": binding("2000-01-01"),
        "status": binding("https://fedlex.data.admin.ch/vocabulary/enforcement-status/0"),
        "typeDocument": binding("https://fedlex.data.admin.ch/vocabulary/resource-type/10"),
        "basicAct": binding(BASE_ACT),
        "taxonomy": binding("https://fedlex.data.admin.ch/vocabulary/legal-taxonomy/4715"),
    }
    return [
        {
            **common,
            "titleExpression": binding(WORK + "/de"),
            "language": binding("http://publications.europa.eu/resource/authority/language/DEU"),
            "title": binding("Bundesverfassung der Schweizerischen Eidgenossenschaft"),
        },
        {
            **common,
            "titleExpression": binding(WORK + "/fr"),
            "language": binding("http://publications.europa.eu/resource/authority/language/FRA"),
            "title": binding("Constitution fédérale de la Confédération suisse"),
        },
    ]


def expression_rows():
    return [
        {
            "version": binding(FUTURE_DE.rsplit("/", 1)[0]),
            "versionDate": binding("2029-01-01"),
            "expression": binding(FUTURE_DE),
            "language": binding("http://publications.europa.eu/resource/authority/language/DEU"),
            "manifestation": binding(FUTURE_DE + "/html"),
            "format": binding("https://fedlex.data.admin.ch/vocabulary/user-format/html"),
            "file": binding("https://fedlex.data.admin.ch/filestore/future.html"),
        },
        {
            "version": binding(CURRENT_VERSION),
            "versionDate": binding("2024-03-03"),
            "expression": binding(CURRENT_DE),
            "language": binding("http://publications.europa.eu/resource/authority/language/DEU"),
            "manifestation": binding(CURRENT_DE + "/pdf-a"),
            "format": binding("https://fedlex.data.admin.ch/vocabulary/user-format/pdf-a"),
            "file": binding("https://fedlex.data.admin.ch/filestore/current-de.pdf"),
        },
        {
            "version": binding(CURRENT_VERSION),
            "versionDate": binding("2024-03-03"),
            "expression": binding(CURRENT_DE),
            "language": binding("http://publications.europa.eu/resource/authority/language/DEU"),
            "manifestation": binding(CURRENT_DE + "/html"),
            "format": binding("https://fedlex.data.admin.ch/vocabulary/user-format/html"),
            "file": binding("https://fedlex.data.admin.ch/filestore/current-de.html"),
        },
        {
            "version": binding(CURRENT_VERSION),
            "versionDate": binding("2024-03-03"),
            "expression": binding(CURRENT_FR),
            "language": binding("http://publications.europa.eu/resource/authority/language/FRA"),
            "manifestation": binding(CURRENT_FR + "/html"),
            "format": binding("https://fedlex.data.admin.ch/vocabulary/user-format/html"),
            "file": binding("https://fedlex.data.admin.ch/filestore/current-fr.html"),
        },
    ]


def relation_rows():
    return [
        {
            "relation": binding(WORK),
            "relationClass": binding("basicAct"),
            "fromWork": binding(WORK),
            "toWork": binding(BASE_ACT),
        },
        {
            "relation": binding(AMENDING_ACT + "/legal-analysis/LegalResourceImpact/1"),
            "relationClass": binding("impact"),
            "fromWork": binding(AMENDING_ACT),
            "toWork": binding(WORK),
            "relationType": binding(
                "https://fedlex.data.admin.ch/vocabulary/legal-resource-impact-type/amendment"
            ),
            "informationSource": binding(
                "https://fedlex.data.admin.ch/vocabulary/information-source/data-from-legiconso"
            ),
            "entryInForce": binding("2024-03-03"),
        },
    ]


def fedlex_transport(*, feed_items=None, reconciliation_rows=None, requests=None):
    feed_items = feed_items or [
        (
            "Bundesverfassung der Schweizerischen Eidgenossenschaft",
            "Wed, 02 Sep 2026 12:23:13 GMT",
            WORK,
        )
    ]
    requests = requests if requests is not None else []

    def respond(request):
        requests.append(str(request.url))
        if request.url.path.startswith("/api/rss-"):
            return httpx.Response(200, headers={"content-type": "application/xml"}, content=rss(*feed_items))
        if request.url.path == "/sparqlendpoint":
            query = request.url.params["query"]
            if "fedlex.data.admin.ch/eli/cc/" in query and "GROUP BY ?work" in query:
                return sparql(
                    reconciliation_rows
                    or [
                        {
                            "work": binding(WORK),
                            "documentDate": binding("1999-04-18"),
                            "latestVersionDate": binding("2024-03-03"),
                        }
                    ]
                )
            if "dct:identifier" in query:
                return sparql(metadata_rows())
            if "?manifestation ?format ?file" in query:
                return sparql(expression_rows())
            if "jolux:LegalResourceImpact" in query:
                return sparql(relation_rows())
            return sparql([{"work": binding(WORK)}])
        if request.url.path.endswith("/html"):
            return httpx.Response(
                302,
                headers={"location": "https://fedlex.data.admin.ch/filestore/fedlex-current.html"},
            )
        if request.url.path.endswith("fedlex-current.html"):
            return httpx.Response(
                200,
                headers={"content-type": "text/html; charset=utf-8"},
                content=policy(),
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    return httpx.MockTransport(respond)


def connector(settings, **values):
    return FedlexConnector(
        settings,
        transport=fedlex_transport(),
        sleep=lambda _: asyncio.sleep(0),
        now=lambda: datetime(2026, 9, 3, tzinfo=UTC),
        **values,
    )


@pytest.mark.asyncio
async def test_rss_discovery_uses_overlap_stable_eli_identity_and_watermark(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path, allow_private_sources=True)
    source = connector(settings, mode="rss", language="de")

    first = await source.discover_since(None, {})
    assert first.items[0].external_identity == WORK
    assert first.next_cursor == {"watermark": "2026-09-02T12:23:13Z", "overlap_days": 2}
    repeated = await source.discover_since(first.next_cursor, {})
    assert repeated.items == first.items
    assert repeated.empty_is_valid is True


@pytest.mark.asyncio
async def test_reconciliation_is_keyset_paged_and_resets_after_bounded_cycle(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path, allow_private_sources=True)
    requests = []
    source = FedlexConnector(
        settings,
        mode="reconcile",
        collection="cc",
        page_size=2,
        transport=fedlex_transport(
            reconciliation_rows=[
                {"work": binding(WORK), "latestVersionDate": binding("2024-03-03")},
                {"work": binding("https://fedlex.data.admin.ch/eli/cc/2022/491")},
            ],
            requests=requests,
        ),
        sleep=lambda _: asyncio.sleep(0),
    )
    page = await source.discover_since({"last_key": BASE_ACT, "cycle": 4}, {})
    assert page.next_cursor == {
        "last_key": "https://fedlex.data.admin.ch/eli/cc/2022/491",
        "cycle": 4,
    }
    query = httpx.URL(requests[-1]).params["query"]
    assert "GROUP BY ?work" in query and "FILTER(STR(?work) >" in query

    completed = FedlexConnector(
        settings,
        mode="reconcile",
        collection="cc",
        page_size=2,
        transport=fedlex_transport(reconciliation_rows=[{"work": binding(WORK)}]),
        sleep=lambda _: asyncio.sleep(0),
    )
    assert (await completed.discover_since(None, {})).next_cursor == {"last_key": "", "cycle": 1}


@pytest.mark.asyncio
async def test_jolux_metadata_versions_manifestations_and_relations_are_preserved(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path, allow_private_sources=True)
    requests = []
    source = FedlexConnector(
        settings,
        transport=fedlex_transport(requests=requests),
        sleep=lambda _: asyncio.sleep(0),
        now=lambda: datetime(2026, 9, 3, tzinfo=UTC),
    )
    reference = (await source.discover_since(None, {})).items[0]
    metadata = await source.fetch_metadata(reference)
    expressions = await source.list_expressions(metadata)
    relations = await source.extract_relations(metadata)

    assert metadata.identifiers[0].scheme == "eli_uri"
    assert metadata.identifiers[1].scheme == "sr_rs" and metadata.identifiers[1].value == "101"
    assert metadata.metadata["available_languages"] == ["de", "fr"]
    assert {item.language for item in expressions} == {"de", "fr"}
    assert next(item for item in expressions if item.expression_key == CURRENT_DE).artifact_url.endswith(
        "/html"
    )
    assert next(item for item in expressions if item.expression_key == FUTURE_DE).artifact_url is None
    assert (
        next(item for item in expressions if item.expression_key == CURRENT_DE).metadata["manifestations"][0][
            "format"
        ]
        == "html"
    )
    assert {item.relation_type for item in relations} == {"implements", "amends"}
    artifact = await source.fetch_official_artifact(
        next(item for item in expressions if item.expression_key == CURRENT_DE)
    )
    assert artifact and artifact.url.endswith("fedlex-current.html")
    assert any(url.endswith(CURRENT_DE + "/html") for url in requests)


def test_runner_deduplicates_catalogue_with_existing_add_law_flow(harness):
    client, fetcher, service, _ = harness
    fetcher.values[WORK] = policy()
    added = client.post("/api/laws", json={"url": WORK})
    assert added.status_code == 201, added.text

    source = FedlexConnector(
        service.settings,
        transport=fedlex_transport(),
        sleep=lambda _: asyncio.sleep(0),
        now=lambda: datetime(2026, 9, 3, tzinfo=UTC),
    )
    result = asyncio.run(service.connector_runner.run_page(source, stream=source.stream))
    assert result.status == "persisted" and result.persisted == 1, (result.error or "")[:1000]
    with service.db.session(include_all_organizations=True) as session:
        works = session.scalars(select(RegulatoryWork)).all()
        mapping = session.scalar(select(LegacyDocumentMapping))
        assert len(works) == 3  # monitored law plus two explicit official relation targets
        assert mapping.mapping_status == "matched"
        assert (
            session.scalar(
                select(func.count())
                .select_from(RegulatoryIdentifier)
                .where(
                    RegulatoryIdentifier.scheme == "eli_uri", RegulatoryIdentifier.normalized_value == WORK
                )
            )
            == 1
        )
        assert session.scalar(select(func.count()).select_from(ConnectorReceipt)) == 3
        assert session.scalar(select(func.count()).select_from(RegulatoryExpression)) >= 5
        assert session.scalar(select(func.count()).select_from(RegulatoryDocumentVersion)) >= 4
        assert session.scalar(select(func.count()).select_from(RegulatoryRelation)) == 2
        events = session.scalars(select(RegulatoryEvent)).all()
        assert {event.event_type for event in events} == {"new_version", "status_changed"}
        assert sum(event.event_type == "new_version" for event in events) == 3
        amending_work = session.scalar(
            select(RegulatoryWork)
            .join(RegulatoryIdentifier)
            .where(
                RegulatoryIdentifier.scheme == "eli_uri",
                RegulatoryIdentifier.normalized_value == AMENDING_ACT,
            )
        )
        amendment = session.scalar(
            select(RegulatoryRelation).where(RegulatoryRelation.relation_type == "amends")
        )
        assert amendment.subject_work_id == amending_work.id
        assert amendment.object_work_id == mapping.work_id
        state = session.scalar(select(ConnectorState))
        assert state.stream == "rss-de" and state.cursor_json["overlap_days"] == 2


def test_fedlex_stream_factory_includes_fast_feeds_and_all_catalogues(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    assert {item.stream for item in fedlex_connectors(settings)} == {
        "rss-de",
        "rss-fr",
        "rss-it",
        "reconcile-cc",
        "reconcile-oc",
        "reconcile-fga",
    }


def test_manual_sync_rejects_unknown_stream_without_network(harness):
    client, _, _, _ = harness
    response = client.post("/api/connectors/fedlex/reconcile-unknown/sync")
    assert response.status_code == 422
    assert response.json()["code"] == "fedlex_stream_invalid"


@pytest.mark.asyncio
async def test_contract_drift_does_not_infer_repeal_from_missing_metadata(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path, allow_private_sources=True)

    def respond(request):
        if request.url.path.startswith("/api/rss-"):
            return httpx.Response(200, content=rss(("Act", "Wed, 02 Sep 2026 12:23:13 GMT", WORK)))
        return sparql([])

    source = FedlexConnector(
        settings,
        transport=httpx.MockTransport(respond),
        sleep=lambda _: asyncio.sleep(0),
    )
    reference = (await source.discover_since(None, {})).items[0]
    with pytest.raises(DomainError) as error:
        await source.fetch_metadata(reference)
    assert error.value.code == "connector_contract_drift"
