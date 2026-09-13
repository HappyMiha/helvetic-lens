"""Public SIMAP 1.5.1 boundary; no authenticated attachments or interest actions.

Publication gates must also be enforced by eventual history readers and delivery,
not merely when an observation is ingested. Raw evidence hashes are audit values,
not a claim that every JSON formatting difference is a material tender change.
"""

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from email.utils import parsedate_to_datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx

from .tender_contracts import CpvAncestry

ZURICH = ZoneInfo("Europe/Zurich")
BASE = "https://www.simap.ch/api"
MAX_BYTES = 8_000_000
PUB_TYPES = {
    "request_for_information",
    "advance_notice",
    "abandonment",
    "direct_award",
    "award",
    "revocation",
    "participant_selection",
    "selective_offering_phase",
    "tender",
    "competition",
    "study_contract",
}


class PublicationEmbargo(ValueError):
    def __init__(self, until):
        self.until = until
        super().__init__("Publication is not yet permitted for third-party distribution")


class SourceUnavailable(ValueError):
    def __init__(self, reason, retry_after_seconds=None, *, status_code=None):
        self.reason = reason
        self.retry_after_seconds = retry_after_seconds
        self.status_code = status_code
        super().__init__(reason)


def source_id(value):
    if not isinstance(value, str):
        raise ValueError("Expected an official UUID")
    return str(UUID(value))


def source_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Expected an explicit publication date")
    return date.fromisoformat(value)


def aware(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("An aware observation clock is required")
    return value.astimezone(UTC)


def publication_gate(value):
    # Use the date of THIS correction/publication, never its initial publication.
    return datetime.combine(source_date(value), time(8), ZURICH).astimezone(UTC)


def deadline(value):
    """Preserve unknown or ambiguous deadlines; never turn a date into midnight."""
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:Z|[+-][0-9]{2}:[0-9]{2})?", value
    ):
        raise ValueError("Unsupported deadline precision")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        # An explicit source offset fixes the instant, including a repeated
        # autumn hour. Never replace it with today's offset or a naive clock.
        return parsed.astimezone(UTC)
    candidates = set()
    for fold in (0, 1):
        candidate = parsed.replace(tzinfo=ZURICH, fold=fold).astimezone(UTC)
        if candidate.astimezone(ZURICH).replace(tzinfo=None) == parsed:
            candidates.add(candidate)
    if len(candidates) != 1:
        raise ValueError("Ambiguous or nonexistent local deadline")
    return candidates.pop()


def cursor(value):
    if value == "":
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{8}\|[0-9]{1,20}", value):
        raise ValueError("Invalid source search cursor")
    datetime.strptime(value[:8], "%Y%m%d")
    return value


@dataclass(frozen=True)
class SearchPage:
    publications: tuple[dict, ...]
    next_cursor: str | None
    withheld_until: datetime | None


@dataclass(frozen=True)
class PublicationReferences:
    publications: tuple[dict, ...]
    withheld_until: datetime | None


def _permitted_references(entries, *, project_id, now):
    """Collapse a shared publication referenced by multiple lots, retaining scope."""
    project_id, now = source_id(project_id), aware(now)
    seen, withheld = {}, []
    for item, lot_id in entries:
        if not isinstance(item, dict) or item.get("pubType") not in PUB_TYPES:
            raise ValueError("Invalid publication reference")
        publication_id = source_id(item.get("id"))
        ready_at = publication_gate(item.get("publicationDate"))
        if lot_id is not None:
            lot_id = source_id(lot_id)
        if ready_at > now:
            withheld.append(ready_at)
        metadata = {
            "project_id": project_id,
            "publication_id": publication_id,
            "publication_date": item["publicationDate"],
            "publication_type": item["pubType"],
        }
        if publication_id in seen:
            if seen[publication_id][0] != metadata:
                raise ValueError("Conflicting publication references")
            seen[publication_id][1].add(lot_id)
        else:
            seen[publication_id] = (metadata, {lot_id})
    return PublicationReferences(
        tuple(
            {**value, "lot_ids": sorted(lot for lot in lots if lot is not None)}
            for value, lots in seen.values()
            if publication_gate(value["publication_date"]) <= now
        ),
        min(withheld) if withheld else None,
    )


