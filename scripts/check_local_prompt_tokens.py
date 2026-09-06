"""Offline protocol smoke test in a disposable CPU container, never the live runner.

Mount an existing model read-only and the current model_manager package on
PYTHONPATH. This starts its own loopback server, tests synthetic text only and
terminates that child. It does not approve model quality or benchmark GPUs.
"""

import argparse
import asyncio
import hashlib
import json
import tempfile
import time
from pathlib import Path

import httpx
from model_manager.prompt_budget import measure_prompt


async def check(args):
    address = "http://127.0.0.1:18099"
    snapshot = {
        "binding_fingerprint": "a" * 64, "deployment_id": "a" * 32,
        "context_window_tokens": 1024, "default_output_tokens": 8,
    }
    command = [
        args.runner, "-m", args.model, "--alias", "token-smoke", "--host", "127.0.0.1", "--port", "18099",
        "--chat-template-file", args.template, "--ctx-size", "1024", "--parallel", "1", "--n-predict", "8",
        "--n-gpu-layers", "0", "--threads", "2", "--threads-batch", "2", "--no-warmup",
    ]
    with tempfile.TemporaryFile() as log:
        process = await asyncio.create_subprocess_exec(*command, stdout=log, stderr=asyncio.subprocess.STDOUT)
        try:
            async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
                deadline = time.monotonic() + 90
                while True:
                    if process.returncode is not None:
                        raise RuntimeError("Disposable runner exited before becoming healthy")
                    try:
                        ready = (await client.get(address + "/health")).is_success
                    except httpx.HTTPError:
                        ready = False
                    if ready:
                        break
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Disposable runner did not become ready")
                    await asyncio.sleep(0.25)
                props = (await client.get(address + "/props")).json()
                results = []
                examples = [
                    ("de-CH", "Erkläre diese synthetische Änderung: zehn statt fünf Tage."),
                    ("fr-CH", "Explique cette modification fictive : dix jours au lieu de cinq."),
                    ("it-CH", "Spiega questa modifica fittizia: dieci giorni invece di cinque."),
                    ("rm-CH", "Explitga questa midada fictiva: diesch dis empè da tschintg."),
                    ("en-CH", "Explain this synthetic change: ten days instead of five. 🧪"),
                    ("repair", 'Repair this synthetic malformed result: {"answer": . Return {"answer":"test"}.'),
                ]
                for name, question in examples:
                    payload = {
                        "model": "token-smoke", "messages": [
                            {"role": "system", "content": 'Synthetic evidence only. Return one JSON object with an "answer" string.'},
                            {"role": "user", "content": question},
                        ],
                        "max_tokens": 8, "stream": False, "temperature": 0,
                        "response_format": {"type": "json_object", "schema": {
                            "type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"],
                        }},
                    }
                    body = json.dumps(payload).encode()
                    measured = await measure_prompt(client, {"url": address}, snapshot, payload, body)
                    assert measured["fits"]
                    response = await client.post(address + "/v1/chat/completions", content=body, headers={"content-type": "application/json"})
                    response.raise_for_status()
                    actual = response.json()["usage"]["prompt_tokens"]
                    assert actual == measured["input_tokens"], (name, measured, actual)
                    results.append({"case": name, "measured_input_tokens": actual, "usage_prompt_tokens": actual})
                payload["messages"][1]["content"] = "Synthetic oversized evidence. " * 300
                body = json.dumps(payload).encode()
                large = await measure_prompt(client, {"url": address}, snapshot, payload, body)
                assert not large["fits"] and large["input_tokens"] > 1024
                # Counting an oversized input is allowed; generation is not requested.
                return {
                    "status": "passed", "scope": "offline CPU tokenizer/template protocol only",
                    "build_info": props.get("build_info"), "context_tokens": props["default_generation_settings"]["n_ctx"],
                    "model_file": Path(args.model).name,
                    "template_sha256": hashlib.sha256(Path(args.template).read_bytes()).hexdigest(),
                    "cases": results, "oversized_count_only": large["input_tokens"],
                }
        except BaseException:
            log.seek(0, 2)
            size = log.tell()
            log.seek(max(0, size - 4000))
            print(log.read().decode(errors="replace"))
            raise
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 10)
                except TimeoutError:
                    process.kill()
                    await process.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", default="/app/llama-server")
    parser.add_argument("--model", required=True)
    parser.add_argument("--template", required=True)
    print(json.dumps(asyncio.run(check(parser.parse_args())), indent=2))
