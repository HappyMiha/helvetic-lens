"""Swiss Federal Supreme Court adapter over the official decision index and HTML."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlsplit

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
from .official_source_contracts import FEDERAL_COURT_CONTRACT
from .regulatory_corpus import DateInput, DocumentInput, ExpressionInput, IdentifierInput

COURT_INDEX = (
    "https://search.bger.ch/ext/eurospider/live/de/php/aza/http/"
    "index_aza.php?lang=de&mode=index&search=false"
)
COURT_DATE_INDEX = (
    "https://search.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php"
)
COURT_DECISION = "https://search.bger.ch/ext/eurospider/live/de/php/aza/http/index.php"
COURT_ROBOTS = "https://search.bger.ch/robots.txt"
COURT_SITEMAP = "https://www.bger.ch/sitemap.xml"
COURT_LANGUAGES = frozenset({"de", "fr", "it"})
LATEST_OVERLAP_DATES = 5
_DOCKET = re.compile(r"\b(?:[0-9]{1,2}[A-Z]?|[A-Z]{1,3})[_ .][0-9]+/[0-9]{4}\b")
_AZA = re.compile(r"aza://([0-9]{2})-([0-9]{2})-([0-9]{4})-([^&#]+)", re.I)
_AZA_DOCKET = re.compile(r"(.+?)([_.])([0-9]+)-([0-9]{4})$")
_DAY_DE = re.compile(r"\b([0-9]{2})\.([0-9]{2})\.([0-9]{4})\b")
_SR_RS = re.compile(r"\b(?:SR|RS)\s+([0-9]+(?:\.[0-9]+){0,4})\b", re.I)
_ARTICLE_ACT = re.compile(
    r"\b(?:Art\.|Artikel|articolo)\s*([0-9]+[a-z]?)"
    r"(?:\s*(?:Abs\.|al\.|cpv\.)\s*[0-9]+)?"
    r"(?:\s*(?:lit\.|let\.)\s*[a-z])?\s+([A-ZÄÖÜ][A-Za-zÀ-ÿ0-9]{1,15})\b",
    re.I,
)
_DECISION_HEADING = {
    "de": re.compile(r"\b(?:Urteil|Entscheid)\s+vom\b", re.I),
    "fr": re.compile(r"\bArr[eê]t\s+du\b", re.I),
    "it": re.compile(r"\bSentenza\s+del\b", re.I),
}
_SUBJECT_HEADING = frozenset({"gegenstand", "objet", "oggetto"})
_CHALLENGE_MARKERS = ("captcha", "access denied", "zugriff verweigert", "cloudflare")


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _iso_day(value: str) -> str:
    match = _DAY_DE.fullmatch(value.strip())
    if not match:
        raise DomainError(
            "The Federal Supreme Court returned an invalid date.",
            502,
            "connector_contract_drift",
        )
    day, month, year = match.groups()
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError as exc:
        raise DomainError(
            "The Federal Supreme Court returned an invalid date.",
            502,
            "connector_contract_drift",
        ) from exc


def _date_url(value: date) -> str:
    return f"{COURT_DATE_INDEX}?{urlencode({'date': value.strftime('%Y%m%d'), 'lang': 'de', 'mode': 'news'})}"


def _decision_url(aza_identity: str) -> str:
    query = urlencode(
        {
            "highlight_docid": aza_identity,
            "lang": "de",
            "type": "show_document",
            "zoom": "",
        },
        quote_via=quote,
    )
    return f"{COURT_DECISION}?{query}"


def _jump_url(aza_identity: str) -> str:
    return f"https://relevancy.bger.ch/cgi-bin/JumpCGI?{urlencode({'id': aza_identity[6:]})}"


def _aza_from_url(value: str) -> tuple[str, str, str]:
    try:
        parsed = urlsplit(value)
        query = parse_qs(parsed.query)
    except ValueError as exc:
        raise DomainError(
            "The Federal Supreme Court returned an invalid decision URL.",
            502,
            "connector_contract_drift",
        ) from exc
    raw = (query.get("highlight_docid") or query.get("docid") or [""])[0]
    match = _AZA.fullmatch(raw)
    if not match:
        raise DomainError(
            "The Federal Supreme Court decision URL has no valid Aza identity.",
            502,
            "connector_contract_drift",
        )
    day, month, year, docket_token = match.groups()
    docket_match = _AZA_DOCKET.fullmatch(docket_token)
    if not docket_match:
        raise DomainError(
            "The Federal Supreme Court returned an invalid docket.",
            502,
            "connector_contract_drift",
        )
    prefix, separator, number, docket_year = docket_match.groups()
    docket = f"{prefix}{separator}{number}/{docket_year}"
    if not _DOCKET.fullmatch(docket):
        raise DomainError(
            "The Federal Supreme Court returned an invalid docket.",
            502,
            "connector_contract_drift",
        )
    try:
        decision_day = date(int(year), int(month), int(day)).isoformat()
    except ValueError as exc:
        raise DomainError(
            "The Federal Supreme Court returned an invalid decision date.",
            502,
            "connector_contract_drift",
        ) from exc
    return raw, docket.replace(" ", "_"), decision_day


def _decode_html(artifact: ConnectorArtifact) -> BeautifulSoup:
    soup = BeautifulSoup(artifact.body, "html.parser")
    text = _clean(soup.get_text(" ", strip=True)).casefold()
    if any(marker in text for marker in _CHALLENGE_MARKERS):
        raise DomainError(
            "The Federal Supreme Court returned a challenge page.",
            502,
            "connector_challenge_page",
        )
    return soup


def _latest_dates(soup: BeautifulSoup) -> list[date]:
    heading = _clean(soup.get_text(" ", strip=True)).casefold()
    if not any(
        marker in heading
        for marker in ("neu aufgenommenen entscheide", "nouveaux arrêts", "nuove sentenze")
    ):
        raise DomainError(
            "The Federal Supreme Court latest index template changed.",
            502,
            "connector_contract_drift",
        )
    found = []
    for link in soup.find_all("a", href=True):
        parsed = urlsplit(urljoin(COURT_INDEX, link["href"]))
        raw = (parse_qs(parsed.query).get("date") or [""])[0]
        if not re.fullmatch(r"[0-9]{8}", raw):
            continue
        try:
            value = date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
        except ValueError as exc:
            raise DomainError(
                "The Federal Supreme Court latest index returned an invalid date.",
                502,
                "connector_contract_drift",
            ) from exc
        if value not in found:
            found.append(value)
    if not found or found != sorted(found, reverse=True):
        raise DomainError(
            "The Federal Supreme Court latest index is empty or unordered.",
            502,
            "connector_contract_drift",
        )
    return found


def _date_rows(soup: BeautifulSoup, insertion_day: date, source_url: str) -> list[dict]:
    text = _clean(soup.get_text(" ", strip=True)).casefold()
    expected = insertion_day.strftime("%d.%m.%Y")
    if "neu aufgenommenen entscheide" not in text or expected not in text:
        raise DomainError(
            "The Federal Supreme Court date index template changed.",
            502,
            "connector_contract_drift",
        )
    rows = []
    table_rows = soup.find_all("tr")
    for index, row in enumerate(table_rows):
        link = row.find("a", href=True)
        if not link:
            continue
        absolute = urljoin(source_url, link["href"])
        if "show_document" not in absolute:
            continue
        aza_identity, docket, decision_day = _aza_from_url(absolute)
        cells = [
            value
            for cell in row.find_all("td")
            if (value := _clean(cell.get_text(" ", strip=True)))
        ]
        if len(cells) < 2 or _iso_day(cells[0]) != decision_day:
            raise DomainError(
                "The Federal Supreme Court date row no longer matches its decision URL.",
                502,
                "connector_contract_drift",
            )
        area = cells[-1]
        intended = area.endswith("*")
        area = area.rstrip("*").strip()
        subject = ""
        if index + 1 < len(table_rows) and not table_rows[index + 1].find("a", href=True):
            subject = _clean(table_rows[index + 1].get_text(" ", strip=True))
        canonical = _decision_url(aza_identity)
        row_data = {
            "aza_identity": aza_identity,
            "docket": docket,
            "decision_date": decision_day,
            "insertion_date": insertion_day.isoformat(),
            "area": area,
            "subject": subject,
            "publication_intended": intended,
            "canonical_url": canonical,
            "source_url": source_url,
        }
        row_data["source_revision"] = _fingerprint(row_data)
        rows.append(row_data)
    if len({item["aza_identity"] for item in rows}) != len(rows):
        raise DomainError(
            "The Federal Supreme Court date index contains duplicate Aza identities.",
            502,
            "connector_contract_drift",
        )
    return rows


def _decision_content(soup: BeautifulSoup, docket: str) -> tuple[object, list[str]]:
    content = soup.select_one("#highlight_content .content")
    if content is None:
        raise DomainError(
            "The Federal Supreme Court decision template changed.",
            502,
            "connector_contract_drift",
        )
    paragraphs = [_clean(node.get_text(" ", strip=True)) for node in content.select(":scope > .para")]
    paragraphs = [value for value in paragraphs if value]
    if docket not in paragraphs:
        raise DomainError(
            "The Federal Supreme Court decision body does not match its docket.",
            502,
            "connector_contract_drift",
        )
    return content, paragraphs


def _language(paragraphs: list[str]) -> str:
    opening = " ".join(paragraphs[:20])
    for language, pattern in _DECISION_HEADING.items():
        if pattern.search(opening):
            return language
    raise DomainError(
        "The Federal Supreme Court decision language could not be identified.",
        502,
        "connector_contract_drift",
    )


def _chamber(paragraphs: list[str], docket: str) -> str | None:
    docket_index = paragraphs.index(docket)
    for index in range(docket_index + 1, min(len(paragraphs), docket_index + 8)):
        if any(pattern.search(paragraphs[index]) for pattern in _DECISION_HEADING.values()):
            return paragraphs[index + 1] if index + 1 < len(paragraphs) else None
    return None


def _subject(paragraphs: list[str], fallback: str) -> str:
    for index, value in enumerate(paragraphs):
        if value.casefold().rstrip(":") in _SUBJECT_HEADING and index + 1 < len(paragraphs):
            return paragraphs[index + 1]
    return fallback


def _reference_candidates(paragraphs: list[str]) -> dict:
    sr_rs = set()
    provisions = {}
    for paragraph_number, paragraph in enumerate(paragraphs, start=1):
        for value in _SR_RS.findall(paragraph):
            sr_rs.add(value.upper())
        for article, act in _ARTICLE_ACT.findall(paragraph):
            key = (article.lower(), act.upper())
            provisions.setdefault(
                key,
                {
                    "article": article,
                    "act": act.upper(),
                    "paragraph": paragraph_number,
                    "excerpt": paragraph[:500],
                },
            )
    return {
        "sr_rs": sorted(sr_rs),
        "provisions": sorted(provisions.values(), key=lambda item: (item["act"], item["article"])),
    }


class FederalCourtConnector(OfficialConnector):
    """Overlapping latest decisions and bounded two-year date reconciliation."""

    manifest = FEDERAL_COURT_CONTRACT.manifest

    def __init__(
        self,
        settings: Settings,
        logger: IntegrationLogger | None = None,
        *,
        mode: str = "latest",
        item_page_size: int = 10,
        latest_overlap_dates: int = LATEST_OVERLAP_DATES,
        transport=None,
        sleep=None,
        today=lambda: datetime.now(UTC).date(),
        now=lambda: datetime.now(UTC),
    ):
        if mode not in {"latest", "reconcile"}:
            raise ValueError("Unsupported Federal Supreme Court connector mode")
        options = {"transport": transport}
        if sleep is not None:
            options["sleep"] = sleep
        self.http = ConnectorHttpClient(settings, self.manifest, logger, **options)
        self.mode = mode
        self.item_page_size = max(1, min(item_page_size, 25))
        self.latest_overlap_dates = max(1, min(latest_overlap_dates, 14))
        self.today = today
        self.now = now
        self._listings: dict[str, dict] = {}
        self._artifacts: dict[str, ConnectorArtifact] = {}
        self._metadata: dict[str, dict] = {}

    async def _index(self) -> tuple[list[date], str]:
        artifact = await self.http.get(
            COURT_INDEX,
            operation="federal_court_latest_index",
            max_bytes=1_000_000,
            headers={"Accept": "text/html"},
        )
        return _latest_dates(_decode_html(artifact)), artifact.url

    async def _day(self, value: date) -> tuple[list[dict], str]:
        artifact = await self.http.get(
            _date_url(value),
            operation="federal_court_date_index",
            max_bytes=2_000_000,
            headers={"Accept": "text/html"},
        )
        rows = _date_rows(_decode_html(artifact), value, artifact.url)
        for row in rows:
            self._listings[row["aza_identity"]] = row
        return rows, artifact.url

    async def discover_since(self, cursor: dict | None, page_checkpoint: dict) -> DiscoveryPage:
        cursor = dict(cursor or {})
        cycle = int(cursor.get("cycle", 0))
        item_offset = max(0, int(cursor.get("item_offset", 0)))
        if self.mode == "latest":
            dates, index_url = await self._index()
            overlap = dates[: self.latest_overlap_dates]
            date_offset = max(0, min(int(cursor.get("date_offset", 0)), len(overlap) - 1))
            insertion_day = overlap[date_offset]
            rows, source_url = await self._day(insertion_day)
            if not rows:
                raise DomainError(
                    "The Federal Supreme Court returned an implausibly empty latest interval.",
                    502,
                    "connector_contract_drift",
                )
            selected = rows[item_offset : item_offset + self.item_page_size]
            day_finished = item_offset + len(selected) >= len(rows)
            if not day_finished:
                next_cursor = {
                    "date_offset": date_offset,
                    "item_offset": item_offset + len(selected),
                    "cycle": cycle,
                }
                complete = False
            elif date_offset + 1 < len(overlap):
                next_cursor = {"date_offset": date_offset + 1, "item_offset": 0, "cycle": cycle}
                complete = False
            else:
                next_cursor = {"date_offset": 0, "item_offset": 0, "cycle": cycle + 1}
                complete = True
            provenance = f"{source_url}#latest-index={index_url}"
        else:
            end = self.today()
            start = date(end.year - 1, 1, 1)
            raw_day = cursor.get("insertion_date")
            try:
                insertion_day = date.fromisoformat(raw_day) if raw_day else start
            except ValueError as exc:
                raise DomainError(
                    "The Federal Supreme Court reconciliation cursor is invalid.",
                    500,
                    "connector_cursor_invalid",
                ) from exc
            if insertion_day < start or insertion_day > end:
                insertion_day = start
            rows, source_url = await self._day(insertion_day)
            selected = rows[item_offset : item_offset + self.item_page_size]
            day_finished = item_offset + len(selected) >= len(rows)
            if not day_finished:
                next_cursor = {
                    "insertion_date": insertion_day.isoformat(),
                    "item_offset": item_offset + len(selected),
                    "cycle": cycle,
                }
                complete = False
            elif insertion_day < end:
                next_cursor = {
                    "insertion_date": (insertion_day + timedelta(days=1)).isoformat(),
                    "item_offset": 0,
                    "cycle": cycle,
                }
                complete = False
            else:
                next_cursor = {
                    "insertion_date": start.isoformat(),
                    "item_offset": 0,
                    "cycle": cycle + 1,
                }
                complete = True
            provenance = source_url
        references = tuple(
            DiscoveryReference(
                row["aza_identity"],
                row["source_revision"],
                row["canonical_url"],
                row["source_url"],
            )
            for row in selected
        )
        return DiscoveryPage(
            references,
            next_cursor,
            provenance,
            self.manifest.schema_version,
            complete=complete,
            empty_is_valid=not rows,
        )

    async def fetch_metadata(self, reference: DiscoveryReference) -> ConnectorMetadata:
        listing = self._listings.get(reference.external_identity)
        if listing is None or listing["source_revision"] != reference.source_revision:
            raise DomainError(
                "The Federal Supreme Court discovery row is no longer available.",
                502,
                "connector_source_changed",
            )
        artifact = await self.http.get(
            reference.canonical_url,
            operation="federal_court_decision_html",
            max_bytes=8_000_000,
            headers={"Accept": "text/html"},
        )
        soup = _decode_html(artifact)
        _, paragraphs = _decision_content(soup, listing["docket"])
        language = _language(paragraphs)
        candidates = _reference_candidates(paragraphs)
        artifact_hash = hashlib.sha256(artifact.body).hexdigest()
        title_subject = _subject(paragraphs, listing["subject"] or listing["area"])
        title = f"{listing['docket']} — {title_subject}" if title_subject else listing["docket"]
        metadata = {
            **listing,
            "court": "Swiss Federal Supreme Court",
            "chamber": _chamber(paragraphs, listing["docket"]),
            "language": language,
            "descriptors": [value for value in (listing["area"], listing["subject"]) if value],
            "reference_candidates": candidates,
            "artifact_sha256": artifact_hash,
            "artifact_content_type": artifact.content_type,
            "jump_url": _jump_url(reference.external_identity),
            "retrieved_at": self.now().isoformat(),
        }
        self._artifacts[reference.external_identity] = ConnectorArtifact(
            artifact.url,
            artifact.body,
            artifact.content_type,
            f"{listing['docket'].replace('/', '-')}.html",
            expected_sha256=artifact_hash,
            raw_provenance={
                "source": artifact.url,
                "date_index": listing["source_url"],
                "retrieved_at": metadata["retrieved_at"],
            },
        )
        self._metadata[reference.external_identity] = metadata
        dates = (
            DateInput(
                "work",
                "decision_date",
                listing["decision_date"],
                "day",
                "federal_court_aza",
                reference.canonical_url,
            ),
            DateInput(
                "work",
                "published_at",
                listing["insertion_date"],
                "day",
                "federal_court_latest_index",
                listing["source_url"],
            ),
        )
        return ConnectorMetadata(
            external_identity=reference.external_identity,
            source_revision=reference.source_revision,
            kind="court_decision",
            title=title,
            canonical_url=reference.canonical_url,
            identifiers=(
                IdentifierInput("court_docket", listing["docket"], reference.canonical_url),
                IdentifierInput("aza_uri", reference.external_identity, reference.canonical_url),
                IdentifierInput("official_url", reference.canonical_url, reference.canonical_url),
            ),
            lifecycle_status="decided",
            dates=dates,
            metadata=metadata,
            raw_provenance={
                "provider": "Swiss Federal Supreme Court",
                "date_index": listing["source_url"],
                "decision": artifact.url,
                "retrieved_at": metadata["retrieved_at"],
                "attribution": self.manifest.attribution,
            },
        )

    async def list_expressions(self, metadata: ConnectorMetadata) -> tuple[ConnectorExpression, ...]:
        details = self._metadata.get(metadata.external_identity)
        if details is None:
            raise DomainError(
                "The Federal Supreme Court decision metadata is unavailable.",
                502,
                "connector_source_changed",
            )
        return (
            ConnectorExpression(
                language=details["language"],
                expression_key=metadata.external_identity,
                title=metadata.title,
                official_url=metadata.canonical_url,
                version_key=f"{metadata.external_identity}:{details['artifact_sha256']}",
                artifact_url=metadata.canonical_url,
                dates=(
                    DateInput(
                        "version",
                        "version_date",
                        details["decision_date"],
                        "day",
                        "federal_court_aza",
                        metadata.canonical_url,
                    ),
                ),
                metadata={
                    "record_kind": "official_decision_html",
                    "artifact_sha256": details["artifact_sha256"],
                    "jump_url": details["jump_url"],
                },
            ),
        )

    async def fetch_official_artifact(
        self, expression: ConnectorExpression
    ) -> ConnectorArtifact | None:
        artifact = self._artifacts.get(expression.expression_key)
        if artifact is None:
            raise DomainError(
                "The Federal Supreme Court decision artifact is unavailable.",
                502,
                "connector_source_changed",
            )
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
        relations = []
        for value in candidates.get("sr_rs") or []:
            relations.append(
                ConnectorRelation(
                    target=self._target_reference("sr_rs", value, f"SR/RS {value}"),
                    relation_type="cites",
                    state="confirmed",
                    provenance_method="exact_identifier",
                    evidence={"identifier": f"SR/RS {value}", "source": metadata.canonical_url},
                    rule_revision="federal-court-references-v1",
                )
            )
        provisions_by_act = {}
        for item in candidates.get("provisions") or []:
            provisions_by_act.setdefault(item["act"], []).append(item)
        for act, provisions in sorted(provisions_by_act.items()):
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
                    rule_revision="federal-court-references-v1",
                )
            )
        return tuple(relations)

    async def health(self) -> ConnectorHealthReport:
        try:
            dates, index_url = await self._index()
            robots = await self.http.get(
                COURT_ROBOTS,
                operation="federal_court_robots",
                max_bytes=100_000,
                headers={"Accept": "text/plain"},
            )
            robots_text = robots.body.decode("utf-8", errors="replace")
            if not re.search(r"(?im)^\s*Crawl-delay:\s*2(?:\.0)?\s*$", robots_text):
                raise DomainError(
                    "The Federal Supreme Court crawl policy changed.",
                    502,
                    "connector_contract_drift",
                )
            return ConnectorHealthReport(
                "healthy",
                "The Federal Supreme Court latest index and crawl policy are available.",
                self.now(),
                {
                    **self.manifest.source_contract,
                    "observed": {
                        "latest_dates": len(dates),
                        "newest_insertion_date": dates[0].isoformat(),
                        "crawl_delay_seconds": 2,
                    },
                    "index_url": index_url,
                    "robots_url": robots.url,
                    "declared_sitemap": COURT_SITEMAP,
                },
            )
        except DomainError as exc:
            return ConnectorHealthReport(
                "degraded",
                exc.message,
                self.now(),
                {**self.manifest.source_contract, "error_code": exc.code},
            )


def federal_court_connectors(
    settings: Settings,
    logger: IntegrationLogger | None = None,
) -> tuple[FederalCourtConnector, ...]:
    return (
        FederalCourtConnector(settings, logger, mode="latest"),
        FederalCourtConnector(settings, logger, mode="reconcile"),
    )
