"""Swiss Federal Criminal Court adapter over its official latest-decision feed."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, date, datetime
from urllib.parse import urljoin, urlsplit

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
from .official_source_contracts import FEDERAL_CRIMINAL_COURT_CONTRACT
from .pdf_reader import read_pdf
from .regulatory_corpus import DateInput, DocumentInput, ExpressionInput, IdentifierInput

COURT_HOME = "https://www.bstger.ch/de/home/index"
COURT_ROBOTS = "https://www.bstger.ch/robots.txt"
LATEST_OVERLAP_ITEMS = 50
_DOCUMENT_PATH = re.compile(r"^/api/getDocumentContent/([0-9a-f-]{36})$", re.I)
_DOCKET = re.compile(r"\b[A-Z]{1,3}\.[0-9]{4}\.[0-9]+[A-Z]?\b")
_SR_RS = re.compile(r"\b(?:SR|RS)\s+([0-9]+(?:\.[0-9]+){0,4})\b", re.I)
_ARTICLE_ACT = re.compile(
    r"\b(?:Art\.|Artikel|articolo)\s*([0-9]+[a-z]?)"
    r"(?:\s*(?:Abs\.|al\.|cpv\.)\s*[0-9]+)?"
    r"(?:\s*(?:lit\.|let\.)\s*[a-z])?\s+([A-ZÄÖÜ][A-Za-zÀ-ÿ0-9]{1,15})\b",
    re.I,
)
_DATE_HEADING = {
    "de": re.compile(r"\b(?:Urteil|Beschluss)\s+vom\s+(\d{1,2})\.?\s+([^\s]+)\s+(\d{4})", re.I),
    "fr": re.compile(r"\b(?:Jugement|Arr[eê]t|D[ée]cision)\s+du\s+(\d{1,2})\s+([^\s]+)\s+(\d{4})", re.I),
    "it": re.compile(r"\b(?:Sentenza|Decisione)\s+del\s+(\d{1,2})\s+([^\s]+)\s+(\d{4})", re.I),
}
_MONTHS = {
    "januar": 1, "janvier": 1, "gennaio": 1,
    "februar": 2, "fevrier": 2, "fvrier": 2, "febbraio": 2,
    "marz": 3, "mars": 3, "marzo": 3,
    "april": 4, "avril": 4, "aprile": 4,
    "mai": 5, "maggio": 5,
    "juni": 6, "juin": 6, "giugno": 6,
    "juli": 7, "juillet": 7, "luglio": 7,
    "august": 8, "aout": 8, "aot": 8, "agosto": 8,
    "september": 9, "septembre": 9, "settembre": 9,
    "oktober": 10, "octobre": 10, "ottobre": 10,
    "november": 11, "novembre": 11,
    "dezember": 12, "decembre": 12, "dcembre": 12, "dicembre": 12,
}


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _fingerprint(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _month_token(value: str) -> str:
    return (
        value.casefold()
        .replace("ä", "a")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("û", "u")
        .replace("ô", "o")
        .replace("�", "")
        .strip(".,")
    )


def _decode_home(artifact: ConnectorArtifact) -> BeautifulSoup:
    soup = BeautifulSoup(artifact.body, "html.parser")
    text = _clean(soup.get_text(" ", strip=True)).casefold()
    if "liste der neu aufgenommenen entscheide" not in text:
        raise DomainError(
            "The Federal Criminal Court latest-decision template changed.",
            502,
            "connector_contract_drift",
        )
    return soup


def _latest_rows(soup: BeautifulSoup, source_url: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for card in soup.select(".list-group-item"):
        links = [
            link
            for link in card.find_all("a", href=True)
            if "getDocumentContent" in link.get("href", "")
        ]
        if not links:
            continue
        canonical_url = urljoin(source_url, links[0]["href"])
        path_match = _DOCUMENT_PATH.fullmatch(urlsplit(canonical_url).path)
        if not path_match:
            raise DomainError(
                "The Federal Criminal Court returned an invalid decision URL.",
                502,
                "connector_contract_drift",
            )
        document_id = str(uuid.UUID(path_match.group(1)))
        if document_id in seen:
            continue
        card_text = _clean(card.get_text(" ", strip=True))
        dockets = _DOCKET.findall(card_text)
        if not dockets:
            raise DomainError(
                "The Federal Criminal Court latest feed omitted a court docket.",
                502,
                "connector_contract_drift",
            )
        subject = next(
            (
                _clean(link.get_text(" ", strip=True)).split(";;", 1)[0]
                for link in links
                if _clean(link.get_text(" ", strip=True)).casefold() not in {"(pdf)", "pdf"}
            ),
            "",
        )
        row = {
            "document_id": document_id,
            "dockets": list(dict.fromkeys(dockets)),
            "subject": subject,
            "canonical_url": canonical_url,
            "source_url": source_url,
        }
        row["source_revision"] = _fingerprint(row)
        rows.append(row)
        seen.add(document_id)
    if not rows:
        raise DomainError(
            "The Federal Criminal Court latest-decision feed is unexpectedly empty.",
            502,
            "connector_contract_drift",
        )
    return rows


def _pdf_metadata(body: bytes, dockets: list[str]) -> dict:
    if not body.startswith(b"%PDF"):
        raise DomainError(
            "The Federal Criminal Court decision is no longer a PDF.",
            502,
            "connector_contract_drift",
        )
    try:
        pdf = read_pdf(body, text_page_limit=40)
        total_pages = pdf.page_count
        pages = [_clean("\n".join(page.blocks)) for page in pdf.pages]
    except DomainError as exc:
        raise DomainError(
            "The Federal Criminal Court decision PDF could not be read.",
            502,
            "connector_contract_drift",
        ) from exc
    opening = " ".join(pages[:3])
    if not any(docket in opening for docket in dockets):
        raise DomainError(
            "The Federal Criminal Court PDF does not match its listed docket.",
            502,
            "connector_contract_drift",
        )
    language = ""
    decision_date = ""
    chamber = None
    for candidate, pattern in _DATE_HEADING.items():
        match = pattern.search(opening)
        if not match:
            continue
        day, month_name, year = match.groups()
        month = _MONTHS.get(_month_token(month_name))
        if month is None:
            continue
        try:
            decision_date = date(int(year), month, int(day)).isoformat()
        except ValueError as exc:
            raise DomainError(
                "The Federal Criminal Court returned an invalid decision date.",
                502,
                "connector_contract_drift",
            ) from exc
        language = candidate
        tail = opening[match.end() : match.end() + 180]
        chamber_match = re.search(
            r"\b(?:Strafkammer|Beschwerdekammer|Berufungskammer|Cour des affaires p.nales|"
            r"Cour des plaintes|Cour d.appel|Corte penale|Corte dei reclami penali|Corte d.appello)\b",
            tail,
            re.I,
        )
        chamber = _clean(chamber_match.group(0)) if chamber_match else None
        if chamber:
            normalized_chamber = chamber.casefold()
            if "affaires" in normalized_chamber:
                chamber = "Cour des affaires pénales"
            elif "plaintes" in normalized_chamber:
                chamber = "Cour des plaintes"
            elif "appel" in normalized_chamber:
                chamber = "Cour d'appel"
        break
    if not language or not decision_date:
        raise DomainError(
            "The Federal Criminal Court decision language or date could not be identified.",
            502,
            "connector_contract_drift",
        )
    evidence_text = "\n".join(pages)
    sr_rs = sorted(set(_SR_RS.findall(evidence_text)))
    provisions: dict[tuple[str, str], dict] = {}
    for page_number, page in enumerate(pages, start=1):
        for article, act in _ARTICLE_ACT.findall(page):
            key = (article.casefold(), act.upper())
            provisions.setdefault(
                key,
                {"article": article, "act": act.upper(), "page": page_number, "excerpt": page[:500]},
            )
    return {
        "language": language,
        "decision_date": decision_date,
        "chamber": chamber,
        "page_count": total_pages,
        "citation_scan_pages": len(pages),
        "reference_candidates": {
            "sr_rs": sr_rs,
            "provisions": sorted(provisions.values(), key=lambda item: (item["act"], item["article"])),
        },
    }


class FederalCriminalCourtConnector(OfficialConnector):
    """Bounded overlap over decisions explicitly listed by the court as newly added."""

    manifest = FEDERAL_CRIMINAL_COURT_CONTRACT.manifest

    def __init__(
        self,
        settings: Settings,
        logger: IntegrationLogger | None = None,
        *,
        item_page_size: int = 5,
        overlap_items: int = LATEST_OVERLAP_ITEMS,
        transport=None,
        sleep=None,
        now=lambda: datetime.now(UTC),
    ):
        options = {"transport": transport}
        if sleep is not None:
            options["sleep"] = sleep
        self.http = ConnectorHttpClient(settings, self.manifest, logger, **options)
        self.item_page_size = max(1, min(item_page_size, 10))
        self.overlap_items = max(1, min(overlap_items, 100))
        self.now = now
        self._listings: dict[str, dict] = {}
        self._artifacts: dict[str, ConnectorArtifact] = {}
        self._metadata: dict[str, dict] = {}

    async def _home(self) -> tuple[list[dict], ConnectorArtifact]:
        artifact = await self.http.get(
            COURT_HOME,
            operation="federal_criminal_court_latest",
            max_bytes=1_000_000,
            headers={"Accept": "text/html"},
        )
        rows = _latest_rows(_decode_home(artifact), artifact.url)[: self.overlap_items]
        for row in rows:
            self._listings[row["document_id"]] = row
        return rows, artifact

    async def discover_since(self, cursor: dict | None, page_checkpoint: dict) -> DiscoveryPage:
        cursor = dict(cursor or {})
        cycle = max(0, int(cursor.get("cycle", 0)))
        offset = max(0, int(cursor.get("offset", 0)))
        rows, artifact = await self._home()
        if offset >= len(rows):
            offset = 0
        selected = rows[offset : offset + self.item_page_size]
        complete = offset + len(selected) >= len(rows)
        next_cursor = {"offset": 0 if complete else offset + len(selected), "cycle": cycle + int(complete)}
        return DiscoveryPage(
            tuple(
                DiscoveryReference(
                    row["document_id"],
                    row["source_revision"],
                    row["canonical_url"],
                    row["source_url"],
                )
                for row in selected
            ),
            next_cursor,
            artifact.url,
            self.manifest.schema_version,
            complete=complete,
            empty_is_valid=False,
        )

    async def fetch_metadata(self, reference: DiscoveryReference) -> ConnectorMetadata:
        listing = self._listings.get(reference.external_identity)
        if listing is None or listing["source_revision"] != reference.source_revision:
            raise DomainError(
                "The Federal Criminal Court discovery row is no longer available.",
                502,
                "connector_source_changed",
            )
        artifact = await self.http.get(
            listing["canonical_url"],
            operation="federal_criminal_court_decision_pdf",
            max_bytes=20_000_000,
            headers={"Accept": "application/pdf"},
        )
        details = _pdf_metadata(artifact.body, listing["dockets"])
        digest = hashlib.sha256(artifact.body).hexdigest()
        observed_at = self.now()
        metadata = {
            **listing,
            **details,
            "court": "Swiss Federal Criminal Court",
            "court_level": "federal",
            "jurisdiction": "Switzerland",
            "artifact_sha256": digest,
            "artifact_content_type": artifact.content_type,
            "detected_at": observed_at.isoformat(),
            "coverage": "Decisions present in the official latest-decision list at observation time.",
        }
        self._artifacts[reference.external_identity] = ConnectorArtifact(
            artifact.url,
            artifact.body,
            "application/pdf",
            f"{listing['dockets'][0].replace('.', '-')}.pdf",
            expected_sha256=digest,
            raw_provenance={
                "source": artifact.url,
                "latest_feed": listing["source_url"],
                "retrieved_at": observed_at.isoformat(),
            },
        )
        self._metadata[reference.external_identity] = metadata
        primary_docket = listing["dockets"][0]
        title = f"{primary_docket} — {listing['subject']}" if listing["subject"] else primary_docket
        return ConnectorMetadata(
            external_identity=reference.external_identity,
            source_revision=reference.source_revision,
            kind="court_decision",
            title=title,
            canonical_url=listing["canonical_url"],
            identifiers=(
                IdentifierInput("federal_criminal_court_document", reference.external_identity, listing["canonical_url"]),
                *(IdentifierInput("court_docket", docket, listing["canonical_url"]) for docket in listing["dockets"]),
                IdentifierInput("official_url", listing["canonical_url"], listing["canonical_url"]),
            ),
            lifecycle_status="decided",
            dates=(
                DateInput("work", "decision_date", details["decision_date"], "day", "official_decision_pdf", listing["canonical_url"]),
                DateInput("work", "detected_at", observed_at.isoformat(), "instant", "official_latest_feed", listing["source_url"]),
            ),
            metadata=metadata,
            raw_provenance={
                "provider": "Swiss Federal Criminal Court",
                "latest_feed": listing["source_url"],
                "decision": artifact.url,
                "retrieved_at": observed_at.isoformat(),
                "attribution": self.manifest.attribution,
            },
        )

    async def list_expressions(self, metadata: ConnectorMetadata) -> tuple[ConnectorExpression, ...]:
        details = self._metadata.get(metadata.external_identity)
        if details is None:
            raise DomainError("The court decision metadata is unavailable.", 502, "connector_source_changed")
        return (
            ConnectorExpression(
                language=details["language"],
                expression_key=metadata.external_identity,
                title=metadata.title,
                official_url=metadata.canonical_url,
                version_key=f"{metadata.external_identity}:{details['artifact_sha256']}",
                artifact_url=metadata.canonical_url,
                dates=(DateInput("version", "version_date", details["decision_date"], "day", "official_decision_pdf", metadata.canonical_url),),
                metadata={
                    "record_kind": "official_decision_pdf",
                    "artifact_sha256": details["artifact_sha256"],
                    "citation_scan_pages": details["citation_scan_pages"],
                },
            ),
        )

    async def fetch_official_artifact(self, expression: ConnectorExpression) -> ConnectorArtifact | None:
        artifact = self._artifacts.get(expression.expression_key)
        if artifact is None:
            raise DomainError("The court decision artifact is unavailable.", 502, "connector_source_changed")
        return artifact

    @staticmethod
    def _target_reference(scheme: str, value: str, title: str) -> DocumentInput:
        return DocumentInput(
            kind="unclassified_document",
            authority="fedlex",
            identifiers=(IdentifierInput(scheme, value),),
            title=title,
            expression=ExpressionInput("und", f"federal-law-reference:{scheme}:{value}"),
            metadata={"placeholder_from_exact_court_reference": True},
        )

    async def extract_relations(self, metadata: ConnectorMetadata) -> tuple[ConnectorRelation, ...]:
        candidates = metadata.metadata.get("reference_candidates") or {}
        relations = [
            ConnectorRelation(
                target=self._target_reference("sr_rs", value, f"SR/RS {value}"),
                relation_type="cites",
                state="confirmed",
                provenance_method="exact_identifier",
                evidence={"identifier": f"SR/RS {value}", "source": metadata.canonical_url},
                rule_revision="federal-criminal-court-references-v1",
            )
            for value in candidates.get("sr_rs") or []
        ]
        by_act: dict[str, list[dict]] = {}
        for item in candidates.get("provisions") or []:
            by_act.setdefault(item["act"], []).append(item)
        for act, provisions in sorted(by_act.items()):
            relations.append(
                ConnectorRelation(
                    target=self._target_reference("legal_abbreviation", act, act),
                    relation_type="cites",
                    state="confirmed",
                    provenance_method="text_rule",
                    evidence={
                        "act": act,
                        "articles": sorted({item["article"] for item in provisions}),
                        "citations": provisions,
                        "source": metadata.canonical_url,
                    },
                    rule_revision="federal-criminal-court-references-v1",
                )
            )
        return tuple(relations)

    async def health(self) -> ConnectorHealthReport:
        try:
            rows, artifact = await self._home()
            robots = await self.http.get(
                COURT_ROBOTS,
                operation="federal_criminal_court_robots",
                max_bytes=100_000,
                headers={"Accept": "text/plain"},
            )
            robots_text = robots.body.decode("utf-8", errors="replace")
            if re.search(r"(?im)^\s*Disallow:\s*/de/home(?:/index)?\s*$", robots_text):
                raise DomainError("The Federal Criminal Court crawl policy changed.", 502, "connector_contract_drift")
            return ConnectorHealthReport(
                "healthy",
                "The Federal Criminal Court latest-decision list is available.",
                self.now(),
                {
                    **self.manifest.source_contract,
                    "observed": {"latest_decisions": len(rows), "newest_docket": rows[0]["dockets"][0]},
                    "latest_feed_url": artifact.url,
                    "robots_url": robots.url,
                },
            )
        except DomainError as exc:
            return ConnectorHealthReport(
                "degraded",
                exc.message,
                self.now(),
                {**self.manifest.source_contract, "error_code": exc.code},
            )


def federal_criminal_court_connectors(
    settings: Settings, logger: IntegrationLogger | None = None
) -> tuple[FederalCriminalCourtConnector, ...]:
    return (FederalCriminalCourtConnector(settings, logger),)
