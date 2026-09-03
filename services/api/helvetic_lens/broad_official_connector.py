"""Bounded official-news connectors for the federal portal and FINMA."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from .config import DomainError, Settings
from .connectors import (
    ConnectorExpression,
    ConnectorHealthReport,
    ConnectorHttpClient,
    ConnectorMetadata,
    DiscoveryPage,
    DiscoveryReference,
    OfficialConnector,
)
from .db import utcnow
from .integration_logs import IntegrationLogger
from .official_source_contracts import FEDERAL_NEWS_CONTRACT, FINMA_CONTRACT, _validate_payload
from .regulatory_corpus import DateInput, IdentifierInput


def _instant(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class FederalNewsConnector(OfficialConnector):
    manifest = FEDERAL_NEWS_CONTRACT.manifest

    def __init__(
        self,
        settings: Settings,
        logger: IntegrationLogger | None = None,
        *,
        language="de",
        page_size=25,
        transport=None,
        sleep=None,
        now=lambda: datetime.now(UTC),
    ):
        if language not in {"de", "fr", "it", "rm", "en"} or not 1 <= page_size <= 100:
            raise ValueError("Unsupported federal-news stream")
        self.settings, self.language, self.page_size, self.now = settings, language, page_size, now
        self._items: dict[str, dict] = {}
        options = {"transport": transport}
        if sleep is not None:
            options["sleep"] = sleep
        self.http = ConnectorHttpClient(settings, self.manifest, logger, **options)

    @property
    def stream(self):
        return f"news-{self.language}"

    def _url(self, cursor):
        current = cursor or {}
        end = current.get("window_end") or self.now().date().isoformat()
        start = current.get("watermark") or (self.now() - timedelta(days=14)).date().isoformat()
        params = [
            ("languages", self.language),
            ("newsKinds", "CONTENT_HUB"),
            ("newsKinds", "ONSB"),
            ("start_date", start[:10] + "T00:00:00.000Z"),
            ("end_date", end[:10] + "T23:59:59.999Z"),
            ("offset", str(current.get("offset", 0))),
            ("limit", str(self.page_size)),
            ("sort", "ASC"),
        ]
        return "https://d-nsbc-p.admin.ch/v1/search?" + urlencode(params)

    async def health(self):
        try:
            artifact = await self.http.get(
                self._url({"offset": 0}), operation="federal_news_health", max_bytes=2_000_000
            )
            observed = _validate_payload("federal_news_json", artifact.body)
            return ConnectorHealthReport(
                "healthy",
                "The bounded federal news contract passed.",
                self.now(),
                {**self.manifest.source_contract, "observed": observed},
            )
        except DomainError as exc:
            return ConnectorHealthReport(
                "degraded", exc.message, self.now(), {**self.manifest.source_contract, "error_code": exc.code}
            )

    async def discover_since(self, cursor, page_checkpoint):
        url = self._url(cursor)
        artifact = await self.http.get(url, operation="federal_news_discovery", max_bytes=2_000_000)
        try:
            payload = json.loads(artifact.body)
            items = payload["items"]
            total = int(payload.get("pageResults", len(items)))
            if not isinstance(items, list):
                raise TypeError
        except (ValueError, TypeError, KeyError) as exc:
            raise DomainError(
                "Federal news no longer matches the documented result contract.",
                502,
                "connector_contract_drift",
            ) from exc
        refs = []
        for item in items:
            if not isinstance(item, dict) or not all(
                item.get(key) for key in ("langGroupId", "title", "publishDate")
            ):
                raise DomainError(
                    "Federal news omitted a required item field.", 502, "connector_contract_drift"
                )
            identity = str(item["langGroupId"])
            canonical = f"https://www.admin.ch/{self.language}/newnsb/{identity}"
            self._items[identity] = item
            refs.append(DiscoveryReference(identity, _fingerprint(item), canonical, f"{url}#item={identity}"))
        current = cursor or {}
        offset = int(current.get("offset", 0))
        terminal = offset + len(items) >= total or not items
        newest = max(
            (
                _instant(item["content"].get("systemdata", {}).get("updatedAt") or item["publishDate"])
                for item in items
            ),
            default=current.get("watermark") or self.now().isoformat().replace("+00:00", "Z"),
        )
        next_cursor = {
            "watermark": newest
            if terminal
            else current.get("watermark", (self.now() - timedelta(days=14)).isoformat()),
            "offset": 0 if terminal else offset + len(items),
        }
        if not terminal:
            next_cursor["window_end"] = current.get("window_end") or self.now().date().isoformat()
        return DiscoveryPage(
            tuple(refs),
            next_cursor,
            url,
            self.manifest.schema_version,
            complete=terminal,
            empty_is_valid=bool(cursor),
        )

    async def _item(self, reference):
        if reference.external_identity in self._items:
            return self._items[reference.external_identity]
        artifact = await self.http.get(
            self._url(None), operation="federal_news_metadata", max_bytes=2_000_000
        )
        for item in json.loads(artifact.body).get("items", []):
            if str(item.get("langGroupId")) == reference.external_identity:
                return item
        raise DomainError(
            "The discovered federal news item is no longer available.", 502, "connector_item_missing"
        )

    async def fetch_metadata(self, reference):
        item = await self._item(reference)
        published = _instant(item["publishDate"])
        publisher = ", ".join(
            str(p.get("name") or p) if isinstance(p, dict) else str(p)
            for p in item.get("publishers", [])
            if p
        )
        return ConnectorMetadata(
            reference.external_identity,
            reference.source_revision,
            "official_notice",
            item["title"],
            reference.canonical_url,
            (IdentifierInput("news_service_bund_id", reference.external_identity, reference.canonical_url),),
            lifecycle_status="published",
            dates=(
                DateInput(
                    "work", "published_at", published, "instant", "news_service_bund", reference.canonical_url
                ),
            ),
            metadata={
                "notice_context_only": True,
                "publication_category": item.get("newsCategory"),
                "publisher": publisher,
                "topics": item.get("topics", []),
                "language": self.language,
            },
            raw_provenance={
                "method": "news_service_bund_json",
                "source": reference.raw_provenance_ref,
                "retrieved_at": utcnow().isoformat(),
            },
        )

    async def list_expressions(self, metadata):
        return (
            ConnectorExpression(
                self.language,
                f"{metadata.canonical_url}#{metadata.source_revision}",
                metadata.title,
                metadata.canonical_url,
                metadata.source_revision,
                metadata.canonical_url,
                metadata={"official_notice": True},
            ),
        )

    async def fetch_official_artifact(self, expression):
        artifact = await self.http.get(
            expression.artifact_url, operation="federal_news_artifact", headers={"Accept": "text/html"}
        )
        return replace(
            artifact,
            raw_provenance={
                "official_page_sha256": hashlib.sha256(artifact.body).hexdigest(),
                "retrieved_at": utcnow().isoformat(),
            },
        )

    async def extract_relations(self, metadata):
        return ()


class FinmaNewsConnector(OfficialConnector):
    manifest = FINMA_CONTRACT.manifest

    def __init__(
        self,
        settings: Settings,
        logger: IntegrationLogger | None = None,
        *,
        language="de",
        transport=None,
        sleep=None,
        now=lambda: datetime.now(UTC),
    ):
        if language not in {"de", "fr", "it", "en"}:
            raise ValueError("Unsupported FINMA language")
        self.settings, self.language, self.now = settings, language, now
        self._items = {}
        options = {"transport": transport}
        if sleep is not None:
            options["sleep"] = sleep
        self.http = ConnectorHttpClient(settings, self.manifest, logger, **options)

    @property
    def stream(self):
        return f"news-{self.language}"

    @property
    def feed_url(self):
        return f"https://www.finma.ch/{self.language}/rss/news/"

    def _parse(self, body):
        try:
            root = ElementTree.fromstring(body)
            items = []
            for node in root.iter():
                if node.tag.rsplit("}", 1)[-1] != "item":
                    continue
                values = {child.tag.rsplit("}", 1)[-1]: "".join(child.itertext()).strip() for child in node}
                if not all(values.get(k) for k in ("title", "link", "pubDate")):
                    raise ValueError
                items.append(values)
            if not items:
                raise ValueError
            return items
        except (ElementTree.ParseError, ValueError) as exc:
            raise DomainError(
                "FINMA RSS no longer matches the expected contract.", 502, "connector_contract_drift"
            ) from exc

    async def health(self):
        try:
            artifact = await self.http.get(self.feed_url, operation="finma_health", max_bytes=2_000_000)
            observed = _validate_payload("finma_rss", artifact.body)
            return ConnectorHealthReport(
                "healthy",
                "The bounded FINMA news contract passed.",
                self.now(),
                {**self.manifest.source_contract, "observed": observed},
            )
        except DomainError as exc:
            return ConnectorHealthReport(
                "degraded", exc.message, self.now(), {**self.manifest.source_contract, "error_code": exc.code}
            )

    async def discover_since(self, cursor, page_checkpoint):
        artifact = await self.http.get(self.feed_url, operation="finma_discovery", max_bytes=2_000_000)
        items = self._parse(artifact.body)
        cutoff = None
        if (cursor or {}).get("watermark"):
            cutoff = datetime.fromisoformat(cursor["watermark"].replace("Z", "+00:00")) - timedelta(days=2)
        selected = []
        for item in items:
            published = _instant(item["pubDate"])
            if cutoff is None or datetime.fromisoformat(published.replace("Z", "+00:00")) >= cutoff:
                identity = item.get("guid") or item["link"]
                self._items[identity] = item
                selected.append(
                    DiscoveryReference(
                        identity, _fingerprint(item), item["link"], f"{self.feed_url}#guid={identity}"
                    )
                )
        latest = max(_instant(item["pubDate"]) for item in items)
        return DiscoveryPage(
            tuple(selected),
            {"watermark": latest, "overlap_days": 2},
            self.feed_url,
            self.manifest.schema_version,
            complete=True,
            empty_is_valid=bool(cursor),
        )

    async def fetch_metadata(self, reference):
        item = self._items.get(reference.external_identity)
        if not item:
            raise DomainError(
                "The discovered FINMA item is no longer in the bounded feed.", 502, "connector_item_missing"
            )
        description = BeautifulSoup(item.get("description", ""), "html.parser").get_text(" ", strip=True)
        published = _instant(item["pubDate"])
        return ConnectorMetadata(
            reference.external_identity,
            reference.source_revision,
            "official_notice",
            item["title"],
            reference.canonical_url,
            (IdentifierInput("finma_news_url", reference.canonical_url, reference.canonical_url),),
            lifecycle_status="published",
            dates=(DateInput("work", "published_at", published, "instant", "finma_rss", self.feed_url),),
            metadata={
                "notice_context_only": True,
                "description": description,
                "category": item.get("category"),
                "language": self.language,
            },
            raw_provenance={
                "method": "finma_rss",
                "source": reference.raw_provenance_ref,
                "retrieved_at": utcnow().isoformat(),
            },
        )

    async def list_expressions(self, metadata):
        return (
            ConnectorExpression(
                self.language,
                f"{metadata.canonical_url}#{metadata.source_revision}",
                metadata.title,
                metadata.canonical_url,
                metadata.source_revision,
                metadata.canonical_url,
                metadata={"official_notice": True},
            ),
        )

    async def fetch_official_artifact(self, expression):
        artifact = await self.http.get(
            expression.artifact_url, operation="finma_artifact", headers={"Accept": "text/html"}
        )
        return replace(
            artifact,
            raw_provenance={
                "official_page_sha256": hashlib.sha256(artifact.body).hexdigest(),
                "retrieved_at": utcnow().isoformat(),
            },
        )

    async def extract_relations(self, metadata):
        return ()


def federal_news_connectors(settings, logger=None):
    return tuple(
        FederalNewsConnector(settings, logger, language=language)
        for language in ("de", "fr", "it", "rm", "en")
    )


def finma_news_connectors(settings, logger=None):
    return tuple(
        FinmaNewsConnector(settings, logger, language=language) for language in ("de", "fr", "it", "en")
    )
