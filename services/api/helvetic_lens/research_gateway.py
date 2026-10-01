"""The product research gateway: one dispatch policy and one execution receipt.

The job coordinator owns authorization, deadlines and transactions. This module
selects only registered capabilities and never widens a job's evidence audience.
"""
import json
import re
from copy import deepcopy

from . import search_channels
from .analysis import InferenceBudget
from .domain_packs import for_product
from .product_operations import fingerprint
from .research_contracts import SKILLS

CONTRACT = "research-execution/v1"
SEARCH_ORDER = ["saved_evidence", "reviewed_claims", "source_apis", "public_web", "evidence_synthesis"]


def route(settings, work):
    pack = for_product(work["product"])
    skill = SKILLS[work["phase"]]
    if skill.id not in pack.skill_ids:
        raise ValueError("The selected domain does not register this task")
    provider, reason = skill.provider, skill.name
    if work.get("skip"):
        provider, reason = "deterministic", "Current access or source policy excludes this operation."
    elif work.get("retained_capture"):
        provider, reason = "database", "Reuse an exact retained public capture; its capture date is unchanged."
    elif work["phase"] == "compare" and (not work["input"]["current"] or not work["input"]["previous"]):
        provider, reason = "deterministic", "There is no pair of findings to compare."
    value = {"contract": CONTRACT, "task": skill.id, "skill_version": skill.version,
        "pack_id": pack.id, "pack_version": pack.version, "provider": provider,
        "input_schema": skill.input_schema, "output_schema": skill.output_schema,
        "input_fingerprint": fingerprint({k: v for k, v in work.items()
            if k in {"input", "query", "item", "source_id", "retained_capture"}}),
        "input_references": [work["source_id"]] if work.get("source_id") else [],
        "privacy": "public_query_only" if skill.id == "search" else "authorized_evidence_only",
        "reason": reason, "model": None, "estimated_cost_usd": None,
        "cost_basis": "Unknown until measured; local hosting costs are not estimated.",
        "fallback": None}
    inputs = work.get("input", {})
    for source in [*inputs.get("sources", []), *inputs.get("saved_knowledge", {}).get("sources", [])]:
        if isinstance(source, dict) and source.get("id") and source["id"] not in value["input_references"]:
            value["input_references"].append(source["id"])
    if provider == "synthesis":
        value.update(provider=settings.apertus_provider, model=settings.apertus_model)
    if skill.id == "search":
        value["source_adapters"] = list(pack.discovery_sources)
        value["broad_provider"] = "none" if work.get("skipped_paid_search") else settings.web_search_provider
        value["skipped_paid_search"] = work.get("skipped_paid_search")
    return value


def record(settings, state, work):
    work["execution_route"] = route(settings, work)
    state["steps"][-1]["execution"] = deepcopy(work["execution_route"])
    if work.get("item"):
        state["steps"][-1]["source_url"] = work["item"]["url"]
    if work.get("source_id"):
        state["steps"][-1]["source_id"] = work["source_id"]
    if work.get("skip"):
        state["steps"][-1]["skipped"] = True


def finish(state, work, result, *, failed, elapsed):
    step = state["steps"][-1]
    receipt = step["execution"]
    receipt["latency_ms"] = round(elapsed * 1000, 2)
    receipt["outcome"] = "unavailable" if failed else "completed"
    receipt["output_reference"] = step.get("source_id") or step["id"]
    if not failed:
        serial = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        receipt["output_fingerprint"] = fingerprint(serial)
    if work.get("model_route"):
        receipt.update({key: work["model_route"].get(key) for key in
            ("provider", "model", "prompt_fingerprint", "response_schema_fingerprint")})
    if isinstance(result, dict) and work["phase"] == "gate":
        receipt["decision"] = {key: result.get(key) for key in ("engine", "model", "verdict", "confidence")}
        receipt["decision"]["measurement"] = deepcopy(result.get("usage"))
        receipt["provider"] = result.get("engine") or "unavailable"
        receipt["model"] = result.get("model")
        receipt["fallback"] = deepcopy(result.get("fallback_errors", []))
        if result.get("usage", {}).get("estimated_cost_usd") is not None:
            receipt["estimated_cost_usd"] = result["usage"]["estimated_cost_usd"]
            receipt["cost_basis"] = deepcopy(result["usage"]["cost_basis"])
    if isinstance(result, dict) and work["phase"] == "search":
        receipt["channels"] = deepcopy(result.get("retrieval", {}).get("lanes", []))
        receipt["skipped_channels"] = deepcopy(result.get("retrieval", {}).get("skipped_channels", []))
    if isinstance(result, dict) and work["phase"] == "recall":
        from .evidence_embeddings import MODEL
        receipt.update(model=MODEL, fallback=result.get("semantic_status"),
            prepared_records=result.get("prepared_records"), preparing=result.get("pending", False))


async def complete(service, work, system, schema, seconds):
    if SKILLS[work["phase"]].provider != "synthesis":
        raise ValueError("This registered task must not call the synthesis model")
    work["model_route"] = {"provider": service.settings.apertus_provider, "model": service.settings.apertus_model,
        "prompt_fingerprint": fingerprint(system), "response_schema_fingerprint": fingerprint(schema.model_json_schema()),
        "basis": "Configured model for this request; not an independently verified serving identity."}
    return await service.model_client.complete(system, json.dumps(work["input"], ensure_ascii=False),
        response_schema=schema.model_json_schema(), budget=InferenceBudget(max_requests=1, max_seconds=seconds))


async def execute(service, work, seconds):
    from . import decision_search, decision_sources, product_iterative_steps

    if route(service.settings, work) != work["execution_route"]:
        raise ValueError("Research routing configuration changed after dispatch")
    if work.get("retained_capture"):
        return deepcopy(work["retained_capture"])
    if work.get("research") and work["phase"] != "compare":
        return await product_iterative_steps.execute(service, work, seconds)
    if work["phase"] == "search":
        result = await decision_search.execute(search_channels.request_settings(service.settings, work.get("skipped_paid_search")),
            work["query"], "auto", "balanced", work["product"])
        search_channels.note_skipped_paid(result.setdefault("retrieval", {}), work.get("skipped_paid_search"))
        return result
    if work["phase"] == "read":
        if work.get("file"):
            from .product_contributions import read_file

            return await read_file(service.environment_settings.storage_path / "artifacts", work["file"])
        return await decision_sources.safe_inspect(service.settings, work["query"], work["item"], "auto",
            rank_passages=False, excerpt_limit=8)
    if work["phase"] == "compare":
        from .product_claim_evolution import SYSTEM, Comparison

        if work["execution_route"]["provider"] == "deterministic":
            return Comparison()
        schema = Comparison
    else:
        from .product_investigation_worker import SYSTEM
        from .product_investigations import Extraction

        schema = Extraction
    raw = await complete(service, work, SYSTEM, schema, seconds)
    if not isinstance(raw, str) or len(raw) > (10000 if work["phase"] == "compare" else 30000):
        raise ValueError("Unbounded research response")
    return schema.model_validate_json(re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip()))
