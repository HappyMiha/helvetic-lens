"""Stable official-notice ingestion for the core Swiss authorities."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from .config import DomainError, Settings
from .connectors import (
    ConnectorArtifact,
    ConnectorExpression,
    ConnectorHealthReport,
    ConnectorHttpClient,
    ConnectorMetadata,
    ConnectorRelation,
    DiscoveryPage,
    DiscoveryReference,
    OfficialConnector,
)
from .integration_logs import IntegrationLogger
from .official_source_contracts import PARLIAMENT_CONTRACT
from .regulatory_corpus import DateInput, DocumentInput, ExpressionInput, IdentifierInput

PARLIAMENT_NOTICE_API = (
    "https://www.parlament.ch/press-releases/"
    "_api/Lists/getByTitle('Pages')/Items"
)
NOTICE_LANGUAGES = {"de": 1031, "fr": 1036, "it": 1040, "en": 1033, "rm": 1047}
NOTICE_PAGE_SIZE = 25
_ELI = re.compile(r"https?://(?:www\.)?fedlex(?:\.data)?\.admin\.ch/eli/(?:cc|oc|fga)/[^\s\"'<>]+", re.I)
_SR = re.compile(r"\b(?:SR|RS)\s+([0-9]+(?:\.[0-9]+){1,4})\b", re.I)
_AFFAIR_URL = re.compile(r"[?&]AffairId=([0-9]{6,10})\b", re.I)


def _fingerprint(value: object) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise DomainError(
            "Swiss Parliament returned an invalid notice timestamp.",
            502,
            "connector_contract_drift",
        ) from exc
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _odata_rows(artifact: ConnectorArtifact) -> list[dict]:
    try:
        payload = json.loads(artifact.body)
        rows = payload.get("d", {}).get("results")
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
        raise DomainError(
            "Swiss Parliament returned invalid notice JSON.",
            502,
            "connector_contract_drift",
        ) from exc
    if not isinstance(rows, list):
        raise DomainError(
            "Swiss Parliament changed its official notice response.",
            502,
            "connector_contract_drift",
        )
    return rows


class ParliamentNoticeConnector(OfficialConnector):
    """Incremental SharePoint/OData feed behind Parliament's official press pages."""

    manifest = PARLIAMENT_CONTRACT.manifest
    stream = "notices"

    def __init__(
        self,
        settings: Settings,
        logger: IntegrationLogger | None = None,
        *,
        transport=None,
        sleep=None,
        now=lambda: datetime.now(UTC),
    ):
        options = {"transport": transport}
        if sleep is not None:
            options["sleep"] = sleep
        self.http = ConnectorHttpClient(settings, self.manifest, logger, **options)
        self.now = now
        self._rows: dict[str, dict] = {}
        self._reference_candidates: dict[str, dict[str, set[str]]] = {}

    def _feed_url(self, cursor: dict | None) -> str:
        watermark = (
            _parse_time(cursor["modified"])
            if cursor and cursor.get("modified")
            else self.now() - timedelta(days=30)
        )
        # Modified is the source's edit watermark. ID breaks equal-timestamp ties.
        watermark_text = watermark.strftime("%Y-%m-%dT%H:%M:%SZ")
        item_id = int((cursor or {}).get("id") or 0)
        params = {
            "$select": (
                "Id,Title_en,Title_de,Title_fr,Title_it,Title_rm,EventDate,Modified,"
                "FileRef,NewsType,HasDisplayPage,MMAuthor"
            ),
            "$filter": (
                f"Modified gt datetime'{watermark_text}' or "
                f"(Modified eq datetime'{watermark_text}' and Id gt {item_id})"
            ),
            "$orderby": "Modified asc,Id asc",
            "$top": str(NOTICE_PAGE_SIZE),
        }
        return f"{PARLIAMENT_NOTICE_API}?{urlencode(params)}"

    async def discover_since(self, cursor: dict | None, page_checkpoint: dict) -> DiscoveryPage:
        url = self._feed_url(cursor)
        artifact = await self.http.get(
            url,
            operation="parliament_notice_discovery",
            max_bytes=1_000_000,
            headers={"Accept": "application/json;odata=verbose"},
        )
        rows = _odata_rows(artifact)
        references = []
        for row in rows:
            item_id = str(row.get("Id") or row.get("ID") or "")
            modified = row.get("Modified")
            file_ref = str(row.get("FileRef") or "")
            if not item_id.isdigit() or not modified or not file_ref.startswith("/press-releases/"):
                raise DomainError(
                    "Swiss Parliament notice fields no longer match the source contract.",
                    502,
                    "connector_contract_drift",
                )
            _parse_time(modified)
            canonical = urljoin("https://www.parlament.ch", file_ref)
            revision = f"{modified}:{row.get('__metadata', {}).get('etag', '')}"
            self._rows[item_id] = row
            references.append(
                DiscoveryReference(item_id, revision, canonical, artifact.url)
            )
        next_cursor = cursor
        if rows:
            last = rows[-1]
            next_cursor = {
                "modified": _parse_time(last["Modified"]).isoformat(),
                "id": int(last.get("Id") or last.get("ID")),
            }
        return DiscoveryPage(
            tuple(references),
            next_cursor,
            artifact.url,
            self.manifest.schema_version,
            complete=len(rows) < NOTICE_PAGE_SIZE,
            empty_is_valid=True,
        )

    async def fetch_metadata(self, reference: DiscoveryReference) -> ConnectorMetadata:
        row = self._rows.get(reference.external_identity)
        if not row:
            raise DomainError(
                "The Parliament notice was not retained for this ingestion page.",
                502,
                "connector_source_changed",
            )
        modified = _parse_time(row["Modified"])
        published = _parse_time(row.get("EventDate") or row["Modified"])
        titles = {
            language: " ".join(str(row.get(f"Title_{language}") or "").split())
            for language in NOTICE_LANGUAGES
        }
        primary = titles["de"] or titles["fr"] or titles["it"] or next(
            (title for title in titles.values() if title), "Official Parliament notice"
        )
        return ConnectorMetadata(
            external_identity=reference.external_identity,
            source_revision=reference.source_revision,
            kind="official_notice",
            title=primary,
            canonical_url=reference.canonical_url,
            identifiers=(
                IdentifierInput(
                    "parliament_notice_id",
                    reference.external_identity,
                    reference.canonical_url,
                ),
            ),
            lifecycle_status="published",
            dates=(
                DateInput("work", "published_at", published.isoformat(), "instant", "official_metadata", reference.canonical_url),
                DateInput("work", "fetched_at", self.now().isoformat(), "instant", "connector_fetch", reference.raw_provenance_ref),
            ),
            metadata={
                "notice_context_only": True,
                "notice_type": (row.get("NewsType") or {}).get("TermGuid"),
                "author": row.get("MMAuthor"),
                "titles": titles,
                "modified_at": modified.isoformat(),
            },
            raw_provenance={
                "odata_item_id": reference.external_identity,
                "odata_etag": row.get("__metadata", {}).get("etag"),
                "discovery_url": reference.raw_provenance_ref,
                "official_page": reference.canonical_url,
            },
        )

    async def list_expressions(self, metadata: ConnectorMetadata) -> tuple[ConnectorExpression, ...]:
        titles = metadata.metadata.get("titles") or {}
        expressions = []
        for language, lcid in NOTICE_LANGUAGES.items():
            title = titles.get(language)
            if not title:
                continue
            url = f"{metadata.canonical_url}?lang={lcid}"
            expressions.append(
                ConnectorExpression(
                    language=language,
                    expression_key=url,
                    title=title,
                    official_url=url,
                    version_key=f"{metadata.source_revision}:{language}",
                    artifact_url=url,
                    dates=(
                        DateInput("expression", "version_date", metadata.metadata["modified_at"], "instant", "official_metadata", url),
                    ),
                    metadata={
                        "notice_id": metadata.external_identity,
                        "notice_context_only": True,
                        "source_language": language,
                    },
                )
            )
        return tuple(expressions)

    async def fetch_official_artifact(self, expression: ConnectorExpression) -> ConnectorArtifact | None:
        artifact = await self.http.get(
            expression.artifact_url or expression.official_url,
            operation="parliament_notice_page",
            max_bytes=2_000_000,
            headers={"Accept": "text/html"},
        )
        soup = BeautifulSoup(artifact.body, "html.parser")
        main = soup.select_one("main") or soup.select_one("#contentBox") or soup.body
        text = "\n\n".join(
            value for value in (" ".join(node.get_text(" ", strip=True).split()) for node in (main or soup).select("h1,h2,h3,p,li"))
            if value
        )
        if len(text) < 120:
            raise DomainError(
                "The official Parliament notice page no longer exposes a usable body.",
                502,
                "connector_contract_drift",
            )
        candidates = self._reference_candidates.setdefault(
            str(expression.metadata["notice_id"]), {"eli": set(), "sr_rs": set(), "affairs": set()}
        )
        candidates["eli"].update(match.rstrip(".,);]") for match in _ELI.findall(text))
        candidates["sr_rs"].update(_SR.findall(text))
        candidates["affairs"].update(_AFFAIR_URL.findall(text))
        body = text.encode("utf-8")
        return ConnectorArtifact(
            artifact.url,
            body,
            "text/plain; charset=utf-8",
            f"parliament-notice-{expression.metadata['notice_id']}-{expression.language}.txt",
            raw_provenance={
                "official_page_sha256": hashlib.sha256(artifact.body).hexdigest(),
                "official_page_content_type": artifact.content_type,
                "extraction": "semantic heading/paragraph/list text",
            },
        )

    @staticmethod
    def _target(authority: str, kind: str, scheme: str, value: str, title: str, url: str | None = None) -> DocumentInput:
        return DocumentInput(
            kind=kind,
            authority=authority,
            identifiers=(IdentifierInput(scheme, value, url),),
            title=title,
            stable_official_url=url,
            expression=ExpressionInput("und", f"notice-reference:{scheme}:{value}", official_url=url),
            metadata={"placeholder_from_exact_notice_reference": True},
        )

    async def extract_relations(self, metadata: ConnectorMetadata) -> tuple[ConnectorRelation, ...]:
        candidates = self._reference_candidates.get(
            metadata.external_identity, {"eli": set(), "sr_rs": set(), "affairs": set()}
        )
        relations = []
        for eli in sorted(candidates["eli"]):
            relations.append(ConnectorRelation(
                self._target("fedlex", "unclassified_document", "eli_uri", eli, eli, eli),
                "cites", "confirmed", "exact_identifier",
                {"identifier": eli, "source": metadata.canonical_url},
                rule_revision="parliament-notice-references-v1",
            ))
        for value in sorted(candidates["sr_rs"]):
            relations.append(ConnectorRelation(
                self._target("fedlex", "unclassified_document", "sr_rs", value, f"SR/RS {value}"),
                "cites", "confirmed", "exact_identifier",
                {"identifier": f"SR/RS {value}", "source": metadata.canonical_url},
                rule_revision="parliament-notice-references-v1",
            ))
        for affair in sorted(candidates["affairs"]):
            url = f"https://www.parlament.ch/de/ratsbetrieb/suche-curia-vista/geschaeft?AffairId={affair}"
            relations.append(ConnectorRelation(
                self._target("swiss_parliament", "parliamentary_business", "parliament_affair_id", affair, f"Parliamentary affair {affair}", url),
                "cites", "confirmed", "exact_identifier",
                {"identifier": affair, "source": metadata.canonical_url},
                rule_revision="parliament-notice-references-v1",
            ))
        return tuple(relations)

    async def health(self) -> ConnectorHealthReport:
        try:
            artifact = await self.http.get(
                self._feed_url({"modified": (self.now() - timedelta(days=7)).isoformat(), "id": 0}),
                operation="parliament_notice_health",
                max_bytes=1_000_000,
                headers={"Accept": "application/json;odata=verbose"},
            )
            rows = _odata_rows(artifact)
            return ConnectorHealthReport(
                "healthy",
                "The official Swiss Parliament notice feed is available.",
                self.now(),
                {
                    **self.manifest.source_contract,
                    "notice_discovery": "SharePoint/OData Pages list",
                    "notice_languages": list(NOTICE_LANGUAGES),
                    "observed_rows": len(rows),
                    "url": artifact.url,
                },
            )
        except DomainError as exc:
            return ConnectorHealthReport(
                "degraded", exc.message, self.now(),
                {**self.manifest.source_contract, "error_code": exc.code},
            )
