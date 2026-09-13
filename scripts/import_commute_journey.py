"""Import exact ordered timetable legs and interchange proof from a pinned ZIP.

Dry run by default; --apply publishes the shared catalog without source grants,
private monitors, feature activation, network requests or emails.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from helvetic_lens.commute_interchanges import run_import
from helvetic_lens.config import Settings
from helvetic_lens.db import Database
from helvetic_lens.transport_static import LegRequest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--leg", nargs=3, action="append", required=True, metavar=("TRIP_ID", "BOARD_SEQUENCE", "ALIGHT_SEQUENCE"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        requests = tuple(LegRequest(trip, args.date, int(board), int(alight)) for trip, board, alight in args.leg)
        if not 2 <= len(requests) <= 8 or len(set(requests)) != len(requests):
            raise ValueError("Choose two to eight distinct legs in travel order")
    except ValueError as error:
        parser.error(str(error))
    database = Database(Settings())
    try:
        report = run_import(database, args.archive, expected_version=args.version, expected_sha256=args.sha256,
                            requests=requests, apply=args.apply)
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    finally:
        database.engine.dispose()


if __name__ == "__main__":
    main()
