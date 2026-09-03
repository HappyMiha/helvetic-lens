import asyncio
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import func, select

from helvetic_lens.config import DomainError, Settings
from helvetic_lens.extraction import extract
from helvetic_lens.models import (
    ConnectorItemError,
    ConnectorReceipt,
    ConnectorState,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryExpression,
    RegulatoryIdentifier,
    RegulatoryRelation,
    RegulatoryWork,
)
from helvetic_lens.parliament_connector import ParliamentConnector, parliament_connectors

AFFAIR = "20250069"
RELATED_AFFAIR = "20250070"
ELI = "https://fedlex.data.admin.ch/eli/cc/171_10"
DOCUMENT = "https://www.parlament.ch/centers/documents/example.html"


def catalogue_rows(count=50, revision="2026-08-25T08:59:16Z", start=20250001):
    return [
        {"id": start + index, "updated": revision, "shortId": f"25.{index + 1:03d}"}
        for index in range(count)
    ]


def detail(
    affair_id=AFFAIR,
    *,
    language="de",
    revision="2026-08-25T08:59:16Z",
    state_id=230,
):
    translations = {
        "de": ("Epidemiengesetz. Teilrevision", "Beratung abgeschlossen"),
        "fr": ("Loi sur les épidémies. Révision", "Délibération terminée"),
        "it": ("Legge sulle epidemie. Revisione", "Deliberazione conclusa"),
    }
    title, state_name = translations.get(language, translations["fr"])
    short_id = "25.069" if affair_id == AFFAIR else f"25.{str(affair_id)[-3:]}"
    return {
        "id": int(affair_id),
        "updated": revision,
        "shortId": short_id,
        "language": language,
        "title": title,
        "additionalIndexing": "2841;04",
        "affairType": {"id": 1, "abbreviation": "BRG", "name": "Government bill"},
        "deposit": {"date": "2025-08-20T00:00:00Z", "legislativePeriod": 52, "session": "5210"},
        "descriptors": [{"id": 2841, "name": "Health"}],
        "state": {"id": state_id, "name": state_name},
        "texts": [
            {"type": {"id": 1, "name": "Text"}, "value": f"{title}. Art. 6; SR 171.10; {ELI}"},
        ],
        "roles": [{"person": {"id": 123, "firstName": "Ada", "lastName": "Example"}}],
        "relatedAffairs": [int(RELATED_AFFAIR)],
        "drafts": [
            {
                "index": 0,
                "texts": [{"type": {"id": 2}, "value": f"Official draft text in {language}."}],
                "links": [
                    {
                        "url": DOCUMENT,
                        "title": f"Official committee report {language}",
                        "date": "/Date(1784066400000+0200)/",
                    }
                ],
                "references": [],
                "preConsultations": [
                    {
                        "committee": {
                            "id": 19,
                            "abbreviation": "SGK-SR",
                            "name": "Social Security and Health Committee",
                        }
                    }
                ],
            }
        ],
    }


def parliament_transport(*, phase=None, fail_second=False, row_count=3):
    async def handler(request: httpx.Request):
        current_phase = phase.get("revision", phase.get("value", 0)) if phase else 0
        revision = "2026-08-26T09:00:00Z" if current_phase else "2026-08-25T08:59:16Z"
        state_id = 229 if current_phase else 230
        path = request.url.path.rstrip("/")
        if path == "/affairs" and request.url.params.get("format") == "json":
            page = int(request.url.params.get("pageNumber", "1"))
            rows = catalogue_rows(row_count, revision, start=int(AFFAIR)) if page == 1 else []
            return httpx.Response(200, json=rows)
        if path == "/affairs":
            return httpx.Response(
                200,
                text="<html><main>Page 1 of 1 (3 entries)</main></html>",
                headers={"content-type": "text/html"},
            )
        if path.startswith("/affairs/"):
            affair_id = path.rsplit("/", 1)[-1]
            if fail_second and affair_id == str(int(AFFAIR) + 1) and phase.get("fail", False):
                return httpx.Response(200, json={"id": int(affair_id), "language": "de"})
            requested = request.url.params.get("lang", "de")
            actual = "fr" if requested == "en" else requested
            return httpx.Response(
                200,
                json=detail(
                    affair_id,
                    language=actual,
                    revision=revision,
                    state_id=state_id,
                ),
            )
        if path == "/centers/documents/example.html":
            return httpx.Response(
                200,
                text="<html><main><h1>Official report</h1><p>This is the official related parliamentary document with enough text for extraction.</p></main></html>",
                headers={"content-type": "text/html"},
            )
        return httpx.Response(404, json={"error": "fixture route missing"})

    return httpx.MockTransport(handler)


def connector(settings, **kwargs):
    return ParliamentConnector(
        settings,
        mode=kwargs.pop("mode", "catalogue"),
        item_page_size=kwargs.pop("item_page_size", 10),
        transport=kwargs.pop("transport", parliament_transport()),
        sleep=lambda _: asyncio.sleep(0),
        now=lambda: datetime(2026, 9, 3, 8, 0, tzinfo=UTC),
        **kwargs,
    )


def test_parliament_catalogue_uses_bounded_slices_and_id_order(tmp_path):
    source = connector(Settings(_env_file=None, data_dir=tmp_path), item_page_size=2)
    health = asyncio.run(source.health())
    first = asyncio.run(source.discover_since(None, {}))
    second = asyncio.run(source.discover_since(first.next_cursor, {}))

    assert health.status == "healthy"
    assert health.source_contract["observed"]["ordered_by"] == "id"
    assert [item.external_identity for item in first.items] == [AFFAIR, str(int(AFFAIR) + 1)]
    assert first.next_cursor == {"item_offset": 2, "cycle": 0, "page_number": 1}
    assert [item.external_identity for item in second.items] == [str(int(AFFAIR) + 2)]
    assert second.complete is True
    assert second.next_cursor == {"page_number": 1, "item_offset": 0, "cycle": 1}


