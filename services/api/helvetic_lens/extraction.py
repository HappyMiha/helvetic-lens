import asyncio
import hashlib
import ipaddress
import json
import re
import socket
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup, UnicodeDammit

from .config import DomainError, Settings
from .integration_logs import IntegrationLogger, response_snapshot
from .pdf_reader import MAX_PDF_PAGES, PDF_EXTRACTOR_VERSION, read_pdf

EXTRACTOR_VERSION = "native-v3"
FEDLEX_DATA_ORIGIN = "https://fedlex.data.admin.ch"
FEDLEX_SPARQL_ENDPOINT = FEDLEX_DATA_ORIGIN + "/sparqlendpoint"
FEDLEX_ELI_HOSTS = {"fedlex.admin.ch", "www.fedlex.admin.ch", "fedlex.data.admin.ch"}
FEDLEX_DEFAULT_LANGUAGE = "de"
FEDLEX_ELI_PATH = re.compile(
    r"^/eli/(?P<collection>cc|oc|fga)/(?P<year>[A-Za-z0-9._~%-]+)/"
    r"(?P<identifier>[A-Za-z0-9._~%-]+)"
    r"(?:(?:/(?P<version>\d{8}))?/(?P<language>de|fr|it|rm|en)"
    r"(?:/(?P<format>html|pdf-a|pdf-x))?)?/?$",
    re.I,
)
FEDLEX_METADATA_LIMIT = 256 * 1024
_PDF_LINE_BREAK_HYPHEN = re.compile(
    r"(?P<head>[^\W\d_])(?P<hyphen>[-\u2010\u2011])[\t ]*\r?\n[\t ]*"
    r"(?P<continuation>[^\W\d_]+)",
    re.UNICODE,
)
_HYPHENATED_CONJUNCTIONS = frozenset(
    {"and", "e", "ed", "et", "ni", "o", "or", "ou", "oder", "u", "ubain", "und"}
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def _normalize_pdf_block(text: str) -> str:
    """Repair only soft wraps that are still explicit in PDF extractor output."""

    text = unicodedata.normalize("NFC", text).replace("\u00ad", "")

    def repair(match: re.Match) -> str:
        continuation = match.group("continuation")
        if continuation.casefold() in _HYPHENATED_CONJUNCTIONS:
            return f"{match.group('head')}{match.group('hyphen')} {continuation}"
        if continuation[0].isupper():
            return f"{match.group('head')}{match.group('hyphen')}{continuation}"
        return f"{match.group('head')}{continuation}"

    return normalize(_PDF_LINE_BREAK_HYPHEN.sub(repair, text))


def canonical_url(value: str) -> str:
    value, _ = urldefrag(value.strip())
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise DomainError("Enter a valid public HTTP or HTTPS URL.") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise DomainError("Enter a full public URL beginning with https:// or http://.")
    if parsed.username or parsed.password:
        raise DomainError("URLs containing credentials are not supported.")
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    if port and not (parsed.scheme == "https" and port == 443 or parsed.scheme == "http" and port == 80):
        host += f":{port}"
    return urlunsplit((parsed.scheme.lower(), host, parsed.path or "/", parsed.query, ""))


async def validate_public_url(value: str, allow_private: bool = False) -> str:
    url = canonical_url(value)
    if allow_private:
        return url
    parsed = urlsplit(url)
    try:
        answers = await asyncio.to_thread(
            socket.getaddrinfo,
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise DomainError("The source hostname could not be resolved.", 422, "unreachable_source") from exc
    if not answers or any(not ipaddress.ip_address(item[4][0]).is_global for item in answers):
        raise DomainError(
            "Only public source addresses are allowed. Private and local addresses are blocked.",
            422,
            "private_source",
        )
    return url


def within_section(url: str, source_url: str, section: str) -> bool:
    parsed, origin = urlsplit(canonical_url(url)), urlsplit(canonical_url(source_url))
    boundary = "/" + section.strip("/")
    return parsed.netloc == origin.netloc and (
        boundary == "/" or parsed.path == boundary or parsed.path.startswith(boundary + "/")
    )


@dataclass
class Fetched:
    url: str
    body: bytes
    content_type: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class FedlexEliReference:
    source_url: str
    work_uri: str
    collection: str
    language: str
    language_defaulted: bool = False
    expression_uri: str | None = None
    version_date: str | None = None
    requested_format: str | None = None


def fedlex_eli_reference(value: str) -> FedlexEliReference | None:
    """Map a public Fedlex ELI page to its stable Linked Data identifiers."""

    url = canonical_url(value)
    parsed = urlsplit(url)
    if parsed.hostname not in FEDLEX_ELI_HOSTS:
        return None
    match = FEDLEX_ELI_PATH.fullmatch(parsed.path)
    if not match:
        return None
    values = match.groupdict()
    collection = values["collection"].lower()
    language = (values["language"] or FEDLEX_DEFAULT_LANGUAGE).lower()
    work_uri = f"{FEDLEX_DATA_ORIGIN}/eli/{collection}/{values['year']}/{values['identifier']}"
    version = values["version"]
    return FedlexEliReference(
        source_url=url,
        work_uri=work_uri,
        collection=collection,
        language=language,
        language_defaulted=values["language"] is None,
        expression_uri=f"{work_uri}/{version}/{language}" if version else None,
        version_date=(f"{version[:4]}-{version[4:6]}-{version[6:]}" if version else None),
        requested_format=values["format"].lower() if values["format"] else None,
    )


@dataclass
class Extracted:
    title: str
    text: str
    passages: list[dict]
    content_type: str
    filename: str
    body: bytes
    extractor: str = EXTRACTOR_VERSION

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def preview(self) -> dict:
        return {
            "title": self.title,
            "content_type": self.content_type,
            "characters": len(self.text),
            "passage_count": len(self.passages),
            "page_count": max((p.get("page") or 0 for p in self.passages), default=0),
            "excerpt": self.text[:6000],
            "content_hash": self.content_hash,
            "extractor": self.extractor,
        }


class Fetcher:
    def __init__(self, settings: Settings, integration_logger: IntegrationLogger | None = None):
        self.settings = settings
        self.integration_logger = integration_logger

    def log_exchange(
        self,
        *,
        provider: str,
        operation: str,
        method: str,
        url: str,
        started: float,
        status: str,
        request_headers=None,
        request_body=None,
        response: httpx.Response | None = None,
        response_body=None,
        error: str | None = None,
    ) -> None:
        if not self.integration_logger:
            return
        if response_body is None and response is not None:
            try:
                response_body = response_snapshot(
                    response.content, response.headers.get("content-type", "")
                )
            except httpx.ResponseNotRead:
                response_body = None
        self.integration_logger.record(
            provider=provider,
            operation=operation,
            method=method,
            url=url,
            status=status,
            duration_ms=(time.monotonic() - started) * 1000,
            request_headers=request_headers,
            request_body=request_body,
            response_status=response.status_code if response is not None else None,
            response_headers=response.headers if response is not None else None,
            response_body=response_body,
            error=error,
        )

    async def fetch(
        self, url: str, provider: str = "native", *, boundary: tuple[str, str] | None = None
    ) -> Fetched:
        def check_boundary(target: str):
            if boundary and not within_section(target, *boundary):
                raise DomainError(
                    "This document redirects outside the selected website section. Add its URL directly if you want to track it.",
                    422,
                    "outside_section",
                )

        check_boundary(url)
        if provider == "firecrawl":
            fetched = await self._firecrawl(url)
            check_boundary(fetched.url)
            return fetched
        if provider != "native":
            raise DomainError("Choose native extraction or Firecrawl.")
        try:
            fedlex = fedlex_eli_reference(url)
            fedlex_metadata = {}
            fedlex_artifact_prefix = None
            if fedlex:
                url, fedlex_metadata, fedlex_artifact_prefix = await self._resolve_fedlex_eli(fedlex)
            async with httpx.AsyncClient(
                timeout=self.settings.fetch_timeout_seconds,
                follow_redirects=False,
                trust_env=False,
                headers={"User-Agent": "HelveticLens/0.1 (+document monitoring)"},
            ) as client:
                for _ in range(6):
                    if fedlex_artifact_prefix:
                        self._validate_fedlex_artifact(url, fedlex_artifact_prefix)
                    else:
                        check_boundary(url)
                    url = await validate_public_url(url, self.settings.allow_private_sources)
                    started, response, logged = time.monotonic(), None, False
                    chunks: list[bytes] = []

                    def log(status: str, error: str | None = None, body=None):
                        nonlocal logged
                        if not logged:
                            self.log_exchange(
                                provider="website",
                                operation="fetch_document",
                                method="GET",
                                url=url,
                                started=started,
                                status=status,
                                request_headers=client.headers,
                                response=response,
                                response_body=body,
                                error=error,
                            )
                            logged = True

                    try:
                        async with client.stream("GET", url) as response:
                            if response.status_code in {301, 302, 303, 307, 308}:
                                location = response.headers.get("location")
                                if not location:
                                    message = "The source returned a redirect without a destination."
                                    log("error", message)
                                    raise DomainError(message)
                                log("success", body={"redirect_to": location})
                                url = urljoin(url, location)
                                continue
                            if response.status_code >= 400:
                                message = (
                                    f"The source returned HTTP {response.status_code}. "
                                    "Try a direct public document URL."
                                )
                                log("error", message)
                                raise DomainError(message, 422, "source_http_error")
                            size = 0
                            async for chunk in response.aiter_bytes():
                                size += len(chunk)
                                if size > self.settings.max_document_bytes:
                                    message = "The document exceeds the configured download limit."
                                    log(
                                        "error",
                                        message,
                                        response_snapshot(
                                            b"".join(chunks),
                                            response.headers.get("content-type", ""),
                                        ),
                                    )
                                    raise DomainError(message, 413, "document_too_large")
                                chunks.append(chunk)
                            body = b"".join(chunks)
                            content_type = response.headers.get("content-type", "")
                            log("success", body=response_snapshot(body, content_type))
                            return Fetched(
                                url,
                                body,
                                content_type,
                                {"provider": "native", **fedlex_metadata},
                            )
                    except DomainError:
                        raise
                    except httpx.HTTPError:
                        log(
                            "error",
                            "The website request failed before a complete response was received.",
                            response_snapshot(
                                b"".join(chunks),
                                response.headers.get("content-type", "") if response else "",
                            ),
                        )
                        raise
        except httpx.TimeoutException as exc:
            raise DomainError(
                "The source timed out. The previous good version is unchanged.", 422, "source_timeout"
            ) from exc
        except httpx.HTTPError as exc:
            raise DomainError(
                "The source could not be downloaded. Check its URL or try a direct PDF.",
                422,
                "source_unavailable",
            ) from exc
        raise DomainError("The source exceeded the redirect limit.")

    async def _resolve_fedlex_eli(self, reference: FedlexEliReference):
        title_uri = f"{reference.work_uri}/{reference.language}"
        formats = [reference.requested_format] if reference.requested_format else ["html", "pdf-a", "pdf-x"]
        format_values = "\n".join(
            f"    (<{FEDLEX_DATA_ORIGIN}/vocabulary/user-format/{name}> {priority})"
            for priority, name in enumerate(formats)
        )
        if reference.expression_uri:
            version_selection = (
                f"BIND(<{reference.expression_uri}> AS ?expression)\n"
                f'BIND("{reference.version_date}"^^xsd:date AS ?date)'
            )
        elif reference.collection == "cc":
            version_selection = f"""
  ?version jolux:isMemberOf <{reference.work_uri}> ;
           jolux:dateApplicability ?date ;
           jolux:isRealizedBy ?expression .
  FILTER(STRENDS(STR(?expression), "/{reference.language}"))
  FILTER(?date <= xsd:date(NOW()))
"""
        else:
            version_selection = f"BIND(<{title_uri}> AS ?expression)"
        query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?expression ?date ?manifestation ?file ?title ?priority WHERE {{
  OPTIONAL {{ <{title_uri}> jolux:title ?title . }}
  {version_selection}
  ?expression jolux:isEmbodiedBy ?manifestation .
  VALUES (?userFormat ?priority) {{
{format_values}
  }}
  ?manifestation jolux:userFormat ?userFormat ;
                 jolux:isExemplifiedBy ?file .
}}
ORDER BY DESC(?date) ?priority
LIMIT 1
"""
        headers = {
            "User-Agent": "HelveticLens/0.1 (+document monitoring)",
            "Accept": "application/sparql-results+json",
        }
        request_body = {"query": query, "format": "application/sparql-results+json"}
        started, response, logged = time.monotonic(), None, False

        def log(status: str, error: str | None = None):
            nonlocal logged
            if not logged:
                self.log_exchange(
                    provider="fedlex",
                    operation="resolve_eli",
                    method="GET",
                    url=FEDLEX_SPARQL_ENDPOINT,
                    started=started,
                    status=status,
                    request_headers=headers,
                    request_body=request_body,
                    response=response,
                    error=error,
                )
                logged = True

        try:
            async with httpx.AsyncClient(
                timeout=min(self.settings.fetch_timeout_seconds, 30),
                trust_env=False,
                headers=headers,
            ) as client:
                response = await client.get(
                    FEDLEX_SPARQL_ENDPOINT,
                    params=request_body,
                    headers={"Accept": "application/sparql-results+json"},
                )
            if response.status_code >= 400:
                message = f"Fedlex metadata returned HTTP {response.status_code}. Retry the preview later."
                log("error", message)
                raise DomainError(message, 502, "fedlex_metadata_error")
            if len(response.content) > FEDLEX_METADATA_LIMIT:
                message = "Fedlex returned more metadata than the resolver accepts."
                log("error", message)
                raise DomainError(message, 502, "fedlex_metadata_error")
            rows = response.json()["results"]["bindings"]
            log("success")
        except DomainError as exc:
            log("error", exc.message)
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            log("error", "Fedlex metadata could not be read.")
            raise DomainError(
                "Fedlex metadata could not be read. Retry the preview later.",
                502,
                "fedlex_metadata_error",
            ) from exc
        if not rows:
            raise DomainError(
                f"Fedlex has no current {reference.language.upper()} HTML or PDF publication for this ELI law.",
                422,
                "fedlex_document_unavailable",
            )
        row = rows[0]
        try:
            expression = row["expression"]["value"]
            manifestation = row["manifestation"]["value"]
            artifact = canonical_url(row["file"]["value"])
            version_date = row.get("date", {}).get("value") or reference.version_date
            title = row.get("title", {}).get("value")
        except (KeyError, TypeError, ValueError, DomainError) as exc:
            raise DomainError(
                "Fedlex returned incomplete document metadata.", 502, "fedlex_metadata_error"
            ) from exc
        expected_expression = (
            reference.expression_uri
            if reference.expression_uri
            else f"{reference.work_uri}/{version_date.replace('-', '')}/{reference.language}"
            if reference.collection == "cc" and version_date
            else title_uri
        )
        if expression != expected_expression or not manifestation.startswith(expression + "/"):
            raise DomainError(
                "Fedlex returned document metadata outside the requested ELI law.",
                502,
                "fedlex_metadata_error",
            )
        format_name = manifestation.rsplit("/", 1)[-1]
        if format_name not in formats:
            raise DomainError(
                "Fedlex returned a document format outside the requested ELI publication.",
                502,
                "fedlex_metadata_error",
            )
        artifact_prefix = f"/filestore/fedlex.data.admin.ch{urlsplit(manifestation).path}/"
        self._validate_fedlex_artifact(artifact, artifact_prefix)
        metadata = {
            "fedlex_eli": True,
            "eli_source_url": reference.source_url,
            "eli_work_uri": reference.work_uri,
            "eli_expression_uri": expression,
            "eli_manifestation_uri": manifestation,
            "eli_version_date": version_date,
            "eli_format": format_name,
            "eli_language": reference.language,
            "eli_language_defaulted": reference.language_defaulted,
        }
        if title:
            metadata["eli_title"] = title[:500]
        return artifact, metadata, artifact_prefix

    @staticmethod
    def _validate_fedlex_artifact(value: str, path_prefix: str):
        parsed = urlsplit(canonical_url(value))
        if (
            parsed.scheme != "https"
            or parsed.hostname != "fedlex.data.admin.ch"
            or parsed.port not in {None, 443}
            or parsed.query
            or not parsed.path.startswith(path_prefix)
        ):
            raise DomainError(
                "Fedlex returned a document URL outside its official publication store.",
                502,
                "fedlex_metadata_error",
            )

    async def _firecrawl(self, url: str) -> Fetched:
        key = self.settings.firecrawl_api_key.get_secret_value()
        if not key:
            raise DomainError(
                "Firecrawl is not configured. Use native HTML/PDF extraction or configure a key on the server.",
                503,
                "provider_not_configured",
            )
        url = await validate_public_url(url, self.settings.allow_private_sources)
        endpoint = self.settings.firecrawl_api_url.rstrip("/") + "/v2/scrape"
        headers = {"Authorization": f"Bearer {key}"}
        payload = {
            "url": url,
            "formats": ["html"],
            "onlyMainContent": True,
            "maxAge": 0,
            "timeout": 60000,
        }
        started, response, logged = time.monotonic(), None, False

        def log(status: str, error: str | None = None):
            nonlocal logged
            if not logged:
                self.log_exchange(
                    provider="firecrawl",
                    operation="scrape_document",
                    method="POST",
                    url=endpoint,
                    started=started,
                    status=status,
                    request_headers=headers,
                    request_body=payload,
                    response=response,
                    error=error,
                )
                logged = True

        try:
            async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                )
            if response.status_code >= 400:
                message = (
                    f"Firecrawl returned HTTP {response.status_code}. "
                    "Check its credentials and usage limit."
                )
                log("error", message)
                raise DomainError(message, 502, "provider_error")
            result = response.json()
            if not result.get("success") or not result.get("data", {}).get("html"):
                raise DomainError("Firecrawl did not return usable HTML.", 502, "provider_error")
            data = result["data"]
            metadata = data.get("metadata") or {}
            final_url = await validate_public_url(
                metadata.get("sourceURL") or url, self.settings.allow_private_sources
            )
            body = data["html"].encode("utf-8")
            if len(body) > self.settings.max_document_bytes:
                raise DomainError("The extracted page exceeds the document limit.", 413)
            log("success")
            return Fetched(
                final_url,
                body,
                "text/html; charset=utf-8",
                {
                    "provider": "firecrawl",
                    "cache_state": metadata.get("cacheState"),
                    "cached_at": metadata.get("cachedAt"),
                },
            )
        except DomainError as exc:
            log("error", exc.message)
            raise
        except (httpx.HTTPError, ValueError) as exc:
            log("error", "Firecrawl could not complete the request.")
            raise DomainError("Firecrawl could not complete the request.", 502, "provider_error") from exc


def extract(
    body: bytes, content_type: str = "", filename: str = "document", provider: str = "native"
) -> Extracted:
    if not body:
        raise DomainError("The document is empty.", 422, "empty_document")
    name = PurePosixPath(filename.replace("\\", "/")).name or "document"
    mime = content_type.split(";")[0].strip().lower()
    passages: list[dict] = []
    title = name
    if body.startswith(b"%PDF") or mime == "application/pdf" or name.lower().endswith(".pdf"):
        mime = "application/pdf"
        pdf = read_pdf(body, max_pages=MAX_PDF_PAGES)
        title = normalize(pdf.title or name)
        for page in pdf.pages:
            for block in page.blocks:
                raw_text = unicodedata.normalize("NFC", block).strip()
                text = _normalize_pdf_block(block)
                if text:
                    passage = {"text": text, "page": page.number}
                    if normalize(raw_text) != text:
                        passage["raw_text"] = raw_text
                    passages.append(passage)
        if not passages:
            raise DomainError(
                "This PDF has no extractable text. Scanned PDFs require OCR, which is not in this MVP.",
                422,
                "ocr_required",
            )
    else:
        decoded = UnicodeDammit(body).unicode_markup
        if not decoded or "\x00" in decoded:
            raise DomainError(
                "This file is not supported text, HTML, or a text-based PDF.", 422, "unsupported_input"
            )
        is_json = mime in {"application/json", "text/json"} or name.lower().endswith(".json")
        if is_json:
            try:
                payload = json.loads(decoded)
            except json.JSONDecodeError as exc:
                raise DomainError(
                    "This JSON document could not be read.", 422, "invalid_json"
                ) from exc

            def collect_json(value, path="$"):
                if isinstance(value, dict):
                    for key, item in value.items():
                        collect_json(item, f"{path}.{key}")
                elif isinstance(value, list):
                    for index, item in enumerate(value):
                        collect_json(item, f"{path}[{index}]")
                elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
                    raw_value = str(value)
                    text_value = normalize(
                        BeautifulSoup(raw_value, "html.parser").get_text(" ", strip=True)
                        if re.search(r"<[^>]+>", raw_value)
                        else raw_value
                    )
                    if text_value:
                        passages.append({"text": text_value, "page": None, "json_path": path})

            collect_json(payload)
            if isinstance(payload, dict) and payload.get("title"):
                title = normalize(str(payload["title"]))
            mime = "application/json"
        elif (
            mime in {"text/html", "application/xhtml+xml"}
            or name.lower().endswith((".html", ".htm"))
            or bool(re.search(r"<(?:html|body|article|main|p|h1)\b", decoded[:3000], re.I))
        ):
            mime = "text/html"
            soup = BeautifulSoup(decoded, "html.parser")
            title_element = soup.find("h1") or soup.title
            if title_element:
                title = normalize(title_element.get_text(" ", strip=True))
            if soup.select_one("input[type=password]"):
                raise DomainError(
                    "This appears to be a login page. Use a public document URL.", 422, "login_required"
                )
            for node in soup.select(
                "script, style, noscript, svg, nav, header, footer, aside, form, template"
            ):
                node.decompose()
            court_root = soup.select_one("#highlight_content .content")
            root = (
                court_root
                or soup.find("main")
                or soup.find("article")
                or soup.find(attrs={"role": "main"})
                or soup.body
                or soup
            )
            tags = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "tr", "pre", "blockquote"}
            nodes = (
                root.select(":scope > .para")
                if court_root is not None
                else root.find_all(list(tags))
            )
            for node in nodes:
                if any(parent.name in tags for parent in node.parents if parent is not root):
                    continue
                text = normalize(node.get_text(" ", strip=True))
                if text:
                    passages.append({"text": text, "page": None})
            if not passages:
                passages = [
                    {"text": normalize(t), "page": None}
                    for t in root.get_text("\n", strip=True).splitlines()
                    if normalize(t)
                ]
        elif (
            mime.startswith("text/")
            or name.lower().endswith((".txt", ".md"))
            or mime in {"", "application/octet-stream"}
        ):
            mime = "text/plain"
            passages = [
                {"text": normalize(t), "page": None} for t in re.split(r"\n\s*\n", decoded) if normalize(t)
            ]
        else:
            raise DomainError(
                "Only HTML, TXT, and text-based PDF documents are supported.", 422, "unsupported_input"
            )
    text = "\n\n".join(p["text"] for p in passages)
    if len(text) < 40:
        raise DomainError(
            "The page has too little usable text. It may require JavaScript; try a direct PDF or an explicitly configured rendering provider.",
            422,
            "empty_extraction",
        )
    if len(text) > 1200000 or len(passages) > 6000:
        raise DomainError("The extracted document exceeds the MVP text limit.", 413, "document_too_large")
    for number, passage in enumerate(passages, 1):
        passage["id"] = f"p{number:05d}"
    extractor = f"{provider}-{PDF_EXTRACTOR_VERSION}" if mime == "application/pdf" else f"{provider}-v3"
    return Extracted(title[:500], text, passages, mime, name, body, extractor)


def discover_links(fetched: Fetched, section: str = "/", limit: int = 50) -> dict:
    if fetched.body.startswith(b"%PDF"):
        raise DomainError("Choose an HTML listing page for discovery, or add this PDF directly as a law.")
    soup = BeautifulSoup(fetched.body, "html.parser")
    for node in soup.select("nav, header, footer, aside, form, script, style, [role=navigation]"):
        node.decompose()
    root = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.find("article") or soup.body or soup
    seen, candidates = set(), []
    for link in root.find_all("a", href=True):
        try:
            url = canonical_url(urljoin(fetched.url, link["href"]))
        except DomainError:
            continue
        parsed = urlsplit(url)
        if not within_section(url, fetched.url, section):
            continue
        if url in seen or url == canonical_url(fetched.url):
            continue
        if re.search(r"\.(?:jpg|png|svg|css|js|zip|xlsx?|docx?|mp4|mp3)(?:$)", parsed.path, re.I):
            continue
        seen.add(url)
        label = (
            normalize(link.get_text(" ", strip=True)) or PurePosixPath(parsed.path).name or parsed.hostname
        )
        candidates.append(
            {
                "url": url,
                "title": label[:300],
                "format_hint": (
                    "PDF"
                    if parsed.path.lower().endswith(".pdf")
                    else "TXT"
                    if parsed.path.lower().endswith((".txt", ".md"))
                    else "HTML"
                ),
                "verified": False,
            }
        )
    # Give direct document files a place in a bounded result, even on link-heavy portals.
    candidates.sort(key=lambda candidate: candidate["format_hint"] == "HTML")
    return {
        "candidates": candidates[:limit],
        "candidate_count": len(candidates),
        "returned_count": min(len(candidates), limit),
        "limit": limit,
        "limit_reached": len(candidates) > limit,
        "depth": 1,
        "note": "Links from this listing page only. Format hints are unverified until preview; this is not exhaustive site coverage.",
    }
