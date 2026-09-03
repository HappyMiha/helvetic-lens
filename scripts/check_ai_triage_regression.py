"""Run the checked-in HL-064 labelled corpus without contacting an AI provider."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from helvetic_lens.triage_regression import run_gate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="Evaluate the complete 1,401-passage-per-side rewrite fixture.",
    )
    args = parser.parse_args()
    result = run_gate(ROOT / "demo" / "ai-triage-regression.json", full=args.full)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
