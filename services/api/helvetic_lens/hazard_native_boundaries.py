"""First installation of the reviewed public swisstopo edition.

No private place is sent to the publisher. Existing installations (including a
removed selection, corrupt asset, expired review or interrupted install) belong
to the operator and are never repaired or reactivated implicitly. Publication
checks both the pinned archive and decoded geometry through the native installer.
"""

import hashlib
import tempfile
import time
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from .hazard_boundaries import BoundaryError
from .hazard_boundary_store import install_catalogue

URL = "https://data.geo.admin.ch/ch.swisstopo.swissboundaries3d/swissboundaries3d_2026-01/swissboundaries3d_2026-01_2056_5728.gpkg.zip"
ARCHIVE_SHA256 = "68e922353c76fa5db3cef06a32f9711c0198faa6fbd2b5bcde9edc88b0f8999f"
ARCHIVE_BYTES = 37_361_779
VERSION = "2026-01"
REVIEWED_AT = datetime(2026, 9, 14, tzinfo=UTC)
# The reviewed January edition is not silently carried into the next edition's
# year. Renewal uses the existing explicit, hash-bound operator installer.
EXPIRES_ON = date(2027, 1, 1)
MAX_SECONDS = 60


def ensure(data_dir, *, now, checkpoint=lambda: None, client=None, monotonic=time.monotonic):
    if (not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None
            or now < REVIEWED_AT or now.astimezone(UTC).date() >= EXPIRES_ON):
        raise BoundaryError("boundary_version_outside_review")
    base = Path(data_dir)
    root = base / "hazard-boundaries"
    if root.exists() or root.is_symlink():
        return {"state": "existing_catalogue"}
    checkpoint()
    base.mkdir(parents=True, exist_ok=True)
    lock = base / ".hazard-boundary-download.lock"
    try:
        with lock.open("xb"):
            pass
    except FileExistsError:
        return {"state": "installation_in_progress"}
    owned = client is None
    temporary = None
    started = monotonic()

    def guard():
        checkpoint()
        if monotonic() - started > MAX_SECONDS:
            raise BoundaryError("boundary_download_deadline")

    try:
        client = client or httpx.Client(timeout=httpx.Timeout(20, connect=10), follow_redirects=False)
        if root.exists() or root.is_symlink():
            return {"state": "existing_catalogue"}
        guard()
        # A standalone Request does not inherit a supplied client's auth,
        # cookies or query defaults. Redirects are never followed.
        request = httpx.Request("GET", URL, headers={"Accept": "application/x.geopackage+zip, application/zip, application/octet-stream",
            "Accept-Encoding": "identity", "User-Agent": "HelveticLens/1.0 (+https://helveticlens.ch)"},
            extensions={"timeout": {"connect": 10, "read": 20, "write": 20, "pool": 20}})
        with closing(client.send(request, stream=True, follow_redirects=False, auth=None)) as response:
            if (response.status_code != 200 or response.url != httpx.URL(URL)
                    or response.headers.get("content-encoding", "identity").lower() != "identity"
                    or response.headers.get("content-type", "").split(";")[0].lower().strip()
                    not in {"application/x.geopackage+zip", "application/zip", "application/octet-stream", "application/x-zip-compressed"}):
                raise BoundaryError("boundary_download_unavailable")
            length = response.headers.get("content-length")
            if length is not None and length != str(ARCHIVE_BYTES):
                raise BoundaryError("boundary_archive_size_invalid")
            size, digest = 0, hashlib.sha256()
            with tempfile.NamedTemporaryFile(dir=base, prefix=".hazard-boundary-", suffix=".zip", delete=False) as output:
                temporary = Path(output.name)
                for chunk in response.iter_raw(64 * 1024):
                    guard()
                    size += len(chunk)
                    if size > ARCHIVE_BYTES:
                        raise BoundaryError("boundary_archive_size_invalid")
                    digest.update(chunk)
                    output.write(chunk)
            if size != ARCHIVE_BYTES or digest.hexdigest() != ARCHIVE_SHA256:
                raise BoundaryError("boundary_archive_hash_invalid")
        guard()
        result = install_catalogue(base, temporary, archive_sha256=ARCHIVE_SHA256,
            version=VERSION, expires_on=EXPIRES_ON, now=now, require_new_root=True)
        return {"state": "installed", **result}
    except httpx.HTTPError:
        raise BoundaryError("boundary_download_unavailable") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if owned and client is not None:
            client.close()
        lock.unlink()
