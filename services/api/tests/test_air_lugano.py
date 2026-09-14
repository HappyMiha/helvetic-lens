"""Lugano official CSV, independent rights, private lifecycle and delivery regression."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from test_air_watch import api as _api_fixture
from test_air_watch import changes, command, configuration, create, run
from test_auth import _csrf
from test_tender_repository import db as _db_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import air_delivery, air_email_preferences, air_nabel, air_runtime, air_sources
from helvetic_lens.air_models import AirMeasurement, AirMonitor, AirReadingVersion, AirSourceCache
from helvetic_lens.config import DomainError
from helvetic_lens.models import User

api, db, template = _api_fixture, _db_fixture, _template_fixture
BASE = "/api/air-watch"


def metadata():
    return {
        "success": True,
        "result": {
            "name": air_nabel.PACKAGE,
            "state": "active",
            "organization": {"name": "bundesamt-fur-umwelt-bafu"},
            "resources": [
                {
                    "id": air_nabel.RESOURCE_ID,
                    "state": "active",
                    "url": air_nabel.SOURCE_URL,
                    "rights": air_nabel.LICENSE,
                    "license": air_nabel.LICENSE,
                }
            ],
        },
    }


def csv_body(now, value="40", count=30):
    header = [
        "Station: Lugano-Università",
        "Stadt",
        "Stundenmittelwerte",
        "MEZ/CET",
        "Quelle: NABEL",
        "Die Messwerte des laufenden Jahres sind vorläufig und noch nicht abschliessend geprüft.",
        "Datum/Zeit;O3 [ug/m3];NO2 [ug/m3];PM10 [ug/m3];PM2.5 [ug/m3]",
    ]
    rows = [
        f"{(now - timedelta(hours=i)).astimezone(air_nabel.CET):%d.%m.%Y %H:%M};{value};7.7;6.7;3.3"
        for i in reversed(range(count))
    ]
    return ("\n".join(header + rows) + "\n").encode("latin-1")


def feed(database, now, value="40", body=None):
    with database.session(include_all_organizations=True) as session:
        session.execute(
            update(AirSourceCache)
            .where(AirSourceCache.key.in_(["catalog:LUG", "LUG"]))
            .values(next_fetch_at=now - timedelta(seconds=1))
        )
        session.commit()
    assert air_sources.collect(database, "catalog:LUG", now=now, fetch_nabel_metadata=metadata) == "updated"
    assert (
        air_sources.collect(
            database,
            "LUG",
            now=now,
            fetch_nabel_csv=lambda _: body if body is not None else csv_body(now, value),
        )
        == "updated"
    )


@pytest.mark.parametrize(
    "at",
    [
        datetime(2026, 3, 29, 1, tzinfo=UTC),
        datetime(2026, 9, 14, 0, tzinfo=UTC),
        datetime(2026, 10, 25, 1, tzinfo=UTC),
    ],
)
def test_declared_fixed_cet_across_summer_and_dst(at):
    samples = air_nabel.parse(csv_body(at), at)
    assert len(samples) == 120
    assert samples[-4]["timestamp"] == at.isoformat()
    assert samples[-4]["source_time_label"] == (at + timedelta(hours=1)).strftime("%d.%m.%Y %H:%M")
    assert samples[-4]["source"] == air_nabel.ATTRIBUTION
    assert samples[-4]["license_url"] != air_sources.LICENSE


@pytest.mark.parametrize(
    "old,new",
    [
        (b"Lugano-Universit\xe0", b"Basel-Binningen"),
        (b"MEZ/CET", b"CEST"),
        (b"PM10 [ug/m3]", b"PM10 [mg/m3]"),
        (b";40;", b";NaN;"),
        (b";40;", b";1,2;"),
        (b"Stundenmittelwerte", b"Tagesmittelwerte"),
    ],
)
def test_reject_changed_station_unit_period_clock_and_numbers(old, new):
    now = datetime(2026, 9, 14, tzinfo=UTC)
    with pytest.raises(ValueError):
        air_nabel.parse(csv_body(now).replace(old, new), now)


def test_zero_missing_invalid_and_future_placeholders():
    now = datetime(2026, 9, 14, tzinfo=UTC)
    body = csv_body(now, count=1).replace(b";40;7.7;6.7;3.3", b";0;;-1;3.3")
    body += b"14.09.2026 02:00;;;;\n"
    samples = air_nabel.parse(body, now)
    assert [(s["value"], s["quality"]) for s in samples] == [
        ("0", "provisional"),
        (None, "missing"),
        (None, "invalid"),
        ("3.3", "provisional"),
    ]
    with pytest.raises(ValueError):
        air_nabel.parse(body.replace(b"02:00;;;;", b"02:00;1;;;"), now)
    with pytest.raises(ValueError):
        air_nabel.parse(body + body.splitlines()[7] + b"\n", now)


@pytest.mark.parametrize(
    "field,value",
    [
        ("rights", "restricted"),
        ("license", "restricted"),
        ("url", "https://map.geo.admin.ch/"),
        ("id", "geometry-resource"),
        ("state", "deleted"),
    ],
)
def test_exact_data_query_resource_grant_required(field, value):
    raw = metadata()
    raw["result"]["resources"][0][field] = value
    with pytest.raises(ValueError):
        air_nabel.validate_metadata(raw)


@pytest.mark.parametrize("raw", [None, [], "html", {"success": False}])
def test_malformed_catalogue_response_fails_closed(raw):
    with pytest.raises(ValueError):
        air_nabel.validate_metadata(raw)


def test_bounded_real_request_shape(monkeypatch):
    captured = []

    def capture(url, data=None):
        captured.append((url, data))
        return b"csv"

    monkeypatch.setattr(air_nabel, "request", capture)
    air_nabel.request_csv(datetime(2026, 9, 14, 23, tzinfo=UTC))
    url, data = captured[0]
    assert url == air_nabel.CSV_URL
    assert data["von"] == "2026-09-11" and data["bis"] == "2026-09-15"
    assert data["station"] == "3" and data["datentyp"] == "stunden"
    assert data["schadstoffsliste[]"] == ["1", "2", "6", "7"]


@pytest.mark.parametrize("mode", ["redirect", "oversize"])
def test_http_boundary_rejects_redirects_and_oversized_bodies(monkeypatch, mode):
    import httpx

    real_client = httpx.Client
    calls = []

    def respond(request):
        calls.append(str(request.url))
        if mode == "redirect":
            return httpx.Response(302, headers={"Location": "https://example.invalid/"})
        return httpx.Response(200, content=b"x" * (air_nabel.MAX_BYTES + 1))

    monkeypatch.setattr(
        air_nabel.httpx,
        "Client",
        lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(respond)),
    )
    with pytest.raises((httpx.HTTPStatusError, ValueError)):
        air_nabel.request_metadata()
    assert calls == [air_nabel.METADATA_URL]


def test_lugano_worker_uses_own_source_keys(api, monkeypatch):
    from helvetic_lens import air_jobs

    client, service, settings, _, now = api
    feed(service.db, now)
    row = command(client, create(client, configuration(station_id="LUG")), "start")
    keys = []
    monkeypatch.setattr(air_jobs, "collect", lambda database, key, **kwargs: keys.append(key))
    air_jobs.refresh(service.db, settings, monitor_id=row["id"], version=row["version"], now=now)
    assert keys == ["catalog:LUG", "LUG", "daily:LUG"]
    with service.db.session() as session:
        monitor = session.get(AirMonitor, row["id"])
        assert monitor.state["coverage"]["O3:hourly_mean"]["sample"]["station_id"] == "LUG"


def test_lugano_private_lifecycle_today_correction_withdrawal_and_basel_isolation(api):
    client, service, _, _, now = api
    feed(service.db, now)
    assert {s["id"] for s in client.get(BASE + "/stations").json()["stations"]} == {"BAS", "LUG"}
    config = configuration(station_id="LUG", name="Lugano air")
    preview = client.post(BASE + "/preview", json={"configuration": config}, headers=_csrf(client)).json()
    assert preview["station"]["id"] == "LUG" and preview["start_available"]
    row = command(client, create(client, config), "start")
    run(service, row, now)
    feed(service.db, now + timedelta(hours=1), "60")
    run(service, row, now + timedelta(hours=1))
    event = changes(client, row)[0]
    assert event["evidence"]["sample"]["station_id"] == "LUG"
    assert client.get(BASE + "/today").json()["items"][0]["monitor_name"] == "Lugano air"
    feed(service.db, now + timedelta(hours=1), "44")
    run(service, row, now + timedelta(hours=1))
    assert changes(client, row)[0]["kind"] == "threshold_cleared"
    with service.db.session() as session:
        versions = list(
            session.scalars(select(AirReadingVersion).where(AirReadingVersion.station_id == "LUG"))
        )
        assert any(v.evidence["corrected"] for v in versions)
        assert all(
            r.evidence["source_url"] == air_sources.SOURCE_URL
            for r in session.scalars(select(AirMeasurement).where(AirMeasurement.station_id == "BAS"))
        )
        complete = air_runtime.series(air_runtime.samples(session, "LUG"), "PM25", "rolling_24h_mean")
        assert complete[-1]["value"] == "3.3000"
    body = csv_body(now + timedelta(hours=1), "44").splitlines()
    body[-1] = body[-1].split(b";")[0] + b";;;;"
    feed(service.db, now + timedelta(hours=1), body=b"\n".join(body))
    preview = client.post(BASE + "/preview", json={"configuration": config}, headers=_csrf(client)).json()
    assert not preview["start_available"]
    assert all(c["status"] == "unknown" for c in preview["coverage"].values())
    row = command(client, row, "pause")
    row = command(client, row, "archive")
    assert row["status"] == "archived"


def test_lugano_contract_failure_is_independent_and_cannot_be_bypassed(api):
    client, service, _, _, now = api
    feed(service.db, now)
    with service.db.session() as session:
        session.get(AirSourceCache, "catalog:LUG").error = "source_unavailable"
        session.get(AirSourceCache, "LUG").next_fetch_at = now
        session.commit()
    assert (
        air_sources.collect(
            service.db, "LUG", now=now, fetch_nabel_csv=lambda _: pytest.fail("unlicensed request")
        )
        == "source_unavailable"
    )
    catalog = client.get(BASE + "/stations").json()
    assert [s["id"] for s in catalog["stations"]] == ["BAS"]
    assert catalog["unsupported"][0]["area"] == "Lugano"
    response = client.post(
        BASE + "/preview", json={"configuration": configuration(station_id="LUG")}, headers=_csrf(client)
    )
    assert response.status_code == 422


@pytest.mark.parametrize("revoke", [False, True])
def test_lugano_consent_delivery_rechecks_own_catalogue_and_private_owner(db, revoke):
    from test_air_delivery import SETTINGS
    from test_tender_delivery import Mailer

    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
    feed(db, now)
    with db.session() as session:
        session.get(User, "owner").email_verified_at = now
        row = air_runtime.create(session, "owner", configuration(station_id="LUG"), str(uuid4()))
        identifier = row["id"]
        session.commit()
    with db.session() as session:
        row = air_email_preferences.configure(
            session,
            "owner",
            identifier,
            expected_version=1,
            configuration={"delivery": {"email": "immediate"}},
            consent=True,
            now=now,
        )
        session.commit()
    with db.session() as session:
        monitor = session.get(AirMonitor, identifier)
        air_runtime.command(session, "owner", identifier, monitor.version, "start", now)
        air_runtime.evaluate(session, monitor, now)
        session.commit()
    at = now + timedelta(hours=1)
    feed(db, at, "60")
    with db.session() as session:
        air_runtime.evaluate(session, session.get(AirMonitor, identifier), at)
        session.commit()
        with pytest.raises(DomainError):
            air_runtime.owned(session, "peer", identifier)
    fake = Mailer()
    with db.session() as session:
        monitor = session.get(AirMonitor, identifier)
        revision = monitor.email_revision

    def revoke_contract():
        if revoke:
            with db.session() as session:
                session.get(AirSourceCache, "catalog:LUG").error = "source_unavailable"
                session.commit()

    result = air_delivery.deliver(
        db,
        SETTINGS,
        monitor_id=identifier,
        consent_revision=revision,
        mailer=fake,
        now=at,
        before_send=revoke_contract,
    )
    if revoke:
        assert not fake.calls
        assert result["status"] != "sent"
        return
    assert result == {"status": "sent", "changes": 1}
    assert len(fake.calls) == 1 and identifier in fake.calls[0][0][2]
    assert "µg" not in fake.calls[0][0][2]
