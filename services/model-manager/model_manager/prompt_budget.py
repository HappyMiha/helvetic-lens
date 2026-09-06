"""Measure a complete chat request on the reserved llama.cpp runner, without decoding."""

from __future__ import annotations

import asyncio
import hashlib
import json

import httpx

from .core import ModelManagerError

SCHEMA = "local-prompt-budget-v1"
SAFETY_TOKENS = 128
PREFLIGHT_SECONDS = 10


def request_fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
    ).encode()).hexdigest()


def output_reserve(payload: dict, snapshot: dict) -> int:
    # Do not guess precedence between llama.cpp's native and OAI aliases.
    limits = [payload[key] for key in ("max_tokens", "max_completion_tokens", "n_predict") if key in payload]
    if not limits:
        limits = [snapshot["default_output_tokens"]]
    if any(type(value) is not int or not 1 <= value <= 1048576 for value in limits) or len(set(limits)) != 1:
        raise ModelManagerError(
            "Use one positive output token limit; conflicting or unlimited token settings are not supported.",
            422, "invalid_output_token_limit",
        )
    if "n" in payload and (type(payload["n"]) is not int or payload["n"] != 1):
        raise ModelManagerError("Local inference supports one response per request.", 422, "invalid_response_count")
    return limits[0]


async def measure_prompt(client: httpx.AsyncClient, target: dict, snapshot: dict, payload: dict, body: bytes) -> dict:
    """Caller owns admission and the deployment lease until generation completes.

    The pinned runner's input_tokens handler uses its chat parser, template and
    tokenize_mixed(..., true, true), including BOS/control/generation-prefix tokens.
    No separate tokenizer, character ratio, template reimplementation or inference.
    """
    output = output_reserve(payload, snapshot)
    try:
        fingerprint = request_fingerprint(payload)
        async with asyncio.timeout(PREFLIGHT_SECONDS):
            props_response = await client.get(target["url"] + "/props", timeout=PREFLIGHT_SECONDS)
            props_response.raise_for_status()
            props = props_response.json()
            context = props["default_generation_settings"]["n_ctx"]
            if type(context) is not int or not 1 <= context <= 1048576 or type(props.get("total_slots")) is not int or props["total_slots"] != 1:
                raise ValueError("Unverified per-slot context")
            counted = await client.post(
                target["url"] + "/v1/chat/completions/input_tokens", content=body,
                headers={"content-type": "application/json"}, timeout=PREFLIGHT_SECONDS,
            )
            counted.raise_for_status()
            data = counted.json()
            tokens = data["input_tokens"]
            if data.get("object") != "response.input_tokens" or type(tokens) is not int or tokens < 1:
                raise ValueError("Unverified input count")
    except (httpx.HTTPError, TimeoutError, ValueError, TypeError, KeyError) as exc:
        # Fail once, before generation. Retrying unchanged prompts or falling back
        # to an estimate would defeat the guard. Never expose raw provider bodies.
        raise ModelManagerError(
            "The local runner could not verify the complete prompt token budget. No generation was started. "
            "Check the pinned llama.cpp runtime and its input_tokens/props endpoints.",
            422, "token_budget_unavailable",
        ) from exc
    effective_context = min(context, snapshot["context_window_tokens"])
    return {
        "schema_version": SCHEMA,
        "method": "llama_cpp_chat_input_tokens",
        "request_sha256": fingerprint,
        "binding_fingerprint": snapshot["binding_fingerprint"],
        "deployment_id": snapshot["deployment_id"],
        "input_tokens": tokens,
        "reserved_output_tokens": output,
        "safety_tokens": SAFETY_TOKENS,
        "context_window_tokens": effective_context,
        "runner_context_tokens": context,
        "fits": tokens + output + SAFETY_TOKENS <= effective_context,
    }
