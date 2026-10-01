"""The product research gateway: one dispatch policy and one execution receipt.

The job coordinator owns authorization, deadlines and transactions. This module
selects only registered capabilities and never widens a job's evidence audience.
"""
import json
import re
from copy import deepcopy
from time import monotonic

from pydantic import ValidationError

from . import search_channels
from .analysis import InferenceBudget, ModelClient
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
    elif work.get("retained_document") or work.get("file"):
        provider, reason = "local_reader", "Continue reading the same retained original without another web fetch."
    elif work.get("retained_capture"):
        provider, reason = "database", "Reuse an exact retained public capture; its capture date is unchanged."
    elif work["phase"] == "compare" and (not work["input"]["current"] or not work["input"]["previous"]):
        provider, reason = "deterministic", "There is no pair of findings to compare."
    value = {"contract": CONTRACT, "task": skill.id, "skill_version": skill.version,
        "pack_id": pack.id, "pack_version": pack.version, "provider": provider,
        "input_schema": skill.input_schema, "output_schema": skill.output_schema,
        "input_fingerprint": fingerprint({k: v for k, v in work.items()
            if k in {"input", "query", "item", "source_id", "retained_capture", "document_cursor", "document_sha256", "retained_document"}}),
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
    if "document_index" in work:
        state["steps"][-1]["document_index"] = work["document_index"]
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
            ("provider", "model", "prompt_fingerprint", "response_schema_fingerprint", "output_allowance", "format_repair", "model_usage", "model_requests")})
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
    client = service.model_client
    token = client.begin_trace("background") if isinstance(client, ModelClient) else None
    try:
        return await _complete(service, work, system, schema, seconds)
    finally:
        if token is not None:
            events = client.end_trace(token)
            route = work.setdefault("model_route", {})
            route["model_usage"] = [{k: v for k, v in event["usage"].items()
                if k in {"prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"}
                and type(v) is int and v >= 0} for event in events if isinstance(event.get("usage"), dict)]
            route["model_requests"] = sum(event.get("outcome") in {"success", "error"} for event in events)


async def _complete(service, work, system, schema, seconds):
    if SKILLS[work["phase"]].provider != "synthesis":
        raise ValueError("This registered task must not call the synthesis model")
    system += """\nReturn one compact JSON object, with schema properties at the root, never
wrapped in a schema name. Enum values are exact and case-sensitive. Use brief
statements and the shortest sufficient verbatim quotes, not entire paragraphs.
Optional unsupported details must be omitted, not invented. Keep all required
fields, especially document section coverage. Prefer a few useful findings over
repeating the same fact in claims, entities and observations. Finish the JSON.
"""
    options = {}
    if (work.get("unmetered_research") and isinstance(service.model_client, ModelClient)
            and service.settings.apertus_provider != "docker" and work["phase"] in {"extract", "brief", "document_review"}):
        options["max_output_tokens"] = max(4096, service.settings.apertus_max_tokens)
    work["model_route"] = {"provider": service.settings.apertus_provider, "model": service.settings.apertus_model,
        "output_allowance": options.get("max_output_tokens", service.settings.apertus_max_tokens),
        "prompt_fingerprint": fingerprint(system), "response_schema_fingerprint": fingerprint(schema.model_json_schema()),
        "basis": "Configured model for this request; not an independently verified serving identity."}
    started = monotonic()
    content = json.dumps(work["input"], ensure_ascii=False)
    raw = await service.model_client.complete(system, content,
        response_schema=schema.model_json_schema(), budget=InferenceBudget(max_requests=1, max_seconds=seconds), **options)
    raw = response_object(raw, schema)
    # Hosted JSON mode does not enforce the schema. Repair the format once with
    # the same evidence, never by accepting unsupported or guessed fields.
    if isinstance(service.model_client, ModelClient) and work.get("unmetered_research"):
        errors = []
        try:
            if work["phase"] == "extract":
                from .product_question_renewal import parse_recoverable
                parsed = parse_recoverable(schema, raw, {key: "_" + key + "_unavailable" for key in
                    ("applicability_checks", "entities", "relationships", "source_class", "read_relevance", "professional_facts")})
                errors = extraction_citation_errors(parsed, work)
            else:
                schema.model_validate_json(raw)
        except ValidationError as exc:
            errors = [{"path": list(e["loc"]), "reason": e["msg"]} for e in exc.errors(include_input=False, include_url=False)][:16]
        if errors:
            remaining = seconds - (monotonic() - started)
            if remaining > 5:
                work["model_route"]["format_repair"] = True
                raw = await service.model_client.complete(system + "\nThe previous response failed validation. Correct these validation errors using the original evidence. Omit unsupported optional fields. Do not invent a quote or locator.\n" + json.dumps(errors[:16]),
                    json.dumps({"original_evidence": work["input"], "previous_invalid_response": raw[:30000]}, ensure_ascii=False),
                    response_schema=schema.model_json_schema(), budget=InferenceBudget(max_requests=1, max_seconds=remaining), **options)
    return response_object(raw, schema)


