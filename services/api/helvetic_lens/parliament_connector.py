"""Swiss Parliament affairs catalogue adapter over the official legacy web service."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .config import DomainError, Settings
from .connectors import (
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
    validate_official_url,
)
from .integration_logs import IntegrationLogger
from .official_source_contracts import PARLIAMENT_CONTRACT
from .regulatory_corpus import DateInput, DocumentInput, ExpressionInput, IdentifierInput

PARLIAMENT_API = "https://ws-old.parlament.ch"
PARLIAMENT_LANGUAGES = ("de", "fr", "it", "en")
PARLIAMENT_PAGE_ROWS = 50
PARLIAMENT_FINAL_STATE_IDS = frozenset({25, 26, 27, 60, 229})
_PAGE_COUNT = re.compile(r"\bPage\s+1\s+of\s+([0-9'’.,]+)\b", re.I)
_ELI_REFERENCE = re.compile(
    r"https?://(?:www\.)?fedlex(?:\.data)?\.admin\.ch/eli/(?:cc|oc|fga)/[^\s\"'<>]+",
    re.I,
)
_SR_REFERENCE = re.compile(r"\b(?:SR|RS)\s+([0-9]+(?:\.[0-9]+){1,4})\b", re.I)
_ARTICLE_REFERENCE = re.compile(r"\b(?:Art\.|Article|Artikel)\s*([0-9]+[a-z]?)\b", re.I)
_GAZETTE_REFERENCE = re.compile(r"\b(?:BBl|FF|FFe)\s+[0-9]{4}\s+[0-9]+\b", re.I)


def _fingerprint(value: object) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def _items(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _parse_json(artifact: ConnectorArtifact, operation: str):
    try:
        payload = json.loads(artifact.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DomainError(
            f"Swiss Parliament returned invalid JSON for {operation}.",
            502,
            "connector_contract_drift",
        ) from exc
    return payload


def _iso(value) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    match = re.fullmatch(r"/?Date\(([-+]?\d+)(?:[-+]\d+)?\)/?", text)
    if match:
        return datetime.fromtimestamp(int(match.group(1)) / 1000, UTC).isoformat()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def _day(value) -> str | None:
    parsed = _iso(value)
    return parsed[:10] if parsed else None


def _text(value) -> str:
    if value is None:
        return ""
    raw = str(value)
    if re.search(r"<[^>]+>", raw):
        raw = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    return " ".join(raw.split())


def _https_official(value: str) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if parsed.username or parsed.password or port not in {None, 80, 443}:
        return None
    host = parsed.hostname.lower()
    if host not in PARLIAMENT_CONTRACT.manifest.allowed_hosts:
        return None
    netloc = f"{host}:443" if port == 443 else host
    return urlunsplit(("https", netloc, parsed.path, parsed.query, ""))


def _business_url(affair_id: str) -> str:
    return (
        "https://www.parlament.ch/de/ratsbetrieb/suche-curia-vista/geschaeft"
        f"?AffairId={affair_id}"
    )


def _api_url(affair_id: str, language: str, *, format_json: bool = True) -> str:
    suffix = f"?lang={language}"
    if format_json:
        suffix += "&format=json"
    return f"{PARLIAMENT_API}/affairs/{affair_id}{suffix}"


def _substantive_projection(detail: dict) -> dict:
    drafts = []
    for draft in _items(detail.get("drafts")):
        if not isinstance(draft, dict):
            continue
        drafts.append(
            {
                "index": draft.get("index"),
                "texts": draft.get("texts") or [],
                "references": draft.get("references") or [],
                "links": draft.get("links") or [],
            }
        )
    return {
        "id": detail.get("id"),
        "language": detail.get("language"),
        "title": detail.get("title"),
        "affairType": detail.get("affairType"),
        "deposit": detail.get("deposit"),
        "descriptors": detail.get("descriptors") or [],
        "additionalIndexing": detail.get("additionalIndexing"),
        "texts": detail.get("texts") or [],
        "drafts": drafts,
    }


def _summary(detail: dict) -> str:
    title = _text(detail.get("title"))
    values = []
    for item in _items(detail.get("texts")):
        value = _text(item.get("value") if isinstance(item, dict) else item)
        if value and value != title and value not in values:
            values.append(value)
    for draft in _items(detail.get("drafts")):
        if not isinstance(draft, dict):
            continue
        for item in _items(draft.get("texts")):
            value = _text(item.get("value") if isinstance(item, dict) else item)
            if value and value != title and value not in values:
                values.append(value)
    return "\n\n".join(values)[:12000]


def _official_artifacts(detail: dict) -> list[dict]:
    found = []
    seen = set()
    for draft in _items(detail.get("drafts")):
        if not isinstance(draft, dict):
            continue
        draft_index = draft.get("index")
        for reference in _items(draft.get("references")):
            if not isinstance(reference, dict):
                continue
            publication = reference.get("publication") or {}
            url = _https_official(publication.get("url") or reference.get("url"))
            if not url or url in seen:
                continue
            seen.add(url)
            found.append(
                {
                    "url": url,
                    "title": _text(reference.get("title") or publication.get("source") or "Document"),
                    "date": _day(reference.get("date")),
                    "kind": "reference",
                    "draft_index": draft_index,
                    "publication": publication,
                }
            )
        for link in _items(draft.get("links")):
            if not isinstance(link, dict):
                continue
            url = _https_official(link.get("url"))
            if not url or url in seen:
                continue
            seen.add(url)
            found.append(
                {
                    "url": url,
                    "title": _text(link.get("title") or "Document"),
                    "date": _day(link.get("date")),
                    "kind": "draft_link",
                    "draft_index": draft_index,
                }
            )
    return found


def _committees(detail: dict) -> list[dict]:
    result, seen = [], set()
    for draft in _items(detail.get("drafts")):
        if not isinstance(draft, dict):
            continue
        for consultation in _items(draft.get("preConsultations")):
            committee = consultation.get("committee") if isinstance(consultation, dict) else None
            if not isinstance(committee, dict) or committee.get("id") in seen:
                continue
            seen.add(committee.get("id"))
            result.append(committee)
    return result


def _kind(detail: dict) -> str:
    type_id = int((detail.get("affairType") or {}).get("id") or 0)
    if type_id in {3, 4}:
        return "initiative"
    if type_id in {1, 2} and any(
        (draft.get("texts") or draft.get("references"))
        for draft in _items(detail.get("drafts"))
        if isinstance(draft, dict)
    ):
        return "bill"
    return "parliamentary_business"


class ParliamentConnector(OfficialConnector):
    """Bounded catalogue, recent-window, and known-active affair streams."""

    manifest: ConnectorManifest = PARLIAMENT_CONTRACT.manifest

    def __init__(
        self,
        settings: Settings,
        logger: IntegrationLogger | None = None,
        *,
        mode: str = "catalogue",
        active_ids: tuple[str, ...] = (),
        item_page_size: int = 10,
        recent_window_pages: int = 4,
        transport=None,
        sleep=None,
        now=lambda: datetime.now(UTC),
    ):
        if mode not in {"catalogue", "recent", "active"}:
            raise ValueError("Unsupported Parliament connector mode")
        options = {"transport": transport}
        if sleep is not None:
            options["sleep"] = sleep
        self.http = ConnectorHttpClient(settings, self.manifest, logger, **options)
        self.mode = mode
        self.active_ids = tuple(
            sorted({str(item) for item in active_ids if str(item).isdigit()}, key=int)
        )
        self.item_page_size = max(1, min(item_page_size, 25))
        self.recent_window_pages = max(1, min(recent_window_pages, 20))
        self.now = now
        self.stream = mode
        self._last_page: int | None = None
        self._details: dict[str, dict[str, dict]] = {}
        self._inline_artifacts: dict[str, ConnectorArtifact] = {}

    async def _page_count(self) -> int:
        artifact = await self.http.get(
            f"{PARLIAMENT_API}/affairs?lang=en",
            operation="parliament_page_count",
            max_bytes=1_000_000,
            headers={"Accept": "text/html"},
        )
        text = BeautifulSoup(artifact.body, "html.parser").get_text(" ", strip=True)
        match = _PAGE_COUNT.search(text)
        if not match:
            raise DomainError(
                "Swiss Parliament no longer exposes the expected affair page count.",
                502,
                "connector_contract_drift",
            )
        count = int(re.sub(r"[^0-9]", "", match.group(1)))
        if count < 1:
            raise DomainError(
                "Swiss Parliament returned an invalid affair page count.",
                502,
                "connector_contract_drift",
            )
        self._last_page = count
        return count

    async def _catalogue_page(self, page_number: int) -> tuple[list[dict], str]:
        url = (
            f"{PARLIAMENT_API}/affairs?pageNumber={page_number}"
            "&format=json&lang=de"
        )
        artifact = await self.http.get(
            url,
            operation="parliament_affair_catalogue",
            max_bytes=1_000_000,
            headers={"Accept": "application/json"},
        )
        payload = _parse_json(artifact, "the affair catalogue")
        if not isinstance(payload, list) or not payload:
            raise DomainError(
                "Swiss Parliament returned an implausibly empty affair page.",
                502,
                "connector_contract_drift",
            )
        previous = None
        for row in payload:
            if not isinstance(row, dict) or not row.get("id") or not row.get("updated"):
                raise DomainError(
                    "Swiss Parliament omitted an affair identity or update timestamp.",
                    502,
                    "connector_contract_drift",
                )
            affair_id = int(row["id"])
            if previous is not None and affair_id <= previous:
                raise DomainError(
                    "Swiss Parliament affair ordering no longer matches the connector contract.",
                    502,
                    "connector_contract_drift",
                )
            previous = affair_id
        return payload, artifact.url

    def _references(self, rows: list[dict]) -> tuple[DiscoveryReference, ...]:
        return tuple(
            DiscoveryReference(
                external_identity=str(row["id"]),
                source_revision=str(row["updated"]),
                canonical_url=_business_url(str(row["id"])),
                raw_provenance_ref=(
                    f"{PARLIAMENT_API}/affairs/{row['id']}?format=json&lang=de"
                ),
            )
            for row in rows
        )

    async def discover_since(self, cursor: dict | None, page_checkpoint: dict) -> DiscoveryPage:
        cursor = dict(cursor or {})
        if self.mode == "active":
            last_id = int(cursor.get("last_id", 0))
            remaining = [item for item in self.active_ids if int(item) > last_id]
            selected = remaining[: self.item_page_size]
            references = []
            for affair_id in selected:
                records = await self._load_details(affair_id)
                primary = next(iter(records.values()))
                references.append(
                    DiscoveryReference(
                        affair_id,
                        str(primary["payload"]["updated"]),
                        _business_url(affair_id),
                        primary["artifact"].url,
                    )
                )
            cycle = int(cursor.get("cycle", 0))
            complete = len(selected) == len(remaining)
            next_cursor = (
                {"last_id": 0, "cycle": cycle + 1}
                if complete
                else {"last_id": int(selected[-1]), "cycle": cycle}
            )
            return DiscoveryPage(
                tuple(references),
                next_cursor,
                f"{PARLIAMENT_API}/affairs#known-active",
                self.manifest.schema_version,
                complete=complete,
                empty_is_valid=not self.active_ids,
            )

        last_page = self._last_page or await self._page_count()
        cycle = int(cursor.get("cycle", 0))
        item_offset = max(0, int(cursor.get("item_offset", 0)))
        if self.mode == "catalogue":
            page_number = max(1, min(int(cursor.get("page_number", 1)), last_page))
            page_offset = None
        else:
            page_offset = max(0, min(int(cursor.get("page_offset", 0)), self.recent_window_pages - 1))
            page_number = max(1, last_page - page_offset)

        rows, source_url = await self._catalogue_page(page_number)
        selected = rows[item_offset : item_offset + self.item_page_size]
        if not selected:
            raise DomainError(
                "Swiss Parliament paging changed during the current reconciliation.",
                502,
                "connector_contract_drift",
            )
        page_finished = item_offset + len(selected) >= len(rows)
        complete = False
        if not page_finished:
            next_cursor = {**cursor, "item_offset": item_offset + len(selected), "cycle": cycle}
            if self.mode == "catalogue":
                next_cursor["page_number"] = page_number
            else:
                next_cursor["page_offset"] = page_offset
        elif self.mode == "catalogue" and page_number < last_page:
            next_cursor = {"page_number": page_number + 1, "item_offset": 0, "cycle": cycle}
        elif self.mode == "recent" and page_offset + 1 < min(last_page, self.recent_window_pages):
            next_cursor = {"page_offset": page_offset + 1, "item_offset": 0, "cycle": cycle}
        else:
            complete = True
            next_cursor = (
                {"page_number": 1, "item_offset": 0, "cycle": cycle + 1}
                if self.mode == "catalogue"
                else {"page_offset": 0, "item_offset": 0, "cycle": cycle + 1}
            )
        return DiscoveryPage(
            self._references(selected),
            next_cursor,
            f"{source_url}#rows-{item_offset + 1}-{item_offset + len(selected)}",
            self.manifest.schema_version,
            complete=complete,
        )

    async def _load_details(self, affair_id: str) -> dict[str, dict]:
        if affair_id in self._details:
            return self._details[affair_id]
        records = {}
        for requested in PARLIAMENT_LANGUAGES:
            artifact = await self.http.get(
                _api_url(affair_id, requested),
                operation="parliament_affair_detail",
                max_bytes=4_000_000,
                headers={"Accept": "application/json"},
                accepted_statuses=frozenset({404}),
            )
            if artifact.status_code == 404:
                continue
            payload = _parse_json(artifact, "an affair detail")
            if not isinstance(payload, dict) or str(payload.get("id")) != affair_id:
                raise DomainError(
                    "Swiss Parliament returned an affair detail with the wrong identity.",
                    502,
                    "connector_contract_drift",
                )
            actual = str(payload.get("language") or requested).lower()
            if actual not in PARLIAMENT_LANGUAGES:
                raise DomainError(
                    "Swiss Parliament returned an unsupported language code.",
                    502,
                    "connector_contract_drift",
                )
            records.setdefault(actual, {"payload": payload, "artifact": artifact})
        if not records:
            raise DomainError(
                "Swiss Parliament returned no available language record for this affair.",
                502,
                "connector_contract_drift",
            )
        self._details[affair_id] = records
        return records

    async def fetch_metadata(self, reference: DiscoveryReference) -> ConnectorMetadata:
        records = await self._load_details(reference.external_identity)
        for record in records.values():
            if str(record["payload"].get("updated")) != reference.source_revision:
                raise DomainError(
                    "Swiss Parliament changed the affair during ingestion; retry the page.",
                    502,
                    "connector_source_changed",
                )
        primary_language = next(
            (language for language in PARLIAMENT_LANGUAGES if language in records),
            next(iter(records)),
        )
        primary = records[primary_language]["payload"]
        state = primary.get("state") or {}
        state_id = int(state.get("id") or 0)
        state_names = {
            language: _text((record["payload"].get("state") or {}).get("name"))
            for language, record in records.items()
        }
        titles = {
            language: _text(record["payload"].get("title"))
            for language, record in records.items()
        }
        summaries = {
            language: _summary(record["payload"])
            for language, record in records.items()
        }
        artifacts = {
            language: _official_artifacts(record["payload"])
            for language, record in records.items()
        }
        all_text = json.dumps(
            [_substantive_projection(record["payload"]) for record in records.values()],
            ensure_ascii=False,
        )
        reference_candidates = {
            "eli": sorted({item.rstrip(".,);]") for item in _ELI_REFERENCE.findall(all_text)}),
            "sr_rs": sorted(set(_SR_REFERENCE.findall(all_text))),
            "articles": sorted(set(_ARTICLE_REFERENCE.findall(all_text))),
            "federal_gazette": sorted(set(_GAZETTE_REFERENCE.findall(all_text))),
        }
        deposit = primary.get("deposit") or {}
        dates = ()
        if _day(deposit.get("date")):
            dates = (
                DateInput(
                    target="work",
                    kind="published_at",
                    value=_day(deposit.get("date")),
                    precision="day",
                    provenance="parliament_webservice",
                    source_url=reference.canonical_url,
                ),
            )
        short_id = str(primary.get("shortId") or "").strip()
        identifiers = [
            IdentifierInput("parliament_affair_id", reference.external_identity, reference.canonical_url)
        ]
        if short_id:
            identifiers.append(IdentifierInput("parliament_short_id", short_id, reference.canonical_url))
        related_affairs = []
        for value in _items(primary.get("relatedAffairs")):
            affair_id = value.get("id") if isinstance(value, dict) else value
            if affair_id and str(affair_id) != reference.external_identity:
                related_affairs.append(str(affair_id))
        metadata = {
            "short_id": short_id or None,
            "available_languages": list(records),
            "titles": titles,
            "summaries": summaries,
            "affair_type": primary.get("affairType") or {},
            "state_id": state_id or None,
            "state_names": state_names,
            "is_final": state_id in PARLIAMENT_FINAL_STATE_IDS,
            "updated_at": reference.source_revision,
            "deposit": deposit,
            "descriptors": primary.get("descriptors") or [],
            "authors": primary.get("roles") or [],
            "committees": _committees(primary),
            "sessions": sorted(
                {
                    str(value)
                    for value in [deposit.get("session"), (primary.get("handling") or {}).get("session")]
                    if value
                }
            ),
            "votes_url": f"{PARLIAMENT_API}/votes/affairs/{reference.external_identity}",
            "official_artifacts": artifacts,
            "related_affairs": sorted(set(related_affairs), key=int),
            "reference_candidates": reference_candidates,
            "record_urls": {language: record["artifact"].url for language, record in records.items()},
            "retrieved_at": self.now().isoformat(),
        }
        return ConnectorMetadata(
            external_identity=reference.external_identity,
            source_revision=reference.source_revision,
            kind=_kind(primary),
            title=titles.get("de") or titles.get("fr") or next(iter(titles.values())),
            canonical_url=reference.canonical_url,
            identifiers=tuple(identifiers),
            lifecycle_status=f"parliament-state:{state_id}" if state_id else None,
            dates=dates,
            metadata=metadata,
            raw_provenance={
                "provider": "Swiss Parliament web service",
                "records": metadata["record_urls"],
                "retrieved_at": metadata["retrieved_at"],
                "attribution": self.manifest.attribution,
            },
        )

    async def list_expressions(self, metadata: ConnectorMetadata) -> tuple[ConnectorExpression, ...]:
        records = await self._load_details(metadata.external_identity)
        expressions = []
        seen_documents = set()
        for language in PARLIAMENT_LANGUAGES:
            record = records.get(language)
            if not record:
                continue
            detail = record["payload"]
            projection = _substantive_projection(detail)
            content_revision = _fingerprint(projection)
            expression_key = _api_url(metadata.external_identity, language)
            body = json.dumps(
                projection,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            self._inline_artifacts[expression_key] = ConnectorArtifact(
                url=record["artifact"].url,
                body=body,
                content_type="application/json; charset=utf-8",
                filename=f"parliament-affair-{metadata.external_identity}-{language}.json",
                raw_provenance={
                    "source_record": record["artifact"].url,
                    "projection": "substantive-fields-v1",
                },
            )
            expressions.append(
                ConnectorExpression(
                    language=language,
                    expression_key=expression_key,
                    title=_text(detail.get("title")),
                    official_url=metadata.canonical_url,
                    version_key=(
                        f"{metadata.external_identity}:{language}:record:{content_revision[:20]}"
                    ),
                    artifact_url=record["artifact"].url,
                    metadata={
                        "record_kind": "official_api_substantive_projection",
                        "source_record_url": record["artifact"].url,
                        "summary": metadata.metadata["summaries"].get(language),
                        "content_revision": content_revision,
                    },
                )
            )
            for document in metadata.metadata["official_artifacts"].get(language, []):
                url = document["url"]
                if url in seen_documents:
                    continue
                seen_documents.add(url)
                document_revision = _fingerprint(document)
                dates = ()
                if document.get("date"):
                    dates = (
                        DateInput(
                            target="version",
                            kind="published_at",
                            value=document["date"],
                            precision="day",
                            provenance="parliament_webservice",
                            source_url=url,
                        ),
                    )
                expressions.append(
                    ConnectorExpression(
                        language=language,
                        expression_key=(
                            f"parliament:{metadata.external_identity}:{language}:document:"
                            f"{_fingerprint(url)[:16]}"
                        ),
                        title=document["title"],
                        official_url=url,
                        version_key=(
                            f"{metadata.external_identity}:{language}:document:"
                            f"{document_revision[:20]}"
                        ),
                        artifact_url=url,
                        dates=dates,
                        metadata={
                            "record_kind": "official_linked_document",
                            "affair_id": metadata.external_identity,
                            **document,
                        },
                    )
                )
                break
        return tuple(expressions)

    async def fetch_official_artifact(
        self, expression: ConnectorExpression
    ) -> ConnectorArtifact | None:
        if expression.expression_key in self._inline_artifacts:
            return self._inline_artifacts[expression.expression_key]
        if not expression.artifact_url:
            return None
        artifact = await self.http.get(
            expression.artifact_url,
            operation="parliament_official_document",
            headers={"Accept": "application/pdf, text/html, application/octet-stream"},
        )
        return ConnectorArtifact(
            artifact.url,
            artifact.body,
            artifact.content_type,
            artifact.filename,
            raw_provenance={
                "affair_id": expression.metadata.get("affair_id"),
                "source": expression.artifact_url,
            },
            status_code=artifact.status_code,
        )

    def _target_affair(self, affair_id: str) -> DocumentInput:
        url = _business_url(affair_id)
        return DocumentInput(
            kind="parliamentary_business",
            authority=self.manifest.authority,
            identifiers=(IdentifierInput("parliament_affair_id", affair_id, url),),
            title=f"Swiss Parliament affair {affair_id}",
            stable_official_url=url,
            expression=ExpressionInput("und", f"parliament-affair:{affair_id}", official_url=url),
            metadata={"placeholder_from_official_relation": True},
        )

    @staticmethod
    def _target_fedlex(scheme: str, value: str) -> DocumentInput:
        is_eli = scheme == "eli_uri"
        return DocumentInput(
            kind="unclassified_document",
            authority="fedlex",
            identifiers=(IdentifierInput(scheme, value, value if is_eli else None),),
            title=value if is_eli else f"SR/RS {value}",
            stable_official_url=value if is_eli else None,
            expression=ExpressionInput(
                "und",
                f"fedlex-reference:{scheme}:{value}",
                official_url=value if is_eli else None,
            ),
            metadata={"placeholder_from_exact_parliament_reference": True},
        )

    async def extract_relations(self, metadata: ConnectorMetadata) -> tuple[ConnectorRelation, ...]:
        candidates = metadata.metadata.get("reference_candidates") or {}
        relations = []
        for affair_id in metadata.metadata.get("related_affairs") or []:
            relations.append(
                ConnectorRelation(
                    target=self._target_affair(affair_id),
                    relation_type="potentially_impacts",
                    state="proposed",
                    provenance_method="official_metadata",
                    evidence={
                        "source_affair": metadata.external_identity,
                        "target_affair": affair_id,
                        "field": "relatedAffairs",
                        "source": metadata.canonical_url,
                    },
                    rule_revision="parliament-exact-references-v1",
                )
            )
        for eli_uri in candidates.get("eli") or []:
            canonical = validate_official_url(eli_uri.replace("http://", "https://"), self.manifest.allowed_hosts)
            relations.append(
                ConnectorRelation(
                    target=self._target_fedlex("eli_uri", canonical),
                    relation_type="cites",
                    state="confirmed",
                    provenance_method="exact_identifier",
                    evidence={"identifier": canonical, "source": metadata.canonical_url},
                    rule_revision="parliament-exact-references-v1",
                )
            )
        for sr_rs in candidates.get("sr_rs") or []:
            relations.append(
                ConnectorRelation(
                    target=self._target_fedlex("sr_rs", sr_rs),
                    relation_type="cites",
                    state="confirmed",
                    provenance_method="exact_identifier",
                    evidence={"identifier": f"SR/RS {sr_rs}", "source": metadata.canonical_url},
                    rule_revision="parliament-exact-references-v1",
                )
            )
        return tuple(relations)

    async def health(self) -> ConnectorHealthReport:
        try:
            rows, url = await self._catalogue_page(1)
            page_count = await self._page_count()
            return ConnectorHealthReport(
                "healthy",
                "The Swiss Parliament affair catalogue contract is available.",
                self.now(),
                {
                    **self.manifest.source_contract,
                    "observed": {
                        "rows_per_page": len(rows),
                        "first_id": rows[0]["id"],
                        "last_id": rows[-1]["id"],
                        "page_count": page_count,
                        "ordered_by": "id",
                    },
                    "url": url,
                },
            )
        except DomainError as exc:
            return ConnectorHealthReport(
                "degraded",
                exc.message,
                self.now(),
                {**self.manifest.source_contract, "error_code": exc.code},
            )


def parliament_connectors(
    settings: Settings,
    logger: IntegrationLogger | None = None,
    *,
    active_ids: tuple[str, ...] = (),
) -> tuple[ParliamentConnector, ...]:
    return (
        ParliamentConnector(settings, logger, mode="catalogue"),
        ParliamentConnector(settings, logger, mode="recent"),
        ParliamentConnector(settings, logger, mode="active", active_ids=active_ids),
    )
