import asyncio
import gzip
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import func, select

from helvetic_lens.config import DomainError
from helvetic_lens.connectors import (
    CONNECTOR_CONTRACT_VERSION,
    ConnectorArtifact,
    ConnectorExpression,
    ConnectorHealthReport,
    ConnectorHttpClient,
    ConnectorManifest,
    ConnectorMetadata,
    ConnectorRelation,
    DiscoveryPage,
    DiscoveryReference,
    OfficialConnector,
)
from helvetic_lens.models import (
    ConnectorItemError,
    ConnectorPage,
    ConnectorReceipt,
    ConnectorState,
    RegulatoryDocumentVersion,
    RegulatoryRelation,
    RegulatoryWork,
)
from helvetic_lens.official_source_contracts import (
    FEDERAL_COURT_CONTRACT,
    FEDERAL_CRIMINAL_COURT_CONTRACT,
    FEDERAL_NEWS_CONTRACT,
    FEDLEX_CONTRACT,
    FINMA_CONTRACT,
    PARLIAMENT_CONTRACT,
    probe_source_contract,
)
from helvetic_lens.regulatory_corpus import (
    DocumentInput,
    ExpressionInput,
    IdentifierInput,
)

MANIFEST = ConnectorManifest(
    name="fixture-official",
    authority="fixture-authority",
    connector_version="1.2.0",
    schema_version="fixture-v3",
    allowed_hosts=frozenset({"official.example"}),
    attribution="Fixture Authority Open Data, retrieved from the canonical official link.",
    source_contract={"format": "fixture-json", "page_size": 2},
)


@dataclass
class FixtureConnector(OfficialConnector):
    manifest: ConnectorManifest = MANIFEST
    fail_identity_once: str = ""
    empty: bool = False
    calls: list = field(default_factory=list)

    @property
    def references(self):
        return (
            DiscoveryReference(
                "law:a",
                "2026-09-01T12:00:00Z",
                "https://official.example/law/a",
                "fixture://catalogue/page-1#0",
            ),
            DiscoveryReference(
                "law:b",
                "2026-09-02T12:00:00Z",
                "https://official.example/law/b",
                "fixture://catalogue/page-1#1",
            ),
        )

    async def discover_since(self, cursor, page_checkpoint):
        self.calls.append(("discover", cursor, page_checkpoint))
        return DiscoveryPage(
            items=() if self.empty else self.references,
            next_cursor={"offset": 2},
            raw_provenance_ref="fixture://catalogue/page-1",
            schema_version=self.manifest.schema_version,
            complete=True,
            empty_is_valid=False,
        )

    async def fetch_metadata(self, reference):
        self.calls.append(("metadata", reference.external_identity))
        if self.fail_identity_once == reference.external_identity:
            self.fail_identity_once = ""
            raise DomainError("Fixture item failed once.", 502, "fixture_item_failure")
        suffix = reference.external_identity.rsplit(":", 1)[-1]
        return ConnectorMetadata(
            external_identity=reference.external_identity,
            source_revision=reference.source_revision,
            kind="act",
            title=f"Fixture Act {suffix.upper()}",
            canonical_url=reference.canonical_url,
            identifiers=(IdentifierInput("fixture_id", reference.external_identity),),
            lifecycle_status="in_force",
            metadata={"source_updated": reference.source_revision},
            raw_provenance={"catalogue_row": reference.raw_provenance_ref},
        )

    async def list_expressions(self, metadata):
        self.calls.append(("expressions", metadata.external_identity))
        suffix = metadata.external_identity.rsplit(":", 1)[-1]
        return (
            ConnectorExpression(
                language="de",
                expression_key=f"fixture:{suffix}:de",
                title=metadata.title,
                official_url=f"https://official.example/law/{suffix}/de",
                version_key=metadata.source_revision,
                artifact_url=f"https://official.example/law/{suffix}/de.html",
            ),
        )

    async def fetch_official_artifact(self, expression):
        self.calls.append(("artifact", expression.expression_key))
        body = (
            f"<html><main><h1>{expression.title}</h1>"
            "<p>Official fixture content with a stable legal provision.</p></main></html>"
        ).encode()
        return ConnectorArtifact(
            expression.artifact_url,
            body,
            "text/html; charset=utf-8",
            expression.artifact_url.rsplit("/", 1)[-1],
            raw_provenance={"fixture": True},
        )

    async def extract_relations(self, metadata):
        self.calls.append(("relations", metadata.external_identity))
        if metadata.external_identity != "law:b":
            return ()
        target = DocumentInput(
            kind="act",
            authority=self.manifest.authority,
            identifiers=(IdentifierInput("fixture_id", "law:a"),),
            title="Fixture Act A",
            stable_official_url="https://official.example/law/a",
            expression=ExpressionInput(
                language="de",
                key="fixture:a:de",
                title="Fixture Act A",
                official_url="https://official.example/law/a/de",
            ),
        )
        return (
            ConnectorRelation(
                target=target,
                relation_type="amends",
                state="confirmed",
                provenance_method="official_metadata",
                evidence={"catalogue_field": "amends", "target": "law:a"},
                rule_revision="fixture-v3",
            ),
        )

    async def health(self):
        self.calls.append(("health",))
        return ConnectorHealthReport(
            "healthy",
            "Fixture source contract is available.",
            datetime.now(UTC),
            {"required_fields": ["id", "updated", "url"]},
        )


