"""Run the repeatable HL-032 structured-output and concurrency benchmark."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path


def request_json(url: str, payload: dict | None = None, headers: dict | None = None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST" if payload is not None else "GET",
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=300) as response:
        value = json.loads(response.read())
        return value, response.headers, (time.monotonic() - started) * 1000


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "supported": {"type": "boolean"},
        "impact": {"type": "string", "enum": ["low", "medium", "high"]},
        "citation_rows": {
            "type": "array",
            "items": {"type": "integer", "minimum": 1, "maximum": 3},
            "maxItems": 3,
        },
    },
    "required": ["supported", "impact", "citation_rows"],
}


def call(base_url: str, model: str, index: int, padding: int = 0):
    evidence = (
        "Row 1: deadline changed from 30 to 45 days. "
        "Row 2: contact title changed. Row 3: formatting only. " + ("legal text " * padding)
    )
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Return only the requested JSON. Cite rows 1 to 3 only.",
            },
            {
                "role": "user",
                "content": f"Structured regulatory test {index}. Evidence: {evidence}",
            },
        ],
        "temperature": 0,
        "max_tokens": 80,
        "response_format": {"type": "json_object", "schema": SCHEMA},
    }
    try:
        envelope, headers, elapsed = request_json(
            base_url + "/openai/v1/chat/completions",
            payload,
            {"X-Helvetic-Organization": f"benchmark-{index % 3}", "X-Helvetic-Priority": "interactive"},
        )
        content = json.loads(envelope["choices"][0]["message"]["content"])
        schema_valid = (
            isinstance(content.get("supported"), bool)
            and content.get("impact") in {"low", "medium", "high"}
            and isinstance(content.get("citation_rows"), list)
        )
        citation_valid = all(value in {1, 2, 3} for value in content.get("citation_rows", []))
        timings = envelope.get("timings", {})
        return {
            "index": index,
            "ok": schema_valid and citation_valid,
            "schema_valid": schema_valid,
            "citation_valid": citation_valid,
            "latency_ms": round(elapsed, 2),
            "queue_wait_ms": float(headers.get("x-helvetic-queue-wait-ms", 0)),
            "slot": headers.get("x-helvetic-slot"),
            "prompt_tokens": envelope.get("usage", {}).get("prompt_tokens"),
            "completion_tokens": envelope.get("usage", {}).get("completion_tokens"),
            "tokens_per_second": timings.get("predicted_per_second"),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 - benchmark must retain every failed sample
        return {
            "index": index,
            "ok": False,
            "schema_valid": False,
            "citation_valid": False,
            "latency_ms": None,
            "queue_wait_ms": None,
            "slot": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "tokens_per_second": None,
            "error": f"{type(exc).__name__}: {exc}"[:500],
        }


def gpu_sample():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return [int(row.strip()) for row in result.stdout.splitlines() if row.strip()]
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:12436")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    inventory, _, _ = request_json(args.base_url + "/v1/inventory")
    deployment = inventory.get("deployment") or {}
    if deployment.get("state") not in {"ready", "degraded"}:
        raise SystemExit("Start a verified local model before benchmarking.")
    model = deployment["served_model_id"]
    peak_vram = gpu_sample()
    peak_runner_rss = (inventory.get("runtime_metrics") or {}).get("runner_rss_bytes", 0)
    stop = threading.Event()

    def sample_gpu():
        nonlocal peak_vram, peak_runner_rss
        while not stop.wait(0.1):
            current = gpu_sample()
            if len(current) > len(peak_vram):
                peak_vram.extend([0] * (len(current) - len(peak_vram)))
            peak_vram = [max(old, current[i] if i < len(current) else 0) for i, old in enumerate(peak_vram)]
            try:
                live, _, _ = request_json(args.base_url + "/v1/inventory")
                peak_runner_rss = max(
                    peak_runner_rss,
                    (live.get("runtime_metrics") or {}).get("runner_rss_bytes", 0),
                )
            except OSError:
                pass

    sampler = threading.Thread(target=sample_gpu, daemon=True)
    sampler.start()
    # Twenty representative schema-constrained calls, including progressively
    # larger evidence payloads to measure stable context rather than advertise it.
    paddings = [0, 100, 500, 1000, 1500] * 4
    samples = [call(args.base_url, model, index + 1, padding) for index, padding in enumerate(paddings)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        concurrent = list(pool.map(lambda value: call(args.base_url, model, value, 20), [101, 102]))
    stop.set()
    sampler.join(timeout=2)
    successful = [sample for sample in samples if sample["ok"]]
    tps = [sample["tokens_per_second"] for sample in successful if sample["tokens_per_second"]]
    latencies = [sample["latency_ms"] for sample in successful]
    report = {
        "benchmark": "HL-032-local-structured-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "deployment": deployment,
        "hardware": inventory.get("hardware"),
        "runtime_image": inventory.get("runtime_image"),
        "representative_calls": {
            "total": len(samples),
            "successful": len(successful),
            "schema_valid": sum(sample["schema_valid"] for sample in samples),
            "citation_valid": sum(sample["citation_valid"] for sample in samples),
            "timeouts": sum("timed out" in (sample["error"] or "").lower() for sample in samples),
            "oom": sum("memory" in (sample["error"] or "").lower() for sample in samples),
            "latency_ms_median": round(statistics.median(latencies), 2) if latencies else None,
            "tokens_per_second_median": round(statistics.median(tps), 2) if tps else None,
            "maximum_stable_prompt_tokens": max(
                (sample["prompt_tokens"] or 0 for sample in successful), default=0
            ),
            "samples": samples,
        },
        "concurrent_pair": {
            "required_profile": "dual-1080-replicated",
            "profile_matched": deployment.get("hardware_profile") == "dual-1080-replicated",
            "successful": sum(sample["ok"] for sample in concurrent),
            "distinct_slots": sorted({sample["slot"] for sample in concurrent if sample["slot"]}),
            "samples": concurrent,
        },
        "peak_gpu_memory_mib": peak_vram,
        "peak_runner_ram_bytes": peak_runner_rss,
        "load_time_ms": (
            round(
                (
                    datetime.fromisoformat(deployment["ready_at"])
                    - datetime.fromisoformat(deployment["started_at"])
                ).total_seconds()
                * 1000,
                2,
            )
            if deployment.get("ready_at") and deployment.get("started_at")
            else None
        ),
        "accepted_slots": deployment.get("accepted_slots"),
        "result": "pass" if len(successful) == 20 and all(sample["ok"] for sample in concurrent) else "fail",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("representative_calls", "concurrent_pair", "result")}, indent=2))


if __name__ == "__main__":
    main()
