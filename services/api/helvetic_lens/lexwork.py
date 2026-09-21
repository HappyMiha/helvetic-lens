"""Bounded direct-law resolution for the Basel-Stadt and Bern official publishers.

The public metadata is the same version selection used by the publisher's UI.
This is not catalogue discovery and never treats a PDF pinned to one version as
an automatically updating law.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlsplit

from .config import DomainError

PUBLISHERS = {"www.gesetzessammlung.bs.ch": "CH-BS", "www.belex.sites.be.ch": "CH-BE"}
LAW_NUMBER = r"(?:RiE |RiB |BeE |BeB |BaB )?[0-9]+(?:\.[0-9]+)*"
LAW_PATH = re.compile(rf"^/app/(?P<language>de|fr|it)/texts_of_law/(?P<number>{LAW_NUMBER})(?:/versions/(?P<version>[1-9][0-9]*))?/?$")
DATA_PATH = re.compile(rf"^/data/(?P<number>{LAW_NUMBER})/(?P<language>de|fr|it)/?$")
METADATA_LIMIT = 2_000_000


@dataclass(frozen=True)
class LawReference:
    origin: str
    number: str
    language: str
    version: int | None
    source_url: str
    jurisdiction: str


def reference(value: str) -> LawReference | None:
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or parsed.hostname not in PUBLISHERS
                or parsed.username or parsed.password or parsed.port not in {None, 443} or parsed.query):
            return None
        match = LAW_PATH.fullmatch(unquote(parsed.path)) or DATA_PATH.fullmatch(unquote(parsed.path))
        if not match:
            return None
        values = match.groupdict()
        return LawReference(f"https://{parsed.hostname}", values["number"], values["language"],
                            int(values["version"]) if values.get("version") else None,
                            value, PUBLISHERS[parsed.hostname])
    except ValueError:
        return None


def unavailable(message):
    return DomainError(message, 502, "lexwork_document_unavailable")


async def fetch_law(fetcher, ref: LawReference):
    # Imported here to keep the existing Fetcher/extraction module independent.
    from .extraction import Fetched, canonical_url

    metadata_url = f"{ref.origin}/api/{ref.language}/texts_of_law/{quote(ref.number, safe='.')}"
    if ref.version:
        metadata_url += f"/versions/{ref.version}"
    metadata = await fetcher.fetch(metadata_url, boundary=(ref.origin, f"/api/{ref.language}/texts_of_law"))
    if canonical_url(metadata.url) != metadata_url or len(metadata.body) > METADATA_LIMIT:
        raise unavailable("The cantonal publisher returned an unexpected metadata document.")
    try:
        law = json.loads(metadata.body)["text_of_law"]
        selected = law["selected_version"]
        current = law["current_version"]
        version = selected["id"]
        if (law["systematic_number"] != ref.number or type(version) is not int or version <= 0
                or (version != ref.version if ref.version else version != current["id"])):
            raise ValueError()
        pdf = selected.get("pdf_link_tol_with_annexes") or selected["pdf_link_tol"]
        allowed = {f"{ref.origin}/api/{ref.language}/versions/{version}/{suffix}"
                   for suffix in ("pdf_file", "pdf_file_with_annexes")}
        if not isinstance(pdf, str) or pdf not in allowed:
            raise ValueError()
    except (ValueError, KeyError, TypeError) as exc:
        raise unavailable("The cantonal publisher could not verify the requested law, language and PDF version.") from exc
    fetched = await fetcher.fetch(pdf, boundary=(ref.origin, f"/api/{ref.language}/versions/{version}"))
    if canonical_url(fetched.url) != pdf or not fetched.body.startswith(b"%PDF"):
        raise unavailable("The cantonal publisher did not return the exact official PDF.")
    return Fetched(fetched.url, fetched.body, "application/pdf", {
        **fetched.metadata,
        "lexwork": True,
        "lexwork_source_url": ref.source_url,
        "lexwork_metadata_url": metadata_url,
        "lexwork_metadata_sha256": hashlib.sha256(metadata.body).hexdigest(),
        "lexwork_systematic_number": ref.number,
        "lexwork_version_id": version,
        "lexwork_version_selection": "historical" if ref.version else "current",
        "lexwork_source_version_label": selected.get("version_dates_str"),
        "lexwork_title": law.get("title"),
        "lexwork_language": ref.language,
        "lexwork_jurisdiction": ref.jurisdiction,
        "lexwork_annexes_included": pdf.endswith("pdf_file_with_annexes"),
    })
