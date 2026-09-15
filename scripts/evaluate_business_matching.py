"""Author and evaluate offline B2/B7/B8 packages without promoting a model."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from helvetic_lens import business_matching_eval as evaluation
from helvetic_lens.semantic_matching_eval import digest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    schemas = commands.add_parser("schemas", help="Create blank authoring schemas; no fabricated gold labels.")
    schemas.add_argument("--output", type=Path)
    evaluate = commands.add_parser("evaluate", help="Evaluate exact captured package revisions offline.")
    for name in ("root", "dataset", "labels", "predictions", "audits"):
        evaluate.add_argument("--" + name, type=Path, required=True)
    evaluate.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.exists():
            raise ValueError("Output already exists")
        if args.command == "schemas":
            result = {name: getattr(evaluation, name).model_json_schema()
                for name in ("Dataset", "Labels", "Predictions", "Audits", "Permission")}
            code = 0
        else:
            result = evaluation.evaluate(args.root, args.dataset, args.labels, args.predictions, args.audits)
            code = 0 if result["package_targets_met"] else 1
        raw = (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        if args.output:
            with args.output.open("xb") as stream:
                stream.write(raw)
            print(json.dumps({"output": str(args.output), "sha256": digest(raw),
                "exit_code": code, "capability_approved": False}))
        else:
            print(raw.decode(), end="")
        return code
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        # Pydantic/path errors can contain private text and credential values.
        print(json.dumps({"error": "invalid_business_evaluation_package",
            "message": "Check schemas, hashes, permissions, review order, split and output filename.",
            "capability_approved": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
