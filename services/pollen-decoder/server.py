"""Private, single-request GRIB decoder. No database, source fetch or shared volume."""

import base64
import csv
import hashlib
import io
import json
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import numpy as np
from pollen_decode_proof import read_fields, validate_fields

MAX_BODY = 96 * 1024 * 1024
VARIABLES = {"ALNUsnc", "BETUsnc", "CORYsnc", "POACsnc", "AMBRsnc"}


def decode(request):
    if set(request) != {"protocol", "variable", "issue_time", "lead_hours", "artifacts"} or request["protocol"] != 1:
        raise ValueError("Unsupported decoder request")
    variable, lead = request["variable"], request["lead_hours"]
    if variable not in VARIABLES or type(lead) is not int or not 1 <= lead <= 120:
        raise ValueError("Unsupported forecast variable or horizon")
    issue = datetime.fromisoformat(request["issue_time"])
    if issue.tzinfo is None or issue.utcoffset() != timedelta(0):
        raise ValueError("Issue time must be UTC")
    names = {f"{variable}.grib2", "DEN.grib2", "horizontal_constants_icon-ch2-eps.grib2", "stations.csv"}
    if set(request["artifacts"]) != names:
        raise ValueError("Forecast/density/grid/station artifacts are required")
    hashes, total = {}, 0
    with tempfile.TemporaryDirectory(prefix="pollen-grib-") as directory:
        root = Path(directory)
        for name, item in request["artifacts"].items():
            if set(item) != {"sha256", "base64"}:
                raise ValueError("Invalid artifact envelope")
            body = base64.b64decode(item["base64"], validate=True)
            total += len(body)
            if total > 64 * 1024 * 1024 or (name == "stations.csv" and len(body) > 256 * 1024):
                raise ValueError("Decoder artifact bound exceeded")
            digest = hashlib.sha256(body).hexdigest()
            if digest != item["sha256"]:
                raise ValueError("Decoder artifact hash mismatch")
            hashes[name] = digest
            (root / name).write_bytes(body)
        fields, runtime = read_fields(root, variable, Path("/opt/cosmo"))
        _, valid = validate_fields(fields, request)
        latitudes, longitudes = fields["CLAT"][1], fields["CLON"][1]
        if (not all(np.all(np.isfinite(values)) for _, values in fields.values())
                or np.any(np.abs(latitudes) > 90) or np.any(np.abs(longitudes) > 180)):
            raise ValueError("Invalid coordinates or model values")
        stations = list(csv.DictReader(io.StringIO((root / "stations.csv").read_bytes().decode("cp1252")), delimiter=";"))
        if not 1 <= len(stations) <= 100 or len({s["station_abbr"] for s in stations}) != len(stations):
            raise ValueError("Invalid station catalogue")
        latitude_rad, longitude_rad = np.radians(latitudes), np.radians(longitudes)
        points = []
        for station in stations:
            latitude, longitude = float(station["station_coordinates_wgs84_lat"]), float(station["station_coordinates_wgs84_lon"])
            if not np.isfinite(latitude + longitude) or abs(latitude) > 90 or abs(longitude) > 180:
                raise ValueError("Invalid station coordinates")
            station_lat, station_lon = np.radians([latitude, longitude])
            haversine = (np.sin((latitude_rad - station_lat) / 2) ** 2
                + np.cos(latitude_rad) * np.cos(station_lat) * np.sin((longitude_rad - station_lon) / 2) ** 2)
            cell = int(np.argmin(haversine))
            distance = float(6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(haversine[cell], 0, 1))))
            if distance > 5:
                points.append({"station_id": station["station_abbr"], "availability": "outside_grid"})
                continue
            number = Decimal(str(fields[variable][1][cell]))
            density = Decimal(str(fields["DEN"][1][cell]))
            if number < 0 or density <= 0:
                raise ValueError("Invalid model pollen concentration or density")
            with localcontext() as context:
                context.prec = 80
                concentration = format(number * density, "f")
            points.append({"station_id": station["station_abbr"], "availability": "usable", "grid_cell": cell,
                "mapping_distance_km": distance, "value": concentration, "number_per_kg": str(number), "density_kg_m3": str(density)})
        return {"protocol": 1, "variable": variable, "issue_time": issue.isoformat(), "valid_time": valid.isoformat(),
                "grid": str(fields["DEN"][0]["uuidOfHGrid"]), "layer": "80", "unit": "number/m3",
                "artifact_hashes": hashes, "runtime": runtime, "points": points}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # No artifact bodies, source URLs or private data enter access logs.

    def reply(self, status, value):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(200 if self.path == "/health" else 404, {"protocol": 1})

    def do_POST(self):
        self.connection.settimeout(30)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if self.path != "/decode" or not 0 < length <= MAX_BODY or self.headers.get("Transfer-Encoding"):
                self.reply(400, {"error": "invalid_decoder_request"})
                return
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Incomplete decoder request")
            result = decode(json.loads(body))
        except Exception:  # noqa: BLE001 - HTTP boundary must never expose native decoder errors or source data.
            self.reply(422, {"error": "forecast_decode_failed"})
            return
        self.reply(200, result)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8093), Handler).serve_forever()
