"""Versioned connector contract and crash-safe page ingestion."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlsplit

import httpx
from sqlalchemy import func, select

from .config import DomainError, Settings
from .db import Database, utcnow
from .extraction import extract, validate_public_url
from .integration_logs import IntegrationLogger, response_snapshot
from .models import (
    ConnectorItemError,
    ConnectorPage,
    ConnectorReceipt,
    ConnectorState,
)
from .regulatory_corpus import (
    DateInput,
    DocumentInput,
    EventInput,
    ExpressionInput,
    IdentifierInput,
    RegulatoryCorpus,
    RelationInput,
    VersionInput,
    normalize_url,
)

CONNECTOR_CONTRACT_VERSION = "helvetic-lens.connector/v1"
CONNECTOR_HEALTH = {"healthy", "degraded", "error", "unknown"}
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


def _require(value: str, field_name: str) -> str:
    cleaned = " ".join((value or "").split())
    if not cleaned:
        raise DomainError(
            f"The connector omitted required field '{field_name}'.",
            502,
            "connector_contract_drift",
        )
    return cleaned


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class ConnectorManifest:
    name: str
    authority: str
    connector_version: str
    schema_version: str
    allowed_hosts: frozenset[str]
    attribution: str
    source_contract: dict = field(default_factory=dict)
    minimum_interval_seconds: float = 0.0

    def validate(self) -> None:
        _require(self.name, "manifest.name")
        _require(self.authority, "manifest.authority")
        _require(self.connector_version, "manifest.connector_version")
        _require(self.schema_version, "manifest.schema_version")
        _require(self.attribution, "manifest.attribution")
        if not self.allowed_hosts:
            raise DomainError(
                "The connector has no allowed official hosts.",
                502,
                "connector_contract_drift",
            )


@dataclass(frozen=True)
class DiscoveryReference:
    external_identity: str
    source_revision: str
    canonical_url: str
    raw_provenance_ref: str

    def validate(self, manifest: ConnectorManifest) -> None:
        _require(self.external_identity, "external_identity")
        _require(self.source_revision, "source_revision")
        _require(self.raw_provenance_ref, "raw_provenance_ref")
        validate_official_url(self.canonical_url, manifest.allowed_hosts)


@dataclass(frozen=True)
class DiscoveryPage:
    items: tuple[DiscoveryReference, ...]
    next_cursor: dict | None
    raw_provenance_ref: str
    schema_version: str
    complete: bool = False
    empty_is_valid: bool = False


@dataclass(frozen=True)
class ConnectorHealthReport:
    status: str
    message: str
    checked_at: datetime
    source_contract: dict = field(default_factory=dict)

    def validate(self) -> None:
        if self.status not in CONNECTOR_HEALTH:
            raise DomainError(
                "The connector returned an invalid health state.",
                502,
                "connector_contract_drift",
            )
        _require(self.message, "health.message")


@dataclass(frozen=True)
class ConnectorMetadata:
    external_identity: str
    source_revision: str
    kind: str
    title: str
    canonical_url: str
    identifiers: tuple[IdentifierInput, ...]
    lifecycle_status: str | None = None
    dates: tuple[DateInput, ...] = ()
    metadata: dict = field(default_factory=dict)
    raw_provenance: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorExpression:
    language: str
    expression_key: str
    title: str
    official_url: str
    version_key: str | None = None
    artifact_url: str | None = None
    dates: tuple[DateInput, ...] = ()
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorArtifact:
    url: str
    body: bytes
    content_type: str
    filename: str
    expected_sha256: str | None = None
    raw_provenance: dict = field(default_factory=dict)
    status_code: int = 200


@dataclass(frozen=True)
class ConnectorRelation:
    target: DocumentInput
    relation_type: str
    state: str
    provenance_method: str
    evidence: dict
    confidence: float | None = None
    rule_revision: str | None = None
    reverse: bool = False


class OfficialConnector(ABC):
    """All official-source adapters implement the same bounded operations."""

    manifest: ConnectorManifest

    @abstractmethod
    async def discover_since(self, cursor: dict | None, page_checkpoint: dict) -> DiscoveryPage: ...

    @abstractmethod
    async def fetch_metadata(self, reference: DiscoveryReference) -> ConnectorMetadata: ...

    @abstractmethod
    async def list_expressions(self, metadata: ConnectorMetadata) -> tuple[ConnectorExpression, ...]: ...

    @abstractmethod
    async def fetch_official_artifact(self, expression: ConnectorExpression) -> ConnectorArtifact | None: ...

    @abstractmethod
    async def extract_relations(self, metadata: ConnectorMetadata) -> tuple[ConnectorRelation, ...]: ...

    @abstractmethod
    async def health(self) -> ConnectorHealthReport: ...


def validate_official_url(value: str, allowed_hosts: frozenset[str]) -> str:
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError as exc:
        raise DomainError("The connector returned an invalid URL.", 502, "connector_invalid_url") from exc
    if (
        parsed.scheme != "https"
        or not host
        or host not in {item.lower() for item in allowed_hosts}
        or parsed.username
        or parsed.password
        or port not in {None, 443}
    ):
        raise DomainError(
            "The connector returned a URL outside its official HTTPS allowlist.",
            502,
            "connector_invalid_url",
        )
    return normalize_url(value)


class ConnectorHttpClient:
    """Shared redirect, retry, rate-limit, size, and diagnostic policy."""

    def __init__(
        self,
        settings: Settings,
        manifest: ConnectorManifest,
        logger: IntegrationLogger | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep=asyncio.sleep,
        jitter=lambda: random.uniform(0.05, 0.25),
    ):
        manifest.validate()
        self.settings = settings
        self.manifest = manifest
        self.logger = logger
        self.transport = transport
        self.sleep = sleep
        self.jitter = jitter
        self._rate_lock = asyncio.Lock()
        self._last_request = 0.0

    async def _rate_limit(self) -> None:
        async with self._rate_lock:
            delay = self.manifest.minimum_interval_seconds - (time.monotonic() - self._last_request)
            if delay > 0:
                await self.sleep(delay)
            self._last_request = time.monotonic()

    def _log(
        self,
        *,
        operation: str,
        attempt: int,
        url: str,
        started: float,
        response: httpx.Response | None,
        error: str | None,
    ) -> None:
        if not self.logger:
            return
        body = None
        if response is not None:
            body = response_snapshot(response.content, response.headers.get("content-type", ""))
        self.logger.record(
            provider=self.manifest.name,
            operation=f"{operation}_attempt_{attempt}",
            method="GET",
            url=url,
            status="success" if response is not None and error is None else "error",
            duration_ms=(time.monotonic() - started) * 1000,
            request_headers={"Accept": "application/json, text/json, application/xml, text/html, */*"},
            response_status=response.status_code if response is not None else None,
            response_headers=response.headers if response is not None else None,
            response_body=body,
            error=error,
        )

    async def get(
        self,
        url: str,
        *,
        operation: str,
        max_bytes: int | None = None,
        headers: dict | None = None,
        accepted_statuses: frozenset[int] = frozenset(),
    ) -> ConnectorArtifact:
        current = validate_official_url(url, self.manifest.allowed_hosts)
        limit = max_bytes or self.settings.max_document_bytes
        attempts = 3
        last_error: Exception | None = None
        async with httpx.AsyncClient(
            timeout=self.settings.fetch_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=self.transport,
            headers={
                "User-Agent": "HelveticLens/0.1 (+https://github.com/HappyMiha/helvetic-lens)",
                "Accept": "application/json, text/json, application/xml, text/html, */*",
                **(headers or {}),
            },
        ) as client:

            async def bounded_request(target: str) -> httpx.Response:
                request = client.build_request("GET", target)
                raw = await client.send(request, stream=True)
                chunks: list[bytes] = []
                size = 0
                try:
                    declared_size = raw.headers.get("content-length")
                    if declared_size and int(declared_size) > limit:
                        raise DomainError(
                            "The official artifact exceeds the connector content limit.",
                            413,
                            "connector_content_too_large",
                        )
                    async for chunk in raw.aiter_bytes():
                        size += len(chunk)
                        if size > limit:
                            raise DomainError(
                                "The official artifact exceeds the connector content limit.",
                                413,
                                "connector_content_too_large",
                            )
                        chunks.append(chunk)
                    response_headers = dict(raw.headers)
                    # aiter_bytes() has already decoded gzip/br content. Keeping the
                    # original encoding header would make the reconstructed bounded
                    # response decode the bytes a second time.
                    response_headers.pop("content-encoding", None)
                    response_headers.pop("content-length", None)
                    return httpx.Response(
                        raw.status_code,
                        headers=response_headers,
                        content=b"".join(chunks),
                        request=request,
                    )
                finally:
                    await raw.aclose()

            for attempt in range(1, attempts + 1):
                started = time.monotonic()
                response = None
                try:
                    await self._rate_limit()
                    target = await validate_public_url(current, self.settings.allow_private_sources)
                    response = await bounded_request(target)
                    redirects = 0
                    while response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location or redirects >= 5:
                            raise DomainError(
                                "The official source returned an invalid redirect chain.",
                                502,
                                "connector_redirect_error",
                            )
                        current = validate_official_url(
                            urljoin(current, location), self.manifest.allowed_hosts
                        )
                        target = await validate_public_url(current, self.settings.allow_private_sources)
                        response = await bounded_request(target)
                        redirects += 1
                    if response.status_code in _RETRYABLE_STATUS:
                        raise httpx.HTTPStatusError(
                            "temporary official source response",
                            request=response.request,
                            response=response,
                        )
                    if response.status_code >= 400 and response.status_code not in accepted_statuses:
                        raise DomainError(
                            f"The official source returned HTTP {response.status_code}.",
                            502,
                            "connector_http_error",
                        )
                    self._log(
                        operation=operation,
                        attempt=attempt,
                        url=current,
                        started=started,
                        response=response,
                        error=None,
                    )
                    content_type = response.headers.get("content-type", "application/octet-stream")
                    filename = PurePosixPath(urlsplit(current).path).name or "artifact"
                    return ConnectorArtifact(
                        current,
                        response.content,
                        content_type,
                        filename,
                        status_code=response.status_code,
                    )
                except DomainError as exc:
                    self._log(
                        operation=operation,
                        attempt=attempt,
                        url=current,
                        started=started,
                        response=response,
                        error=exc.message,
                    )
                    raise
                except (httpx.HTTPError, httpx.TimeoutException) as exc:
                    last_error = exc
                    self._log(
                        operation=operation,
                        attempt=attempt,
                        url=current,
                        started=started,
                        response=response,
                        error="Temporary official source failure; retrying."
                        if attempt < attempts
                        else "Official source failed after bounded retries.",
                    )
                    if attempt < attempts:
                        await self.sleep((2 ** (attempt - 1)) * 0.25 + self.jitter())
        raise DomainError(
            "The official source failed after bounded retries.",
            502,
            "connector_unavailable",
        ) from last_error


@dataclass(frozen=True)
class ConnectorRunResult:
    connector: str
    stream: str
    status: str
    page_id: str | None
    persisted: int
    total: int
    next_cursor: dict | None
    error: str | None = None


class ConnectorRunner:
    """Persist one discovery page and advance only after a safe commit boundary."""

    def __init__(
        self,
        db: Database,
        corpus: RegulatoryCorpus,
        settings: Settings,
    ):
        self.db = db
        self.corpus = corpus
        self.settings = settings

    def _state(self, session, manifest: ConnectorManifest, stream: str) -> ConnectorState:
        state = session.scalar(
            select(ConnectorState).where(
                ConnectorState.connector == manifest.name,
                ConnectorState.stream == stream,
            )
        )
        if state is None:
            state = ConnectorState(
                connector=manifest.name,
                stream=stream,
                contract_version=CONNECTOR_CONTRACT_VERSION,
                connector_version=manifest.connector_version,
                schema_version=manifest.schema_version,
                cursor_json=None,
                page_checkpoint_json={},
                health="unknown",
                source_contract_json=dict(manifest.source_contract),
            )
            session.add(state)
            session.flush()
        return state

    def _degrade(self, manifest: ConnectorManifest, stream: str, message: str) -> None:
        with self.db.session(include_all_organizations=True) as session:
            state = self._state(session, manifest, stream)
            state.health = "degraded"
            state.health_message = message[:2000]
            state.last_completed_at = utcnow()
            state.updated_at = utcnow()
            session.commit()

    def _validate_page(
        self,
        manifest: ConnectorManifest,
        page: DiscoveryPage,
        input_cursor: dict | None,
    ) -> None:
        if page.schema_version != manifest.schema_version:
            raise DomainError(
                "The official source schema version no longer matches the connector.",
                502,
                "connector_contract_drift",
            )
        _require(page.raw_provenance_ref, "page.raw_provenance_ref")
        if not page.items and not page.empty_is_valid:
            raise DomainError(
                "The official source returned an implausibly empty discovery page.",
                502,
                "connector_contract_drift",
            )
        if page.items and not page.complete and page.next_cursor == input_cursor:
            raise DomainError(
                "The official source did not advance its discovery cursor.",
                502,
                "connector_contract_drift",
            )
        for item in page.items:
            item.validate(manifest)

    def _page_key(
        self,
        manifest: ConnectorManifest,
        stream: str,
        cursor: dict | None,
        page: DiscoveryPage,
    ) -> str:
        return _fingerprint(
            {
                "connector": manifest.name,
                "stream": stream,
                "schema": page.schema_version,
                "cursor": cursor,
                "next": page.next_cursor,
                "raw": page.raw_provenance_ref,
                "items": [(item.external_identity, item.source_revision) for item in page.items],
            }
        )

    def _save_artifact(self, artifact: ConnectorArtifact):
        digest = hashlib.sha256(artifact.body).hexdigest()
        if artifact.expected_sha256 and artifact.expected_sha256.lower() != digest:
            raise DomainError(
                "The downloaded artifact hash does not match official metadata.",
                502,
                "connector_artifact_hash_mismatch",
            )
        if len(artifact.body) > self.settings.max_document_bytes:
            raise DomainError(
                "The official artifact exceeds the configured document limit.",
                413,
                "connector_content_too_large",
            )
        extracted = extract(
            artifact.body,
            artifact.content_type,
            artifact.filename,
            provider="official_connector",
        )
        extension = Path(extracted.filename).suffix.lower()[:12]
        artifact_key = digest + extension
        folder = self.settings.storage_path / "artifacts"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / artifact_key
        if not path.exists():
            path.write_bytes(artifact.body)
        return digest, artifact_key, extracted

    def _validate_metadata(
        self,
        manifest: ConnectorManifest,
        reference: DiscoveryReference,
        metadata: ConnectorMetadata,
    ) -> None:
        if metadata.external_identity != reference.external_identity:
            raise DomainError(
                "Connector metadata changed the stable external identity.",
                502,
                "connector_contract_drift",
            )
        if metadata.source_revision != reference.source_revision:
            raise DomainError(
                "Connector metadata changed the source revision.",
                502,
                "connector_contract_drift",
            )
        _require(metadata.title, "metadata.title")
        if not metadata.identifiers:
            raise DomainError(
                "Connector metadata omitted authority identifiers.",
                502,
                "connector_contract_drift",
            )
        validate_official_url(metadata.canonical_url, manifest.allowed_hosts)

    async def _persist_item(
        self,
        connector: OfficialConnector,
        stream: str,
        reference: DiscoveryReference,
    ) -> int:
        manifest = connector.manifest
        metadata = await connector.fetch_metadata(reference)
        self._validate_metadata(manifest, reference, metadata)
        expressions = await connector.list_expressions(metadata)
        if not expressions:
            raise DomainError(
                "Connector metadata has no available language expression.",
                502,
                "connector_contract_drift",
            )

        prepared = []
        for expression in expressions:
            language = _require(expression.language, "expression.language").lower()
            expression_key = _require(expression.expression_key, "expression.expression_key")
            official_url = validate_official_url(expression.official_url, manifest.allowed_hosts)
            with self.db.session(include_all_organizations=True) as session:
                receipt = session.scalar(
                    select(ConnectorReceipt).where(
                        ConnectorReceipt.connector == manifest.name,
                        ConnectorReceipt.stream == stream,
                        ConnectorReceipt.external_identity == metadata.external_identity,
                        ConnectorReceipt.expression_key == expression_key,
                        ConnectorReceipt.source_revision == metadata.source_revision,
                    )
                )
            if receipt:
                continue

            version_input = None
            artifact_hash = None
            if expression.version_key:
                artifact = await connector.fetch_official_artifact(expression)
                if artifact is not None:
                    artifact_url = validate_official_url(artifact.url, manifest.allowed_hosts)
                    artifact_hash, artifact_key, extracted = self._save_artifact(
                        replace(artifact, url=artifact_url)
                    )
                    version_input = VersionInput(
                        key=expression.version_key,
                        content_hash=extracted.content_hash,
                        artifact_key=artifact_key,
                        extractor=extracted.extractor,
                        text=extracted.text,
                        passages=tuple(extracted.passages),
                        content_type=extracted.content_type,
                        filename=extracted.filename,
                        source_url=artifact_url,
                        fetched_at=utcnow(),
                        metadata={
                            **expression.metadata,
                            "artifact_sha256": artifact_hash,
                            "raw_provenance": artifact.raw_provenance,
                        },
                    )
                else:
                    version_input = VersionInput(
                        key=expression.version_key,
                        source_url=expression.artifact_url or official_url,
                        metadata=dict(expression.metadata),
                    )

            prepared.append(
                (
                    expression_key,
                    artifact_hash,
                    DocumentInput(
                        kind=metadata.kind,
                        authority=manifest.authority,
                        identifiers=metadata.identifiers,
                        title=metadata.title,
                        stable_official_url=metadata.canonical_url,
                        lifecycle_status=metadata.lifecycle_status,
                        metadata={
                            **metadata.metadata,
                            "connector": manifest.name,
                            "connector_version": manifest.connector_version,
                            "schema_version": manifest.schema_version,
                            "raw_provenance": metadata.raw_provenance,
                            "attribution": manifest.attribution,
                        },
                        expression=ExpressionInput(
                            language=language,
                            key=expression_key,
                            title=expression.title or metadata.title,
                            official_url=official_url,
                            metadata=dict(expression.metadata),
                            version=version_input,
                        ),
                        dates=metadata.dates + expression.dates,
                    ),
                )
            )

        relations = await connector.extract_relations(metadata) if prepared else ()
        source_result = None
        source_version_id = None
        with self.db.session(include_all_organizations=True) as session:
            for expression_key, artifact_hash, document in prepared:
                # A competing worker may have committed after the preflight check.
                receipt = session.scalar(
                    select(ConnectorReceipt).where(
                        ConnectorReceipt.connector == manifest.name,
                        ConnectorReceipt.stream == stream,
                        ConnectorReceipt.external_identity == metadata.external_identity,
                        ConnectorReceipt.expression_key == expression_key,
                        ConnectorReceipt.source_revision == metadata.source_revision,
                    )
                )
                if receipt:
                    continue
                primary_identifier = next(
                    (item for item in document.identifiers if item.scheme == "eli_uri"),
                    None,
                )
                if primary_identifier:
                    self.corpus.bind_legacy_official_identity(
                        session,
                        authority=document.authority,
                        scheme=primary_identifier.scheme,
                        value=primary_identifier.value,
                        kind=document.kind,
                        stable_official_url=document.stable_official_url
                        or primary_identifier.source_url
                        or primary_identifier.value,
                    )
                merged = self.corpus.merge_document(session, document)
                source_result = source_result or merged
                source_version_id = source_version_id or (merged.version.id if merged.version else None)
                event_evidence = {
                    "connector": manifest.name,
                    "stream": stream,
                    "external_identity": metadata.external_identity,
                    "source_revision": metadata.source_revision,
                    "expression_key": expression_key,
                    "reference": reference.raw_provenance_ref,
                }
                if merged.created_work:
                    self.corpus.record_event(
                        session,
                        EventInput(
                            work_id=merged.work.id,
                            expression_id=merged.expression.id,
                            document_version_id=merged.version.id if merged.version else None,
                            authority=manifest.authority,
                            event_type="created",
                            detected_at=utcnow(),
                            provenance_method="official_metadata",
                            source_url=metadata.canonical_url,
                            evidence=event_evidence,
                            external_key=(
                                f"{manifest.name}:{stream}:{metadata.external_identity}:created"
                            ),
                            connector=manifest.name,
                        ),
                    )
                if merged.created_version and merged.version:
                    self.corpus.record_event(
                        session,
                        EventInput(
                            work_id=merged.work.id,
                            expression_id=merged.expression.id,
                            document_version_id=merged.version.id,
                            authority=manifest.authority,
                            event_type="new_version",
                            detected_at=utcnow(),
                            provenance_method="official_metadata",
                            source_url=metadata.canonical_url,
                            evidence={
                                **event_evidence,
                                "version_key": merged.version.version_key,
                            },
                            external_key=(
                                f"{manifest.name}:{stream}:{expression_key}:"
                                f"{merged.version.version_key}:new_version"
                            ),
                            connector=manifest.name,
                        ),
                    )
                if merged.lifecycle_changed:
                    self.corpus.record_event(
                        session,
                        EventInput(
                            work_id=merged.work.id,
                            expression_id=merged.expression.id,
                            document_version_id=merged.version.id if merged.version else None,
                            authority=manifest.authority,
                            event_type="status_changed",
                            detected_at=utcnow(),
                            provenance_method="official_metadata",
                            source_url=metadata.canonical_url,
                            evidence={
                                **event_evidence,
                                "previous_status": merged.previous_lifecycle_status,
                                "current_status": document.lifecycle_status,
                            },
                            external_key=(
                                f"{manifest.name}:{stream}:{metadata.external_identity}:"
                                f"{metadata.source_revision}:status:{document.lifecycle_status}"
                            ),
                            connector=manifest.name,
                        ),
                    )
                session.add(
                    ConnectorReceipt(
                        connector=manifest.name,
                        stream=stream,
                        external_identity=metadata.external_identity,
                        expression_key=expression_key,
                        source_revision=metadata.source_revision,
                        work_id=merged.work.id,
                        expression_id=merged.expression.id,
                        document_version_id=merged.version.id if merged.version else None,
                        canonical_url=metadata.canonical_url,
                        artifact_hash=artifact_hash,
                        raw_provenance_json={
                            **metadata.raw_provenance,
                            "reference": reference.raw_provenance_ref,
                            "attribution": manifest.attribution,
                        },
                        contract_version=CONNECTOR_CONTRACT_VERSION,
                        connector_version=manifest.connector_version,
                        schema_version=manifest.schema_version,
                    )
                )

            if source_result:
                for relation in relations:
                    target = self.corpus.merge_document(session, relation.target)
                    subject_work_id = (
                        target.work.id if relation.reverse else source_result.work.id
                    )
                    object_work_id = (
                        source_result.work.id if relation.reverse else target.work.id
                    )
                    self.corpus.record_relation(
                        session,
                        RelationInput(
                            subject_work_id=subject_work_id,
                            object_work_id=object_work_id,
                            source_version_id=None if relation.reverse else source_version_id,
                            authority=manifest.authority,
                            relation_type=relation.relation_type,
                            state=relation.state,
                            provenance_method=relation.provenance_method,
                            evidence=relation.evidence,
                            confidence=relation.confidence,
                            rule_or_model_revision=relation.rule_revision,
                        ),
                    )
            session.commit()
        return 1

    async def run_page(
        self,
        connector: OfficialConnector,
        *,
        stream: str = "default",
    ) -> ConnectorRunResult:
        manifest = connector.manifest
        manifest.validate()
        with self.db.session(include_all_organizations=True) as session:
            state = self._state(session, manifest, stream)
            state.connector_version = manifest.connector_version
            state.schema_version = manifest.schema_version
            state.contract_version = CONNECTOR_CONTRACT_VERSION
            state.last_started_at = utcnow()
            state.updated_at = utcnow()
            cursor = state.cursor_json
            checkpoint = dict(state.page_checkpoint_json or {})
            session.commit()

        try:
            health = await connector.health()
            health.validate()
            if health.status == "error":
                raise DomainError(health.message, 502, "connector_unavailable")
            page = await connector.discover_since(cursor, checkpoint)
            self._validate_page(manifest, page, cursor)
        except DomainError as exc:
            self._degrade(manifest, stream, exc.message)
            return ConnectorRunResult(manifest.name, stream, "degraded", None, 0, 0, cursor, exc.message)
        except Exception:
            message = "The official source response could not be read using the expected contract."
            self._degrade(manifest, stream, message)
            return ConnectorRunResult(manifest.name, stream, "degraded", None, 0, 0, cursor, message)

        page_key = self._page_key(manifest, stream, cursor, page)
        with self.db.session(include_all_organizations=True) as session:
            state = self._state(session, manifest, stream)
            record = session.scalar(
                select(ConnectorPage).where(
                    ConnectorPage.connector == manifest.name,
                    ConnectorPage.stream == stream,
                    ConnectorPage.page_key == page_key,
                )
            )
            if record and record.status == "persisted":
                return ConnectorRunResult(
                    manifest.name,
                    stream,
                    "persisted",
                    record.id,
                    record.persisted_count,
                    record.item_count,
                    record.output_cursor_json,
                )
            if record is None:
                record = ConnectorPage(
                    connector=manifest.name,
                    stream=stream,
                    page_key=page_key,
                    input_cursor_json=cursor,
                    output_cursor_json=page.next_cursor,
                    safe_checkpoint_json={"next_index": 0},
                    item_count=len(page.items),
                    raw_provenance_ref=page.raw_provenance_ref,
                    attribution=manifest.attribution,
                )
                session.add(record)
                session.flush()
            start_index = int((record.safe_checkpoint_json or {}).get("next_index", 0))
            page_id = record.id
            already_persisted = record.persisted_count
            session.commit()

        for index in range(start_index, len(page.items)):
            reference = page.items[index]
            try:
                count = await self._persist_item(connector, stream, reference)
            except Exception as exc:
                message = exc.message if isinstance(exc, DomainError) else str(exc)
                code = exc.code if isinstance(exc, DomainError) else "connector_item_error"
                with self.db.session(include_all_organizations=True) as session:
                    state = self._state(session, manifest, stream)
                    record = session.get(ConnectorPage, page_id)
                    attempt = (
                        session.scalar(
                            select(func.count())
                            .select_from(ConnectorItemError)
                            .where(
                                ConnectorItemError.page_id == page_id,
                                ConnectorItemError.item_index == index,
                            )
                        )
                        or 0
                    ) + 1
                    session.add(
                        ConnectorItemError(
                            page_id=page_id,
                            item_index=index,
                            external_identity=reference.external_identity,
                            attempt=attempt,
                            code=code,
                            detail=message[:4000],
                            retryable=True,
                            raw_provenance_ref=reference.raw_provenance_ref,
                        )
                    )
                    record.status = "partial"
                    record.error_count += 1
                    record.error_detail = message[:2000]
                    record.safe_checkpoint_json = {"next_index": index}
                    state.page_checkpoint_json = {
                        "page_key": page_key,
                        "next_index": index,
                    }
                    state.health = "degraded"
                    state.health_message = message[:2000]
                    state.last_completed_at = utcnow()
                    state.updated_at = utcnow()
                    session.commit()
                    return ConnectorRunResult(
                        manifest.name,
                        stream,
                        "partial",
                        page_id,
                        record.persisted_count,
                        len(page.items),
                        cursor,
                        message,
                    )
            with self.db.session(include_all_organizations=True) as session:
                state = self._state(session, manifest, stream)
                record = session.get(ConnectorPage, page_id)
                record.persisted_count = already_persisted + count
                already_persisted = record.persisted_count
                record.safe_checkpoint_json = {"next_index": index + 1}
                state.page_checkpoint_json = {
                    "page_key": page_key,
                    "next_index": index + 1,
                }
                session.commit()

        with self.db.session(include_all_organizations=True) as session:
            state = self._state(session, manifest, stream)
            record = session.get(ConnectorPage, page_id)
            state.cursor_json = page.next_cursor
            state.page_checkpoint_json = {}
            state.health = health.status
            state.health_message = health.message[:2000]
            state.source_contract_json = {
                **manifest.source_contract,
                **health.source_contract,
            }
            state.last_completed_at = utcnow()
            state.last_success_at = utcnow()
            state.updated_at = utcnow()
            record.status = "persisted"
            record.completed_at = utcnow()
            record.safe_checkpoint_json = {"next_index": len(page.items)}
            session.commit()
            return ConnectorRunResult(
                manifest.name,
                stream,
                "persisted",
                page_id,
                record.persisted_count,
                len(page.items),
                page.next_cursor,
            )

    def statuses(self) -> list[dict]:
        with self.db.session(include_all_organizations=True) as session:
            states = session.scalars(
                select(ConnectorState).order_by(ConnectorState.connector, ConnectorState.stream)
            ).all()
            return [
                {
                    "connector": state.connector,
                    "stream": state.stream,
                    "health": state.health,
                    "message": state.health_message,
                    "contract_version": state.contract_version,
                    "connector_version": state.connector_version,
                    "schema_version": state.schema_version,
                    "cursor": state.cursor_json,
                    "checkpoint": state.page_checkpoint_json,
                    "source_contract": state.source_contract_json,
                    "last_started_at": state.last_started_at,
                    "last_completed_at": state.last_completed_at,
                    "last_success_at": state.last_success_at,
                }
                for state in states
            ]
