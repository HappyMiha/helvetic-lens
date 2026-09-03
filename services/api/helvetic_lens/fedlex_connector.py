"""Native Fedlex RSS and JOLux/SPARQL catalogue connector."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import PurePosixPath
from urllib.parse import urlencode, urlsplit
from xml.etree import ElementTree

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
from .db import utcnow
from .extraction import FEDLEX_DATA_ORIGIN, FEDLEX_SPARQL_ENDPOINT, fedlex_eli_reference
from .integration_logs import IntegrationLogger
from .official_source_contracts import FEDLEX_CONTRACT, _validate_payload
from .regulatory_corpus import DateInput, DocumentInput, ExpressionInput, IdentifierInput

FEDLEX_LANGUAGES = {"de": "DEU", "fr": "FRA", "it": "ITA", "rm": "ROH", "en": "ENG"}
FEDLEX_RSS_LANGUAGES = frozenset({"de", "fr", "it"})
FEDLEX_COLLECTIONS = frozenset({"cc", "oc", "fga"})
FEDLEX_RSS_OVERLAP = timedelta(days=2)
FEDLEX_METADATA_LIMIT = 2_000_000
FEDLEX_PAGE_SIZE = 25
FEDLEX_EXPRESSION_LIMIT = 500
_JOLUX = "http://data.legilux.public.lu/resource/ontology/jolux#"


def _binding(row: dict, key: str) -> str | None:
    value = row.get(key)
    return value.get("value") if isinstance(value, dict) else None


def _rows(payload: bytes, *, required: frozenset[str] = frozenset()) -> list[dict]:
    try:
        parsed = json.loads(payload)
        rows = parsed["results"]["bindings"]
        if not isinstance(rows, list):
            raise TypeError
        for row in rows:
            if not isinstance(row, dict) or any(not _binding(row, field) for field in required):
                raise TypeError
        return rows
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DomainError(
            "Fedlex SPARQL no longer matches the expected JOLux result contract.",
            502,
            "connector_contract_drift",
        ) from exc


def _iso_instant(value: str) -> str:
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError) as exc:
        raise DomainError(
            "Fedlex RSS contains an invalid publication timestamp.",
            502,
            "connector_contract_drift",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _date(value: str | None, kind: str, source_url: str, *, target: str = "work") -> DateInput | None:
    if not value:
        return None
    return DateInput(
        target=target,
        kind=kind,
        value=value,
        precision="instant" if "T" in value else "day",
        provenance="fedlex_jolux",
        source_url=source_url,
    )


def _eli_collection(work_uri: str) -> str:
    reference = fedlex_eli_reference(work_uri)
    if not reference or reference.work_uri != work_uri:
        raise DomainError(
            "Fedlex returned an invalid ELI work identity.",
            502,
            "connector_contract_drift",
        )
    return reference.collection


def _language_from_uri(value: str | None, expression_uri: str) -> str:
    if value:
        code = value.rsplit("/", 1)[-1].upper()
        for language, official in FEDLEX_LANGUAGES.items():
            if official == code:
                return language
    candidate = expression_uri.rstrip("/").rsplit("/", 1)[-1].lower()
    if candidate in FEDLEX_LANGUAGES:
        return candidate
    raise DomainError(
        "Fedlex returned an expression with an unknown language.",
        502,
        "connector_contract_drift",
    )


def _kind(collection: str) -> str:
    return "official_notice" if collection == "fga" else "act"


def _relation_type(value: str | None, fallback: str = "potentially_impacts") -> str:
    code = (value or "").casefold()
    if any(marker in code for marker in ("repeal", "abrog", "aufheb")):
        return "repeals"
    if any(marker in code for marker in ("replace", "ersetz", "remplac")):
        return "replaces"
    if any(marker in code for marker in ("amend", "modif", "änder")):
        return "amends"
    return fallback


class FedlexConnector(OfficialConnector):
    """One bounded Fedlex stream: RSS language or one collection reconciliation page."""

    manifest = FEDLEX_CONTRACT.manifest

    def __init__(
        self,
        settings: Settings,
        logger: IntegrationLogger | None = None,
        *,
        mode: str = "rss",
        language: str = "de",
        collection: str = "cc",
        page_size: int = FEDLEX_PAGE_SIZE,
        transport=None,
        sleep=None,
        now=lambda: datetime.now(UTC),
    ):
        if mode not in {"rss", "reconcile"}:
            raise ValueError("Fedlex mode must be rss or reconcile")
        if mode == "rss" and language not in FEDLEX_RSS_LANGUAGES:
            raise ValueError("Fedlex RSS is supported for de, fr, and it")
        if collection not in FEDLEX_COLLECTIONS:
            raise ValueError("Unknown Fedlex collection")
        if not 1 <= page_size <= 100:
            raise ValueError("Fedlex page size must be between 1 and 100")
        self.settings = settings
        self.mode = mode
        self.language = language
        self.collection = collection
        self.page_size = page_size
        self.now = now
        options = {"transport": transport}
        if sleep is not None:
            options["sleep"] = sleep
        self.http = ConnectorHttpClient(settings, self.manifest, logger, **options)

    @property
    def stream(self) -> str:
        return f"rss-{self.language}" if self.mode == "rss" else f"reconcile-{self.collection}"

    @property
    def rss_url(self) -> str:
        return f"{FEDLEX_DATA_ORIGIN}/api/rss-{self.language}.xml"

    async def _sparql(self, query: str, operation: str) -> list[dict]:
        url = (
            FEDLEX_SPARQL_ENDPOINT
            + "?"
            + urlencode({"query": query, "format": "application/sparql-results+json"})
        )
        artifact = await self.http.get(
            url,
            operation=operation,
            max_bytes=FEDLEX_METADATA_LIMIT,
            headers={"Accept": "application/sparql-results+json"},
        )
        return _rows(artifact.body)

    async def health(self) -> ConnectorHealthReport:
        try:
            if self.mode == "rss":
                artifact = await self.http.get(
                    self.rss_url,
                    operation="fedlex_rss_health",
                    max_bytes=1_000_000,
                )
                observed = _validate_payload("fedlex_rss", artifact.body)
            else:
                rows = await self._sparql(
                    """
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT DISTINCT ?work WHERE {
  ?work a jolux:Work .
  FILTER(STRSTARTS(STR(?work), "https://fedlex.data.admin.ch/eli/"))
} LIMIT 1
""",
                    "fedlex_sparql_health",
                )
                if not rows or not _binding(rows[0], "work"):
                    raise DomainError(
                        "Fedlex SPARQL returned an implausibly empty health result.",
                        502,
                        "connector_contract_drift",
                    )
                observed = {"format": "sparql-results+json", "sample_work": _binding(rows[0], "work")}
            return ConnectorHealthReport(
                "healthy",
                "The bounded Fedlex source contract passed.",
                self.now(),
                {**self.manifest.source_contract, "observed": observed, "stream": self.stream},
            )
        except DomainError as exc:
            return ConnectorHealthReport(
                "degraded",
                exc.message,
                self.now(),
                {**self.manifest.source_contract, "error_code": exc.code, "stream": self.stream},
            )

    async def discover_since(self, cursor: dict | None, page_checkpoint: dict) -> DiscoveryPage:
        if self.mode == "rss":
            return await self._discover_rss(cursor)
        return await self._discover_reconciliation(cursor)

    async def _discover_rss(self, cursor: dict | None) -> DiscoveryPage:
        artifact = await self.http.get(
            self.rss_url,
            operation="fedlex_rss_discovery",
            max_bytes=1_000_000,
        )
        try:
            root = ElementTree.fromstring(artifact.body)
            build_date = next(
                (
                    "".join(node.itertext()).strip()
                    for node in root.iter()
                    if node.tag.endswith("lastBuildDate")
                ),
                None,
            )
            entries = []
            for node in root.iter():
                if not node.tag.endswith("item"):
                    continue
                values = {child.tag.rsplit("}", 1)[-1]: "".join(child.itertext()).strip() for child in node}
                if not {"title", "link", "pubDate"}.issubset(values):
                    raise ValueError
                work = fedlex_eli_reference(values["link"])
                if not work or work.source_url != work.work_uri:
                    raise ValueError
                published = _iso_instant(values["pubDate"])
                entries.append((published, work.work_uri, values))
        except (ElementTree.ParseError, ValueError) as exc:
            raise DomainError(
                "Fedlex RSS no longer matches the expected item contract.",
                502,
                "connector_contract_drift",
            ) from exc
        if not entries:
            raise DomainError(
                "Fedlex RSS unexpectedly contains no publications.",
                502,
                "connector_contract_drift",
            )
        watermark = (cursor or {}).get("watermark")
        cutoff = None
        if watermark:
            try:
                cutoff = datetime.fromisoformat(watermark.replace("Z", "+00:00")) - FEDLEX_RSS_OVERLAP
            except ValueError as exc:
                raise DomainError(
                    "The saved Fedlex RSS cursor is invalid.",
                    500,
                    "connector_cursor_invalid",
                ) from exc
        selected = [
            item
            for item in entries
            if cutoff is None or datetime.fromisoformat(item[0].replace("Z", "+00:00")) >= cutoff
        ]
        latest = max(item[0] for item in entries)
        items = tuple(
            DiscoveryReference(
                external_identity=work_uri,
                source_revision=hashlib.sha256(
                    json.dumps(
                        {"published": published, "title": values["title"], "language": self.language},
                        sort_keys=True,
                    ).encode()
                ).hexdigest(),
                canonical_url=work_uri,
                raw_provenance_ref=(
                    f"{self.rss_url}#guid={values.get('guid') or work_uri}"
                    f"&published={published}&language={self.language}"
                ),
            )
            for published, work_uri, values in selected
        )
        return DiscoveryPage(
            items=items,
            next_cursor={"watermark": latest, "overlap_days": FEDLEX_RSS_OVERLAP.days},
            raw_provenance_ref=f"{self.rss_url}#lastBuildDate={build_date or latest}",
            schema_version=self.manifest.schema_version,
            complete=True,
            empty_is_valid=bool(cursor),
        )

    async def _discover_reconciliation(self, cursor: dict | None) -> DiscoveryPage:
        last_key = (cursor or {}).get("last_key") or ""
        prefix = f"{FEDLEX_DATA_ORIGIN}/eli/{self.collection}/"
        query = f"""
