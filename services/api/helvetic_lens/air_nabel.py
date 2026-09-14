"""Official Lugano NABEL hourly CSV and its explicitly licensed data-query resource."""

import csv
import hashlib
import io
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx

from .air_contracts import utc
from .river_sources import digest

SOURCE_URL = "https://www.bafu.admin.ch/de/datenabfrage-nabel"
LICENSE = "https://opendata.swiss/terms-of-use#terms_by"
PACKAGE = "nationales-beobachtungsnetz-fur-luftfremdstoffe-nabel-stationen"
METADATA_URL = "https://ckan.opendata.swiss/api/3/action/package_show?id=" + PACKAGE
RESOURCE_ID = "89870650-c833-4b92-8305-75cd7b5fa578"
CSV_URL = "https://bafu.meteotest.ch/nabel/index.php/ausgabe/index/german?webgrab=no"
ATTRIBUTION = "BAFU / NABEL · Lugano-Università · Stundenmittelwerte"
STATION = {
    "id": "LUG",
    "name": "Lugano-Università",
    "area": "Lugano",
    "representativeness": "urban_station",
    "source_url": SOURCE_URL,
}
CET = timezone(timedelta(hours=1))  # The CSV declares MEZ/CET, including in summer.
MAX_BYTES = 200_000
METHOD = "nabel-lugano-hourly-cet-v1"


def request(url, data=None):
    if url not in {METADATA_URL, CSV_URL} or (data is None) != (url == METADATA_URL):
        raise ValueError("Unsupported NABEL request")
    with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
        with client.stream("GET" if data is None else "POST", url, data=data) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise ValueError("NABEL response exceeded bound")
            return bytes(body)


def request_metadata():
    import json

    return json.loads(request(METADATA_URL))


def request_csv(now):
    local = utc(now).astimezone(CET)
    return request(
        CSV_URL,
        {
            "abfrageflag": "true",
            "nach": "station",
            "station": "3",
            "schadstoffsliste[]": ["1", "2", "6", "7"],
            "datentyp": "stunden",
            "zeitraum": "frei",
            "von": (local - timedelta(hours=96)).date().isoformat(),
            "bis": local.date().isoformat(),
            "ausgabe": "csv",
        },
    )


def validate_metadata(raw):
    if not isinstance(raw, dict) or raw.get("success") is not True:
        raise ValueError("NABEL catalogue unavailable")
    package = raw["result"]
    if (
        package["name"] != PACKAGE
        or package["state"] != "active"
        or package["organization"]["name"] != "bundesamt-fur-umwelt-bafu"
    ):
        raise ValueError("NABEL publisher changed")
    resources = [r for r in package["resources"] if r["id"] == RESOURCE_ID]
    if (
        len(resources) != 1
        or resources[0]["url"] != SOURCE_URL
        or resources[0]["state"] != "active"
        or resources[0]["rights"] != LICENSE
        or resources[0]["license"] != LICENSE
    ):
        raise ValueError("NABEL data-query rights changed")
    return {
        "schema_version": METHOD,
        "source_url": SOURCE_URL,
        "license_url": LICENSE,
        "resource_id": RESOURCE_ID,
        "metadata_sha256": digest(raw),
    }


def parse(raw, now):
    now = utc(now)
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise ValueError("Invalid NABEL response")
    lines = raw.decode("latin-1").splitlines()
    if (
        len(lines) < 8
        or len(lines) > 128
        or lines[:5]
        != ["Station: Lugano-Università", "Stadt", "Stundenmittelwerte", "MEZ/CET", "Quelle: NABEL"]
        or lines[5]
        != "Die Messwerte des laufenden Jahres sind vorläufig und noch nicht abschliessend geprüft."
        or lines[6] != "Datum/Zeit;O3 [ug/m3];NO2 [ug/m3];PM10 [ug/m3];PM2.5 [ug/m3]"
    ):
        raise ValueError("NABEL station, time, unit or quality contract changed")
    observations, times = [], set()
    response_hash = hashlib.sha256(raw).hexdigest()
    for row in csv.reader(io.StringIO("\n".join(lines[7:])), delimiter=";", strict=True):
        if len(row) != 5 or not re.fullmatch(r"\d{2}\.\d{2}\.\d{4} \d{2}:00", row[0]):
            raise ValueError("Invalid NABEL hour")
        at = utc(datetime.strptime(row[0], "%d.%m.%Y %H:%M").replace(tzinfo=CET))
        if at in times:
            raise ValueError("Duplicate NABEL hour")
        times.add(at)
        if at > now:
            if any(row[1:]):
                raise ValueError("Future populated NABEL observation")
            continue
        if at < now - timedelta(hours=96):
            continue
        for metric, value in zip(("O3", "NO2", "PM10", "PM25"), row[1:], strict=True):
            quality = "missing"
            if value:
                if not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
                    raise ValueError("Invalid NABEL number")
                quality = "provisional" if 0 <= Decimal(value) <= 100000 else "invalid"
            sample = {
                "station_id": "LUG",
                "metric": metric,
                "timestamp": at.isoformat(),
                "value": value if quality == "provisional" else None,
                "unit": "µg/m³",
                "period": "hourly_mean",
                "quality": quality,
                "method": METHOD,
                "source_url": SOURCE_URL,
                "source": ATTRIBUTION,
                "license_url": LICENSE,
                "source_time_label": row[0],
                "source_timezone": "MEZ/CET (UTC+01:00)",
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
    if not observations:
        raise ValueError("No NABEL observations within recovery window")
    return observations
