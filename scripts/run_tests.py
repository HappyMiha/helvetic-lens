"""Run an API tier with explicit bounded workers and reproducible diagnostics."""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("smoke", "functional", "integration", "release", "full"), default="full")
    parser.add_argument("--workers", type=int, choices=range(5), default=2,
                        help="0 for serial diagnostics; at most four isolated workers (default: 2).")
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--junitxml", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, "-m", "pytest", "-c", "services/api/pyproject.toml",
               "-p", "no:cacheprovider", "services/api/tests", "--test-suite", args.suite,
               "-vv", "--durations=25", "-o", "faulthandler_timeout=120"]
    if args.collect_only:
        command.append("--collect-only")
    elif args.workers:
        command.extend(["-n", str(args.workers), "--dist=loadfile", "--max-worker-restart=0"])
    if args.fail_fast:
        command.append("--maxfail=1")
    if args.junitxml:
        command.extend(["--junitxml", str(args.junitxml.resolve())])
    return subprocess.call(command, cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
