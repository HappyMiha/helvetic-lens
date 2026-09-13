"""Explicit offline native-asset check; no download or production activation.

Run with the January 2026 official GeoPackage ZIP and a new JSON output path.
The original archive remains outside Git. Public city-centre probes are test
coordinates, never saved user locations. Source attribution accompanies evidence.
"""

import argparse
import hashlib
import json
import zipfile
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

from helvetic_lens.hazard_boundaries import load_geopackage
from helvetic_lens.hazard_cap import CAPArea
from helvetic_lens.hazard_contracts import MunicipalityLocation, PointLocation
from helvetic_lens.hazard_matching import CANTON, COMMUNE, match_location

ARCHIVE_SHA256 = "68e922353c76fa5db3cef06a32f9711c0198faa6fbd2b5bcde9edc88b0f8999f"
PACKAGE_SHA256 = "1f122cb7a06f2d312a84b7c0a91116348ba907054d487f0a70b9d2302984e6fc"
ASSET = "https://data.geo.admin.ch/ch.swisstopo.swissboundaries3d/swissboundaries3d_2026-01/swissboundaries3d_2026-01_2056_5728.gpkg.zip"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new evidence output path")
    if args.archive.stat().st_size != 37361779:
        raise ValueError("Unexpected native archive length")
    if hashlib.sha256(args.archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Archive differs from official STAC checksum")
    with zipfile.ZipFile(args.archive) as archive:
        entries = archive.infolist()
        if (len(entries) != 1 or entries[0].filename != "swissBOUNDARIES3D_1_5_LV95_LN02.gpkg"
                or entries[0].file_size != 74231808):
            raise ValueError("Unexpected native archive contents")
        payload = archive.read(entries[0])
    catalogue = load_geopackage(payload, sha256=PACKAGE_SHA256, version="2026-01",
                                expires_on=args.as_of + timedelta(days=1))
    if len(catalogue.municipalities) != 2110 or len(catalogue.cantons) != 26:
        raise ValueError("Native edition coverage changed")
    proofs = []
    for name, lat, lon, canton, code in (
        ("Basel", 47.56, 7.59, "BS", "2701"), ("Bern", 46.948, 7.447, "BE", "351"),
        ("Moutier", 47.28, 7.37, "JU", "6831"), ("Saint-Louis", 47.588, 7.56, "BS", None),
        ("Vaduz", 47.141, 9.52, "SG", None), ("Busingen", 47.696, 8.69, "SH", None),
    ):
        proof = catalogue.verify_location(PointLocation(kind="point", canton=canton, latitude=lat,
                                                       longitude=lon), on_date=args.as_of)
        if proof.state != ("verified" if code else "no_match") or proof.municipality_code != code:
            raise ValueError(f"Native geography check failed: {name}")
        proofs.append({"probe": name, **asdict(proof)})
    old = catalogue.verify_location(MunicipalityLocation(kind="municipality", canton="BE", municipality_code="700"),
                                    on_date=args.as_of)
    if old.reason != "municipality_not_in_version":
        raise ValueError("Former Moutier code must not silently select a current municipality")
    proofs.append({"probe": "former Moutier code", **asdict(old)})
    basel = MunicipalityLocation(kind="municipality", canton="BS", municipality_code="2701")
    home = PointLocation(kind="point", canton="BS", latitude=47.56, longitude=7.59)
    named = CAPArea("Synthetic Basel filter", (), (), ((COMMUNE, "2701"),), None, None)
    inside = CAPArea("Synthetic Basel polygon", (((47.557, 7.586), (47.557, 7.594),
        (47.563, 7.594), (47.563, 7.586), (47.557, 7.586)),), (), (), None, None)
    abroad = CAPArea("Synthetic outside polygon with dissemination canton", (((47.587, 7.559),
        (47.587, 7.561), (47.589, 7.561), (47.589, 7.559), (47.587, 7.559)),), (), ((CANTON, "BS"),), None, None)
    circle = CAPArea("Synthetic Basel circle", (), ((47.56, 7.59, 0.05),), (), None, None)
    matching = []
    for label, area, place, binding, expected, basis in (
        ("municipality named by source", named, basel, "2026-01", "match", "administrative_filter"),
        ("named filter is not exact home geometry", named, home, "2026-01", "unavailable", "administrative_filter"),
        ("Basel polygon intersects municipality", inside, basel, "2026-01", "match", "explicit_geometry"),
        ("Basel polygon includes home", inside, home, "2026-01", "match", "explicit_geometry"),
        ("foreign polygon not expanded by canton code", abroad, home, "2026-01", "no_match", "geography"),
        ("small circle inside municipality", circle, basel, "2026-01", "match", "explicit_geometry"),
        ("unbound historic codes are unknown", named, basel, "2025-01", "unavailable", "geography"),
    ):
        matched = match_location((area,), place, catalogue, on_date=args.as_of, geocode_version=binding)
        if matched.state != expected or matched.basis != basis:
            raise ValueError(f"Native geometry matching failed: {label}: {matched}")
        matching.append({"probe": label, **asdict(matched)})
    report = {"asset": ASSET, "archive_sha256": ARCHIVE_SHA256, "package_sha256": PACKAGE_SHA256,
              "as_of": args.as_of.isoformat(), "municipalities": 2110, "cantons": 26, "checks": proofs,
              "synthetic_warning_matching": matching,
              "scope": "Offline native geometry only; no production catalogue, source coverage or active warning."}
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(report, out, indent=2, ensure_ascii=False)
        out.write("\n")
    print("7 native location checks + 7 synthetic warning matches passed; 2110 Swiss political municipalities, 26 cantons")


if __name__ == "__main__":
    main()
