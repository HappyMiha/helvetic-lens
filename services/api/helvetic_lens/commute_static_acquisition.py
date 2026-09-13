"""Bounded shared GTFS archive acquisition from the official CKAN catalog.

No private journey inputs, API keys, browser cookies or signed redirect URLs are
persisted. Scheduling/source approval and immutable version binding are separate.
"""

import csv
import hashlib
import json
import os
import re
import tempfile
import time
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from uuid import UUID
from zipfile import BadZipFile

import httpx

from .commute_acquisition import AcquisitionError, origin, retry_delay
from .commute_sources import clock
from .transport_static import MAX_ARCHIVE, StaticArchive

CATALOG_ORIGIN = "https://data.opentransportdata.swiss"
TOTAL_SECONDS = 240
MAX_RESOURCES = 1000
MAX_CATALOG_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class StaticResource:
    dataset_id: str
    resource_id: str
    version: str
    url: str

    def __post_init__(self):
        for value in (self.dataset_id, self.resource_id):
            if str(UUID(value)) != value:
                raise ValueError("Use a canonical catalog UUID")
        if not re.fullmatch(r"[0-9]{8}", self.version):
            raise ValueError("Unsupported Swiss timetable version")
        datetime.strptime(self.version, "%Y%m%d")
        parsed = urlsplit(self.url)
        if origin(self.url) != CATALOG_ORIGIN or parsed.query:
            raise ValueError("Use the official unsigned catalog resource URL")
        pattern = rf"/dataset/{self.dataset_id}/resource/{self.resource_id}/download/gtfs_fp[0-9]{{4}}_{self.version}\.zip"
        if not re.fullmatch(pattern, parsed.path):
            raise ValueError("Catalog URL and resource/version identifiers disagree")


@dataclass(frozen=True)
class AcquiredArchive:
    path: Path
    resource: StaticResource
    sha256: str
    size: int
    valid_from: date
    valid_to: date


def select_resource(payload, *, dataset_id, version):
    """Select one exact CKAN resource, never the latest filename or display name."""
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise AcquisitionError("static_catalog_unavailable")
    dataset = payload.get("result")
    if not isinstance(dataset, dict) or dataset.get("id") != dataset_id:
        raise AcquisitionError("static_catalog_identity_invalid", blocked=True)
    resources = dataset.get("resources")
    if not isinstance(resources, list) or len(resources) > MAX_RESOURCES:
        raise AcquisitionError("static_catalog_size_limit")
    candidates = set()
    for row in resources:
        if not isinstance(row, dict) or str(row.get("format", "")).upper() != "ZIP":
            continue
        url = row.get("url")
        if not isinstance(url, str) or not url.endswith("_" + version + ".zip"):
            continue
        try:
            candidates.add(StaticResource(dataset_id, row.get("id"), version, url))
        except (ValueError, TypeError, AttributeError):
            raise AcquisitionError("static_catalog_identity_invalid", blocked=True) from None
    if len(candidates) != 1:
        raise AcquisitionError("static_version_ambiguous" if candidates else "static_version_unavailable")
    return candidates.pop()


def fetch_catalog(dataset_id, *, guard=lambda: None, client=None, now=clock, monotonic=time.monotonic):
    """Public CKAN package lookup; access denial is not bypassed by scraping."""
    if str(UUID(dataset_id)) != dataset_id:
        raise ValueError("Use a canonical dataset UUID")
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False, trust_env=False)
    started = monotonic()
    try:
        guard()
        url = CATALOG_ORIGIN + "/api/3/action/package_show?id=" + dataset_id
        request = client.build_request("GET", url)
        request.headers = httpx.Headers({"Host": urlsplit(url).netloc, "Accept": "application/json",
            "Accept-Encoding": "identity", "User-Agent": "HelveticLens-Monitoring/2"})
        with closing(client.send(request, stream=True, auth=None, follow_redirects=False)) as response:
            if response.status_code in (401, 403) or response.is_redirect:
                raise AcquisitionError("static_catalog_access_denied", blocked=True)
            if response.status_code in (429, 503):
                raise AcquisitionError("static_catalog_throttled", retry_after=retry_delay(response.headers.get("Retry-After"), now()))
            if response.status_code != 200:
                raise AcquisitionError("static_catalog_unavailable")
            if response.headers.get("Content-Encoding", "identity").lower() not in ("identity", ""):
                raise AcquisitionError("static_catalog_encoding_unsupported")
            declared = response.headers.get("Content-Length")
            if declared is not None and (not declared.isdigit() or int(declared) > MAX_CATALOG_BYTES):
                raise AcquisitionError("static_catalog_size_limit")
            body = bytearray()
            for chunk in response.iter_raw(chunk_size=65536):
                if len(body) + len(chunk) > MAX_CATALOG_BYTES:
                    raise AcquisitionError("static_catalog_size_limit")
                if monotonic() - started >= 30:
                    raise AcquisitionError("static_catalog_timeout")
                guard()
                body.extend(chunk)
            guard()
            if declared is not None and len(body) != int(declared):
                raise AcquisitionError("static_catalog_body_incomplete")
            if monotonic() - started >= 30:
                raise AcquisitionError("static_catalog_timeout")
            return json.loads(body)
    except httpx.HTTPError:
        raise AcquisitionError("static_catalog_network_error") from None
    except (ValueError, UnicodeError, RecursionError):
        raise AcquisitionError("static_catalog_invalid") from None
    finally:
        if owned:
            client.close()