def test_connector_page_persists_normalized_artifacts_relations_and_replays(harness):
    client, _, service, _ = harness
    connector = FixtureConnector()

    first = asyncio.run(service.connector_runner.run_page(connector, stream="catalogue"))
    assert first.status == "persisted"
    assert first.persisted == first.total == 2
    assert first.next_cursor == {"offset": 2}

    with service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(ConnectorReceipt)) == 2
        receipt = session.scalar(
            select(ConnectorReceipt).where(ConnectorReceipt.external_identity == "law:a")
        )
        assert receipt.canonical_url == "https://official.example/law/a"
        assert receipt.raw_provenance_json["attribution"] == MANIFEST.attribution
        assert session.scalar(select(func.count()).select_from(RegulatoryWork)) == 2
        assert session.scalar(select(func.count()).select_from(RegulatoryRelation)) == 1
        versions = session.scalars(select(RegulatoryDocumentVersion)).all()
        assert len(versions) == 2
        assert all(version.text and version.passages and version.artifact_key for version in versions)
        state = session.scalar(select(ConnectorState))
        assert state.cursor_json == {"offset": 2}
        assert state.page_checkpoint_json == {}
        assert state.contract_version == CONNECTOR_CONTRACT_VERSION
        assert state.health == "healthy"
        # Force the same page to prove a crash/re-delivery cannot duplicate facts.
        state.cursor_json = None
        session.commit()

    replay = asyncio.run(service.connector_runner.run_page(connector, stream="catalogue"))
    assert replay.status == "persisted"
    with service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(ConnectorPage)) == 1
        assert session.scalar(select(func.count()).select_from(ConnectorReceipt)) == 2
        assert session.scalar(select(func.count()).select_from(RegulatoryWork)) == 2

    status = client.get("/api/connectors/status")
    assert status.status_code == 200
    fixture_status = next(item for item in status.json() if item["connector"] == "fixture-official")
    assert fixture_status["source_contract"]["required_fields"] == ["id", "updated", "url"]
    assert {item["connector"] for item in status.json()} >= {
        "fedlex",
        "swiss-parliament",
        "federal-supreme-court",
        "federal-criminal-court",
    }


def test_partial_page_resumes_at_safe_checkpoint_and_only_then_advances_cursor(harness):
    _, _, service, _ = harness
    connector = FixtureConnector(fail_identity_once="law:b")

    partial = asyncio.run(service.connector_runner.run_page(connector, stream="catalogue"))
    assert partial.status == "partial"
    assert partial.persisted == 1
    assert partial.next_cursor is None
    with service.db.session(include_all_organizations=True) as session:
        state = session.scalar(select(ConnectorState))
        page = session.scalar(select(ConnectorPage))
        assert state.cursor_json is None
        assert state.page_checkpoint_json["next_index"] == 1
        assert page.safe_checkpoint_json["next_index"] == 1
        assert page.status == "partial"
        assert session.scalar(select(func.count()).select_from(ConnectorItemError)) == 1

    resumed = asyncio.run(service.connector_runner.run_page(connector, stream="catalogue"))
    assert resumed.status == "persisted"
    assert resumed.persisted == 2
    with service.db.session(include_all_organizations=True) as session:
        state = session.scalar(select(ConnectorState))
        assert state.cursor_json == {"offset": 2}
        assert state.page_checkpoint_json == {}
        assert session.scalar(select(func.count()).select_from(ConnectorReceipt)) == 2


def test_implausibly_empty_page_is_degraded_and_never_advances(harness):
    _, _, service, _ = harness
    result = asyncio.run(service.connector_runner.run_page(FixtureConnector(empty=True), stream="catalogue"))
    assert result.status == "degraded"
    assert "empty" in result.error
    with service.db.session(include_all_organizations=True) as session:
        state = session.scalar(select(ConnectorState))
        assert state.health == "degraded"
        assert state.cursor_json is None
        assert session.scalar(select(func.count()).select_from(ConnectorPage)) == 0


class RecordingLogger:
    def __init__(self):
        self.records = []

    def record(self, **values):
        self.records.append(values)


