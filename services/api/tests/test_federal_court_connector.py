import asyncio
from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy import func, select

from helvetic_lens.config import DomainError, Settings
from helvetic_lens.extraction import extract
from helvetic_lens.federal_court_connector import (
    FederalCourtConnector,
    federal_court_connectors,
)
from helvetic_lens.models import (
    ConnectorItemError,
    ConnectorReceipt,
    ConnectorState,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryIdentifier,
    RegulatoryRelation,
    RegulatoryWork,
)

DOCKETS = ("1C_100/2026", "4A_200/2026")
AZA = ("aza://20-08-2026-1C_100-2026", "aza://21-08-2026-4A_200-2026")


def main_index(challenge=False):
    if challenge:
        return "<html><body>Access denied CAPTCHA</body></html>"
    return """
    <html><main>
      <h1>Liste der neu aufgenommenen Entscheide</h1>
      <a href="?date=20260902&amp;lang=de&amp;mode=news">02.09.2026</a>
      <a href="?date=20260901&amp;lang=de&amp;mode=news">01.09.2026</a>
    </main></html>
    """


def date_index(day="02.09.2026", *, changed=False):
    subject = "Datenschutz und Auskunft" if not changed else "Datenschutz und Berichtigung"
    return f"""
    <html><main>
      <h1>Neue Entscheide</h1>
      <p>Liste der am {day} neu aufgenommenen Entscheide</p>
      <table>
        <tr><td></td><td>20.08.2026</td><td>
          <a href="https://search.bger.ch/ext/eurospider/live/de/php/aza/http/index.php?highlight_docid={AZA[0]}&amp;lang=de&amp;zoom=&amp;type=show_document">{DOCKETS[0]}</a>
        </td><td></td><td>Datenschutz*</td></tr>
        <tr><td></td><td></td><td></td><td></td><td>{subject}</td></tr>
        <tr><td></td><td>21.08.2026</td><td>
          <a href="https://search.bger.ch/ext/eurospider/live/de/php/aza/http/index.php?highlight_docid={AZA[1]}&amp;lang=de&amp;zoom=&amp;type=show_document">{DOCKETS[1]}</a>
        </td><td></td><td>Obligationenrecht</td></tr>
        <tr><td></td><td></td><td></td><td></td><td>Schadenersatz</td></tr>
      </table>
    </main></html>
    """


def decision(index, *, broken=False):
    if broken:
        return "<html><main>Decision temporarily unavailable</main></html>"
    if index == 0:
        heading = "Urteil vom 20. August 2026"
        chamber = "I. öffentlich-rechtliche Abteilung"
        subject = "Datenschutz und Auskunft (Art. 25 DSG)"
        body = "Art. 25 DSG; SR 235.1. Das Gericht prüft den Auskunftsanspruch."
    else:
        heading = "Arrêt du 21 août 2026"
        chamber = "Ire Cour de droit civil"
        subject = "Responsabilité contractuelle (art. 97 CO)"
        body = "L'art. 97 CO et RS 220 sont cités dans le raisonnement."
    return f"""
    <html><head><title>{DOCKETS[index]} 2026</title></head><body><main role="main">
      <h1>Federal Supreme Court decision search</h1>
      <div id="highlight_content"><div class="content">
        <div class="para">Bundesgericht</div>
        <div class="para">Tribunal fédéral</div>
        <div class="para">Tribunale federale</div>
        <div class="para">{DOCKETS[index]}</div>
        <div class="para">{heading}</div>
        <div class="para">{chamber}</div>
        <div class="para">Gegenstand</div>
        <div class="para">{subject}</div>
        <div class="para">Erwägungen:</div>
        <div class="para">{body}</div>
        <div class="para">Das Bundesgericht erkennt.</div>
      </div></div>
    </main></body></html>
    """