def parse_project_header(raw, *, project_id, now):
    """Read latest PUBLIC publication identities; ignore vendor actions/submissions."""
    if not isinstance(raw, dict) or source_id(raw.get("id")) != source_id(project_id):
        raise ValueError("Project header identity mismatch")
    if raw.get("lotsType") == "with":
        lots = raw.get("lots")
        if not isinstance(lots, list) or not 1 <= len(lots) <= 1000:
            raise ValueError("Invalid project header lots")
        scopes, seen = [], set()
        for lot in lots:
            if not isinstance(lot, dict):
                raise ValueError("Invalid project header lot")
            lot_id = source_id(lot.get("id"))
            if lot_id in seen:
                raise ValueError("Duplicate project header lot")
            seen.add(lot_id)
            scopes.append((lot.get("latestPublication"), lot_id))
    elif raw.get("lotsType") == "without":
        if raw.get("lots"):
            raise ValueError("Conflicting project header scope")
        scopes = [(raw.get("latestPublication"), None)]
    else:
        raise ValueError("Unknown project header lot scope")
    entries = []
    for publication, lot_id in scopes:
        if not isinstance(publication, dict) or not isinstance(publication.get("dates"), dict):
            raise ValueError("Invalid latest publication dates")
        entries.append(
            (
                {
                    "id": publication.get("id"),
                    "pubType": publication.get("pubType"),
                    "publicationDate": publication["dates"].get("publicationDate"),
                },
                lot_id,
            )
        )
    return _permitted_references(entries, project_id=project_id, now=now)


def parse_publication_history(raw, *, project_id, now):
    if (
        not isinstance(raw, dict)
        or not isinstance(raw.get("pastPublications"), list)
        or len(raw["pastPublications"]) > 1000
    ):
        raise ValueError("Invalid or oversized publication history")
    # lotNumber is a display number, never a stable lot UUID. Detail parsing
    # establishes exact scope when each historical publication is retrieved.
    return _permitted_references(
        ((item, None) for item in raw["pastPublications"]), project_id=project_id, now=now
    )


def parse_search_page(raw, *, now, previous_cursor=None):
    now = aware(now)
    if not isinstance(raw, dict) or not isinstance(raw.get("projects"), list):
        raise ValueError("Invalid SIMAP search envelope")
    page = raw.get("pagination")
    if (
        not isinstance(page, dict)
        or type(page.get("itemsPerPage")) is not int
        or not 1 <= page["itemsPerPage"] <= 100
    ):
        raise ValueError("Invalid SIMAP pagination")
    if len(raw["projects"]) > page["itemsPerPage"]:
        raise ValueError("Oversized search page")
    continuation = cursor(page.get("lastItem"))
    if continuation is not None and continuation == previous_cursor:
        raise ValueError("Source repeated the pagination cursor")
    publications, withheld, seen = [], [], {}
    for row in raw["projects"]:
        if not isinstance(row, dict) or row.get("pubType") not in PUB_TYPES:
            raise ValueError("Unsupported publication record")
        project = source_id(row.get("id"))
        source_id(row.get("publicationId"))
        ready_at = publication_gate(row.get("publicationDate"))
        lots = row.get("lots")
        if not isinstance(lots, list) or len(lots) > 1000:
            raise ValueError("Invalid publication lot listing")
        lot_ids = set()
        for lot in lots:
            if not isinstance(lot, dict):
                raise ValueError("Invalid lot record")
            lot_id = source_id(lot.get("lotId"))
            source_id(lot.get("publicationId"))
            if lot_id in lot_ids:
                raise ValueError("Duplicate lot identity")
            lot_ids.add(lot_id)
            ready_at = max(ready_at, publication_gate(lot.get("publicationDate")))
        canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if project in seen:
            if seen[project] != canonical:
                raise ValueError("Conflicting duplicate project records")
            continue
        seen[project] = canonical
        if ready_at > now:
            withheld.append(ready_at)
        else:
            publications.append(copy.deepcopy(row))
    # An empty permitted page can still have a continuation. Withheld records
    # also require a scheduled re-read/lookback, not an advanced final watermark.
    return SearchPage(tuple(publications), continuation, min(withheld) if withheld else None)


