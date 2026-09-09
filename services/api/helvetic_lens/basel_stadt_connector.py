"""Basel-Stadt's official OGD legislation mirror, with bounded reconciliation.

Discovery time / numeric version order never imply a legal commencement date.
HTML is the publisher's OGD representation, not the authoritative Kantonsblatt.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from urllib.parse import parse_qs, urlencode, urlsplit

from .config import DomainError
from .connectors import (
    ConnectorArtifact,
    ConnectorExpression,
    ConnectorHealthReport,
    ConnectorHttpClient,
    ConnectorManifest,
    ConnectorMetadata,
    DiscoveryPage,
    DiscoveryReference,
    OfficialConnector,
    validate_official_url,
)
from .regulatory_corpus import DateInput, IdentifierInput

DATASET = "https://data.bs.ch/api/explore/v2.1/catalog/datasets/100354"
DATASET_PAGE = "https://data.bs.ch/explore/dataset/100354/"
MAX_BYTES = 12_000_000
STARTER_WHERE = 'info_badge = "current" AND (systematic_number = "153.260" OR systematic_number = "730.100")'
MANIFEST = ConnectorManifest(
    name="basel-stadt-legislation", authority="basel_stadt",
    connector_version="1.0.0", schema_version="basel-ogd-laws-v1",
    allowed_hosts=frozenset({"data.bs.ch", "www.gesetzessammlung.bs.ch"}),
    attribution="Zentraler Rechtsdienst / Open Data Basel-Stadt, dataset 100354, CC BY 4.0. "
                "OGD text representation; authoritative publication: Kantonsblatt.",
    minimum_interval_seconds=0.2,
    source_contract={"dataset": DATASET_PAGE, "language": "de", "jurisdiction": "CH-BS",
                     "scope": "Published cantonal and municipal legislation versions in dataset 100354",
                     "excluded": ["court decisions", "parliamentary business", "complete Kantonsblatt",
                                  "annex contents", "documents absent from the dataset"]},
)


def fingerprint(row):
    # Taxonomy placement is not a new legal text/version.
    row = {key: value for key, value in row.items() if key not in {"index", "parent", "children", "identifier", "title", "identifier_full", "title_full"}}
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def drift(message):
    return DomainError(message, 502, "connector_contract_drift")


def validate_row(row):
    if not isinstance(row, dict) or type(row.get("v_id")) is not int or row["v_id"] <= 0:
        raise drift("Basel-Stadt omitted its numeric version identity.")
    for key in ("id", "systematic_number", "title_de"):
        if not isinstance(row.get(key), str) or not row[key].strip():
            raise drift("Basel-Stadt omitted required document metadata.")
    if not row["id"].isdigit() or row.get("is_active") not in ("True", "False"):
        raise drift("Basel-Stadt changed its identity or lifecycle schema.")
    url = row.get("version_url_de")
    if not isinstance(url, str):
        raise drift("Basel-Stadt omitted its exact publisher version link.")
    validate_official_url(url, frozenset({"www.gesetzessammlung.bs.ch"}))
    if not urlsplit(url).path.startswith("/app/de/texts_of_law/") or "/versions/" not in urlsplit(url).path:
        raise drift("Basel-Stadt returned a non-version publication link.")
    for field in ("version_active_since", "version_inactive_since"):
        if row.get(field) is not None:
            try:
                date.fromisoformat(row[field])
            except (ValueError, TypeError) as exc:
                raise drift("Basel-Stadt returned an invalid source date.") from exc
    return row


class BaselStadtConnector(OfficialConnector):
    manifest = MANIFEST

    def __init__(self, settings, logger=None, *, stream="catalogue-de", page_size=20, transport=None):
        if stream not in {"catalogue-de", "latest-de", "starter-de"} or not 1 <= page_size <= 20:
            raise DomainError("Choose a supported Basel-Stadt stream and page size.", 422, "connector_stream_invalid")
        self.stream, self.page_size = stream, page_size
        self.http = ConnectorHttpClient(settings, self.manifest, logger, transport=transport)
        self.rows = {}

    async def _query(self, params):
        url = DATASET + "/records?" + urlencode(params)
        artifact = await self.http.get(url, operation="legislation_records", max_bytes=MAX_BYTES)
        try:
            data = json.loads(artifact.body)
            if not isinstance(data, dict) or type(data.get("total_count")) is not int or not isinstance(data.get("results"), list):
                raise ValueError()
            if data["total_count"] < 0 or len(data["results"]) > params["limit"]:
                raise ValueError()
        except (ValueError, TypeError) as exc:
            raise drift("Basel-Stadt changed its OGD response schema.") from exc
        return data, url

    async def discover_since(self, cursor, page_checkpoint):
        state = cursor or {}
        before, remaining, cycle = state.get("before"), state.get("remaining", 50), state.get("cycle", 0)
        if (before is not None and (type(before) is not int or before <= 0)) or type(cycle) is not int or cycle < 0:
            raise DomainError("Restart the Basel-Stadt catalogue cursor.", 422, "connector_cursor_invalid")
        if type(remaining) is not int or not 1 <= remaining <= 50:
            raise DomainError("Restart the Basel-Stadt latest cursor.", 422, "connector_cursor_invalid")
        size = min(self.page_size, remaining) if self.stream == "latest-de" else self.page_size
        params = {"limit": size, "order_by": "v_id desc"}
        if before is not None:
            params["where"] = f"v_id < {before}"
        if self.stream == "starter-de":
            params["where"] = STARTER_WHERE + (f" AND v_id < {before}" if before else "")
        data, url = await self._query(params)
        rows = data["results"]
        if not rows and before is None:
            raise drift("The Basel-Stadt source is unexpectedly empty; coverage cannot be established.")
        if not rows and data["total_count"]:
            raise drift("Basel-Stadt returned an incomplete catalogue page.")
        ids = [row.get("v_id") for row in rows if isinstance(row, dict)]
        if len(ids) != len(rows) or any(type(value) is not int for value in ids):
            raise drift("Basel-Stadt changed its version ordering.")
        if ids != sorted(ids, reverse=True) or (before is not None and any(value >= before for value in ids)):
            raise drift("Basel-Stadt ignored the keyset boundary.")
        self.rows = {}
        items = []
        versions = {}
        for row in rows:
            # Deduplicate repeated taxonomy rows only when their content is identical.
            row = validate_row(row)
            revision = fingerprint(row)
            if row["v_id"] in versions and versions[row["v_id"]] != revision:
                raise drift("Basel-Stadt returned conflicting representations of one version.")
            versions[row["v_id"]] = revision
            key = (row["id"], revision)
            if key in self.rows:
                continue
            self.rows[key] = row
            items.append(DiscoveryReference(row["id"], revision, row["version_url_de"],
                                            DATASET + "/records?" + urlencode({"where": f'v_id = {row["v_id"]}', "limit": 2})))
        complete = len(rows) >= data["total_count"] or not rows or (self.stream == "latest-de" and remaining <= len(rows))
        next_cursor = {"cycle": cycle + 1} if complete else {
            "cycle": cycle, "before": ids[-1], "remaining": max(1, remaining - len(rows)) if self.stream == "latest-de" else 50,
        }
        return DiscoveryPage(tuple(items), next_cursor, url, self.manifest.schema_version,
                             complete=complete, empty_is_valid=not rows)

    async def fetch_metadata(self, reference):
        row = self.rows.get((reference.external_identity, reference.source_revision))
        if row is None:
            # Recovery uses the retained exact query, never a latest-version substitution.
            validate_official_url(reference.raw_provenance_ref, frozenset({"data.bs.ch"}))
            parsed = urlsplit(reference.raw_provenance_ref)
            where = parse_qs(parsed.query).get("where", [""])[0]
            if parsed.path != urlsplit(DATASET + "/records").path or not re.fullmatch(r"v_id = [1-9][0-9]*", where):
                raise drift("Basel-Stadt retained an invalid version lookup.")
            data, _ = await self._query({"where": where, "limit": 2})
            row = next((validate_row(item) for item in data["results"] if fingerprint(item) == reference.source_revision), None)
        if row is None or row["id"] != reference.external_identity or fingerprint(row) != reference.source_revision or row["version_url_de"] != reference.canonical_url:
            raise drift("The Basel-Stadt record changed during ingestion; retry discovery.")
        self.rows[(reference.external_identity, reference.source_revision)] = row
        dates = tuple(DateInput("version", kind, row[field], "day", "official_metadata", reference.canonical_url,
                                {"dataset": "100354", "field": field})
                      for field, kind in (("version_active_since", "effective_from"), ("version_inactive_since", "effective_to"))
                      if row.get(field))
        municipal = {"RiE": "Riehen", "RiB": "Riehen", "BeE": "Bettingen", "BeB": "Bettingen", "BaB": "Basel"}.get(row["systematic_number"].split()[0])
        return ConnectorMetadata(
            reference.external_identity, reference.source_revision,
            {"Gesetz": "act", "Verordnung": "ordinance"}.get(row.get("category_name"), "unclassified_document"),
            row["title_de"], reference.canonical_url,
            (IdentifierInput("basel_law_id", row["id"], DATASET_PAGE), IdentifierInput("basel_sg", row["systematic_number"], reference.canonical_url)),
            lifecycle_status="active" if row["is_active"] == "True" else "inactive",
            dates=dates, metadata={"jurisdiction": "CH-BS", "jurisdictions": ["CH-BS"], "canton": "BS",
                                   "municipality": municipal, "language": "de", "systematic_number": row["systematic_number"],
                                   "version_status": row.get("info_badge"), "category": row.get("category_name"),
                                   "keywords": row.get("keywords_de") or [], "dataset": "100354",
                                   "coverage": "OGD text only; annexes and other source families excluded"},
            raw_provenance={"record_url": reference.raw_provenance_ref, "record_sha256": reference.source_revision,
                            "publisher_version": reference.canonical_url, "dataset": DATASET_PAGE},
        )

    async def list_expressions(self, metadata):
        row = self.rows[(metadata.external_identity, metadata.source_revision)]
        return (ConnectorExpression("de", f'{row["id"]}:de', metadata.title, metadata.canonical_url,
                                    version_key=f'{row["v_id"]}:{metadata.source_revision}', artifact_url=metadata.raw_provenance["record_url"],
                                    metadata={"ogd_version_id": row["v_id"], "record_sha256": metadata.source_revision,
                                              "source_status": row.get("info_badge"), "annexes_included": False,
                                              "record_key": [metadata.external_identity, metadata.source_revision]}),)

    async def fetch_official_artifact(self, expression):
        row = self.rows[tuple(expression.metadata["record_key"])]
        body = row.get("gesetzestext_html")
        if not isinstance(body, str) or not body.strip():
            # Metadata-only stays explicit; never invent source text or swap versions.
            return None
        return ConnectorArtifact(expression.artifact_url, body.encode("utf-8"), "text/html; charset=utf-8",
                                 f'basel-stadt-{row["v_id"]}.html',
                                 raw_provenance={"dataset": DATASET_PAGE, "field": "gesetzestext_html",
                                                 "record_sha256": expression.metadata["record_sha256"],
                                                 "publisher_version": expression.official_url})

    async def extract_relations(self, metadata):
        return ()  # Titles/systematic numbers cannot establish a legal relation.

    async def health(self):
        try:
            data, _ = await self._query({"limit": 1, "order_by": "v_id desc"})
            if not data["results"]:
                raise drift("The Basel-Stadt catalogue is unexpectedly empty.")
            validate_row(data["results"][0])
            return ConnectorHealthReport("healthy", "Basel-Stadt OGD sample readable; complete collection not asserted.", datetime.now(UTC), self.manifest.source_contract)
        except DomainError as exc:
            return ConnectorHealthReport("degraded", str(exc), datetime.now(UTC), self.manifest.source_contract)
