"""Licensed Basel hourly observations; shared bounded polling and revision history."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import uuid4

import httpx
from sqlalchemy import delete, or_, select, update

from .air_contracts import METRICS, SOURCE_URL, STATION, utc
from .air_models import AirMeasurement, AirReadingVersion, AirSourceCache
from .river_sources import digest

API = "https://data.bs.ch/api/explore/v2.1/catalog/datasets/100051"
LICENSE = "https://creativecommons.org/licenses/by/4.0/"
ATTRIBUTION = "Kanton Basel-Stadt · Luftqualität Station Basel-Binningen · MeteoSchweiz / NABEL"
MAX_BYTES = 2_000_000


def request_json(url):
    if url not in {
        API,
        API + "/records?limit=100&offset=0&order_by=datum_zeit%20desc",
        API + "/records?limit=100&offset=100&order_by=datum_zeit%20desc",
    }:
        raise ValueError("Unsupported source request")
    with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
        with client.stream("GET", url, headers={"Accept": "application/json"}) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise ValueError("Source response exceeded bound")
            raw = json.loads(body)
            if not isinstance(raw, dict):
                raise ValueError("Invalid source envelope")
            return raw


def validate_metadata(raw):
    meta = raw["metas"]["default"]
    if (
        raw["dataset_id"] != "100051"
        or meta["license"] != "CC BY 4.0"
        or meta["license_url"] != LICENSE
        or meta["publisher"] != "MeteoSchweiz"
        or meta["title"] != "Luftqualität Station Basel-Binningen"
    ):
        raise ValueError("Source contract changed")
    fields = {f["name"]: f for f in raw["fields"]}
    if fields["datum_zeit"]["type"] != "datetime":
        raise ValueError("Source time schema changed")
    for field in METRICS.values():
        if fields[field]["type"] != "double" or fields[field]["annotations"]["unit"] != "μg/m3":
            raise ValueError("Source unit schema changed")
    return {
        "schema_version": "basel-100051-hourly-v1",
        "license": "CC BY 4.0",
        "license_url": LICENSE,
        "publisher": meta["publisher"],
        "source_url": SOURCE_URL,
        "metadata_sha256": digest(raw),
    }


def parse(pages, now):
    rows = []
    for page in pages:
        if (
            not isinstance(page.get("results"), list)
            or len(page["results"]) > 100
            or type(page.get("total_count")) is not int
        ):
            raise ValueError("Invalid source page")
        rows.extend(page["results"])
    if not rows:
        raise ValueError("Empty source response")
    observations, times = [], set()
    response_hash = digest(pages)
    for row in rows:
        at = datetime.fromisoformat(row["datum_zeit"].replace("Z", "+00:00"))
        if at.tzinfo is None or at.minute or at.second or at.microsecond:
            raise ValueError("Ambiguous observation time")
        at = utc(at)
        if at in times:
            raise ValueError("Duplicate hour across source pages")
        times.add(at)
        if at > now:
            if any(row[field] is not None for field in METRICS.values()):
                raise ValueError("Future populated observation")
            continue  # Provider's future placeholders are not forecasts or measurements.
        if at < now - timedelta(hours=96):
            continue
        for metric, field in METRICS.items():
            raw_value, value = row[field], None
            quality = "missing"
            if raw_value is not None:
                if type(raw_value) not in {int, float}:
                    raise ValueError("Observation must match the numeric source schema")
                number = Decimal(str(raw_value))
                if not number.is_finite():
                    raise ValueError("Non-finite observation")
                if 0 <= number <= 100000:
                    value, quality = format(number, "f"), "provisional"
                else:
                    quality = "invalid"  # Retain withdrawal/invalidity; never clamp to zero.
            sample = {
                "station_id": "BAS",
                "metric": metric,
                "timestamp": at.isoformat(),
                "value": value,
                "unit": "µg/m³",
                "period": "hourly_mean",
                "quality": quality,
                "method": "basel-100051-hourly-v1",
                "source_url": SOURCE_URL,
                "source": ATTRIBUTION,
                "license_url": LICENSE,
                "response_sha256": response_hash,
                "fetched_at": now.isoformat(),
            }
            sample["value_hash"] = digest(
                {
                    k: sample[k]
                    for k in (
                        "station_id",
                        "metric",
                        "timestamp",
                        "value",
                        "quality",
                        "unit",
                        "period",
                        "method",
                    )
                }
            )
            observations.append(sample)
    if not any(s["value"] is not None for s in observations):
        # A valid response with withdrawn values is still authoritative and must be stored.
        if not observations:
            raise ValueError("No observations within recovery window")
    return observations


def _ensure(session, key, now):
    if session.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    session.execute(
        insert(AirSourceCache)
        .values(key=key, data={}, next_fetch_at=now, failures=0)
        .on_conflict_do_nothing(index_elements=["key"])
    )


def collect(database, key="BAS", *, now=None, fetch=request_json):
    if key not in {"catalog", "BAS"}:
        raise ValueError("Unsupported air source")
    now, token = utc(now or datetime.now(UTC)), str(uuid4())
    with database.session(include_all_organizations=True) as session:
        _ensure(session, key, now)
        claimed = session.execute(
            update(AirSourceCache)
            .where(
                AirSourceCache.key == key,
                AirSourceCache.next_fetch_at <= now,
                or_(AirSourceCache.lease_until.is_(None), AirSourceCache.lease_until <= now),
            )
            .values(
                lease_token=token,
                lease_until=now + timedelta(minutes=3),
                next_fetch_at=now + timedelta(hours=1),
            )
        ).rowcount
        session.commit()
    if not claimed:
        return "cached_or_busy"
    try:
        samples = []
        if key == "catalog":
            data = validate_metadata(fetch(API))
        else:
            with database.session(include_all_organizations=True) as session:
                catalog = session.get(AirSourceCache, "catalog")
                if (
                    catalog is None
                    or catalog.error
                    or not catalog.fetched_at
                    or now - utc(catalog.fetched_at) > timedelta(hours=25)
                ):
                    raise ValueError("Current source contract unavailable")
            pages = [
                fetch(API + f"/records?limit=100&offset={offset}&order_by=datum_zeit%20desc")
                for offset in (0, 100)
            ]
            samples = parse(pages, now)
            data = {"response_sha256": digest(pages), "sample_count": len(samples), "recovery_hours": 72}
    except (httpx.HTTPError, ValueError, KeyError, TypeError, InvalidOperation):
        with database.session(include_all_organizations=True) as session:
            row = session.scalar(
                select(AirSourceCache)
                .where(AirSourceCache.key == key, AirSourceCache.lease_token == token)
                .with_for_update()
            )
            if row:
                row.failures += 1
                row.error = "source_unavailable"
                row.lease_until = row.lease_token = None
                row.next_fetch_at = now + timedelta(hours=min(24, 2 ** min(row.failures - 1, 5)))
                session.commit()
        return "source_unavailable"
    with database.session(include_all_organizations=True) as session:
        row = session.scalar(
            select(AirSourceCache)
            .where(AirSourceCache.key == key, AirSourceCache.lease_token == token)
            .with_for_update()
        )
        if row is None:
            return "lease_lost"
        for sample in samples:
            identity = digest([sample["station_id"], sample["metric"], sample["timestamp"]])
            previous = session.get(AirMeasurement, identity)
            if previous and previous.evidence["value_hash"] == sample["value_hash"]:
                continue
            sample["revision"] = previous.evidence["revision"] + 1 if previous else 1
            sample["corrected"] = bool(
                previous and (previous.evidence["quality"] != "missing" or previous.evidence.get("corrected"))
            )
            sample["previous_value_hash"] = previous.evidence["value_hash"] if previous else None
            version_id = digest([identity, sample["revision"], sample["value_hash"]])
            sample["version_id"] = version_id
            session.add(
                AirReadingVersion(
                    id=version_id,
                    station_id="BAS",
                    metric=sample["metric"],
                    measured_at=utc(sample["timestamp"]),
                    evidence=sample,
                )
            )
            if previous:
                previous.evidence = sample
            else:
                session.add(
                    AirMeasurement(
                        id=identity,
                        station_id="BAS",
                        metric=sample["metric"],
                        measured_at=utc(sample["timestamp"]),
                        evidence=sample,
                    )
                )
        if key == "BAS":
            # A withdrawal must not rewind the reader to an older apparently good hour.
            known = [s["timestamp"] for s in samples if s["value"] is not None]
            if row.data.get("latest_observation_at"):
                known.append(row.data["latest_observation_at"])
            data["latest_observation_at"] = max(known, default=None)
        row.data, row.fetched_at, row.error, row.failures = data, now, None, 0
        row.lease_until = row.lease_token = None
        row.next_fetch_at = now + (timedelta(days=1) if key == "catalog" else timedelta(hours=1))
        for model in (AirMeasurement, AirReadingVersion):
            session.execute(
                delete(model)
                .where(model.measured_at < now - timedelta(days=30))
                .execution_options(synchronize_session=False)
            )
        session.commit()
    return "updated"


def catalogue(session):
    row = session.get(AirSourceCache, "catalog")
    ready = (
        row is not None
        and row.fetched_at is not None
        and not row.error
        and datetime.now(UTC) - utc(row.fetched_at) <= timedelta(hours=25)
    )
    return {
        "stations": [STATION] if ready else [],
        "health": "ready" if ready else "source_unavailable",
        "source_url": SOURCE_URL,
        "attribution": ATTRIBUTION,
        "license_url": LICENSE,
        "unsupported": [{"area": "Lugano", "reason": "source_contract_pending"}],
        "coverage_scope": "verified_station_only",
    }


def cleanup(database, *, now=None):
    now = utc(now or datetime.now(UTC))
    removed = 0
    with database.session(include_all_organizations=True) as session:
        for model in (AirMeasurement, AirReadingVersion):
            removed += session.execute(
                delete(model)
                .where(model.measured_at < now - timedelta(days=30))
                .execution_options(synchronize_session=False)
            ).rowcount
        session.commit()
    return {"removed_measurements": removed}
