"""Decode retained MV2-069 evidence offline; this is not a production collector.

Requires ecCodes, matching COSMO definitions and numpy in an isolated environment.
Never downloads data, enables a monitor or promotes a source gate automatically.
"""

import argparse
import csv
import hashlib
import io
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path


def verify_files(root, manifest):
    if manifest["status"] != "fetched_not_yet_decoded":
        raise ValueError("An incomplete source capture cannot be decoded")
    for name, info in manifest["files"].items():
        if Path(name).name != name or "/" in name or "\\" in name:
            raise ValueError("Invalid retained filename")
        body = (root / name).read_bytes()
        if len(body) != info["bytes"] or hashlib.sha256(body).hexdigest() != info["sha256"]:
            raise ValueError(f"Retained bytes do not match the manifest: {name}")


def concentration(number_per_kg, density):
    number, mass = Decimal(str(number_per_kg)), Decimal(str(density))
    if not number.is_finite() or not mass.is_finite() or number < 0 or mass <= 0:
        raise ValueError("Missing, negative or invalid forecast value/density")
    return str(number * mass)


def validate_fields(fields, manifest):
    variable = manifest["variable"]
    if set(fields) != {variable, "DEN", "CLAT", "CLON"}:
        raise ValueError("Required forecast/density/grid fields are absent")
    reference = fields[variable][0]
    issue = datetime.fromisoformat(manifest["issue_time"])
    valid = issue + timedelta(hours=manifest["lead_hours"])
    expected = {"dataDate": int(issue.strftime("%Y%m%d")), "dataTime": int(issue.strftime("%H%M")),
                "validityDate": int(valid.strftime("%Y%m%d")), "validityTime": int(valid.strftime("%H%M"))}
    for name, (metadata, values) in fields.items():
        if not reference["uuidOfHGrid"] or any(metadata[k] != reference[k] for k in (
            "uuidOfHGrid", "numberOfValues",
        )) or len(values) != reference["numberOfValues"] or len(values) == 0:
            raise ValueError("Grid identity/order/size mismatch")
        if metadata["bitmapPresent"] or metadata["numberOfMissing"]:
            raise ValueError("This proof decoder requires complete fields")
        expected_unit = {variable: "kg-1", "DEN": "kg m-3", "CLAT": "deg N", "CLON": "deg E"}[name]
        if metadata["units"] != expected_unit:
            raise ValueError("Unexpected source unit or GRIB definitions")
        if name in {variable, "DEN"}:
            if metadata["level"] != 80 or metadata["typeOfLevel"] != "generalVerticalLayer":
                raise ValueError("Expected the lowest model layer (80)")
            if any(metadata[k] != value for k, value in expected.items()):
                raise ValueError("Forecast and density must match requested issue/valid time")
    return issue, valid


def read_fields(root, variable):
    import eccodes as ec

    fields = {}
    keys = ("shortName", "units", "level", "typeOfLevel", "uuidOfHGrid", "numberOfValues",
            "dataDate", "dataTime", "validityDate", "validityTime", "bitmapPresent", "numberOfMissing")
    for filename in (f"{variable}.grib2", "DEN.grib2", "horizontal_constants_icon-ch2-eps.grib2"):
        with (root / filename).open("rb") as source:
            while (handle := ec.codes_grib_new_from_file(source)) is not None:
                try:
                    name = ec.codes_get(handle, "shortName")
                    wanted = {"CLAT", "CLON"} if filename.startswith("horizontal_") else {filename[:-6]}
                    if name not in wanted:
                        if not filename.startswith("horizontal_"):
                            raise ValueError("Forecast parameter differs from its manifest")
                        continue
                    if name in fields:
                        raise ValueError("Ambiguous duplicate GRIB field")
                    fields[name] = ({key: ec.codes_get(handle, key) for key in keys}, ec.codes_get_values(handle))
                finally:
                    ec.codes_release(handle)
    return fields, ec.codes_get_api_version()


def decode(root):
    import numpy as np

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    verify_files(root, manifest)
    fields, library_version = read_fields(root, manifest["variable"])
    issue, valid = validate_fields(fields, manifest)
    latitudes, longitudes = fields["CLAT"][1], fields["CLON"][1]
    if (not all(np.all(np.isfinite(values)) for _, values in fields.values())
            or np.any(np.abs(latitudes) > 90) or np.any(np.abs(longitudes) > 180)):
        raise ValueError("Invalid grid coordinates or non-finite values")
    lat_rad, lon_rad = np.radians(latitudes), np.radians(longitudes)
    stations = list(csv.DictReader(io.StringIO((root / "ogd-pollen_meta_stations.csv").read_bytes().decode("cp1252")), delimiter=";"))
    points = []
    for station in stations:
        lat, lon = float(station["station_coordinates_wgs84_lat"]), float(station["station_coordinates_wgs84_lon"])
        station_lat, station_lon = np.radians([lat, lon])
        haversine = (np.sin((lat_rad - station_lat) / 2) ** 2
                     + np.cos(lat_rad) * np.cos(station_lat) * np.sin((lon_rad - station_lon) / 2) ** 2)
        cell = int(np.argmin(haversine))
        distance = float(6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(haversine[cell], 0, 1))))
        # A product mapping bound, not a claim about forecast spatial accuracy.
        if distance > 5:
            raise ValueError("Station lies outside the accepted grid mapping distance")
        number, density = fields[manifest["variable"]][1][cell], fields["DEN"][1][cell]
        points.append({"station_id": station["station_abbr"], "station_name": station["station_name"],
                       "station_latitude": lat, "station_longitude": lon,
                       "grid_cell": cell, "grid_latitude": float(latitudes[cell]),
                       "grid_longitude": float(longitudes[cell]), "mapping_distance_km": distance,
                       "number_per_kg": str(number), "density_kg_m3": str(density),
                       "derived_number_per_m3": concentration(number, density)})
    observation_name = f"ogd-pollen_{manifest['station'].lower()}_h_now.csv"
    observations = list(csv.DictReader(io.StringIO((root / observation_name).read_bytes().decode("cp1252")), delimiter=";"))
    latest = max(observations, key=lambda row: datetime.strptime(
        row["reference_timestamp"], "%d.%m.%Y %H:%M",
    ).replace(tzinfo=UTC))
    measured_at = datetime.strptime(latest["reference_timestamp"], "%d.%m.%Y %H:%M").replace(tzinfo=UTC)
    fetched_at = datetime.fromisoformat(manifest["files"][observation_name]["fetched_at"])
    return {"schema_version": 1, "status": "decoded_source_proof_not_live_service",
            "attribution": "Source: MeteoSwiss", "decoder_library": library_version,
            "acceptance": "Pending definition-version review, categories, lifecycle and product acceptance",
            "observation": {"station_id": manifest["station"], "observed_at": measured_at.isoformat(),
                            "age_at_fetch_seconds": (fetched_at - measured_at).total_seconds(), "source_row": latest},
            "forecast": {"variable": manifest["variable"], "issue_time": issue.isoformat(),
                         "valid_time": valid.isoformat(), "grid_uuid": fields["DEN"][0]["uuidOfHGrid"],
                         "level": 80, "mapping": "nearest grid-cell centre to public station coordinates",
                         "points": points},
            "source_files": manifest["files"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = decode(args.proof)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "stations": len(result["forecast"]["points"])}))


if __name__ == "__main__":
    main()
