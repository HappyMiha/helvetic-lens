"""Official daily periods across acquisition, private history, rules and final email."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select, update
from test_air_lugano import metadata
from test_air_watch import api as _api_fixture
from test_air_watch import changes, command, configuration, create, run
from test_auth import _csrf
from test_tender_repository import db as _db_fixture
from test_tender_repository import template as _template_fixture

from helvetic_lens import air_daily, air_delivery, air_email_preferences, air_runtime, air_sources
from helvetic_lens.air_contracts import DAILY_PERIODS, AirConfiguration
from helvetic_lens.air_models import AirMeasurement, AirMonitor, AirReadingVersion, AirSourceCache
from helvetic_lens.air_nabel import CET
from helvetic_lens.models import User

api, db, template = _api_fixture, _db_fixture, _template_fixture
BASE = "/api/air-watch"


def csv_body(station, now, ozone="40", count=4):
    _, name, area = air_daily.STATIONS[station]
    headers = [
        f"Station: {name}",
        area,
        "Tagesmittelwerte, O3: Maximales Stundenmittel des Tages",
        "Quelle: NABEL",
        "Die Messwerte des laufenden Jahres sind vorläufig und noch nicht abschliessend geprüft.",
        "Datum/Zeit;O3 [ug/m3];NO2 [ug/m3];PM10 [ug/m3];PM2.5 [ug/m3]",
    ]
    today = now.astimezone(CET).date()
    rows = [
        f"{today - timedelta(days=i):%d.%m.%Y};{ozone};7.7;6.7;3.3" for i in reversed(range(1, count + 1))
    ]
    return ("\n".join(headers + rows) + "\n").encode("latin-1")


def feed(db, station, now, ozone="40", body=None):
    with db.session(include_all_organizations=True) as session:
        session.execute(
            update(AirSourceCache)
            .where(AirSourceCache.key.in_(["catalog:LUG", f"daily:{station}"]))
            .values(next_fetch_at=now - timedelta(seconds=1))
        )
        session.commit()
    assert air_sources.collect(db, "catalog:LUG", now=now, fetch_nabel_metadata=metadata) == "updated"
    assert (
        air_sources.collect(
            db,
            f"daily:{station}",
            now=now,
            fetch_daily_csv=lambda selected, at: body if body is not None else csv_body(selected, at, ozone),
        )
        == "updated"
    )


def config(station="BAS", metric="O3"):
    result = configuration(station_id=station)
    result["rules"][0].update(metric=metric, period=DAILY_PERIODS[metric])
    return result


@pytest.mark.parametrize("station", ["BAS", "LUG"])
def test_native_statistic_and_calendar_date_not_hourly_or_rolling(station):
    now = datetime(2026, 9, 14, 7, tzinfo=UTC)
    rows = air_daily.parse(csv_body(station, now), station, now)
    assert len(rows) == 16
    assert rows[-4]["period"] == "daily_max_hourly" and rows[-4]["source_date"] == "2026-09-13"
    assert rows[-4]["timestamp_kind"] == "calendar_date_sort_key"
    assert [r["period"] for r in rows[-3:]] == ["daily_mean"] * 3
    assert not air_runtime.series(rows, "O3", "hourly_mean")
    assert not air_runtime.series(rows, "O3", "rolling_24h_mean")
    assert len(air_runtime.series(rows, "O3", "daily_max_hourly")) == 4
    assert air_runtime.fresh(rows[-4], now)
    assert not air_runtime.fresh(rows[-4], now + timedelta(days=1))


@pytest.mark.parametrize(
    "metric,period", [("O3", "daily_mean"), ("PM25", "daily_max_hourly"), ("NO2", "daily_max_hourly")]
)
def test_daily_rules_reject_different_statistic(metric, period):
    raw = config(metric=metric)
    raw["rules"][0]["period"] = period
    with pytest.raises(ValidationError):
        AirConfiguration.model_validate(raw)


@pytest.mark.parametrize(
    "old,new",
    [
        (b"Stadt", b"Vorst\xe4dtisch"),
        (b"Maximales Stundenmittel", b"Mittelwert"),
        (b"PM10 [ug/m3]", b"PM10 [mg/m3]"),
        (b";40;", b";NaN;"),
        (b"13.09.2026", b"31.09.2026"),
    ],
)
def test_schema_clock_unit_and_non_numeric_drift_fail_closed(old, new):
    now = datetime(2026, 9, 14, 7, tzinfo=UTC)
    with pytest.raises(ValueError):
        air_daily.parse(csv_body("LUG", now).replace(old, new), "LUG", now)


def test_unfinished_day_missing_and_zero_are_distinct():
    now = datetime(2026, 9, 14, 7, tzinfo=UTC)
    body = csv_body("LUG", now, count=1).replace(b";40;7.7;6.7;3.3", b";0;;-1;3.3")
    body += b"14.09.2026;;;;\n"
    rows = air_daily.parse(body, "LUG", now)
    assert [(r["value"], r["quality"]) for r in rows] == [
        ("0", "provisional"),
        (None, "missing"),
        (None, "invalid"),
        ("3.3", "provisional"),
    ]
    with pytest.raises(ValueError):
        air_daily.parse(body.replace(b"14.09.2026;;;;", b"14.09.2026;1;;;"), "LUG", now)
    with pytest.raises(ValueError):
        air_daily.parse(body + body.splitlines()[6] + b"\n", "LUG", now)


@pytest.mark.parametrize("station", ["BAS", "LUG"])
def test_complete_daily_http_history_rules_improvement_withdrawal_and_independent_hourly(api, station):
    client, service, _, _, _ = api
    now = datetime.now(UTC)
    feed(service.db, station, now)
    raw = config(station)
    preview = client.post(BASE + "/preview", json={"configuration": raw}, headers=_csrf(client)).json()
    assert preview["coverage"]["O3:daily_max_hourly"]["status"] == "current"
    row = command(client, create(client, raw), "start")
    run(service, row, now)
    feed(service.db, station, now + timedelta(days=1), "60")
    run(service, row, now + timedelta(days=1))
    event = changes(client, row)[0]
    assert event["evidence"]["sample"]["period"] == "daily_max_hourly"
    assert event["kind"] == "threshold_crossed"
    with service.db.session() as session:
        saved = session.get(AirMonitor, row["id"])
        assert "last_gap" not in saved.state  # Consecutive daily reports are not a 23h outage.
        basel_hourly = [
            r.evidence
            for r in session.scalars(select(AirMeasurement).where(AirMeasurement.station_id == "BAS"))
            if r.evidence["period"] == "hourly_mean"
        ]
        assert len(basel_hourly) == 120
        assert (
            air_runtime.series(
                sorted(basel_hourly, key=lambda s: s["timestamp"]), "PM25", "rolling_24h_mean"
            )[-1]["value"]
            == "3.0000"
        )
    history = client.get(f"{BASE}/monitors/{row['id']}/measurements").json()["items"]
    assert any(r.get("source_date") and r["period"] == "daily_max_hourly" for r in history)
    assert any(i["id"] == event["id"] for i in client.get(BASE + "/today").json()["items"])
    feed(service.db, station, now + timedelta(days=1), "44")
    run(service, row, now + timedelta(days=1))
    assert changes(client, row)[0]["kind"] == "threshold_cleared"
    assert changes(client, row)[0]["evidence"]["corrected"]
    body = csv_body(station, now + timedelta(days=1), "44").splitlines()
    body[-1] = body[-1].split(b";")[0] + b";;;;"
    feed(service.db, station, now + timedelta(days=1), body=b"\n".join(body))
    with service.db.session() as session:
        preview = air_runtime.preview(session, raw, now + timedelta(days=1))
        assert preview["coverage"]["O3:daily_max_hourly"]["status"] == "unknown"
        assert any(r.evidence["corrected"] for r in session.scalars(select(AirReadingVersion)))
    assert command(client, command(client, row, "pause"), "archive")["status"] == "archived"


def test_expired_hourly_rights_do_not_revoke_permitted_daily_but_never_approve_hourly(api):
    client, service, _, _, _ = api
    now = datetime.now(UTC)
    feed(service.db, "BAS", now)
    with service.db.session() as session:
        session.get(AirSourceCache, "catalog").error = "source_unavailable"
        session.commit()
    preview = client.post(BASE + "/preview", json={"configuration": config()}, headers=_csrf(client)).json()
    assert preview["coverage"]["O3:hourly_mean"]["status"] == "stale"
    assert preview["coverage"]["O3:daily_max_hourly"]["status"] == "current"


def test_daily_fetch_is_shared_and_failure_does_not_invalidate_hourly(api):
    client, service, _, _, _ = api
    now = datetime.now(UTC)
    feed(service.db, "BAS", now)
    assert (
        air_sources.collect(
            service.db,
            "daily:BAS",
            now=now,
            fetch_daily_csv=lambda *args: pytest.fail("duplicate daily request"),
        )
        == "cached_or_busy"
    )
    with service.db.session() as session:
        cache = session.get(AirSourceCache, "daily:BAS")
        assert cache.next_fetch_at.replace(tzinfo=UTC) == now + timedelta(hours=6)
        cache.next_fetch_at = now
        session.commit()
    assert (
        air_sources.collect(
            service.db, "daily:BAS", now=now, fetch_daily_csv=lambda *args: b"not a NABEL report"
        )
        == "source_unavailable"
    )
    preview = client.post(BASE + "/preview", json={"configuration": config()}, headers=_csrf(client)).json()
    assert preview["coverage"]["O3:hourly_mean"]["status"] == "current"
    assert preview["coverage"]["O3:daily_max_hourly"]["status"] == "stale"


def test_hourly_and_daily_thresholds_have_distinct_baselines_and_developments(api):
    from test_air_watch import feed as feed_hourly
    from test_air_watch import source_rows

    client, service, _, _, now = api
    feed(service.db, "BAS", now)
    raw = config()
    raw["rules"].append(configuration()["rules"][0])
    row = command(client, create(client, raw), "start")
    run(service, row, now)
    at = now + timedelta(hours=1)
    feed_hourly(service.db, at, source_rows(at, 60))
    run(service, row, at)
    assert [e["evidence"]["sample"]["period"] for e in changes(client, row)] == ["hourly_mean"]
    feed(service.db, "BAS", at, "60")
    run(service, row, at)
    events = changes(client, row)
    assert len(events) == 2 and len({e["development_id"] for e in events}) == 2
    assert {e["evidence"]["sample"]["period"] for e in events} == {"hourly_mean", "daily_max_hourly"}
    assert all(e["evidence"]["sample"]["period"] == e["evidence"]["baseline"]["period"] for e in events)


@pytest.mark.parametrize("mutate", ["none", "withdraw", "source"])
def test_daily_final_send_uses_daily_source_and_current_calendar_report(db, mutate):
    from test_air_delivery import SETTINGS
    from test_tender_delivery import Mailer

    now = datetime.now(UTC)
    feed(db, "LUG", now)
    with db.session() as session:
        session.get(User, "owner").email_verified_at = now
        identifier = air_runtime.create(session, "owner", config("LUG"), str(uuid4()))["id"]
        session.commit()
    with db.session() as session:
        air_email_preferences.configure(
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
    at = now + timedelta(days=1)
    feed(db, "LUG", at, "60")
    with db.session() as session:
        monitor = session.get(AirMonitor, identifier)
        air_runtime.evaluate(session, monitor, at)
        revision = monitor.email_revision
        session.commit()

    def change_source():
        if mutate == "source":
            with db.session() as session:
                session.get(AirSourceCache, "daily:LUG").error = "source_unavailable"
                session.commit()
        elif mutate == "withdraw":
            feed(db, "LUG", at, body=csv_body("LUG", at, "60").replace(b";60;", b";;"))

    fake = Mailer()
    result = air_delivery.deliver(
        db,
        SETTINGS,
        monitor_id=identifier,
        consent_revision=revision,
        now=at,
        mailer=fake,
        before_send=change_source,
    )
    assert bool(fake.calls) == (mutate == "none")
    assert (result["status"] == "sent") == (mutate == "none")
