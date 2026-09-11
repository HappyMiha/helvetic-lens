"""Native retained-result validation and synthetic bounded collector transport."""

import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from test_monitoring_subjects import db as db

from helvetic_lens.config import Settings
from helvetic_lens.monitoring_live_models import MonitoringSourceSample
from helvetic_lens.pollen_forecast import DEFINITIONS_HASH, METHOD, SOURCE, collect_point, decode_response
from helvetic_lens.pollen_sources import ChannelApproval


def retained():
    return json.loads((Path(__file__).resolve().parents[3] / "docs/monitoring-v2/evidence/mv2-031-decoder-rpc-proof.json").read_text())


def validate(value):
    return decode_response(value, variable="AMBRsnc", issue=datetime(2026, 9, 11, tzinfo=UTC),
        valid=datetime(2026, 9, 11, 6, tzinfo=UTC), hashes=retained()["artifact_hashes"])


def test_retained_native_result_has_exact_conversion_and_fifteen_public_stations():
    points = validate(retained())
    assert len(points) == 15
    assert next(p for p in points if p["station_id"] == "PBS")["value"] == "0.9813446439802646875"


@pytest.mark.parametrize("change", [
    lambda r: r.update(unit="number/kg"), lambda r: r.update(variable="BETUsnc"),
    lambda r: r.update(layer="79"), lambda r: r.update(issue_time="2026-09-10T00:00:00Z"),
    lambda r: r["runtime"].update(cosmo_definitions_sha256="0" * 64),
    lambda r: r["runtime"].update(eccodes_native="2.46.0"), lambda r: r["artifact_hashes"].update({"DEN.grib2": "0" * 64}),
    lambda r: r["points"][0].update(value="123"), lambda r: r["points"][0].update(density_kg_m3="NaN"),
    lambda r: r["points"][0].update(value="not-a-decimal"),
    lambda r: r["points"][0].update(mapping_distance_km=6), lambda r: r["points"][0].update(grid_cell=True),
    lambda r: r["points"].append(copy.deepcopy(r["points"][0])),
])
def test_untrusted_decoder_identity_units_mapping_and_runtime_fail_closed(change):
    value = retained()
    change(value)
    with pytest.raises(ValueError):
        validate(value)


def test_forecast_transport_keeps_issue_series_provenance_and_shared_cache(db, tmp_path):
    now = datetime.now(UTC)
    issue = now.replace(hour=0, minute=0, second=0, microsecond=0)
    valid = issue + timedelta(hours=30)
    review = ChannelApproval(version="synthetic-forecast-review", review_sha256="f" * 64, source_id=SOURCE,
        method_version=METHOD, period="forecast_instant", stations=("PBS",), allergens=("ragweed",), status="approved",
        valid_from=now - timedelta(days=1), valid_until=now + timedelta(days=1), freshness_seconds=172800,
        poll_seconds=1200, retention_days=30)
    settings = Settings(_env_file=None, data_dir=tmp_path, pollen_decoder_url="http://pollen-decoder:8093")
    artifacts = {name: ("synthetic-bytes:" + name).encode() for name in ["stations.csv", "horizontal_constants_icon-ch2-eps.grib2", "AMBRsnc.grib2", "DEN.grib2"]}
    def asset(name):
        return {"id": name, "href": "https://data.geo.admin.ch/files/" + name, "file:checksum": "1220" + hashlib.sha256(artifacts[name]).hexdigest()}
    requests = []
    def source(request):
        requests.append(str(request.url))
        path = request.url.path
        if path.endswith("ogd-pollen"):
            return httpx.Response(200, json={"assets": {"ogd-pollen_meta_stations.csv": asset("stations.csv")}})
        if path.endswith("/assets"):
            return httpx.Response(200, json={"assets": [asset("horizontal_constants_icon-ch2-eps.grib2")]})
        if path.endswith("/search"):
            parameter = json.loads(request.content)["forecast:variable"]
            return httpx.Response(200, json={"features": [{"id": "synthetic-" + parameter,
                "properties": {"forecast:perturbed": False, "forecast:variable": parameter,
                    "forecast:reference_datetime": issue.isoformat(), "datetime": valid.isoformat()},
                "assets": {parameter: asset(parameter + ".grib2")}}]})
        return httpx.Response(200, content=artifacts[path.rsplit("/", 1)[1]])
    def decoder(request):
        body = json.loads(request.content)
        assert body["lead_hours"] == 30 and body["issue_time"] == issue.isoformat()
        return httpx.Response(200, json={"protocol": 1, "variable": "AMBRsnc", "issue_time": issue.isoformat(),
            "valid_time": valid.isoformat(), "grid": "synthetic-grid", "layer": "80", "unit": "number/m3",
            "artifact_hashes": {key: value["sha256"] for key, value in body["artifacts"].items()},
            "runtime": {"eccodes_native": "2.47.0", "eccodes_python": "2.47.0", "cosmo_release": "v2.47.0.2", "cosmo_definitions_sha256": DEFINITIONS_HASH},
            "points": [{"station_id": "PBS", "availability": "usable", "grid_cell": 1, "mapping_distance_km": 1.2,
                "number_per_kg": "0.5", "density_kg_m3": "1.25", "value": "0.625"}]})
    with httpx.Client(transport=httpx.MockTransport(source)) as client, httpx.Client(transport=httpx.MockTransport(decoder)) as decoder_client:
        args = dict(approval=review, allergen="ragweed", issue=issue, valid=valid, now=now, client=client, decoder_client=decoder_client)
        assert collect_point(db, settings, **args) == {"status": "collected", "new_revisions": 1}
        previous_requests = len(requests)
        assert collect_point(db, settings, **args)["status"] == "cached_or_collecting"
        assert len(requests) == previous_requests
    with db.session() as session:
        row = session.scalar(select(MonitoringSourceSample))
        assert row.sample_json["series"]["forecast"]["issue_at"] == issue.isoformat().replace("+00:00", "Z")
        assert row.sample_json["value"] == "0.625"
        assert row.provenance_json["conversion"]["density_kg_m3"] == "1.25"
