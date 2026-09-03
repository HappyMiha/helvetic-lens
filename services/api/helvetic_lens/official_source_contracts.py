"""Bounded health probes shared by the three first official connectors."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from .config import DomainError, Settings
from .connectors import (
    ConnectorHealthReport,
    ConnectorHttpClient,
    ConnectorManifest,
)
from .integration_logs import IntegrationLogger


@dataclass(frozen=True)
class OfficialSourceContract:
    manifest: ConnectorManifest
    smoke_url: str
    response_kind: str
    maximum_bytes: int = 1_000_000


FEDLEX_CONTRACT = OfficialSourceContract(
    manifest=ConnectorManifest(
        name="fedlex",
        authority="fedlex",
        connector_version="1.1.0",
        schema_version="fedlex-jolux-v2",
        allowed_hosts=frozenset(
            {"fedlex.data.admin.ch", "www.fedlex.admin.ch", "fedlex.admin.ch"}
        ),
        attribution="Swiss Confederation — Fedlex, retrieved from the linked official publication.",
        source_contract={
            "discovery": "RSS plus paginated JOLux/SPARQL reconciliation",
            "required_identity": "ELI work URI",
            "languages": ["de", "fr", "it", "rm", "en"],
        },
    ),
    smoke_url="https://fedlex.data.admin.ch/api/rss-de.xml",
    response_kind="fedlex_rss",
)

PARLIAMENT_CONTRACT = OfficialSourceContract(
    manifest=ConnectorManifest(
        name="swiss-parliament",
        authority="swiss_parliament",
        connector_version="1.2.0",
        schema_version="parliament-webservice-v3",
        allowed_hosts=frozenset(
            {
                "ws-old.parlament.ch",
                "www.parlament.ch",
                "parlament.ch",
                "www.admin.ch",
                "admin.ch",
                "fedlex.data.admin.ch",
                "www.fedlex.admin.ch",
                "fedlex.admin.ch",
            }
        ),
        attribution=(
            "Parlamentsdienste der Bundesversammlung, Bern — retrieved on the recorded date; "
            "Helvetic Lens is not an official publication."
        ),
        source_contract={
            "discovery": (
                "50-row ID-ordered catalogue, recent tail window, and known-active reconciliation"
            ),
            "required_identity": "affair id",
            "languages": ["de", "fr", "it", "en"],
            "rows_per_official_page": 50,
            "official_notices": (
                "incremental SharePoint/OData Pages feed with immutable source-page snapshots"
            ),
        },
    ),
    smoke_url="https://ws-old.parlament.ch/affairs?format=json&lang=de",
    response_kind="parliament_json",
)

FEDERAL_COURT_CONTRACT = OfficialSourceContract(
    manifest=ConnectorManifest(
        name="federal-supreme-court",
        authority="federal_supreme_court",
        connector_version="1.1.0",
        schema_version="federal-court-html-v2",
        allowed_hosts=frozenset({"search.bger.ch", "relevancy.bger.ch", "www.bger.ch", "bger.ch"}),
        attribution="Swiss Federal Supreme Court, with the canonical official decision link retained.",
        source_contract={
            "discovery": (
                "overlapping latest/date index plus bounded current-and-previous-year "
                "insertion-date reconciliation"
            ),
            "required_identity": "Aza identity and court docket",
            "languages": ["de", "fr", "it"],
            "crawl_delay_seconds": 2,
            "decision_representation": "official HTML",
            "yearly_sitemap_note": (
                "The sitemap declared by robots.txt covers the public website, not the "
                "decision database; yearly coverage therefore uses the official date index."
            ),
        },
        minimum_interval_seconds=2.0,
    ),
    smoke_url=(
        "https://search.bger.ch/ext/eurospider/live/de/php/aza/http/"
        "index_aza.php?lang=de&mode=index&search=false"
    ),
    response_kind="federal_court_html",
)

OFFICIAL_SOURCE_CONTRACTS = (
    FEDLEX_CONTRACT,
    PARLIAMENT_CONTRACT,
    FEDERAL_COURT_CONTRACT,
)


def _validate_payload(kind: str, body: bytes) -> dict:
    try:
        if kind == "fedlex_rss":
            root = ElementTree.fromstring(body)
            tags = {node.tag.rsplit("}", 1)[-1].lower() for node in root.iter()}
            if not ({"item", "entry"} & tags) or "title" not in tags or "link" not in tags:
                raise ValueError("required RSS entry fields are missing")
            return {"format": "xml", "entry_marker": sorted({"item", "entry"} & tags)}
        if kind == "parliament_json":
            payload = json.loads(body)
            if not isinstance(payload, list) or not payload:
                raise ValueError("affair catalogue is unexpectedly empty")
            first = payload[0]
            if not isinstance(first, dict) or not {"id", "updated"}.issubset(first):
                raise ValueError("required affair fields are missing")
            return {"format": "json", "required_fields": ["id", "updated"]}
        if kind == "federal_court_html":
            soup = BeautifulSoup(body, "html.parser")
            text = " ".join(soup.stripped_strings).casefold()
            links = [link.get("href") for link in soup.find_all("a") if link.get("href")]
            markers = ("neu aufgenommenen entscheide", "nouveaux arrêts", "nuove sentenze")
            if not any(marker in text for marker in markers) or not links:
                raise ValueError("latest-decision index markers are missing")
            return {"format": "html", "links_observed": len(links)}
    except (ElementTree.ParseError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise DomainError(
            "The official source response no longer matches its expected contract.",
            502,
            "connector_contract_drift",
        ) from exc
    raise DomainError(
        "The source contract uses an unknown response validator.",
        500,
        "connector_contract_configuration_error",
    )


async def probe_source_contract(
    settings: Settings,
    contract: OfficialSourceContract,
    logger: IntegrationLogger | None = None,
    *,
    transport=None,
    sleep=None,
) -> ConnectorHealthReport:
    options = {"transport": transport}
    if sleep is not None:
        options["sleep"] = sleep
    client = ConnectorHttpClient(settings, contract.manifest, logger, **options)
    try:
        artifact = await client.get(
            contract.smoke_url,
            operation="source_contract_smoke",
            max_bytes=contract.maximum_bytes,
        )
        observed = _validate_payload(contract.response_kind, artifact.body)
        return ConnectorHealthReport(
            "healthy",
            "The bounded official-source contract probe passed.",
            datetime.now(UTC),
            {**contract.manifest.source_contract, "observed": observed, "url": artifact.url},
        )
    except DomainError as exc:
        return ConnectorHealthReport(
            "degraded",
            exc.message,
            datetime.now(UTC),
            {**contract.manifest.source_contract, "error_code": exc.code},
        )