def extraction_citation_errors(result, work):
    """Give the model actionable feedback before the unchanged strict write gate."""
    passages = {p["passage"]: p["text"] for p in work["input"].get("source", {}).get("excerpts", [])}
    groups = [("claims", result.claims)]
    review = getattr(result, "section_review", None)
    if review:
        groups.extend(("section_review." + key, getattr(review, key)) for key in ("observations", "cross_references"))
    errors = [{"path": [key, i, "quote"],
        "reason": "Quote must be an exact substring of the supplied passage at this locator. Copy its exact words; do not paraphrase, concatenate or cite the question."}
        for key, values in groups for i, value in enumerate(values)
        if value.locator not in passages or value.quote not in passages[value.locator]]
    for i, value in enumerate(result.claims):
        if (value.relation == "SUPPORTS" and not value.existing_claim_id
                and not numeric_tokens(value.statement) <= numeric_tokens(value.quote)):
            errors.append({"path": ["claims", i, "statement"], "reason":
                "A directly supported new claim may not introduce numbers absent from its quote. Preserve the quoted quantities and units; leave derived calculations for an explicitly explained analysis."})
    if review:
        for i, value in enumerate(review.observations):
            if value.role == "support" and not numeric_tokens(value.statement) <= numeric_tokens(value.quote):
                errors.append({"path": ["section_review.observations", i, "statement"], "reason":
                    "A supported observation must preserve the quoted quantities, without invented numbers or unverified calculations."})
    return errors


def numeric_tokens(text):
    # Preserve decimal separators: no guessed locale or implicit unit conversion.
    return set(re.findall(r"(?<!\w)\d+(?:[.,]\d+)*", text))


def retain_grounded_items(result, work):
    """Keep independently verified siblings; rejected proposals remain named gaps."""
    errors = extraction_citation_errors(result, work)
    rejected = {}
    for error in errors:
        key, index = error["path"][:2]
        rejected.setdefault(key, set()).add(index)
    for key, indices in rejected.items():
        owner, field = (result.section_review, key.split(".")[1]) if key.startswith("section_review.") else (result, key)
        setattr(owner, field, [value for i, value in enumerate(getattr(owner, field)) if i not in indices])
    if rejected:
        result._analysis_gaps = {key: len(indices) for key, indices in rejected.items()}
        review = getattr(result, "section_review", None)
        if review:
            review.limitations = [*review.limitations,
                "Some proposed findings could not be grounded in exact source passages and were rejected. Their absence is not a negative finding; these interpretation gaps remain unresolved."]
    return result


def response_object(raw, schema):
    """Remove presentation only, never infer missing evidence or field values."""
    if not isinstance(raw, str):
        return raw
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        data = json.loads(raw)
    except ValueError:
        return raw  # Required schema validation will reject malformed JSON.
    title = schema.model_json_schema().get("title", schema.__name__)
    if isinstance(data, dict) and set(data) == {title} and isinstance(data[title], dict):
        return json.dumps(data[title], ensure_ascii=False)
    return raw


async def execute(service, work, seconds):
    from . import decision_search, decision_sources, product_iterative_steps

    if route(service.settings, work) != work["execution_route"]:
        raise ValueError("Research routing configuration changed after dispatch")
    if work["phase"] == "document_review":
        from .product_document_analysis import execute as review_document
        return await review_document(service, work, seconds)
    if work.get("retained_document"):
        from .product_document_storage import read as read_original
        return await read_original(service, work)
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
            rank_passages=False, excerpt_limit=8, **({"retain_original": {"folder": service.environment_settings.storage_path / "artifacts", "prefix": work["run_id"] + "-" + work["branch_id"]}} if "document_cursor" in work else {}), **({"document_cursor": work["document_cursor"]} if "document_cursor" in work else {}))
    if work["phase"] == "compare":
        from .product_claim_evolution import SYSTEM, Comparison

        if work["execution_route"]["provider"] == "deterministic":
            return Comparison()
        schema = Comparison
    else:
        from .product_investigation_worker import SYSTEM
        from .product_professional_context import SYSTEM as professional_system
        from .product_professional_context import ProfessionalExtraction

        SYSTEM += professional_system
        schema = ProfessionalExtraction
    if work.get("input", {}).get("document_section"):
        from . import product_document_analysis as document_analysis
        schema, SYSTEM = document_analysis.schema(schema), SYSTEM + document_analysis.SECTION_SYSTEM
    raw = await complete(service, work, SYSTEM, schema, seconds)
    if not isinstance(raw, str) or len(raw) > (10000 if work["phase"] == "compare" else 30000):
        raise ValueError("Unbounded research response")
    return schema.model_validate_json(re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip()))
