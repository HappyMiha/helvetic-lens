"""Synthetic transport/scale diagnostics; these cannot approve production sources."""

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select
from test_monitoring_subjects import db as db
from test_pollen_thresholds import NOW, SERIES, sample

from helvetic_lens.config import Settings
from helvetic_lens.monitoring_live_models import MonitoringSourceArtifact, MonitoringSourceSample
from helvetic_lens.pollen_categories import CategoryScale, evaluate_category
from helvetic_lens.pollen_collector import FetchBudget, collect_hourly, download
from helvetic_lens.pollen_sources import HOURLY_PARAMETERS, ChannelApproval, decode_daily, decode_hourly


def csv_body(values=None, suffix="h0", date="11.09.2026 06:00", station="PBS"):
    parameters = [p[:-2] + suffix for p in HOURLY_PARAMETERS.values()]
    values = values or ["0", "1.25", "", "2", "3", "4", "5"]
    return (";".join(["station_abbr", "reference_timestamp", *parameters]) + "\n"
        + ";".join([station, date, *values]) + "\n").encode("cp1252")


def approval(now):
    return ChannelApproval(version="synthetic-review-v1", review_sha256="a" * 64,
        source_id="meteoswiss:ogd-pollen", method_version="meteoswiss-automatic-hourly-v1", period="observation_hourly",
        stations=("PBS",), allergens=("birch", "grasses"), status="approved", valid_from=now - timedelta(days=2),
        valid_until=now + timedelta(days=2), freshness_seconds=10800, poll_seconds=1200, retention_days=30)


def test_hourly_decimal_zero_missing_and_identity_are_distinct():
    rows = decode_hourly(csv_body(), station_id="PBS", fetched_at=NOW)
    values = {row.series.allergen: row.value for row in rows}
    assert values["birch"] == Decimal("1.25") and values["hazel"] is None and values["alder"] == 0
    assert all(row.valid_at == NOW - timedelta(hours=2) for row in rows)
    parsed = next(row for row in rows if row.series.allergen == "birch")
    point = parsed.sample(revision=1, fetched_at=NOW, approval=approval(NOW))
    assert point.fresh_until == NOW + timedelta(hours=1)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "NA", " 1", "1e3", "1,5"])
def test_unsupported_source_number_fails_entire_artifact(value):
    with pytest.raises(ValueError):
        decode_hourly(csv_body([value] * 7), station_id="PBS", fetched_at=NOW)


@pytest.mark.parametrize("period,suffix,hours", [("observation_daily_00_24_utc", "d1", 24), ("observation_daily_06_06_utc", "d0", 30)])
def test_daily_interval_end_uses_official_parameter_mapping(period, suffix, hours):
    body = csv_body(suffix=suffix, date="10.09.2026 00:00")
    end = datetime(2026, 9, 10, tzinfo=UTC) + timedelta(hours=hours)
    rows = decode_daily(body, station_id="PBS", fetched_at=NOW, period=period)
    assert all(row.valid_at == end for row in rows)
    with pytest.raises(ValueError):
        decode_daily(body, station_id="PBS", fetched_at=end - timedelta(seconds=1), period=period)


def test_wrong_station_duplicate_and_future_hour_fail_closed():
    body = csv_body()
    for invalid in (csv_body(station="PZH"), body + body.splitlines(keepends=True)[1], csv_body(date="12.09.2026 06:00")):
        with pytest.raises(ValueError):
            decode_hourly(invalid, station_id="PBS", fetched_at=NOW)


def test_download_bounds_checksums_redirects_and_deadline():
    for response in (httpx.Response(302, headers={"location": "http://127.0.0.1/private"}),
        httpx.Response(200, content=b"12345"), httpx.Response(200, content=b"1", headers={"x-amz-meta-sha256": "0" * 64})):
        with httpx.Client(transport=httpx.MockTransport(lambda request: response)) as client:
            with pytest.raises(ValueError):
                download(client, "https://data.geo.admin.ch/test", max_bytes=4)
    budget = FetchBudget(seconds=-1)
    with pytest.raises(ValueError):
        budget.check()


def test_collector_shared_cache_correction_and_failure_preserve_public_rows(db, tmp_path):
    now = datetime.now(UTC)
    stamp = now.replace(minute=0, second=0, microsecond=0).strftime("%d.%m.%Y %H:%M")
    body = csv_body(date=stamp)
    settings = Settings(_env_file=None, data_dir=tmp_path)
    calls = []
    def handler(request):
        calls.append(str(request.url))
        if request.url.path.endswith("/items/pbs"):
            return httpx.Response(200, json={"id": "pbs", "assets": {"ogd-pollen_pbs_h_now.csv": {
                "href": "https://data.geo.admin.ch/source.csv", "file:checksum": "1220" + hashlib.sha256(body).hexdigest()}}})
        return httpx.Response(200, content=body)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        args = dict(station_id="PBS", approval=approval(now), now=now, client=client)
        assert collect_hourly(db, settings, **args) == {"status": "collected", "new_revisions": 2}
        assert collect_hourly(db, settings, **args)["status"] == "cached_or_collecting"
        assert len(calls) == 2
        from helvetic_lens.monitoring_live_models import MonitoringSourceChannel
        def release():
            with db.session() as session:
                channel = session.scalar(select(MonitoringSourceChannel))
                channel.next_fetch_at = now
                session.commit()
        release()
        assert collect_hourly(db, settings, **args)["new_revisions"] == 0
        body = csv_body(["0", "2.25", "", "2", "3", "4", "5"], date=stamp)
        release()
        assert collect_hourly(db, settings, **args)["new_revisions"] == 1
        body = csv_body(["broken"] * 7, date=stamp)
        release()
        assert collect_hourly(db, settings, **args)["status"] == "official_source_unavailable"
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(MonitoringSourceSample)) == 3
        assert session.scalar(select(func.count()).select_from(MonitoringSourceArtifact)) == 2
        assert session.scalar(select(MonitoringSourceChannel)).error_code == "official_source_unavailable"


def scale(**updates):
    return CategoryScale.model_validate({"version": "synthetic-scale-v1", "review_sha256": "b" * 64,
        "source_id": SERIES.source_id, "method_version": SERIES.method_version, "allergen": SERIES.allergen,
        "period": SERIES.period, "status": "approved", "bands": [{"id": "low", "at_or_above": "0"},
        {"id": "high", "at_or_above": "10"}], **updates})


def test_category_boundary_revision_recovery_and_scale_change_rebaseline():
    first = evaluate_category(scale(), sample("0"), now=NOW, prior=None)
    second = evaluate_category(scale(), sample("10", 1), now=NOW + timedelta(hours=1), prior=first["state"])
    assert second["changed"] and second["previous"] == "low" and second["current"] == "high"
    correction = evaluate_category(scale(), sample("0", 1, source_revision=2), now=NOW + timedelta(hours=1), prior=second["state"])
    assert not correction["changed"] and correction["disposition"] == "revision"
    missing = evaluate_category(scale(), sample(None, 2, quality="missing"), now=NOW + timedelta(hours=2), prior=correction["state"])
    assert missing["state"]["category"] == "low" and missing["current"] is None
    recovered = evaluate_category(scale(), sample("30", 3), now=NOW + timedelta(hours=3), prior=missing["state"])
    assert not recovered["changed"] and recovered["disposition"] == "recovered"
    changed_scale = evaluate_category(scale(version="synthetic-v2"), sample("0", 4), now=NOW + timedelta(hours=4), prior=recovered["state"])
    assert not changed_scale["changed"] and changed_scale["disposition"] == "revision"
