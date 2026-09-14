"""NABEL calendar-day statistics: ozone daily max of hourly means, other daily means."""

import csv
import hashlib
import io
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from . import air_nabel
from .air_contracts import DAILY_PERIODS, utc
from .river_sources import digest

STATIONS = {"BAS": ("5", "Basel-Binningen", "Vorstädtisch"), "LUG": ("3", "Lugano-Università", "Stadt")}


def request_csv(station, now):
    if station not in STATIONS:
        raise ValueError("Unsupported daily station")
    today = utc(now).astimezone(air_nabel.CET).date()
    return air_nabel.request(
        air_nabel.CSV_URL,
        {
            "abfrageflag": "true",
            "nach": "station",
            "station": STATIONS[station][0],
            "schadstoffsliste[]": ["1", "2", "6", "7"],
            "datentyp": "tag",
            "zeitraum": "frei",
            "von": (today - timedelta(days=7)).isoformat(),
            "bis": (today - timedelta(days=1)).isoformat(),
            "ausgabe": "csv",
        },
    )


def parse(raw, station, now):
    if station not in STATIONS or not isinstance(raw, bytes) or not raw or len(raw) > air_nabel.MAX_BYTES:
        raise ValueError("Invalid daily response")
    lines = raw.decode("latin-1").splitlines()
    _, name, area = STATIONS[station]
    if (
        len(lines) < 7
        or len(lines) > 15
        or lines[:6]
        != [
            f"Station: {name}",
            area,
            "Tagesmittelwerte, O3: Maximales Stundenmittel des Tages",
            "Quelle: NABEL",
            "Die Messwerte des laufenden Jahres sind vorläufig und noch nicht abschliessend geprüft.",
            "Datum/Zeit;O3 [ug/m3];NO2 [ug/m3];PM10 [ug/m3];PM2.5 [ug/m3]",
        ]
    ):
        raise ValueError("NABEL daily station/statistic/unit contract changed")
    now = utc(now)
    today = now.astimezone(air_nabel.CET).date()
    samples, dates = [], set()
    for row in csv.reader(io.StringIO("\n".join(lines[6:])), delimiter=";", strict=True):
        if len(row) != 5 or not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", row[0]):
            raise ValueError("Invalid daily date")
        day = datetime.strptime(row[0], "%d.%m.%Y").date()
        if day in dates:
            raise ValueError("Duplicate daily date")
        dates.add(day)
        if day >= today:
            if any(row[1:]):
                raise ValueError("Unfinished or future daily statistic")
            continue
        if day < today - timedelta(days=7):
            continue
        for metric, raw_value in zip(DAILY_PERIODS, row[1:], strict=True):
            value, quality = None, "missing"
            if raw_value:
                if not re.fullmatch(r"-?\d+(?:\.\d+)?", raw_value):
                    raise ValueError("Invalid daily value")
                if 0 <= Decimal(raw_value) <= 100000:
                    value, quality = raw_value, "provisional"
                else:
                    quality = "invalid"
            sample = {
                "station_id": station,
                "metric": metric,
                "period": DAILY_PERIODS[metric],
                "source_date": day.isoformat(),
                # Order/history cursor only. This is not an instantaneous source measurement time.
                "timestamp": datetime.combine(day, datetime.min.time(), tzinfo=UTC).isoformat(),
                "timestamp_kind": "calendar_date_sort_key",
                "value": value,
                "quality": quality,
                "unit": "µg/m³",
                "method": f"nabel-{station.lower()}-daily-v1",
                "source_url": air_nabel.SOURCE_URL,
                "license_url": air_nabel.LICENSE,
                "source": f"BAFU / NABEL · {name}",
                "fetched_at": now.isoformat(),
                "response_sha256": hashlib.sha256(raw).hexdigest(),
            }
            sample["value_hash"] = digest(
                {
                    k: sample[k]
                    for k in (
                        "station_id",
                        "metric",
                        "period",
                        "source_date",
                        "value",
                        "quality",
                        "unit",
                        "method",
                    )
                }
            )
            samples.append(sample)
    if not samples:
        raise ValueError("No completed daily reports")
    return samples