def test_shared_http_policy_retries_logs_and_rejects_cross_host_redirect(harness):
    _, _, service, _ = harness
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, request=request, text="temporary")
        return httpx.Response(
            200,
            request=request,
            content=b"<html><main><p>Official content</p></main></html>",
            headers={"content-type": "text/html"},
        )

    async def no_sleep(_):
        return None

    logger = RecordingLogger()
    client = ConnectorHttpClient(
        service.settings.model_copy(update={"allow_private_sources": True}),
        MANIFEST,
        logger,
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
        jitter=lambda: 0,
    )
    artifact = asyncio.run(client.get("https://official.example/catalogue", operation="discover"))
    assert artifact.body.startswith(b"<html>")
    assert attempts == 2
    assert [record["operation"] for record in logger.records] == [
        "discover_attempt_1",
        "discover_attempt_2",
    ]

    compressed_body = gzip.compress(b'{"id":20260001,"title":"Official compressed record"}')
    compressed = ConnectorHttpClient(
        service.settings.model_copy(update={"allow_private_sources": True}),
        MANIFEST,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                request=request,
                content=compressed_body,
                headers={"content-type": "application/json", "content-encoding": "gzip"},
            )
        ),
        sleep=no_sleep,
    )
    decoded = asyncio.run(
        compressed.get("https://official.example/catalogue", operation="compressed")
    )
    assert decoded.body == b'{"id":20260001,"title":"Official compressed record"}'

    def redirect_handler(request):
        return httpx.Response(
            302,
            request=request,
            headers={"location": "https://attacker.example/stolen"},
        )

    blocked = ConnectorHttpClient(
        service.settings.model_copy(update={"allow_private_sources": True}),
        MANIFEST,
        transport=httpx.MockTransport(redirect_handler),
        sleep=no_sleep,
    )
    with pytest.raises(DomainError) as error:
        asyncio.run(blocked.get("https://official.example/catalogue", operation="discover"))
    assert error.value.code == "connector_invalid_url"

    oversized = ConnectorHttpClient(
        service.settings.model_copy(update={"allow_private_sources": True}),
        MANIFEST,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, request=request, content=b"12345")),
        sleep=no_sleep,
    )
    with pytest.raises(DomainError) as error:
        asyncio.run(oversized.get("https://official.example/catalogue", operation="discover", max_bytes=4))
    assert error.value.code == "connector_content_too_large"


@pytest.mark.parametrize(
    ("contract", "body", "content_type"),
    [
        (
            FEDLEX_CONTRACT,
            b"<rss><channel><title>Fedlex</title><item><title>Act</title><link>https://fedlex.data.admin.ch/eli/cc/1</link></item></channel></rss>",
            "application/rss+xml",
        ),
        (
            PARLIAMENT_CONTRACT,
            b'[{"id":20260001,"updated":"2026-09-03T00:00:00Z","shortId":"26.001"}]',
            "application/json",
        ),
        (
            FEDERAL_COURT_CONTRACT,
            b'<html><h1>Liste der neu aufgenommenen Entscheide</h1><a href="/decision">03.09.2026</a></html>',
            "text/html",
        ),
        (
            FEDERAL_CRIMINAL_COURT_CONTRACT,
            b'<html><h1>Liste der neu aufgenommenen Entscheide</h1><a href="https://bstger.weblaw.ch/api/getDocumentContent/39fa0bc1-1f50-4f6b-85dd-dddad405a087">PDF</a></html>',
            "text/html",
        ),
        (
            FEDERAL_NEWS_CONTRACT,
            b'{"items":[{"langGroupId":"news-1","title":"Official notice","publishDate":"2026-09-03T00:00:00Z"}]}',
            "application/json",
        ),
        (
            FINMA_CONTRACT,
            b"<rss><channel><item><title>Notice</title><link>https://www.finma.ch/de/news/notice</link><pubDate>Thu, 03 Sep 2026 00:00:00 GMT</pubDate></item></channel></rss>",
            "text/xml",
        ),
    ],
)
def test_each_official_connector_has_a_fixture_backed_source_contract_probe(
    harness, contract, body, content_type
):
    _, _, service, _ = harness

    def handler(request):
        return httpx.Response(
            200,
            request=request,
            content=body,
            headers={"content-type": content_type},
        )

    async def no_sleep(_):
        return None

    result = asyncio.run(
        probe_source_contract(
            service.settings.model_copy(update={"allow_private_sources": True}),
            contract,
            transport=httpx.MockTransport(handler),
            sleep=no_sleep,
        )
    )
    assert result.status == "healthy"
    assert result.source_contract["observed"]["format"] in {"xml", "json", "html"}


def test_source_contract_template_drift_is_visible_as_degraded(harness):
    _, _, service, _ = harness

    def handler(request):
        return httpx.Response(200, request=request, text="<html><p>maintenance</p></html>")

    async def no_sleep(_):
        return None

    result = asyncio.run(
        probe_source_contract(
            service.settings.model_copy(update={"allow_private_sources": True}),
            FEDERAL_COURT_CONTRACT,
            transport=httpx.MockTransport(handler),
            sleep=no_sleep,
        )
    )
    assert result.status == "degraded"
    assert result.source_contract["error_code"] == "connector_contract_drift"
