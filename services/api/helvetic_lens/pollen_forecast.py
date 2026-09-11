"""Separate official ICON-CH2 forecast collector and private decoder client.

Forecast points use explicit UTC issue, control member and valid instant. An empty
STAC search is unavailable, not zero and not proof of a particular seasonal cause.
"""

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext

import httpx
from sqlalchemy import select

from .monitoring_live_models import MonitoringSourceArtifact, MonitoringSourceChannel, MonitoringSourceSample
from .pollen_collector import STAC, FetchBudget, _lease, _retain, _utc, download, record_artifact
from .pollen_sources import FORECAST_VARIABLES, sample_channel_hash
from .pollen_thresholds import ForecastSeries, PollenSample, PollenSeries, _hash

SOURCE = "meteoswiss:icon-ch2"
METHOD = "icon-ch2-control-nearest-lowest-layer-v1"
COLLECTION = "https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-forecasting-icon-ch2"
DEFINITIONS_HASH = "45a9168efdf755dfe281cb00c0525e7c39d71cbc82513dbd6a819926c8509a1a"


def _artifact(database, settings, client, asset, identity, now, approval, budget):
    budget.check()
    expected = asset.get("file:checksum")
    digest = expected[4:] if expected and expected.startswith("1220") and len(expected) == 68 else None
    if digest:
        with database.session() as session:
            known = session.get(MonitoringSourceArtifact, digest)
            path = settings.data_dir / "monitoring-public-artifacts" / digest[:2] / digest
            if known and path.is_file():
                body = path.read_bytes()
                if len(body) > 64 * 1024 * 1024 or hashlib.sha256(body).hexdigest() != digest:
                    raise ValueError("Retained model artifact changed")
                record_artifact(session, digest=digest, source_id=SOURCE, identity=identity, body=body,
                    fetched=now, retention_days=approval.retention_days, storage_root=settings.data_dir)
                session.commit()
                return body, digest
    body = download(client, asset["href"], max_bytes=64 * 1024 * 1024, budget=budget)[0]
    actual = hashlib.sha256(body).hexdigest()
    if expected and (digest is None or digest != actual):
        raise ValueError("Model artifact checksum mismatch")
    _retain(settings.data_dir, actual, body)
    with database.session() as session:
        record_artifact(session, digest=actual, source_id=SOURCE, identity=identity, body=body,
            fetched=now, retention_days=approval.retention_days, storage_root=settings.data_dir)
        session.commit()
    return body, actual


def decode_response(value, *, variable, issue, valid, hashes):
    if (type(value.get("protocol")) is not int or value.get("protocol") != 1 or value.get("variable") != variable or value.get("artifact_hashes") != hashes
            or value.get("unit") != "number/m3" or value.get("layer") != "80"
            or datetime.fromisoformat(value["issue_time"]) != issue or datetime.fromisoformat(value["valid_time"]) != valid):
        raise ValueError("Decoder returned different source identity or units")
    runtime = value["runtime"]
    if (runtime.get("eccodes_native") != "2.47.0" or runtime.get("eccodes_python") != "2.47.0"
            or runtime.get("cosmo_release") != "v2.47.0.2" or runtime.get("cosmo_definitions_sha256") != DEFINITIONS_HASH):
        raise ValueError("Unaccepted forecast decoder runtime")
    points = value["points"]
    if not 1 <= len(points) <= 100 or len({p["station_id"] for p in points}) != len(points):
        raise ValueError("Invalid decoder station result")
    for point in points:
        if point["availability"] not in {"usable", "outside_grid"}:
            raise ValueError("Unknown decoder availability")
        if point["availability"] != "usable":
            continue
        if any(not isinstance(point[key], str) for key in ("number_per_kg", "density_kg_m3", "value")):
            raise ValueError("Decoder quantities must preserve decimal text")
        try:
            number, density, concentration = (Decimal(point[key]) for key in ("number_per_kg", "density_kg_m3", "value"))
        except InvalidOperation as error:
            raise ValueError("Invalid decoder decimal text") from error
        if not all(v.is_finite() for v in (number, density, concentration)) or number < 0 or density <= 0:
            raise ValueError("Invalid model concentration/density")
        with localcontext() as context:
            context.prec = 80
            if number * density != concentration:
                raise ValueError("Model unit conversion differs from evidence")
        if not 0 <= point["mapping_distance_km"] <= 5 or type(point["grid_cell"]) is not int or point["grid_cell"] < 0:
            raise ValueError("Invalid station-to-grid mapping")
    return points