PREFIX jolux: <{_JOLUX}>
SELECT ?work (MAX(?publicationDate0) AS ?publicationDate)
             (MAX(?documentDate0) AS ?documentDate)
             (MAX(?entryInForce0) AS ?entryInForce)
             (MAX(?noLongerInForce0) AS ?noLongerInForce)
             (MAX(?versionDate0) AS ?latestVersionDate)
             (SAMPLE(?status0) AS ?status) WHERE {{
  ?work a jolux:Work .
  FILTER(STRSTARTS(STR(?work), "{prefix}"))
  FILTER(STR(?work) > {json.dumps(last_key)})
  OPTIONAL {{ ?work jolux:publicationDate ?publicationDate0 . }}
  OPTIONAL {{ ?work jolux:dateDocument ?documentDate0 . }}
  OPTIONAL {{ ?work jolux:dateEntryInForce ?entryInForce0 . }}
  OPTIONAL {{ ?work jolux:dateNoLongerInForce ?noLongerInForce0 . }}
  OPTIONAL {{ ?work jolux:inForceStatus ?status0 . }}
  OPTIONAL {{ ?version jolux:isMemberOf ?work ; jolux:dateApplicability ?versionDate0 . }}
}}
GROUP BY ?work
ORDER BY STR(?work)
LIMIT {self.page_size}
"""
        rows = await self._sparql(query, f"fedlex_{self.collection}_reconciliation")
        unique: dict[str, dict] = {}
        for row in rows:
            work_uri = _binding(row, "work")
            if not work_uri or not work_uri.startswith(prefix):
                raise DomainError(
                    "Fedlex reconciliation returned an out-of-collection identity.",
                    502,
                    "connector_contract_drift",
                )
            _eli_collection(work_uri)
            unique[work_uri] = row
        if not unique and not last_key:
            raise DomainError(
                f"Fedlex {self.collection} reconciliation was implausibly empty.",
                502,
                "connector_contract_drift",
            )
        ordered = sorted(unique.items())
        completed_cycle = len(ordered) < self.page_size
        next_cursor = {
            "last_key": "" if completed_cycle else ordered[-1][0],
            "cycle": int((cursor or {}).get("cycle", 0)) + (1 if completed_cycle else 0),
        }
        items = tuple(
            DiscoveryReference(
                external_identity=work_uri,
                source_revision=hashlib.sha256(
                    json.dumps(
                        {key: _binding(row, key) for key in sorted(row)},
                        sort_keys=True,
                    ).encode()
                ).hexdigest(),
                canonical_url=work_uri,
                raw_provenance_ref=(f"{FEDLEX_SPARQL_ENDPOINT}#collection={self.collection}&work={work_uri}"),
            )
            for work_uri, row in ordered
        )
        return DiscoveryPage(
            items=items,
            next_cursor=next_cursor,
            raw_provenance_ref=(
                f"{FEDLEX_SPARQL_ENDPOINT}#collection={self.collection}"
                f"&after={last_key or 'START'}&limit={self.page_size}"
            ),
            schema_version=self.manifest.schema_version,
            complete=True,
            empty_is_valid=bool(last_key),
        )

    async def fetch_metadata(self, reference: DiscoveryReference) -> ConnectorMetadata:
        work_uri = reference.external_identity
        collection = _eli_collection(work_uri)
        query = f"""