def acquire_archive(resource, directory, *, redirect_origins=(), expected_sha256=None,
                    guard=lambda: None, client=None, now=clock, monotonic=time.monotonic):
    """Stream to a private staging file, validate, then publish by content hash.

    Directory is operator-configured storage, never request data. Existing hash
    files are verified and retained; this function never replaces an archive.
    Caller supplies reviewed redirect origins; no object-storage wildcard.
    """
    if not isinstance(resource, StaticResource):
        raise ValueError("Use an exact validated catalog resource")
    if expected_sha256 is not None and not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise ValueError("Invalid expected archive SHA-256")
    allowed = {CATALOG_ORIGIN}
    for value in redirect_origins:
        if origin(value) != value or urlsplit(value).path:
            raise AcquisitionError("invalid_source_destination", blocked=True)
        allowed.add(value)
    guard()
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, staging_name = tempfile.mkstemp(prefix=".gtfs-", suffix=".part", dir=directory)
    staging = Path(staging_name)
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(20, connect=5), follow_redirects=False, trust_env=False)
    started, url, visited = monotonic(), resource.url, set()
    try:
        with os.fdopen(descriptor, "wb") as target:
            for hop in range(4):
                if origin(url) not in allowed or url in visited:
                    raise AcquisitionError("static_redirect_unreviewed", blocked=True)
                if monotonic() - started >= TOTAL_SECONDS:
                    raise AcquisitionError("static_timeout")
                guard()
                visited.add(url)
                client.cookies.clear()
                request = client.build_request("GET", url)
                request.headers = httpx.Headers({"Host": urlsplit(url).netloc, "Accept": "application/zip",
                    "Accept-Encoding": "identity", "User-Agent": "HelveticLens-Monitoring/2"})
                with closing(client.send(request, stream=True, auth=None, follow_redirects=False)) as response:
                    if response.status_code in (401, 403):
                        raise AcquisitionError("static_access_denied", blocked=True)
                    if response.status_code in (429, 503):
                        raise AcquisitionError("static_throttled", retry_after=retry_delay(response.headers.get("Retry-After"), now()))
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        if not location or len(location) > 8192 or hop == 3:
                            raise AcquisitionError("static_redirect_invalid", blocked=True)
                        url = urljoin(url, location)
                        continue
                    if response.status_code != 200:
                        raise AcquisitionError("static_http_error")
                    if response.headers.get("Content-Encoding", "identity").lower() not in ("", "identity"):
                        raise AcquisitionError("static_encoding_unsupported")
                    length = response.headers.get("Content-Length")
                    if length is not None and (not length.isascii() or not length.isdigit() or len(length) > 12 or int(length) > MAX_ARCHIVE):
                        raise AcquisitionError("static_size_limit")
                    digest, size = hashlib.sha256(), 0
                    for chunk in response.iter_raw(chunk_size=1024 * 1024):
                        size += len(chunk)
                        if size > MAX_ARCHIVE:
                            raise AcquisitionError("static_size_limit")
                        if monotonic() - started >= TOTAL_SECONDS:
                            raise AcquisitionError("static_timeout")
                        guard()
                        target.write(chunk)
                        digest.update(chunk)
                    if length is not None and int(length) != size:
                        raise AcquisitionError("static_body_incomplete")
                    target.flush()
                    os.fsync(target.fileno())
                    break
            else:
                raise AcquisitionError("static_redirect_invalid", blocked=True)
        hashed = digest.hexdigest()
        if expected_sha256 is not None and hashed != expected_sha256:
            raise AcquisitionError("static_checksum_conflict", blocked=True)
        with StaticArchive(staging, expected_version=resource.version) as archive:
            valid_from, valid_to = archive.start, archive.end
            if archive.sha256 != hashed:
                raise AcquisitionError("static_checksum_conflict", blocked=True)
        guard()
        destination = directory / (hashed + ".zip")
        try:
            # Atomic no-replacement publication; concurrent identical downloads
            # can share the verified artifact without replacing one another.
            os.link(staging, destination)
        except FileExistsError:
            if destination.is_symlink() or not destination.is_file():
                raise AcquisitionError("static_cache_conflict", blocked=True) from None
            with StaticArchive(destination, expected_version=resource.version) as existing:
                if existing.sha256 != hashed:
                    raise AcquisitionError("static_cache_conflict", blocked=True)
        return AcquiredArchive(destination, resource, hashed, size, valid_from, valid_to)
    except httpx.HTTPError:
        raise AcquisitionError("static_network_error") from None
    except (BadZipFile, UnicodeError, ValueError, csv.Error):
        raise AcquisitionError("static_archive_invalid") from None
    finally:
        if owned:
            client.close()
        staging.unlink(missing_ok=True)
