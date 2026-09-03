import asyncio
import json
from datetime import UTC, datetime

import httpx
from sqlalchemy import func, select

from helvetic_lens.models import (
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryExpression,
    RegulatoryRelation,
    RegulatoryWork,
)
from helvetic_lens.official_notices_connector import ParliamentNoticeConnector

NOW = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)


def notice_row():
    return {
        "__metadata": {"etag": '"12"'},
        "Id": 10537,
        "Title_de": "Kommission berät das Datenschutzgesetz",
        "Title_fr": "La commission examine la loi sur la protection des données",
        "Title_it": "La Commissione esamina la legge sulla protezione dei dati",
        "Title_en": "Committee examines the Data Protection Act",
        "Title_rm": "La cumissiun examinescha la lescha da protecziun da datas",
        "EventDate": "2026-09-02T14:00:00Z",
        "Modified": "2026-09-02T13:58:15Z",
        "FileRef": "/press-releases/Pages/mm-test-2026-09-02.aspx",
        "HasDisplayPage": True,
        "MMAuthor": "29;#Committee",
        "NewsType": {"TermGuid": "35350bd0-5844-4d61-a634-3481d341c7f6"},
    }


def notice_transport(empty=False):
    async def handler(request: httpx.Request):
        if "/_api/" in request.url.path:
            rows = [] if empty else [notice_row()]
            return httpx.Response(
                200,
                request=request,
                content=json.dumps({"d": {"results": rows}}).encode(),
                headers={"content-type": "application/json;odata=verbose"},
            )
        language = request.url.params.get("lang", "1031")
        body = f"""
        <html lang="de"><main>
          <h1>Official notice {language}</h1>
          <p>The committee considered SR 235.1 and the official proposal in detail.</p>
          <p>See https://fedlex.data.admin.ch/eli/cc/2022/491 and
          https://www.parlament.ch/de/ratsbetrieb/suche-curia-vista/geschaeft?AffairId=20250069
          for the source documents. This paragraph makes the official body long enough.</p>
        </main></html>
        """
        return httpx.Response(
            200,
            request=request,
            text=body,
            headers={"content-type": "text/html; charset=utf-8"},
        )

    return httpx.MockTransport(handler)


async def no_sleep(_):
    return None


def test_parliament_notices_are_incremental_multilingual_and_context_only(harness):
    _, _, service, _ = harness
    connector = ParliamentNoticeConnector(
        service.settings.model_copy(update={"allow_private_sources": True}),
        transport=notice_transport(),
        sleep=no_sleep,
        now=lambda: NOW,
    )

    page = asyncio.run(connector.discover_since(None, {}))
    assert len(page.items) == 1
    assert page.complete is True
    assert page.next_cursor == {"modified": "2026-09-02T13:58:15+00:00", "id": 10537}
    assert "Modified+gt" in page.raw_provenance_ref

    metadata = asyncio.run(connector.fetch_metadata(page.items[0]))
    expressions = asyncio.run(connector.list_expressions(metadata))
    assert metadata.kind == "official_notice"
    assert metadata.metadata["notice_context_only"] is True
    assert {item.language for item in expressions} == {"de", "fr", "it", "en", "rm"}

    for expression in expressions:
        artifact = asyncio.run(connector.fetch_official_artifact(expression))
        assert b"SR 235.1" in artifact.body
        assert artifact.raw_provenance["official_page_sha256"]
    relations = asyncio.run(connector.extract_relations(metadata))
    assert {(item.target.identifiers[0].scheme, item.target.identifiers[0].value) for item in relations} == {
        ("eli_uri", "https://fedlex.data.admin.ch/eli/cc/2022/491"),
        ("parliament_affair_id", "20250069"),
        ("sr_rs", "235.1"),
    }


def test_notice_runner_persists_one_notice_event_without_duplicate_initial_version_event(harness):
    _, _, service, _ = harness
    connector = ParliamentNoticeConnector(
        service.settings.model_copy(update={"allow_private_sources": True}),
        transport=notice_transport(),
        sleep=no_sleep,
        now=lambda: NOW,
    )
    result = asyncio.run(service.connector_runner.run_page(connector, stream="notices"))
    assert result.status == "persisted"
    assert result.persisted == 1

    with service.db.session(include_all_organizations=True) as session:
        work = session.scalar(select(RegulatoryWork).where(RegulatoryWork.kind == "official_notice"))
        assert work is not None
        assert work.metadata_json["notice_context_only"] is True
        expression_ids = session.scalars(
            select(RegulatoryExpression.id).where(RegulatoryExpression.work_id == work.id)
        ).all()
        assert len(expression_ids) == 5
        assert session.scalar(
            select(func.count()).select_from(RegulatoryDocumentVersion).where(
                RegulatoryDocumentVersion.expression_id.in_(expression_ids)
            )
        ) == 5
        events = session.scalars(select(RegulatoryEvent).where(RegulatoryEvent.work_id == work.id)).all()
        assert [event.event_type for event in events] == ["notice_published"]
        assert session.scalar(
            select(func.count()).select_from(RegulatoryRelation).where(
                RegulatoryRelation.subject_work_id == work.id
            )
        ) == 3


def test_notice_health_accepts_an_empty_but_valid_recent_feed(harness):
    _, _, service, _ = harness
    connector = ParliamentNoticeConnector(
        service.settings.model_copy(update={"allow_private_sources": True}),
        transport=notice_transport(empty=True),
        sleep=no_sleep,
        now=lambda: NOW,
    )
    report = asyncio.run(connector.health())
    assert report.status == "healthy"
    assert report.source_contract["observed_rows"] == 0
