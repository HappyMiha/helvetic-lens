"""Bounded MV2-069 source proof. Explicit invocation only; never a runtime fallback.

Retains public source bytes with hashes; signed object URLs are not written to the
manifest. Source: MeteoSwiss, CC BY 4.0. See docs/monitoring-v2/POLLEN_SOURCES.md.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = "https://data.geo.admin.ch/api/stac/v1"
OBSERVATIONS = "ch.meteoschweiz.ogd-pollen"
FORECASTS = "ch.meteoschweiz.ogd-forecasting-icon-ch2"
MAX_BYTES = 64 * 1024 * 1024


def fetch(url, payload=None):
    host = urlsplit(url).hostname or ""
    if urlsplit(url).scheme != "https" or not (host == "data.geo.admin.ch" or host.endswith(".cscs.ch")):
        raise ValueError("Unexpected data provider")
    request = Request(url, data=json.dumps(payload).encode() if payload else None,
                      headers={"User-Agent": "HelveticLens-MV2-069-source-proof/1",
                               **({"Content-Type": "application/json"} if payload else {})})
    with urlopen(request, timeout=90) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("Source proof exceeds 64 MiB per file")
        upstream_hash = response.headers.get("x-amz-meta-sha256")
        digest = hashlib.sha256(body).hexdigest()
        if upstream_hash and upstream_hash != digest:
            raise ValueError("Provider checksum mismatch")
        return body, {"sha256": digest, "bytes": len(body),
                      "fetched_at": datetime.now(UTC).isoformat(),
                      "last_modified": response.headers.get("Last-Modified"),
                      "etag": response.headers.get("ETag"), "provider_sha256": upstream_hash}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--issue-time", required=True)
    parser.add_argument("--station", default="PBS")
    parser.add_argument("--variable", choices=["ALNUsnc", "AMBRsnc", "BETUsnc", "CORYsnc", "POACsnc"],
                        default="AMBRsnc")
    parser.add_argument("--lead-hours", type=int, default=6, choices=range(1, 121))
    args = parser.parse_args()
    issue = datetime.fromisoformat(args.issue_time.replace("Z", "+00:00"))
    if issue.tzinfo is None or issue.utcoffset().total_seconds() != 0:
        parser.error("issue-time must be an explicit UTC instant")
    if not (len(args.station) == 3 and args.station.isalpha() and args.station.isascii()):
        parser.error("station must be the three-letter official identifier")
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "attribution": "Source: MeteoSwiss",
                "terms": "https://opendatadocs.meteoswiss.ch/general/terms-of-use",
                "station": args.station.upper(), "issue_time": issue.isoformat(),
                "variable": args.variable, "lead_hours": args.lead_hours, "files": {}}
    if (args.output / "manifest.json").exists():
        saved = json.loads((args.output / "manifest.json").read_text())
        for key in ("station", "issue_time", "variable", "lead_hours"):
            if saved[key] != manifest[key]:
                raise ValueError("Cannot reuse a proof directory for a different request")
        manifest["files"] = saved["files"]

    def save(name, url, *, identity, expected=None):
        if name in manifest["files"]:
            retained = (args.output / name).read_bytes()
            if hashlib.sha256(retained).hexdigest() != manifest["files"][name]["sha256"]:
                raise ValueError("Retained proof bytes have changed")
            return retained
        body, info = fetch(url)
        if expected and expected.startswith("1220") and info["sha256"] != expected[4:]:
            raise ValueError("STAC SHA-256 mismatch")
        (args.output / name).write_bytes(body)
        manifest["files"][name] = {**info, "source_identity": identity}
        return body

    try:
        observation_url = f"{ROOT}/collections/{OBSERVATIONS}"
        observation = json.loads(fetch(observation_url)[0])
        for name, asset in observation["assets"].items():
            if name in {"ogd-pollen_meta_parameters.csv", "ogd-pollen_meta_stations.csv",
                        "ogd-pollen_meta_datainventory.csv"}:
                save(name, asset["href"], identity=asset["href"], expected=asset.get("file:checksum"))
        item_url = f"{observation_url}/items/{args.station.lower()}"
        item = json.loads(fetch(item_url)[0])
        for suffix in ("h_now", "d_recent"):
            name = f"ogd-pollen_{args.station.lower()}_{suffix}.csv"
            asset = item["assets"][name]
            save(name, asset["href"], identity=asset["href"], expected=asset.get("file:checksum"))
        collection_url = f"{ROOT}/collections/{FORECASTS}"
        # Resolve assets through the documented endpoint. Never persist signed URLs.
        assets = {asset["id"]: asset for asset in json.loads(fetch(collection_url + "/assets")[0])["assets"]}
        for name in ("params_icon-ch2-eps.csv", "horizontal_constants_icon-ch2-eps.grib2"):
            asset = assets[name]
            save(name, asset["href"], identity=f"{collection_url}/assets/{name}",
                 expected=asset.get("file:checksum"))
        for variable in (args.variable, "DEN"):
            name = f"{variable}.grib2"
            if name in manifest["files"] and "properties" in manifest["files"][name]:
                # Resume the same capture even after its upstream item has expired.
                # Keep provenance paired with the retained bytes, not newer metadata.
                save(name, "", identity=manifest["files"][name]["source_identity"])
                continue
            query = {"collections": [FORECASTS], "forecast:reference_datetime": args.issue_time,
                     "forecast:variable": variable, "forecast:perturbed": False,
                     "forecast:horizon": f"P0DT{args.lead_hours:02d}H00M00S"}
            items = json.loads(fetch(f"{ROOT}/search", query)[0])["features"]
            if len(items) != 1:
                raise ValueError(f"Expected one matching {variable} forecast, received {len(items)}")
            forecast = items[0]
            if len(forecast["assets"]) != 1:
                raise ValueError("Ambiguous forecast assets")
            asset = next(iter(forecast["assets"].values()))
            save(name, asset["href"], identity=f"{collection_url}/items/{forecast['id']}",
                 expected=asset.get("file:checksum"))
            manifest["files"][name]["properties"] = forecast["properties"]
        manifest["status"] = "fetched_not_yet_decoded"
    except Exception:
        manifest["status"] = "incomplete"
        raise
    finally:
        (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "files": len(manifest["files"]),
                      "bytes": sum(f["bytes"] for f in manifest["files"].values())}))


if __name__ == "__main__":
    main()