def court_transport(*, phase=None, fail_second=False, challenge=False, bad_robots=False):
    async def handler(request: httpx.Request):
        path = request.url.path
        if path == "/robots.txt":
            delay = 1 if bad_robots else 2
            return httpx.Response(200, text=f"User-agent: *\nCrawl-delay: {delay}\n")
        if path.endswith("/index_aza.php") and request.url.params.get("mode") == "index":
            return httpx.Response(200, text=main_index(challenge), headers={"content-type": "text/html"})
        if path.endswith("/index_aza.php") and request.url.params.get("mode") == "news":
            raw = request.url.params.get("date", "20260902")
            day = f"{raw[6:]}.{raw[4:6]}.{raw[:4]}"
            changed = bool(phase and phase.get("changed"))
            body = date_index(day, changed=changed) if raw == "20260902" else (
                f"<html><main><h1>Neue Entscheide</h1><p>Liste der am {day} neu aufgenommenen Entscheide</p></main></html>"
            )
            return httpx.Response(200, text=body, headers={"content-type": "text/html"})
        if path.endswith("/index.php") and request.url.params.get("type") == "show_document":
            identity = request.url.params.get("highlight_docid")
            index = AZA.index(identity)
            broken = fail_second and index == 1 and phase and phase.get("fail")
            return httpx.Response(
                200,
                text=decision(index, broken=broken),
                headers={"content-type": "text/html; charset=utf-8"},
            )
        return httpx.Response(404, text="fixture route missing")

    return httpx.MockTransport(handler)


def connector(settings, **kwargs):
    delays = kwargs.pop("delays", [])

    async def no_wait(value):
        delays.append(value)

    return FederalCourtConnector(
        settings,
        mode=kwargs.pop("mode", "latest"),
        item_page_size=kwargs.pop("item_page_size", 10),
        latest_overlap_dates=kwargs.pop("latest_overlap_dates", 1),
        transport=kwargs.pop("transport", court_transport()),
        sleep=no_wait,
        today=lambda: date(2026, 9, 3),
        now=lambda: datetime(2026, 9, 3, 8, 0, tzinfo=UTC),
        **kwargs,
    )