PREFIX jolux: <{_JOLUX}>
PREFIX dct: <http://purl.org/dc/terms/>
SELECT DISTINCT ?titleExpression ?language ?title ?identifier ?historicalLegalId
                ?publicationDate ?documentDate ?entryInForce ?noLongerInForce ?endApplicability
                ?status ?typeDocument ?basicAct ?taxonomy WHERE {{
  OPTIONAL {{ <{work_uri}> dct:identifier ?identifier . }}
  OPTIONAL {{ <{work_uri}> jolux:historicalLegalId ?historicalLegalId . }}
  OPTIONAL {{ <{work_uri}> jolux:publicationDate ?publicationDate . }}
  OPTIONAL {{ <{work_uri}> jolux:dateDocument ?documentDate . }}
  OPTIONAL {{ <{work_uri}> jolux:dateEntryInForce ?entryInForce . }}
  OPTIONAL {{ <{work_uri}> jolux:dateNoLongerInForce ?noLongerInForce . }}
  OPTIONAL {{ <{work_uri}> jolux:dateEndApplicability ?endApplicability . }}
  OPTIONAL {{ <{work_uri}> jolux:inForceStatus ?status . }}
  OPTIONAL {{ <{work_uri}> jolux:typeDocument ?typeDocument . }}
  OPTIONAL {{ <{work_uri}> jolux:basicAct ?basicAct . }}
  OPTIONAL {{ <{work_uri}> jolux:classifiedByTaxonomyEntry ?taxonomy . }}
  <{work_uri}> jolux:isRealizedBy ?titleExpression .
  OPTIONAL {{ ?titleExpression jolux:language ?language . }}
  OPTIONAL {{ ?titleExpression jolux:title ?title . }}
}}
LIMIT 100
"""
        rows = await self._sparql(query, "fedlex_metadata")
        if not rows:
            raise DomainError(
                "Fedlex has no metadata for the discovered ELI identity.",
                502,
                "connector_contract_drift",
            )
        titles: dict[str, str] = {}
        for row in rows:
            expression_uri = _binding(row, "titleExpression")
            title = _binding(row, "title")
            if expression_uri and title:
                titles[_language_from_uri(_binding(row, "language"), expression_uri)] = title
        first = rows[0]
        title = titles.get("de") or titles.get("fr") or titles.get("it") or next(iter(titles.values()), None)
        if not title:
            raise DomainError(
                "Fedlex metadata omitted every official-language title.",
                502,
                "connector_contract_drift",
            )
        identifiers = [IdentifierInput("eli_uri", work_uri, work_uri)]
        historical_id = _binding(first, "historicalLegalId")
        if historical_id:
            identifiers.append(IdentifierInput("sr_rs", historical_id, work_uri))
        dates = tuple(
            item
            for item in (
                _date(_binding(first, "publicationDate"), "published_at", work_uri),
                _date(_binding(first, "documentDate"), "version_date", work_uri),
                _date(_binding(first, "entryInForce"), "effective_from", work_uri),
                _date(
                    _binding(first, "noLongerInForce") or _binding(first, "endApplicability"),
                    "effective_to",
                    work_uri,
                ),
            )
            if item
        )
        status = _binding(first, "status")
        lifecycle_status = status.rsplit("/", 1)[-1] if status else None
        return ConnectorMetadata(
            external_identity=work_uri,
            source_revision=reference.source_revision,
            kind=_kind(collection),
            title=title,
            canonical_url=work_uri,
            identifiers=tuple(identifiers),
            lifecycle_status=lifecycle_status,
            dates=dates,
            metadata={
                "collection": collection,
                "titles": titles,
                "available_languages": sorted(titles),
                "publication_identifier": _binding(first, "identifier"),
                "resource_type": _binding(first, "typeDocument"),
                "taxonomy": _binding(first, "taxonomy"),
                "basic_act": _binding(first, "basicAct"),
                "enforcement_status": status,
            },
            raw_provenance={
                "method": "fedlex_jolux_sparql",
                "source": FEDLEX_SPARQL_ENDPOINT,
                "retrieved_at": utcnow().isoformat(),
                "reference": reference.raw_provenance_ref,
            },
        )

    async def list_expressions(self, metadata: ConnectorMetadata) -> tuple[ConnectorExpression, ...]:
        work_uri = metadata.external_identity
        collection = _eli_collection(work_uri)
        if collection == "cc":
            selection = f"""
  ?version jolux:isMemberOf <{work_uri}> ;
           jolux:dateApplicability ?versionDate ;
           jolux:isRealizedBy ?expression .
