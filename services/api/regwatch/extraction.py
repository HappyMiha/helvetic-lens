import asyncio
import hashlib
import ipaddress
import re
import socket
import unicodedata
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

import httpx
import pymupdf
from bs4 import BeautifulSoup, UnicodeDammit

from .config import DomainError, Settings

EXTRACTOR_VERSION = "native-v1"


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


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


@dataclass
class Fetched:
    url: str
    body: bytes
    content_type: str
    metadata: dict = field(default_factory=dict)


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
    def __init__(self, settings: Settings):
        self.settings = settings

    async def fetch(self, url: str, provider: str = "native") -> Fetched:
        if provider == "firecrawl":
            return await self._firecrawl(url)
        if provider != "native":
            raise DomainError("Choose native extraction or Firecrawl.")
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.fetch_timeout_seconds,
                follow_redirects=False,
                trust_env=False,
                headers={"User-Agent": "ApertusRegWatch/0.1 (+document monitoring)"},
            ) as client:
                for _ in range(6):
                    url = await validate_public_url(url, self.settings.allow_private_sources)
                    async with client.stream("GET", url) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location:
                                raise DomainError("The source returned a redirect without a destination.")
                            url = urljoin(url, location)
                            continue
                        if response.status_code >= 400:
                            raise DomainError(
                                f"The source returned HTTP {response.status_code}. Try a direct public document URL.",
                                422,
                                "source_http_error",
                            )
                        chunks, size = [], 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > self.settings.max_document_bytes:
                                raise DomainError(
                                    "The document exceeds the configured download limit.",
                                    413,
                                    "document_too_large",
                                )
                            chunks.append(chunk)
                        return Fetched(
                            url,
                            b"".join(chunks),
                            response.headers.get("content-type", ""),
                            {"provider": "native"},
                        )
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

    async def _firecrawl(self, url: str) -> Fetched:
        key = self.settings.firecrawl_api_key.get_secret_value()
        if not key:
            raise DomainError(
                "Firecrawl is not configured. Use native HTML/PDF extraction or configure a key on the server.",
                503,
                "provider_not_configured",
            )
        url = await validate_public_url(url, self.settings.allow_private_sources)
        try:
            async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
                response = await client.post(
                    self.settings.firecrawl_api_url.rstrip("/") + "/v2/scrape",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "url": url,
                        "formats": ["html"],
                        "onlyMainContent": True,
                        "maxAge": 0,
                        "timeout": 60000,
                    },
                )
            if response.status_code >= 400:
                raise DomainError(
                    f"Firecrawl returned HTTP {response.status_code}. Check its credentials and usage limit.",
                    502,
                    "provider_error",
                )
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
        except (httpx.HTTPError, ValueError) as exc:
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
        try:
            with pymupdf.open(stream=body, filetype="pdf") as pdf:
                if pdf.needs_pass:
                    raise DomainError("Password-protected PDFs are not supported.")
                if pdf.page_count > 250:
                    raise DomainError("This PDF exceeds the 250-page MVP limit.", 413)
                title = normalize((pdf.metadata or {}).get("title") or name)
                for page_number, page in enumerate(pdf, 1):
                    for block in page.get_text("blocks", sort=True):
                        if len(block) > 6 and block[6] != 0:
                            continue
                        text = normalize(block[4])
                        if text:
                            passages.append({"text": text, "page": page_number})
        except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
            raise DomainError(
                "This PDF could not be read. It may be damaged or unsupported.", 422, "invalid_pdf"
            ) from exc
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
        is_html = (
            mime in {"text/html", "application/xhtml+xml"}
            or name.lower().endswith((".html", ".htm"))
            or bool(re.search(r"<(?:html|body|article|main|p|h1)\b", decoded[:3000], re.I))
        )
        if is_html:
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
            root = (
                soup.find("main")
                or soup.find("article")
                or soup.find(attrs={"role": "main"})
                or soup.body
                or soup
            )
            tags = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "tr", "pre", "blockquote"}
            for node in root.find_all(list(tags)):
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
    return Extracted(title[:500], text, passages, mime, name, body, f"{provider}-v1")


def discover_links(fetched: Fetched, section: str = "/", limit: int = 50) -> dict:
    if fetched.body.startswith(b"%PDF"):
        raise DomainError("Choose an HTML listing page for discovery, or add this PDF directly as a law.")
    soup = BeautifulSoup(fetched.body, "html.parser")
    root = soup.find("main") or soup.find("article") or soup.body or soup
    origin = urlsplit(fetched.url)
    boundary = "/" + section.strip("/")
    seen, candidates = set(), []
    for link in root.find_all("a", href=True):
        try:
            url = canonical_url(urljoin(fetched.url, link["href"]))
        except DomainError:
            continue
        parsed = urlsplit(url)
        if parsed.netloc.lower() != origin.netloc.lower():
            continue
        if boundary != "/" and parsed.path != boundary and not parsed.path.startswith(boundary + "/"):
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
                "format_hint": "PDF" if parsed.path.lower().endswith(".pdf") else "HTML",
                "verified": False,
            }
        )
    return {
        "candidates": candidates[:limit],
        "candidate_count": len(candidates),
        "returned_count": min(len(candidates), limit),
        "limit": limit,
        "limit_reached": len(candidates) > limit,
        "depth": 1,
        "note": "Links from this listing page only. Format hints are unverified until preview; this is not exhaustive site coverage.",
    }