def test_federal_court_latest_overlap_and_reconciliation_are_bounded(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    latest = connector(settings, item_page_size=1)
    first = asyncio.run(latest.discover_since(None, {}))
    second = asyncio.run(latest.discover_since(first.next_cursor, {}))

    assert [item.external_identity for item in first.items] == [AZA[0]]
    assert [item.external_identity for item in second.items] == [AZA[1]]
    assert second.complete is True
    assert second.next_cursor == {"date_offset": 0, "item_offset": 0, "cycle": 1}

    reconcile = connector(settings, mode="reconcile")
    empty = asyncio.run(reconcile.discover_since(None, {}))
    assert empty.items == () and empty.empty_is_valid is True
    assert empty.next_cursor == {
        "insertion_date": "2025-01-02",
        "item_offset": 0,
        "cycle": 0,
    }


def test_federal_court_preserves_metadata_html_and_exact_citations(tmp_path):
    delays = []
    source = connector(Settings(_env_file=None, data_dir=tmp_path), delays=delays)
    page = asyncio.run(source.discover_since(None, {}))
    reference = page.items[0]
    metadata = asyncio.run(source.fetch_metadata(reference))
    expression = asyncio.run(source.list_expressions(metadata))[0]
    french_metadata = asyncio.run(source.fetch_metadata(page.items[1]))
    french_expression = asyncio.run(source.list_expressions(french_metadata))[0]
    artifact = asyncio.run(source.fetch_official_artifact(expression))
    relations = asyncio.run(source.extract_relations(metadata))
    extracted = extract(artifact.body, artifact.content_type, artifact.filename, "official_connector")

    assert metadata.kind == "court_decision"
    assert metadata.metadata["language"] == "de"
    assert metadata.metadata["chamber"] == "I. öffentlich-rechtliche Abteilung"
    assert metadata.metadata["decision_date"] == "2026-08-20"
    assert metadata.metadata["insertion_date"] == "2026-09-02"
    assert metadata.metadata["publication_intended"] is True
    assert metadata.metadata["artifact_sha256"] == artifact.expected_sha256
    assert metadata.metadata["jump_url"].startswith("https://relevancy.bger.ch/cgi-bin/JumpCGI")
    assert expression.language == "de" and expression.metadata["record_kind"] == "official_decision_html"
    assert french_metadata.metadata["language"] == "fr"
    assert french_expression.language == "fr"
    assert "Das Gericht prüft" in extracted.text
    assert {item.relation_type for item in relations} == {"cites"}
    assert {item.target.identifiers[0].scheme for item in relations} == {
        "sr_rs",
        "legal_abbreviation",
    }
    assert all(item.relation_type not in {"amends", "repeals"} for item in relations)
    assert delays and all(value >= 1.9 for value in delays)


def test_federal_court_runner_is_idempotent_and_retains_relations(harness):
    _, _, service, _ = harness
    source = connector(service.settings, latest_overlap_dates=1)
    first = asyncio.run(service.connector_runner.run_page(source, stream="latest"))
    repeated = asyncio.run(service.connector_runner.run_page(source, stream="latest"))
    assert first.status == "persisted" and repeated.status == "persisted"

    with service.db.session(include_all_organizations=True) as session:
        decisions = session.scalars(
            select(RegulatoryWork).where(RegulatoryWork.authority == "federal_supreme_court")
        ).all()
        assert len(decisions) == 2
        assert session.scalar(select(func.count()).select_from(RegulatoryDocumentVersion)) == 2
        assert session.scalar(select(func.count()).select_from(ConnectorReceipt)) == 2
        assert session.scalar(select(func.count()).select_from(RegulatoryRelation)) == 4
        events = session.scalars(select(RegulatoryEvent)).all()
        assert sum(item.event_type == "created" for item in events) == 2
        assert sum(item.event_type == "new_version" for item in events) == 2
        identifiers = session.scalars(select(RegulatoryIdentifier)).all()
        assert {item.normalized_value for item in identifiers if item.scheme == "court_docket"} == set(DOCKETS)


def test_federal_court_partial_failure_resumes_same_page(harness):
    _, _, service, _ = harness
    phase = {"fail": True}
    failing = connector(
        service.settings,
        transport=court_transport(phase=phase, fail_second=True),
    )
    first = asyncio.run(service.connector_runner.run_page(failing, stream="latest"))
    assert first.status == "partial" and first.persisted == 1
    with service.db.session(include_all_organizations=True) as session:
        state = session.scalar(select(ConnectorState).where(ConnectorState.stream == "latest"))
        assert state.cursor_json is None
        assert state.page_checkpoint_json["next_index"] == 1
        assert session.scalar(select(func.count()).select_from(ConnectorItemError)) == 1

    phase["fail"] = False
    repaired = connector(service.settings, transport=court_transport(phase=phase))
    result = asyncio.run(service.connector_runner.run_page(repaired, stream="latest"))
    assert result.status == "persisted" and result.persisted == 2, result.error


def test_federal_court_health_rejects_challenge_and_crawl_policy_drift(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    challenged = connector(settings, transport=court_transport(challenge=True))
    policy_drift = connector(settings, transport=court_transport(bad_robots=True))
    assert asyncio.run(challenged.health()).status == "degraded"
    report = asyncio.run(policy_drift.health())
    assert report.status == "degraded"
    assert report.source_contract["error_code"] == "connector_contract_drift"


def test_degraded_federal_court_health_never_advances_the_cursor(harness):
    _, _, service, _ = harness
    challenged = connector(service.settings, transport=court_transport(challenge=True))

    result = asyncio.run(service.connector_runner.run_page(challenged, stream="latest"))

    assert result.status == "degraded"
    assert result.next_cursor is None
    with service.db.session(include_all_organizations=True) as session:
        state = session.scalar(
            select(ConnectorState).where(
                ConnectorState.connector == "federal-supreme-court",
                ConnectorState.stream == "latest",
            )
        )
        assert state.health == "degraded"
        assert state.cursor_json is None


def test_federal_court_factory_and_invalid_stream(harness):
    _, _, service, _ = harness
    sources = federal_court_connectors(service.settings)
    assert {item.mode for item in sources} == {"latest", "reconcile"}
    assert all(item.manifest.minimum_interval_seconds == 2 for item in sources)
    with pytest.raises(DomainError) as error:
        asyncio.run(service.sync_federal_court("unknown"))
    assert error.value.code == "federal_court_stream_invalid"
