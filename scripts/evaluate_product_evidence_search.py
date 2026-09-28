#!/usr/bin/env python3
"""Explicit, local-only development trial. Never an independent accuracy claim.

Run with PYTHONPATH=services/api and the native API Python environment. Laya
settings come from the environment, or an explicitly selected protected operator
JSON file containing LAYA_API_KEY. Fixture text must be non-confidential.
"""
import argparse
import asyncio
import json
import statistics
from dataclasses import asdict
from pathlib import Path

from helvetic_lens.config import Settings
from helvetic_lens.decision_engines import DecisionUnavailable, LayaEngine
from helvetic_lens.product_evidence_search import (
    INSTRUCTIONS,
    RELEVANCE,
    literal_match,
    semantic_state,
)
from pydantic import SecretStr


async def evaluate(args):
    fixture = json.loads(Path(args.fixture).read_text())
    settings = Settings()
    if args.credentials_file:
        settings.laya_api_key = SecretStr(json.loads(Path(args.credentials_file).read_text())["LAYA_API_KEY"])
    if args.laya_base_url:
        settings.laya_base_url = args.laya_base_url
    engine = LayaEngine(settings)
    rows = []
    for value in fixture["rows"]:
        row = dict(value)
        item = {"title": "Synthetic archive fixture", "statement": "", "quote": row["quotation"]}
        row["literal_match"] = literal_match(row["query"], item)
        try:
            answer = await engine.choose(semantic_state(row["query"], item), INSTRUCTIONS, RELEVANCE)
            row.update(decision=asdict(answer), correct=answer.choice == row["expected"])
        except DecisionUnavailable as exc:
            row.update(error=exc.code, correct=False)
        rows.append(row)
    pairs = [rows[i:i + 2] for i in range(0, len(rows), 2)]
    latencies = [row["decision"]["latency_ms"] for row in rows if "decision" in row]
    result = {**fixture, "rows": rows, "local_requests": len(rows), "private_or_hosted_requests": 0,
        "cases": len(rows), "correct": sum(row["correct"] for row in rows),
        "literal_correct": sum(row["literal_match"] == (row["expected"] == "A") for row in rows),
        "mean_latency_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "max_latency_ms": max(latencies) if latencies else None,
        "positive_at_rank_one": sum("decision" in a and "decision" in b and
            a["decision"]["probabilities"]["A"] > b["decision"]["probabilities"]["A"] for a, b in pairs),
        "retrieval_pairs": len(pairs), "estimated_cost_usd": None,
        "cost_scope": "Local compute unmetered; unknown, not zero.", "pgvector_enabled": False, "embedding_requests": 0}
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ["cases", "correct", "positive_at_rank_one", "retrieval_pairs", "mean_latency_ms"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", default="demo/private-evidence-search/fixture.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--credentials-file")
    parser.add_argument("--laya-base-url")
    asyncio.run(evaluate(parser.parse_args()))