def test_parliament_preserves_real_languages_metadata_artifacts_and_exact_relations(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    source = connector(settings, item_page_size=1)
    reference = asyncio.run(source.discover_since(None, {})).items[0]
    metadata = asyncio.run(source.fetch_metadata(reference))
    expressions = asyncio.run(source.list_expressions(metadata))
    relations = asyncio.run(source.extract_relations(metadata))

    assert metadata.kind == "bill"
    assert metadata.lifecycle_status == "parliament-state:230"
    assert metadata.metadata["available_languages"] == ["de", "fr", "it"]
    assert "en" not in metadata.metadata["titles"]
    assert metadata.metadata["short_id"] == "25.069"
    assert metadata.metadata["committees"][0]["id"] == 19
    assert metadata.metadata["sessions"] == ["5210"]
    assert metadata.metadata["reference_candidates"]["sr_rs"] == ["171.10"]
    assert len(expressions) == 4  # three real language records plus one deduplicated document
    record = next(item for item in expressions if item.language == "de" and "record" in item.version_key)
    extracted = extract(
        asyncio.run(source.fetch_official_artifact(record)).body,
        "application/json",
        "record.json",
        "official_connector",
    )
    assert extracted.content_type == "application/json"
    assert any(item.get("json_path") == "$.title" for item in extracted.passages)
    assert {item.relation_type for item in relations} == {"cites", "potentially_impacts"}
    assert sum(item.relation_type == "cites" for item in relations) == 2
    assert next(item for item in relations if item.relation_type == "potentially_impacts").state == "proposed"


def test_parliament_runner_records_status_only_change_without_new_version(harness):
    _, _, service, _ = harness
    phase = {"value": 0}
    source = connector(
        service.settings,
        item_page_size=1,
        transport=parliament_transport(phase=phase, row_count=1),
    )
    first = asyncio.run(service.connector_runner.run_page(source, stream="catalogue"))
    assert first.status == "persisted"
    phase["value"] = 1
    second_source = connector(
        service.settings,
        item_page_size=1,
        transport=parliament_transport(phase=phase, row_count=1),
    )
    second = asyncio.run(service.connector_runner.run_page(second_source, stream="catalogue"))
    repeated = asyncio.run(service.connector_runner.run_page(second_source, stream="catalogue"))
    assert second.status == "persisted" and repeated.status == "persisted", second.error

    with service.db.session(include_all_organizations=True) as session:
        work = session.scalar(
            select(RegulatoryWork)
            .join(RegulatoryIdentifier)
            .where(
                RegulatoryIdentifier.scheme == "parliament_affair_id",
                RegulatoryIdentifier.normalized_value == AFFAIR,
            )
        )
        assert work.lifecycle_status == "parliament-state:229"
        assert work.metadata_json["is_final"] is True
        assert session.scalar(select(func.count()).select_from(RegulatoryExpression)) == 7
        assert session.scalar(select(func.count()).select_from(RegulatoryDocumentVersion)) == 4
        events = session.scalars(select(RegulatoryEvent).where(RegulatoryEvent.work_id == work.id)).all()
        assert sum(item.event_type == "created" for item in events) == 1
        assert sum(item.event_type == "new_version" for item in events) == 4
        assert sum(item.event_type == "status_changed" for item in events) == 1
        assert session.scalar(select(func.count()).select_from(ConnectorReceipt)) == 8
        assert session.scalar(select(func.count()).select_from(RegulatoryRelation)) == 3


def test_parliament_partial_failure_keeps_cursor_and_resumes(harness):
    _, _, service, _ = harness
    phase = {"fail": True}
    failing = connector(
        service.settings,
        item_page_size=2,
        transport=parliament_transport(phase=phase, fail_second=True),
    )
    first = asyncio.run(service.connector_runner.run_page(failing, stream="recent"))
    assert first.status == "partial" and first.persisted == 1
    with service.db.session(include_all_organizations=True) as session:
        state = session.scalar(select(ConnectorState).where(ConnectorState.stream == "recent"))
        assert state.cursor_json is None
        assert state.page_checkpoint_json["next_index"] == 1
        assert session.scalar(select(func.count()).select_from(ConnectorItemError)) == 1

    phase["fail"] = False
    repaired = connector(
        service.settings,
        item_page_size=2,
        transport=parliament_transport(phase=phase, fail_second=False),
    )
    result = asyncio.run(service.connector_runner.run_page(repaired, stream="recent"))
    assert result.status == "persisted" and result.persisted == 2, result.error


def test_parliament_active_stream_and_factory_are_bounded(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    active_ids = (AFFAIR, str(int(AFFAIR) + 1), str(int(AFFAIR) + 2))
    sources = parliament_connectors(settings, active_ids=active_ids)
    assert {item.stream for item in sources} == {"catalogue", "recent", "active"}
    active = connector(settings, mode="active", active_ids=active_ids, item_page_size=2)
    first = asyncio.run(active.discover_since(None, {}))
    second = asyncio.run(active.discover_since(first.next_cursor, {}))
    assert len(first.items) == 2 and first.complete is False
    assert len(second.items) == 1 and second.complete is True
    assert second.next_cursor == {"last_id": 0, "cycle": 1}


def test_parliament_invalid_stream_is_rejected(harness):
    _, _, service, _ = harness
    with pytest.raises(DomainError) as error:
        asyncio.run(service.sync_parliament("unknown"))
    assert error.value.code == "parliament_stream_invalid"