def collect_point(database, settings, *, approval, allergen, issue, valid, now, client=None, decoder_client=None, checkpoint=lambda: None):
    now, issue, valid = _utc(now), _utc(issue), _utc(valid)
    lead = int((valid - issue).total_seconds() / 3600)
    if (not settings.pollen_decoder_url or approval.status != "approved" or approval.source_id != SOURCE
            or approval.method_version != METHOD or approval.period != "forecast_instant" or allergen not in approval.allergens
            or not approval.valid_from <= now < approval.valid_until or allergen not in FORECAST_VARIABLES
            or issue > now or not 1 <= lead <= 120 or issue + timedelta(hours=lead) != valid):
        return {"status": "source_not_approved"}
    variable = FORECAST_VARIABLES[allergen]
    key = _hash({"source": SOURCE, "policy": approval.version, "variable": variable, "issue": issue, "valid": valid})
    token = _lease(database, key, now)
    if token is None:
        with database.session() as session:
            channel = session.get(MonitoringSourceChannel, key)
            return {"status": "cached_or_collecting", "source_error": channel.error_code if channel else None}
    owns_client, owns_decoder = client is None, decoder_client is None
    budget = FetchBudget(checkpoint)
    client = client or httpx.Client(timeout=httpx.Timeout(45, connect=10), trust_env=False)
    decoder_client = decoder_client or httpx.Client(timeout=90, trust_env=False)
    try:
        artifacts, hashes = {}, {}
        observation_collection = json.loads(download(client, STAC, max_bytes=1024 * 1024, budget=budget)[0])
        body, digest = _artifact(database, settings, client, observation_collection["assets"]["ogd-pollen_meta_stations.csv"],
                                  STAC + "#asset=ogd-pollen_meta_stations.csv", now, approval, budget)
        artifacts["stations.csv"] = {"sha256": digest, "base64": base64.b64encode(body).decode()}
        hashes["stations.csv"] = digest
        model_assets = json.loads(download(client, COLLECTION + "/assets", max_bytes=1024 * 1024, budget=budget)[0])["assets"]
        grid_name = "horizontal_constants_icon-ch2-eps.grib2"
        grids = [asset for asset in model_assets if asset["id"] == grid_name]
        if len(grids) != 1:
            raise ValueError("Ambiguous model grid asset")
        body, digest = _artifact(database, settings, client, grids[0], COLLECTION + "/assets/" + grid_name, now, approval, budget)
        artifacts[grid_name] = {"sha256": digest, "base64": base64.b64encode(body).decode()}
        hashes[grid_name] = digest
        for parameter in (variable, "DEN"):
            query = {"collections": [COLLECTION.rsplit("/", 1)[1]], "forecast:reference_datetime": issue.isoformat(),
                     "forecast:variable": parameter, "forecast:perturbed": False, "forecast:horizon": f"P0DT{lead:02d}H00M00S"}
            result = json.loads(download(client, "https://data.geo.admin.ch/api/stac/v1/search", payload=query, max_bytes=1024 * 1024, budget=budget)[0])
            items = result["features"]
            if len(items) != 1 or len(items[0]["assets"]) != 1:
                raise ValueError("No unique requested model point")
            item = items[0]
            props = item["properties"]
            if (props["forecast:perturbed"] is not False or props["forecast:variable"] != parameter
                    or datetime.fromisoformat(props["forecast:reference_datetime"]) != issue
                    or datetime.fromisoformat(props["datetime"]) != valid):
                raise ValueError("STAC model point differs from request")
            body, digest = _artifact(database, settings, client, next(iter(item["assets"].values())),
                                    COLLECTION + "/items/" + item["id"], now, approval, budget)
            name = f"{parameter}.grib2"
            artifacts[name] = {"sha256": digest, "base64": base64.b64encode(body).decode()}
            hashes[name] = digest
        with decoder_client.stream("POST", settings.pollen_decoder_url + "/decode", timeout=budget.check(),
            json={"protocol": 1, "variable": variable, "issue_time": issue.isoformat(), "lead_hours": lead, "artifacts": artifacts}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                budget.check()
                size += len(chunk)
                if size > 256 * 1024:
                    raise ValueError("Decoder result exceeds bound")
                chunks.append(chunk)
            decoded = json.loads(b"".join(chunks))
        points = decode_response(decoded, variable=variable, issue=issue, valid=valid, hashes=hashes)
        fetched = datetime.now(UTC)
        if not approval.valid_from <= fetched < approval.valid_until:
            raise ValueError("Forecast source approval expired during retrieval")
        with database.session() as session:
            channel = session.scalar(select(MonitoringSourceChannel).where(MonitoringSourceChannel.id == key).with_for_update())
            if channel.lease_token != token or _utc(channel.lease_until) <= fetched:
                return {"status": "lease_expired"}
            written = 0
            for point in points:
                if point["station_id"] not in approval.stations or point["availability"] != "usable":
                    continue
                series = PollenSeries(source_id=SOURCE, method_version=METHOD, station_id=point["station_id"],
                    allergen=allergen, period="forecast_instant", forecast=ForecastSeries(model="ICON-CH2", grid=decoded["grid"],
                    member="control", layer="80", cell=point["grid_cell"], issue_at=issue))
                series_hash = _hash(series.model_dump())
                content = _hash({"value": point["value"], "artifacts": hashes, "mapping": point})
                previous = session.scalar(select(MonitoringSourceSample).where(MonitoringSourceSample.series_hash == series_hash,
                    MonitoringSourceSample.valid_at == valid).order_by(MonitoringSourceSample.revision.desc()).limit(1))
                if previous and previous.content_hash == content:
                    continue
                revision = previous.revision + 1 if previous else 1
                sample = PollenSample(series=series, valid_at=valid, source_revision=revision, value=point["value"],
                    quality="usable", rights="approved", policy_version=approval.version, parser_version="icon-ch2-eccodes247-v1",
                    artifact_hashes=tuple(sorted(set(hashes.values()))), fetched_at=fetched,
                    fresh_until=issue + timedelta(seconds=approval.freshness_seconds))
                session.add(MonitoringSourceSample(channel_hash=sample_channel_hash(series), series_hash=series_hash,
                    valid_at=valid, revision=revision, retention_until=fetched + timedelta(days=approval.retention_days),
                    content_hash=content, sample_json=sample.model_dump(mode="json"), provenance_json={
                        "conversion": point, "decoder": decoded["runtime"], "artifact_names": hashes,
                        "source_review_sha256": approval.review_sha256}))
                written += 1
            channel.last_success_at, channel.error_code, channel.failures = fetched, None, 0
            channel.lease_token = channel.lease_until = None
            channel.next_fetch_at = fetched + timedelta(seconds=approval.poll_seconds)
            session.commit()
        return {"status": "collected", "new_revisions": written}
    except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError):
        with database.session() as session:
            channel = session.scalar(select(MonitoringSourceChannel).where(MonitoringSourceChannel.id == key).with_for_update())
            if channel and channel.lease_token == token:
                channel.failures = min(channel.failures + 1, 16)
                channel.error_code = "forecast_unavailable"
                channel.lease_token = channel.lease_until = None
                channel.next_fetch_at = now + timedelta(seconds=min(86400, approval.poll_seconds * 2 ** channel.failures))
                session.commit()
        return {"status": "forecast_unavailable"}
    finally:
        if owns_client:
            client.close()
        if owns_decoder:
            decoder_client.close()
