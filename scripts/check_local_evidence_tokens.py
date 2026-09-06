"""Count-only allocation check against a disposable localhost native runner.

Requires the API dependencies and services/model-manager on PYTHONPATH. The
caller owns the isolated runner lifecycle. No generation, credentials, model
download or application database is used. Synthetic pins below identify only
this protocol fixture; they are not evidence of a production deployment lease.
"""

import argparse
import asyncio
import copy
import json
from urllib.parse import urlsplit

import httpx
from helvetic_lens.analysis import LocalAnswerSignal, ModelClient
from helvetic_lens.config import Settings
from helvetic_lens.runtime_binding import PromptTokenMeasurement
from helvetic_lens.token_evidence import fit_numbered_evidence
from model_manager.prompt_budget import measure_prompt


class NativeCounter(ModelClient):
    def __init__(self, settings, connection, address, snapshot):
        super().__init__(settings)
        self.connection, self.address, self.snapshot = connection, address, snapshot

    async def count_prompt(self, system, user, *, response_schema, budget=None):
        wire = self.chat_payload(system, user, response_schema=response_schema)
        measured = await measure_prompt(
            self.connection, {"url": self.address}, self.snapshot, wire, json.dumps(wire).encode(),
        )
        return PromptTokenMeasurement.model_validate(measured)


async def check(args):
    if urlsplit(args.base_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Use a disposable localhost runner, not a shared/provider endpoint")
    configuration = Settings(_env_file=None, apertus_provider="docker", apertus_model=args.model, apertus_max_tokens=700)
    cases = []
    async with httpx.AsyncClient(timeout=30, trust_env=False) as connection:
        props_response = await connection.get(args.base_url + "/props")
        props_response.raise_for_status()
        props = props_response.json()
        snapshot = {
            "binding_fingerprint": "a" * 64, "deployment_id": "a" * 32,
            "context_window_tokens": props["default_generation_settings"]["n_ctx"], "default_output_tokens": 700,
        }
        model = NativeCounter(configuration, connection, args.base_url, snapshot)
        for locale, sentence in [
            ("de-CH", "Dies ist ein fiktives Dokument für einen technischen Test."),
            ("fr-CH", "Ce document fictif sert uniquement à un test technique."),
            ("it-CH", "Questo documento fittizio serve solo per un test tecnico."),
            ("rm-CH", "Quest document fictiv serva mo per in test tecnic."),
            ("en-CH", "This fictional document is only used for a technical test."),
        ]:
            evidence = [{
                "version_id": side, "passage_id": f"p{index}", "change_id": f"c{index}",
                "change_kind": "modified", "side": side,
                "text": sentence * 100 + (" Five days." if side == "old" else " Ten days."),
            } for index in range(4) for side in ("old", "new")]
            original = copy.deepcopy(evidence)
            payload = {
                "question": "Show the synthetic change.", "output_locale": locale,
                "evidence": {"columns": ["row_number", "change_id", "side", "text"], "rows": [
                    [number, item["change_id"], item["side"], item["text"]] for number, item in enumerate(evidence, 1)
                ]},
                "coverage": {"complete": True, "limited": False},
            }
            system = "Use only synthetic supplied evidence. Select supporting citation_rows and supported. Return JSON."
            allocation = {}
            selected, allowed, schema = await fit_numbered_evidence(
                model, system, payload, LocalAnswerSignal.model_json_schema(), evidence, None, allocation,
            )
            assert allocation["limited"] and 1 < allocation["count_probes"] <= 8
            assert not allocation["measurements"][0]["fits"]
            assert len(allowed) % 2 == 0 and allowed
            assert [item["text"] for item in evidence] == [item["text"] for item in original]
            for row, span in zip(selected["evidence"]["rows"], allocation["windows"], strict=True):
                source = original[row[0] - 1]["text"]
                assert row[-1] == source[span["start"]:span["start"] + span["characters"]]
            # Independent final native recount of exactly the chosen full wire
            # body; this still does not decode text or certify semantic quality.
            final = await model.count_prompt(system, json.dumps(selected, ensure_ascii=False), response_schema=schema)
            assert final.model_dump(mode="json") == allocation["measurements"][-1]
            assert final.fits
            cases.append({
                "locale": locale, "initial_tokens": allocation["measurements"][0]["input_tokens"],
                "selected_tokens": final.input_tokens, "reserved_output": final.reserved_output_tokens,
                "safety": final.safety_tokens, "count_probes": allocation["count_probes"],
                "retained_rows": allocation["row_numbers"], "excerpted": sum(item["excerpted"] for item in allocation["windows"]),
            })
    return {"status": "passed", "scope": "synthetic native count-only allocation; no generation or quality approval",
            "build_info": props.get("build_info"), "context_tokens": snapshot["context_window_tokens"], "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", default="token-smoke")
    print(json.dumps(asyncio.run(check(parser.parse_args())), indent=2))
