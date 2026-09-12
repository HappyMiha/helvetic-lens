"""Bounded official FOEN requests with durable shared leases and 30-day samples."""
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import uuid4

import httpx
from sqlalchemy import delete, or_, select, update

from .river_contracts import DANGER_URL, METRICS, SOURCE_URL, utc
from .river_models import RiverMeasurement, RiverSourceCache

GRAPHQL = "https://data.bafu.admin.ch/api"
LINDAS = "https://lindas.admin.ch/query"
MAX_BYTES = 4_000_000
CATALOG_QUERY = '{ water { observations { stations(where:{status:{_eq:"Aufgebaut"}},limit:1000) { no name riverName latitude longitude } } } }'
DANGER_QUERY = '''PREFIX h: <https://environment.ld.admin.ch/foen/hydro/dimension/>
SELECT ?station ?time ?danger WHERE {
 GRAPH <https://lindas.admin.ch/foen/hydro> {
  ?observation h:station ?station; h:measurementTime ?time.
  OPTIONAL { ?observation h:dangerLevel ?danger }
 }
} LIMIT 1000'''


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def request_json(url, payload):
    # Endpoints and query construction are server-owned; no user URL or credential.
    with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
        options = {"json": payload} if url == GRAPHQL else {"data": {"query": payload}}
        with client.stream("POST", url, headers={"Accept": "application/sparql-results+json" if url == LINDAS else "application/json"}, **options) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise ValueError("Source response limit exceeded")
            data = json.loads(body)
            if not isinstance(data, dict) or data.get("errors"):
                raise ValueError("Incomplete source response")
            return data


def _catalog(raw):
    rows = raw["data"]["water"]["observations"]["stations"]
    if not isinstance(rows, list) or len(rows) >= 1000:
        raise ValueError("Incomplete station catalogue")
    stations = []
    for row in rows:
        station = row["no"]
        if not isinstance(station, str) or len(station) != 4 or not station.isascii() or not station.isdigit() or not station.startswith("2"):
            continue  # The catalogue also contains historical/partner identifiers outside the live feed.
        stations.append({"id": station, "name": str(row["name"])[:160], "waterbody": str(row.get("riverName") or "")[:160],
                         "latitude": row.get("latitude"), "longitude": row.get("longitude"),
                         "source_url": f"https://www.hydrodaten.admin.ch/de/seen-und-fluesse/stationen/{station}"})
    if not stations or len({row["id"] for row in stations}) != len(stations):
        raise ValueError("Empty or duplicate catalogue")
    return {"stations": sorted(stations, key=lambda s: (s["waterbody"], s["name"], s["id"]))}, []


