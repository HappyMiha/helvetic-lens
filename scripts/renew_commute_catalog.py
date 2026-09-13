"""Preview or apply exact saved-journey mappings from an acquired GTFS archive.

Uses the configured database without migrations, network requests, source grants
or feature activation. Dry run is the default; --apply publishes unique mappings
and newly checked rules for previously imported connections whose endpoints are
both requested. Inspect the interchanges report as well as individual leg results.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from helvetic_lens.commute_renewal import run_renewal
from helvetic_lens.config import Settings
from helvetic_lens.db import Database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--reference", type=UUID, action="append", required=True)
    parser.add_argument("--date", type=date.fromisoformat, action="append", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    requests = tuple((str(reference), day) for reference in args.reference for day in args.date)
    if not 1 <= len(requests) <= 32 or len(set(requests)) != len(requests):
        parser.error("Choose between one and 32 distinct reference/date pairs")
    database = Database(Settings())
    try:
        report = run_renewal(database, args.archive, expected_version=args.version,
            expected_sha256=args.sha256, requests=requests, apply=args.apply)
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    finally:
        database.engine.dispose()


if __name__ == "__main__":
    main()
