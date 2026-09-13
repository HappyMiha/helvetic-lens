"""Install a reviewed native boundary archive in an explicitly selected data dir.

This offline operator action publishes geometry only. It does not enable Hazard
Watch, a warning source, private monitoring, emails or any production deployment.
Use the archive SHA-256 from the official STAC entry, and an explicit review
expiry. To renew/replace, pass the SHA-256 of the existing current.json selection.
"""

import argparse
import json
from datetime import date
from pathlib import Path

from helvetic_lens.hazard_boundary_store import install_catalogue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--expires-on", type=date.fromisoformat, required=True)
    parser.add_argument("--expected-selection-sha256")
    args = parser.parse_args()
    print(json.dumps(install_catalogue(args.data_dir, args.archive, archive_sha256=args.archive_sha256,
        version=args.version, expires_on=args.expires_on, expected_selection_sha256=args.expected_selection_sha256)))


if __name__ == "__main__":
    main()
