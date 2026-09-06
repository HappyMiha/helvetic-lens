"""Read-only integrity check for trusted explanation capability approvals."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from helvetic_lens.ai_capabilities import load_registry


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry", type=Path,
        default=ROOT / "services/api/helvetic_lens/ai-capability-profiles.json",
    )
    parser.add_argument("--evidence-root", type=Path, default=ROOT)
    parser.add_argument("--require-approved", action="store_true")
    args = parser.parse_args(argv)
    try:
        registry = load_registry(args.registry, args.evidence_root)
    except (OSError, ValueError):
        # Do not echo untrusted artifact contents or local filesystem details.
        print(json.dumps({"valid": False, "error": "invalid_registry_or_review_evidence"}))
        return 1
    approved = [profile for profile in registry.profiles if profile.status == "approved"]
    ready = bool(approved)
    print(json.dumps({
        "valid": True,
        "approved_profiles": len(approved),
        "approved_task_locale_grants": sum(len(profile.grants) for profile in approved),
        "explanation_approval_available": ready,
        "semantic_quality_verified_by_this_check": False,
        "runtime_routing_enabled_by_this_check": False,
    }))
    return 1 if args.require_approved and not ready else 0


if __name__ == "__main__":
    raise SystemExit(main())
