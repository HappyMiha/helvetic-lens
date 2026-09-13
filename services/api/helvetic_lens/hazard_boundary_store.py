"""Read-only runtime selection of an operator-installed public boundary edition.

Atomic publication of current.json is the selection/renewal/revocation boundary.
No request may upload a catalogue or nominate a filesystem path. The process
holds at most one decoded catalogue, and rechecks selection, expiry and the file
identity before every private location check. It never serves stale fallback.
"""

import hashlib
import io
import json
import os
import tempfile
import threading
import zipfile
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .hazard_boundaries import MAX_PACKAGE_BYTES, BoundaryError, load_geopackage


class BoundarySelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    version: str = Field(pattern=r"^\d{4}-\d{2}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewed_at: datetime
    expires_on: date

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_schema(cls, value):
        if type(value) is not int:
            raise ValueError("Use an integer schema version")
        return value

    @field_validator("reviewed_at")
    @classmethod
    def aware_review(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Review time must include an offset")
        return value


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate selection field")
        result[key] = value
    return result


class BoundaryStore:
    def __init__(self, data_dir):
        self.root = Path(data_dir) / "hazard-boundaries"
        self._lock = threading.Lock()
        self._key = None
        self._catalogue = None

    def _clear(self, reason):
        self._key = self._catalogue = None
        return None, reason

    def _current(self, now):
        try:
            with (self.root / "current.json").open("rb") as source:
                raw = source.read(16385)
            if len(raw) > 16384:
                return self._clear("boundary_selection_invalid")
            selection = BoundarySelection.model_validate(json.loads(raw, object_pairs_hook=_unique_pairs))
            if selection.reviewed_at > now or selection.expires_on <= now.date():
                return self._clear("boundary_version_outside_review")
            objects = (self.root / "objects").resolve()
            path = (objects / (selection.sha256 + ".gpkg")).resolve()
            if path.parent != objects:
                return self._clear("boundary_asset_unavailable")
            stat = path.stat()
            if not path.is_file() or stat.st_size > MAX_PACKAGE_BYTES:
                return self._clear("boundary_asset_unavailable")
            key = (hashlib.sha256(raw).hexdigest(), stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            if key != self._key:
                with path.open("rb") as source:
                    payload = source.read(MAX_PACKAGE_BYTES + 1)
                catalogue = load_geopackage(payload, sha256=selection.sha256,
                    version=selection.version, expires_on=selection.expires_on)
                with (self.root / "current.json").open("rb") as current:
                    if current.read(16385) != raw:
                        return self._clear("boundary_selection_changed")
                after = path.stat()
                if (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != key[1:]:
                    return self._clear("boundary_selection_changed")
                # A newly selected/changed asset is checked against its hash
                # before replacing the cache. A failure clears the old edition.
                self._key, self._catalogue = key, catalogue
            if not self._catalogue.valid_from <= now.date() < self._catalogue.expires_on:
                return self._clear("boundary_version_outside_review")
            return self._catalogue, None
        except FileNotFoundError:
            return self._clear("boundary_catalogue_not_installed")
        except (OSError, ValueError, BoundaryError):
            return self._clear("boundary_catalogue_invalid")

    def verify_location(self, location, *, now=None):
        now = datetime.now(UTC) if now is None else now
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            return {"state": "unavailable", "reason": "boundary_clock_invalid"}
        now = now.astimezone(UTC)
        with self._lock:
            catalogue, reason = self._current(now)
            if catalogue is None:
                return {"state": "unavailable", "reason": reason}
            return asdict(catalogue.verify_location(location, on_date=now.date()))

    def match_warning(self, areas, location, *, geocode_version=None, now=None):
        """Internal worker entry point; geometry matching does not grant source use."""
        from .hazard_matching import match_location

        now = datetime.now(UTC) if now is None else now
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            return {"state": "unavailable", "reason": "boundary_clock_invalid"}
        now = now.astimezone(UTC)
        with self._lock:
            catalogue, reason = self._current(now)
            if catalogue is None:
                return {"state": "unavailable", "reason": reason}
            return asdict(match_location(areas, location, catalogue, on_date=now.date(),
                                         geocode_version=geocode_version))

    def verify_source_scope(self, location, cantons, *, now):
        """Entire saved footprint inside reviewed source cantons, not a warning hit."""
        import shapely
        from pyproj.exceptions import ProjError

        from .hazard_contracts import MunicipalityLocation
        from .hazard_matching import Projector

        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            return {"state": "unavailable", "reason": "boundary_clock_invalid"}
        now = now.astimezone(UTC)
        with self._lock:
            catalogue, reason = self._current(now)
            if catalogue is None:
                return {"state": "unavailable", "reason": reason}
            result = {"version": catalogue.version, "sha256": catalogue.sha256}
            proof = catalogue.verify_location(location, on_date=now.date())
            if proof.state != "verified":
                return {**result, "state": "unavailable", "reason": proof.reason}
            if (not cantons or len(cantons) > 26 or len(set(cantons)) != len(cantons)
                    or not set(cantons) <= set(catalogue.cantons)):
                return {**result, "state": "unavailable", "reason": "source_cantons_invalid"}
            if isinstance(location, MunicipalityLocation) or location.radius_km == 0:
                covered = location.canton in cantons
            else:
                try:
                    projector = Projector()
                    target = projector.circle(location.latitude, location.longitude, location.radius_km)
                    scope = shapely.union_all([catalogue.cantons[canton] for canton in cantons]).intersection(catalogue.country)
                    covered = scope.buffer(-projector.margin).covers(target)
                except (ValueError, ProjError, shapely.errors.GEOSException):
                    return {**result, "state": "unavailable", "reason": "source_scope_geometry_unavailable"}
            return {**result, "state": "verified" if covered else "unavailable",
                    "reason": "whole_location_in_source_scope" if covered else "source_scope_incomplete"}


def install_catalogue(data_dir, archive_path, *, archive_sha256, version, expires_on,
                      expected_selection_sha256=None, now=None):
    """Operator-only offline install/renewal; never called by a user HTTP route.

    The archive checksum must be copied from the reviewed official STAC asset.
    An update requires the exact SHA-256 of current.json. A per-directory
    exclusive lock prevents concurrent publishers; an interrupted lock is left
    for explicit operator inspection instead of being guessed stale.
    """
    now = datetime.now(UTC) if now is None else now
    if (not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None
            or type(expires_on) is not date or expires_on <= now.astimezone(UTC).date()):
        raise BoundaryError("boundary_review_expiry_invalid")
    archive_path = Path(archive_path)
    if not archive_path.is_file() or archive_path.stat().st_size > MAX_PACKAGE_BYTES:
        raise BoundaryError("boundary_archive_invalid")
    # Stream into a bounded private buffer so an archive replaced while hashing
    # cannot supply different content to the subsequent ZIP parser.
    with archive_path.open("rb") as source:
        raw = source.read(MAX_PACKAGE_BYTES + 1)
    if len(raw) > MAX_PACKAGE_BYTES or hashlib.sha256(raw).hexdigest() != archive_sha256:
        raise BoundaryError("boundary_archive_hash_invalid")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if (len(entries) != 1 or not entries[0].filename.lower().endswith(".gpkg")
                    or entries[0].is_dir() or entries[0].file_size > MAX_PACKAGE_BYTES):
                raise BoundaryError("boundary_archive_invalid")
            with archive.open(entries[0]) as source:
                payload = source.read(MAX_PACKAGE_BYTES + 1)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise BoundaryError("boundary_archive_invalid") from exc
    digest = hashlib.sha256(payload).hexdigest()
    selection = BoundarySelection(version=version, sha256=digest, archive_sha256=archive_sha256,
                                  reviewed_at=now, expires_on=expires_on)
    catalogue = load_geopackage(payload, sha256=digest, version=version, expires_on=expires_on)
    if catalogue.valid_from > now.astimezone(UTC).date():
        raise BoundaryError("boundary_version_outside_review")
    root = (Path(data_dir) / "hazard-boundaries").resolve()
    root.mkdir(parents=True, exist_ok=True)
    objects = root / "objects"
    objects.mkdir(exist_ok=True)
    if objects.resolve().parent != root:
        raise BoundaryError("boundary_asset_unavailable")
    lock = root / ".install.lock"
    # Never remove another installer's lock, even when acquiring it fails.
    with lock.open("xb"):
        pass
    temporary = None
    try:
        current = root / "current.json"
        def selection_hash():
            try:
                with current.open("rb") as source:
                    value = source.read(16385)
            except FileNotFoundError:
                return None
            if len(value) > 16384:
                raise BoundaryError("boundary_selection_invalid")
            return hashlib.sha256(value).hexdigest()

        current_hash = selection_hash()
        if current_hash != expected_selection_sha256:
            raise BoundaryError("boundary_selection_conflict")
        path = objects / (digest + ".gpkg")
        if path.exists():
            if path.is_symlink() or path.stat().st_size != len(payload):
                raise BoundaryError("boundary_asset_conflict")
            with path.open("rb") as source:
                if hashlib.sha256(source.read(MAX_PACKAGE_BYTES + 1)).hexdigest() != digest:
                    raise BoundaryError("boundary_asset_conflict")
        else:
            with path.open("xb") as target:
                target.write(payload)
                target.flush()
                os.fsync(target.fileno())
        encoded = selection.model_dump_json(indent=2).encode("utf-8") + b"\n"
        with tempfile.NamedTemporaryFile(dir=root, prefix=".selection-", suffix=".json", delete=False) as target:
            temporary = Path(target.name)
            target.write(encoded)
            target.flush()
            os.fsync(target.fileno())
        latest = selection_hash()
        if latest != expected_selection_sha256:
            raise BoundaryError("boundary_selection_conflict")
        os.replace(temporary, current)
        temporary = None
        return {"selection_sha256": hashlib.sha256(encoded).hexdigest(), "version": version,
                "sha256": digest, "municipalities": len(catalogue.municipalities),
                "cantons": len(catalogue.cantons), "expires_on": expires_on.isoformat()}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock.unlink()