"""
        else:
            selection = f"""
  BIND(<{work_uri}> AS ?version)
  <{work_uri}> jolux:isRealizedBy ?expression .
  OPTIONAL {{ <{work_uri}> jolux:publicationDate ?versionDate . }}
"""
        query = f"""
PREFIX jolux: <{_JOLUX}>
SELECT DISTINCT ?version ?versionDate ?expression ?language ?title ?manifestation ?format ?file WHERE {{
{selection}
  OPTIONAL {{ ?expression jolux:language ?language . }}
  OPTIONAL {{ ?expression jolux:title ?title . }}
  OPTIONAL {{
    ?expression jolux:isEmbodiedBy ?manifestation .
    ?manifestation jolux:userFormat ?format ; jolux:isExemplifiedBy ?file .
  }}
}}
ORDER BY DESC(?versionDate) STR(?expression) STR(?format)
LIMIT {FEDLEX_EXPRESSION_LIMIT}
"""
        rows = await self._sparql(query, "fedlex_expressions")
        grouped: dict[str, dict] = {}
        format_priority = {"html": 0, "pdf-a": 1, "pdf-x": 2, "xml": 3, "docx": 4}
        for row in rows:
            expression_uri = _binding(row, "expression")
            version_uri = _binding(row, "version")
            if not expression_uri or not version_uri or not expression_uri.startswith(version_uri + "/"):
                raise DomainError(
                    "Fedlex returned an expression outside its ELI version.",
                    502,
                    "connector_contract_drift",
                )
            language = _language_from_uri(_binding(row, "language"), expression_uri)
            if not expression_uri.startswith(work_uri + "/"):
                raise DomainError(
                    "Fedlex returned an expression outside the discovered ELI work.",
                    502,
                    "connector_contract_drift",
                )
            record = grouped.setdefault(
                expression_uri,
                {
                    "language": language,
                    "version": version_uri,
                    "date": _binding(row, "versionDate"),
                    "title": _binding(row, "title") or metadata.metadata.get("titles", {}).get(language),
                    "manifestations": [],
                },
            )
            manifestation = _binding(row, "manifestation")
            file_url = _binding(row, "file")
            format_uri = _binding(row, "format")
            if manifestation and format_uri:
                format_name = format_uri.rsplit("/", 1)[-1]
                if not manifestation.startswith(expression_uri + "/"):
                    raise DomainError(
                        "Fedlex returned a manifestation outside its expression.",
                        502,
                        "connector_contract_drift",
                    )
                record["manifestations"].append(
                    {"uri": manifestation, "format": format_name, "file": file_url}
                )
        if not grouped:
            raise DomainError(
                "Fedlex returned no expressions for the discovered work.",
                502,
                "connector_contract_drift",
            )
        today = self.now().date().isoformat()
        latest_applicable: dict[str, str] = {}
        ordered = sorted(
            grouped.items(),
            key=lambda item: (item[1]["date"] or "0000-00-00", item[0]),
            reverse=True,
        )
        for expression_uri, item in ordered:
            if item["language"] not in latest_applicable and (not item["date"] or item["date"] <= today):
                latest_applicable[item["language"]] = expression_uri
        result = []
        for expression_uri, item in ordered:
            manifestations = sorted(
                item["manifestations"],
                key=lambda entry: (format_priority.get(entry["format"], 99), entry["uri"]),
            )
            selected = next(
                (entry for entry in manifestations if entry["format"] in {"html", "pdf-a", "pdf-x"}),
                None,
            )
            artifact_url = (
                selected["uri"]
                if selected and latest_applicable.get(item["language"]) == expression_uri
                else None
            )
            version_key = item["date"] or item["version"]
            dates = ()
            if item["date"]:
                dates = (
                    DateInput(
                        target="version",
                        kind="version_date",
                        value=item["date"],
                        precision="day",
                        provenance="fedlex_jolux",
                        source_url=expression_uri,
                    ),
                )
            result.append(
                ConnectorExpression(
                    language=item["language"],
                    expression_key=expression_uri,
                    title=item["title"] or metadata.title,
                    official_url=expression_uri,
                    version_key=version_key,
                    artifact_url=artifact_url,
                    dates=dates,
                    metadata={
                        "eli_work_uri": work_uri,
                        "eli_version_uri": item["version"],
                        "eli_expression_uri": expression_uri,
                        "version_date": item["date"],
                        "manifestations": manifestations,
                        "selected_manifestation": selected,
                        "artifact_deferred": artifact_url is None,
                    },
                )
            )
        return tuple(result)

    async def fetch_official_artifact(self, expression: ConnectorExpression) -> ConnectorArtifact | None:
        if not expression.artifact_url:
            return None
        artifact = await self.http.get(
            expression.artifact_url,
            operation="fedlex_artifact",
            max_bytes=self.settings.max_document_bytes,
            headers={"Accept": "text/html, application/pdf;q=0.9, */*;q=0.1"},
        )
        return replace(
            artifact,
            filename=PurePosixPath(urlsplit(artifact.url).path).name or f"fedlex-{expression.language}.html",
            raw_provenance={
                "eli_manifestation_uri": expression.artifact_url,
                "dereferenced_url": artifact.url,
                "retrieved_at": utcnow().isoformat(),
            },
        )

    @staticmethod
    def _target_document(work_uri: str, title: str | None = None) -> DocumentInput:
        collection = _eli_collection(work_uri)
        return DocumentInput(
            kind=_kind(collection),
            authority="fedlex",
            identifiers=(IdentifierInput("eli_uri", work_uri, work_uri),),
            title=title or work_uri,
            stable_official_url=work_uri,
            expression=ExpressionInput(
                language="und",
                key=f"{work_uri}/und",
                title=title or work_uri,
                official_url=work_uri,
            ),
            metadata={"collection": collection, "placeholder_from_official_relation": True},
        )

    async def extract_relations(self, metadata: ConnectorMetadata) -> tuple[ConnectorRelation, ...]:
        work_uri = metadata.external_identity
        query = f"""
