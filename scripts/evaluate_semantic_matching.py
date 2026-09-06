"""Offline HL-093 matching baseline/evaluation. Never approves an AI profile."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from helvetic_lens.semantic_matching_eval import (
    Dataset,
    Labels,
    Predictions,
    evaluate,
    load_contract,
    load_dataset,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    schemas = sub.add_parser(
        "schemas", help="Export authoring schemas, not reviewer labels or approval."
    )
    schemas.add_argument("--output", type=Path)
    for name in ("baseline", "evaluate"):
        command = sub.add_parser(name)
        command.add_argument("--dataset", required=True, type=Path)
        command.add_argument("--root", required=True, type=Path)
        command.add_argument(
            "--output",
            type=Path,
            help="Create a new JSON file; existing files are never overwritten.",
        )
        if name == "baseline":
            command.add_argument(
                "--split", required=True, choices=["development", "held_out"]
            )
        else:
            command.add_argument("--labels", required=True, type=Path)
            command.add_argument("--predictions", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.exists():
            raise ValueError(
                "Output already exists; use a new run filename to preserve evidence."
            )
        if args.command == "schemas":
            from helvetic_lens.semantic_matching_baseline import MatchingInput

            result = {
                "schemas": {
                    schema.__name__: schema.model_json_schema()
                    for schema in (Dataset, Labels, Predictions, MatchingInput)
                },
                "explanation_capability_approved": False,
            }
            exit_code = 0
        else:
            dataset, dataset_hash, artifacts = load_dataset(args.dataset, args.root)
        if args.command == "baseline":
            from helvetic_lens.semantic_matching_baseline import (
                implementation_identity,
                run_baseline,
            )

            result = run_baseline(
                dataset,
                dataset_hash,
                artifacts,
                args.split,
                implementation_identity(ROOT),
            )
            exit_code = (
                0
                if result["rows"]
                and all(row["status"] == "ok" for row in result["rows"])
                else 1
            )
        elif args.command == "evaluate":
            labels, labels_hash = load_contract(args.labels, Labels)
            predictions, predictions_hash = load_contract(args.predictions, Predictions)
            result = evaluate(
                dataset,
                dataset_hash,
                artifacts,
                labels,
                predictions,
                labels_hash=labels_hash,
                predictions_hash=predictions_hash,
            )
            exit_code = 0 if result["matching_target_met"] else 1
        encoded = (
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "exit_code": exit_code,
                        "explanation_capability_approved": False,
                    }
                )
            )
        else:
            print(encoded, end="")
        return exit_code
    except (OSError, ValueError, TypeError, KeyError) as error:
        # Do not echo source contents, credentials or validation input values.
        print(
            json.dumps(
                {
                    "error": "invalid_evaluation_package",
                    "error_type": type(error).__name__,
                    "message": "Check package schema, artifact hashes/paths, split binding and output filename. No approval or app write occurred.",
                }
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
