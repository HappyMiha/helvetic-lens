"""Evaluate saved B2 development/validation experiments; never call a model."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from helvetic_lens.semantic_matching_eval import read_bounded, strict_json
from helvetic_lens.tender_semantic_eval import Dataset, evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--threshold", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Do not overwrite datasets, predictions or previous audit evidence.
    raw = read_bounded(args.dataset)
    strict_json(raw)
    dataset = Dataset.model_validate_json(raw)
    results = strict_json(read_bounded(args.results))
    report = evaluate(dataset, results, threshold=args.threshold)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(f"Evaluated {len(report['cases'])} cases; promotion remains disabled.")


if __name__ == "__main__":
    main()