def _number(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("Missing numeric value")
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("Non-finite measurement")
    return format(number, "f")


def _source_time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Source timestamp lacks a timezone")
    return utc(parsed)


def _measurement_samples(raw, station, now):
    rows = raw["data"]["water"]["observations"]["data_10min_mean"]
    if not isinstance(rows, list) or len(rows) > 1000:
        raise ValueError("Unexpected measurement result size")
    samples = []
    response_hash = digest(raw)
    for row in rows:
        metric = row["parameterName"]
        if metric not in METRICS:
            continue
        at = _source_time(row["timestamp"])
        if at > now or at < now - timedelta(hours=49):
            raise ValueError("Measurement outside requested window")
        if at.minute % 10 or at.second:
            raise ValueError("Unaligned source aggregate")
        expected = {"W": {"m ü.M."}, "Q": {"m3/s", "m³/s"}, "WT": {"°C"}}[metric]
        if row.get("unitSymbol") not in expected:
            continue  # Unknown units never become comparable measurements.
        try:
            value = _number(row["value"])
        except (ValueError, InvalidOperation):
            continue
        samples.append({"station_id": station, "metric": metric, "timestamp": at.isoformat(), "value": value,
                        "unit": METRICS[metric][0], "source_unit": row["unitSymbol"],
                        "datum": f"FOEN:{station}:m ü.M." if metric == "W" else None,
                        "aggregation": "10min_mean", "quality": {"1": "provisional", "2": "validated", "3": "definitive"}.get(str(row.get("releaseState")), "validation_not_supplied"),
                        "source_url": SOURCE_URL, "source": "FOEN hydrological observations", "response_sha256": response_hash,
                        "fetched_at": now.isoformat()})
    identities = [(row["metric"], row["timestamp"]) for row in samples]
    if len(set(identities)) != len(identities):
        raise ValueError("Ambiguous duplicate measurements")
    return {"sample_count": len(samples), "response_sha256": response_hash}, samples


def _danger_samples(raw, now):
    rows = raw["results"]["bindings"]
    if not isinstance(rows, list) or len(rows) >= 1000:
        raise ValueError("Incomplete official danger response")
    samples = []
    for row in rows:
        prefix = "https://environment.ld.admin.ch/foen/hydro/station/"
        identifier = row["station"]["value"]
        station = identifier.removeprefix(prefix)
        if not identifier.startswith(prefix) or len(station) != 4 or not station.isascii() or not station.isdigit() or not station.startswith("2"):
            continue
        value = row.get("danger", {}).get("value")
        if value not in {"1", "2", "3", "4", "5"}:
            continue
        at = _source_time(row["time"]["value"])
        if at > now + timedelta(minutes=5):
            raise ValueError("Future danger timestamp")
        samples.append({"station_id": station, "metric": "danger", "timestamp": at.isoformat(), "value": value,
                        "unit": "official_level", "source_unit": "official_level", "datum": None,
                        "aggregation": "official_station_state", "quality": "provisional",
                        "source_url": DANGER_URL, "source": "FOEN LINDAS station danger", "response_sha256": digest(raw),
                        "fetched_at": now.isoformat()})
    if len({(s["station_id"], s["timestamp"]) for s in samples}) != len(samples):
        raise ValueError("Ambiguous official danger state")
    return {"sample_count": len(samples), "response_sha256": digest(raw)}, samples


def _live_samples(raw, station, now):
    # Native live units are verified against the SAME station's aggregate metadata.
    # Aggregate values are never mixed into live threshold or change-window inputs.
    _, metadata = _measurement_samples(raw, station, now)
    units = {}
    for row in metadata:
        units.setdefault(row["metric"], set()).add((row["unit"], row["source_unit"], row["datum"]))
    rows = raw["data"]["water"]["observations"]["data_live"]
    if not isinstance(rows, list) or len(rows) > 1000:
        raise ValueError("Incomplete live data")
    samples = []
    response_hash = digest(raw)
    for row in rows:
        metric = row["parameterName"]
        if metric not in METRICS or len(units.get(metric, set())) != 1 or row["value"] is None:
            continue
        at = _source_time(row["timestamp"])
        if row["stationNo"] != station or at > now or at < now - timedelta(hours=12, minutes=10):
            raise ValueError("Live observation outside its station/window")
        if at.minute % 5 or at.second or type(row["releaseStatus"]) is not int or row["releaseStatus"] != 0:
            raise ValueError("Unverified live method or quality")
        unit, source_unit, datum = next(iter(units[metric]))
        samples.append({"station_id": station, "metric": metric, "timestamp": at.isoformat(), "value": _number(row["value"]),
                        "unit": unit, "source_unit": source_unit, "datum": datum, "aggregation": "live_observation",
                        "quality": "provisional", "release_status": 0, "source_url": SOURCE_URL,
                        "source": "FOEN live hydrological observations", "response_sha256": response_hash, "fetched_at": now.isoformat()})
    if len({(s["metric"], s["timestamp"]) for s in samples}) != len(samples):
        raise ValueError("Ambiguous live measurements")
    return {"sample_count": len(samples), "response_sha256": response_hash, "recovery_hours": 12}, samples


def _ensure_row(session, key, now):
    dialect = session.bind.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    session.execute(insert(RiverSourceCache).values(key=key, data={}, next_fetch_at=now, failures=0).on_conflict_do_nothing(index_elements=["key"]))


def collect(database, key, *, now=None, fetch=request_json):
    now = utc(now or datetime.now(UTC))
    if key not in {"catalog", "danger"} and (len(key) != 4 or not key.isascii() or not key.isdigit() or not key.startswith("2")):
        raise ValueError("Unsupported source key")
    token = str(uuid4())
    with database.session(include_all_organizations=True) as session:
        _ensure_row(session, key, now)
        claimed = session.execute(update(RiverSourceCache).where(RiverSourceCache.key == key,
            RiverSourceCache.next_fetch_at <= now, or_(RiverSourceCache.lease_until.is_(None), RiverSourceCache.lease_until <= now)
        ).values(lease_token=token, lease_until=now + timedelta(minutes=2), next_fetch_at=now + timedelta(minutes=10))).rowcount
        session.commit()
    if not claimed:
        return "cached_or_busy"
    try:
        if key == "catalog":
            data, samples = _catalog(fetch(GRAPHQL, {"query": CATALOG_QUERY}))
        elif key == "danger":
            data, samples = _danger_samples(fetch(LINDAS, DANGER_QUERY), now)
        else:
            start = (now - timedelta(hours=48)).replace(second=0, microsecond=0).isoformat()
            end = now.isoformat()
            query = '{ water { observations { data_10min_mean(where:{station:{no:{_eq:' + json.dumps(key) + '}},timestamp:{_gte:' + json.dumps(start) + ',_lt:' + json.dumps(end) + '},parameterName:{_in:["W","Q","WT"]}}) { timestamp parameterName value unitSymbol releaseState } data_live(where:{stationNo:{_eq:' + json.dumps(key) + '}}) { stationNo parameterName timestamp value releaseStatus } } } }'
            data, samples = _live_samples(fetch(GRAPHQL, {"query": query}), key, now)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, InvalidOperation):
        with database.session(include_all_organizations=True) as session:
            row = session.scalar(select(RiverSourceCache).where(RiverSourceCache.key == key, RiverSourceCache.lease_token == token).with_for_update())
            if row:
                row.failures += 1
                row.error = "source_unavailable"
                row.lease_token = row.lease_until = None
                row.next_fetch_at = now + timedelta(minutes=min(360, 10 * 2 ** min(row.failures - 1, 6)))
                session.commit()
        return "source_unavailable"
    with database.session(include_all_organizations=True) as session:
        row = session.scalar(select(RiverSourceCache).where(RiverSourceCache.key == key, RiverSourceCache.lease_token == token).with_for_update())
        if row is None:
            return "lease_lost"
        for sample in samples:
            identity = digest([sample["station_id"], sample["metric"], sample["timestamp"]])
            previous = session.get(RiverMeasurement, identity)
            if previous:
                previous.evidence = sample
            else:
                session.add(RiverMeasurement(id=identity, station_id=sample["station_id"], metric=sample["metric"],
                    measured_at=utc(sample["timestamp"]), evidence=sample))
        row.data, row.fetched_at, row.error, row.failures = data, now, None, 0
        row.lease_until = row.lease_token = None
        row.next_fetch_at = now + (timedelta(days=1) if key == "catalog" else timedelta(minutes=10))
        session.execute(delete(RiverMeasurement).where(RiverMeasurement.measured_at < now - timedelta(days=30)).execution_options(synchronize_session=False))
        session.commit()
    return "updated"


def catalogue(session):
    row = session.get(RiverSourceCache, "catalog")
    return {"stations": (row.data or {}).get("stations", []) if row else [],
            "fetched_at": utc(row.fetched_at).isoformat() if row and row.fetched_at else None,
            "health": row.error if row and row.error else "ready" if row and row.fetched_at else "waiting",
            "source_url": SOURCE_URL, "attribution": "Federal Office for the Environment (FOEN), Hydrological observations"}


def cleanup(database, *, now=None):
    """Retention continues even when every private monitor is paused or removed."""
    now = utc(now or datetime.now(UTC))
    with database.session(include_all_organizations=True) as session:
        removed = session.execute(delete(RiverMeasurement).where(RiverMeasurement.measured_at < now - timedelta(days=30)).execution_options(synchronize_session=False)).rowcount
        session.commit()
    return {"removed_measurements": removed}