PREFIX jolux: <{_JOLUX}>
SELECT DISTINCT ?relation ?relationClass ?fromWork ?toWork ?relationType ?informationSource
                ?entryInForce ?comment WHERE {{
  {{
    BIND(<{work_uri}> AS ?fromWork)
    <{work_uri}> jolux:basicAct ?toWork .
    BIND(<{work_uri}> AS ?relation)
    BIND("basicAct" AS ?relationClass)
  }} UNION {{
    ?relation a jolux:LegalResourceImpact ;
              jolux:impactFromLegalResource/jolux:legalResourceSubdivisionIsPartOf ?fromWork ;
              jolux:impactToLegalResource/jolux:legalResourceSubdivisionIsPartOf ?toWork .
    FILTER(?fromWork = <{work_uri}> || ?toWork = <{work_uri}>)
    BIND("impact" AS ?relationClass)
    OPTIONAL {{ ?relation jolux:legalResourceImpactHasType ?relationType . }}
    OPTIONAL {{ ?relation jolux:informationSource ?informationSource . }}
    OPTIONAL {{ ?relation jolux:legalResourceImpactHasDateEntryInForce ?entryInForce . }}
    OPTIONAL {{ ?relation jolux:impactToLegalResourceComment ?comment . }}
  }} UNION {{
    ?relation a jolux:Citation ;
              jolux:citationFromLegalResource/jolux:legalResourceSubdivisionIsPartOf ?fromWork ;
              jolux:citationToLegalResource/jolux:legalResourceSubdivisionIsPartOf ?toWork .
    FILTER(?fromWork = <{work_uri}> || ?toWork = <{work_uri}>)
    BIND("citation" AS ?relationClass)
  }}
}}
LIMIT 250
"""
        rows = await self._sparql(query, "fedlex_relations")
        relations = []
        seen = set()
        for row in rows:
            from_work = _binding(row, "fromWork")
            to_work = _binding(row, "toWork")
            relation_class = _binding(row, "relationClass")
            relation_uri = _binding(row, "relation")
            if not from_work or not to_work or not relation_class or not relation_uri:
                raise DomainError(
                    "Fedlex returned an incomplete official relation.",
                    502,
                    "connector_contract_drift",
                )
            if from_work == work_uri:
                target = to_work
                direction = "outgoing"
            elif to_work == work_uri:
                target = from_work
                direction = "incoming"
            else:
                raise DomainError(
                    "Fedlex returned an unrelated JOLux relation.",
                    502,
                    "connector_contract_drift",
                )
            if target == work_uri:
                continue
            if relation_class == "citation":
                relation_type = "cites"
            elif relation_class == "basicAct":
                relation_type = "implements"
            else:
                relation_type = _relation_type(_binding(row, "relationType"))
            key = (target, relation_type, relation_uri, direction)
            if key in seen:
                continue
            seen.add(key)
            relations.append(
                ConnectorRelation(
                    target=self._target_document(target),
                    relation_type=relation_type,
                    state="confirmed",
                    provenance_method="official_metadata",
                    evidence={
                        "relation_uri": relation_uri,
                        "relation_class": relation_class,
                        "direction": direction,
                        "from_work": from_work,
                        "to_work": to_work,
                        "relation_type_uri": _binding(row, "relationType"),
                        "information_source": _binding(row, "informationSource"),
                        "entry_in_force": _binding(row, "entryInForce"),
                        "comment": _binding(row, "comment"),
                        "source": FEDLEX_SPARQL_ENDPOINT,
                    },
                    rule_revision="fedlex-jolux-relations-v1",
                    reverse=direction == "incoming",
                )
            )
        return tuple(relations)


def fedlex_connectors(
    settings: Settings,
    logger: IntegrationLogger | None = None,
) -> tuple[FedlexConnector, ...]:
    """The three fast feeds plus one bounded reconciliation stream per collection."""

    return tuple(
        [FedlexConnector(settings, logger, mode="rss", language=language) for language in ("de", "fr", "it")]
        + [
            FedlexConnector(settings, logger, mode="reconcile", collection=collection)
            for collection in ("cc", "oc", "fga")
        ]
    )