def parse_publication(raw, *, project_id, publication_id, now):
    now = aware(now)
    if not isinstance(raw, dict) or not isinstance(raw.get("base"), dict):
        raise ValueError("Invalid publication detail")
    base = raw["base"]
    project_id, publication_id = source_id(project_id), source_id(publication_id)
    if (
        source_id(base.get("projectId")) != project_id
        or source_id(base.get("id")) != publication_id
        or source_id(raw.get("id")) != publication_id
        or raw.get("type") != base.get("type")
        or base.get("type") not in PUB_TYPES
    ):
        raise ValueError("Publication identity does not match the requested dossier/version")
    ready_at = publication_gate(base.get("publicationDate"))
    if ready_at > now:
        raise PublicationEmbargo(ready_at)
    dates = raw.get("dates") or {}
    if not isinstance(dates, dict):
        raise ValueError("Invalid publication date section")
    if dates.get("publicationDate") and dates["publicationDate"] != base["publicationDate"]:
        raise ValueError("Conflicting publication dates")
    offered = dates.get("offerDeadline")
    try:
        offered_at = deadline(offered)
        deadline_status = "known" if offered_at else "not_provided"
    except ValueError:
        offered_at, deadline_status = None, "invalid_or_ambiguous"
    if type(raw.get("hasProjectDocuments")) is not bool:
        raise ValueError("Invalid document availability indicator")
    original = copy.deepcopy(raw)
    evidence = json.dumps(original, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {
        "schema_version": "simap-publication-1.5.1-v1",
        "project_id": project_id,
        "publication_id": publication_id,
        "publication_date": base["publicationDate"],
        "publish_after": ready_at.isoformat(),
        "publication_type": base["type"],
        "corrected_publication_id": (
            source_id(base["correctedPubId"]) if base.get("correctedPubId") else None
        ),
        "offer_deadline": {
            "source_value": offered,
            "utc": offered_at.isoformat() if offered_at else None,
            "status": deadline_status,
            "source_locator": "/dates/offerDeadline",
        },
        "document_coverage": "requires_authorized_access"
        if raw["hasProjectDocuments"]
        else "no_documents_indicated",
        "qa_coverage": "not_verified",
        "original": original,
        "evidence_sha256": hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
    }


def parse_cpv_ancestry(raw, *, requested_code):
    """Use provider tree edges, never derive hierarchy by trimming code digits."""
    if (
        not isinstance(requested_code, str)
        or not re.fullmatch(r"[0-9]{8}", requested_code)
        or not isinstance(raw, dict)
        or not isinstance(raw.get("codes"), list)
    ):
        raise ValueError("Invalid CPV lookup")
    stack = [(node, ()) for node in raw["codes"]]
    seen, found = set(), []
    while stack:
        node, ancestors = stack.pop()
        if not isinstance(node, dict) or not isinstance(node.get("codes"), list):
            raise ValueError("Invalid CPV tree node")
        code = node.get("code")
        if (
            not isinstance(code, str)
            or not re.fullmatch(r"[0-9]{8}", code)
            or code in seen
            or len(ancestors) > 10
            or len(seen) >= 2000
        ):
            raise ValueError("Ambiguous or oversized CPV tree")
        seen.add(code)
        if code == requested_code:
            found.append(ancestors)
        stack.extend((child, (*ancestors, code)) for child in node["codes"])
    if len(found) != 1:
        raise ValueError("Requested CPV code is absent or ambiguous")
    digest = hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return CpvAncestry(code=requested_code, ancestors=found[0], source_sha256=digest)


class PublicClient:
    """Bounded read-only official requests; background jobs provide shared leases."""

    def _get(self, path, params=None):
        try:
            with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
                with client.stream(
                    "GET", BASE + path, params=params, headers={"Accept": "application/json"}
                ) as response:
                    if response.status_code != 200:
                        retry = response.headers.get("Retry-After", "")
                        if re.fullmatch(r"[0-9]{1,8}", retry):
                            retry = max(60, int(retry))
                        else:
                            try:
                                retry = max(
                                    60,
                                    math.ceil(
                                        (
                                            aware(parsedate_to_datetime(retry)) - datetime.now(UTC)
                                        ).total_seconds()
                                    ),
                                )
                            except (TypeError, ValueError, OverflowError):
                                retry = 300
                        reason = {
                            401: "access_required",
                            403: "access_denied",
                            404: "not_available",
                            429: "rate_limited",
                        }.get(response.status_code, "source_error")
                        raise SourceUnavailable(reason, retry, status_code=response.status_code)
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_BYTES:
                            raise SourceUnavailable("response_too_large")
                    return json.loads(content, parse_constant=self._reject_nonfinite)
        except (httpx.HTTPError, json.JSONDecodeError) as error:
            raise SourceUnavailable("source_unavailable") from error

    @staticmethod
    def _reject_nonfinite(value):
        raise SourceUnavailable("invalid_json_number")

    def search(self, query="", *, last_item=None, cpv_codes=(), newest_from=None, newest_until=None):
        if not isinstance(query, str) or (query != "" and not 3 <= len(query.strip()) <= 1000):
            raise ValueError("Provide a bounded search query")
        if (
            not isinstance(cpv_codes, (list, tuple))
            or len(cpv_codes) > 40
            or any(not isinstance(code, str) or not re.fullmatch(r"[0-9]{8}", code) for code in cpv_codes)
        ):
            raise ValueError("Select bounded official CPV codes")
        if not query and not cpv_codes:
            raise ValueError("A discovery query or CPV selection is required")
        params = [("search", query)] if query else []
        params.extend(("cpvCodes", code) for code in sorted(set(cpv_codes)))
        for name, value in (("newestPublicationFrom", newest_from), ("newestPublicationUntil", newest_until)):
            if value is not None:
                source_date(value)
                params.append((name, value))
        if newest_from is not None and newest_until is not None and newest_from > newest_until:
            raise ValueError("Invalid publication date interval")
        if last_item is not None:
            continuation = cursor(last_item)
            if continuation is None:
                raise ValueError("An empty cursor ends pagination")
            params.append(("lastItem", continuation))
        return self._get("/publications/v2/project/project-search", params)

    def publication(self, project_id, publication_id):
        return self._get(
            f"/publications/v1/project/{source_id(project_id)}/publication-details/{source_id(publication_id)}"
        )

    def project_header(self, project_id):
        return self._get(f"/publications/v2/project/{source_id(project_id)}/project-header")

    def publication_history(self, publication_id, *, lot_id=None):
        return self._get(
            f"/publications/v1/publication/{source_id(publication_id)}/past-publications",
            {"lotId": source_id(lot_id)} if lot_id is not None else None,
        )

    def cpv_ancestry(self, code):
        if not isinstance(code, str) or not re.fullmatch(r"[0-9]{8}", code):
            raise ValueError("Select an official eight-digit CPV code")
        return parse_cpv_ancestry(
            self._get("/codes/v1/cpv/search", {"query": code, "language": "en"}),
            requested_code=code,
        )
