"""Run the checked-in HL-051 relation-candidate gate."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from helvetic_lens.candidate_benchmark import run_benchmark

result = run_benchmark(ROOT / "demo" / "relation-candidate-benchmark.json")
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(1 if result["pgvector_enabled"] else 0)
