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
from .config import DomainError
from .domain_packs import for_product
from .product_operations import fingerprint
from .research_contracts import SKILLS

CONTRACT = "research-execution/v1"
SEARCH_ORDER = ["saved_evidence", "reviewed_claims", "source_apis", "public_web", "evidence_synthesis"]
ANSWER_WORKFLOW = "selected-evidence-one-cited-draft/v3"


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
            ("provider", "model", "prompt_fingerprint", "response_schema_fingerprint", "output_allowance", "format_repair", "answer_review", "model_usage", "model_requests", "evidence_transport", "resumed_stage")})
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
    wire = None
    if (work.get("unmetered_research") and isinstance(service.model_client, ModelClient)
            and work["phase"] in {"plan", "extract", "brief", "reflect", "orient", "document_review"}):
        from .research_model_transport import EvidenceWire
        wire = EvidenceWire(work, schema, system)
        system = wire.system
    response_schema = wire.schema if wire else schema.model_json_schema()
    provider_input = wire.input if wire else work["input"]
    if (work.get("unmetered_research") and isinstance(service.model_client, ModelClient)
            and service.settings.apertus_provider != "docker" and work["phase"] in {"extract", "brief", "document_review"}):
        options["max_output_tokens"] = max(4096, service.settings.apertus_max_tokens)
    work["model_route"] = {"provider": service.settings.apertus_provider, "model": service.settings.apertus_model,
        "output_allowance": options.get("max_output_tokens", service.settings.apertus_max_tokens),
        "prompt_fingerprint": fingerprint(system), "response_schema_fingerprint": fingerprint(response_schema),
        "basis": "Configured model for this request; not an independently verified serving identity."}
    started = monotonic()
    if wire:
        work["model_route"]["evidence_transport"] = wire.receipt
    from .research_synthesis_resume import EXHAUSTED_REVIEW, PROVIDER_INTERRUPTION

    exhausted = work.get(EXHAUSTED_REVIEW, {})
    work["allow_checked_partial_delivery"] = False
    content = json.dumps(provider_input, ensure_ascii=False)
    resume = None
    selected = None
    if wire and (wire.answer or work["phase"] in {"reflect", "orient"}) and service.settings.apertus_provider != "docker":
        from . import research_evidence_pack as evidence_pack
        from .research_synthesis_resume import KEY, DraftCheckpoint

        workflow = ANSWER_WORKFLOW if wire.answer else "research-reflection/v1-local-evidence"
        if work["phase"] == "orient":
            workflow = "research-orientation/v1-local-evidence"
        previous_checkpoint = work.get(KEY)
        resume = DraftCheckpoint(work, service.settings, system, workflow, response_schema, content, options,
            preparation_policy=evidence_pack.POLICY)
        if previous_checkpoint and resume.value is None:
            work["synthesis_checkpoint_invalidated"] = True
        if resume.value:
            work["model_route"]["resumed_stage"] = resume.value["stage"]
        if wire.answer:
            work["model_route"]["answer_review"] = deepcopy((resume.value or {}).get("review") or {})
            work["model_route"]["answer_review"].update(contract="cited-answer-review/v2", workflow=ANSWER_WORKFLOW)

        def retain_selection():
            state = resume.value or {}
            resume.save(state.get("stage", "preparing"), state.get("raw", ""),
                state.get("hints", []), work["model_route"].get("answer_review", {}))

        retain_selection()
        selected = await evidence_pack.select_evidence(service, wire, wire.input["original_question"],
            seconds - (monotonic() - started), checkpoints=resume.parts, on_progress=retain_selection)
        if work["phase"] == "orient" and not selected:
            raise DomainError("Early orientation needs a retained original passage; research remains unfinished.",
                503, "research_evidence_pack_incomplete")
        # Native reading, access checks and later corrections retain the entire
        # authorized wire. Only this provider request uses the selected originals.
        provider_input = evidence_pack.provider_input(wire, selected)
        response_schema = evidence_pack.bounded_schema(wire.schema, selected)
        content = json.dumps(provider_input, ensure_ascii=False)
        previous_value = resume.value
        resume.bind_request(response_schema, content)
        if previous_value and resume.value is None:
            work["synthesis_checkpoint_invalidated"] = True
        work["allow_checked_partial_delivery"] = bool(wire.answer and resume.value
            and resume.value.get("stage") == "finalizing"
            and exhausted.get("reason") in PROVIDER_INTERRUPTION
            and exhausted.get("input_fingerprint") == wire.receipt["input_fingerprint"]
            and exhausted.get("checkpoint_binding") == resume.binding)
        if exhausted and not work["allow_checked_partial_delivery"]:
            work.pop(EXHAUSTED_REVIEW, None)
            work["exhausted_review_invalidated"] = True
        if resume.value is None:
            work["model_route"].pop("resumed_stage", None)
            if wire.answer:
                work["model_route"]["answer_review"] = {"contract": "cited-answer-review/v2", "workflow": ANSWER_WORKFLOW}
        retain_selection()
        work["model_route"].update(response_schema_fingerprint=fingerprint(response_schema),
            provider_input_fingerprint=fingerprint(provider_input))
        work["model_route"]["evidence_transport"].update(selected_references=len(selected),
            provider_input_characters=len(content))
    # Early orientation and reflection retain selection progress only, never final-answer
    # draft/review stages or publishes a cached proposal as a research decision.
    saved = resume.value if resume and wire.answer and resume.value and resume.value["stage"] != "preparing" else None
    if saved:
        raw = saved["raw"]
        work["model_route"]["resumed_stage"] = saved["stage"]
        work["model_route"]["answer_review"] = deepcopy(saved.get("review") or {})
    else:
        remaining = seconds - (monotonic() - started)
        if resume and remaining < 8:
            raise DomainError("The selected evidence is retained; analysis will continue in the next work step.",
                503, "research_evidence_pack_incomplete")
        raw = await service.model_client.complete(system, content,
            response_schema=response_schema,
            budget=InferenceBudget(max_requests=1, max_seconds=remaining), **options)
    if wire and wire.answer:
        work["model_route"].setdefault("answer_review", {}).update(
            contract="cited-answer-review/v2", workflow=ANSWER_WORKFLOW)
    review_hints = deepcopy(saved.get("hints", [])) if saved else []
    if resume and wire.answer and not saved:
        resume.save("draft", raw, review_hints, work["model_route"]["answer_review"])
    raw = response_object(raw, schema)
    wire_raw = raw

    async def reading_before_publication(parsed):
        if not wire or not wire.answer or saved and saved["stage"] == "finalizing":
            work["publication_review_started"] = True
            return False
        from .product_research_mission import route_continuation
        from .research_answer_review import audit, original_check

        review = work["model_route"]["answer_review"]
        checkpoint = parsed.mission_checkpoint

        def retain_routing():
            if resume:
                resume.save("reviewed", wire.encode_checkpoint(parsed), review_hints, review)

        if work.get("mission_continuation") and checkpoint.action == "continue":
            # Coverage concerns the user's requests, not every proposed extension.
            # Share these exact decisions with finalization; factual review still
            # determines whether the existing answer can actually be published.
            review["continuation_coverage"] = await audit(service.settings, work, wire,
                checkpoint.answer, seconds - (monotonic() - started), coverage_only=True,
                checkpoints=resume.parts if resume else None, on_progress=retain_routing)
            if review["continuation_coverage"].get("question_coverage") == "covered":
                checkpoint.action = "finish"
                checkpoint.next_checks = []
                checkpoint.deepen_branches = []
                checkpoint.reason = "Review the existing answer before opening further research."
                review.pop("original_reading", None)
        previous_reading = review.get("original_reading")
        if previous_reading is None or checkpoint.action == "continue" and (
                previous_reading.get("contract") != "research-next-reading/v2"):
            review["original_reading"] = await original_check(service.settings, work, wire,
                checkpoint, seconds - (monotonic() - started))
        routed = route_continuation(work, checkpoint)
        if resume:
            # The host can bind a next reading to an original outside the
            # initial shortlist. Resume its canonical full-source contract;
            # numeric/factual checks are still required before publication.
            resume.save("reviewed", wire.encode_checkpoint(parsed), review_hints, review)
        if not routed:
            work["publication_review_started"] = True
        return routed

    # Final corrections must not be replaced by cached earlier request drafts.
    # Canonical validation and final evidence/coverage checks still run below.
    # Validate structured responses locally as well. Repair format with the same
    # evidence, never by accepting unsupported or guessed fields.
    if isinstance(service.model_client, ModelClient) and work.get("unmetered_research"):
        errors = []
        parsed = None
        try:
            raw = decode_provider_response(wire, raw, response_schema
                if not saved or saved["stage"] == "draft" else wire.schema) if wire else raw
            if work["phase"] == "extract":
                from .product_question_renewal import parse_recoverable
                parsed = parse_recoverable(schema, raw, {key: "_" + key + "_unavailable" for key in
                    ("applicability_checks", "entities", "relationships", "source_class", "read_relevance", "professional_facts")})
                errors = extraction_citation_errors(parsed, work)
            else:
                parsed = schema.model_validate_json(raw)
                if work["phase"] == "brief" and getattr(parsed, "mission_checkpoint", None):
                    if await reading_before_publication(parsed):
                        return parsed.model_dump_json()
                    if wire and wire.answer:
                        wire_raw = wire.encode_checkpoint(parsed)
                        raw = wire.decode(wire_raw)
                    errors = answer_quantity_errors(parsed.mission_checkpoint.answer, wire.references if wire else None)
        except ValidationError as exc:
            errors = [{"path": list(e["loc"]), "reason": e["msg"]} for e in exc.errors(include_input=False, include_url=False)][:16]
        except (ValueError, KeyError, TypeError) as exc:
            errors = getattr(exc, "validation_errors", [{"reason": "Return valid JSON matching the schema, with supplied integer citation_ref values and no copied citation fields."}])
        if errors and saved and saved["stage"] == "finalizing":
            raise ValueError("Saved final draft failed canonical evidence validation")
        if errors and wire and work["phase"] == "brief" and getattr(parsed, "mission_checkpoint", None):
            from .research_answer_review import complete_citation_context, repair_points
            context = await complete_citation_context(service.settings, work, wire,
                parsed.mission_checkpoint.answer, seconds - (monotonic() - started))
            work["model_route"]["answer_review"]["citation_context"] = context
            def retain_repairs(receipts):
                work["model_route"]["answer_review"]["point_repairs"] = deepcopy(receipts)
                if resume:
                    resume.save("reviewed", wire.encode_checkpoint(parsed), review_hints, work["model_route"]["answer_review"])
            retain_repairs([])
            repairs = await repair_points(service, wire, parsed.mission_checkpoint.answer, seconds - (monotonic() - started),
                on_success=retain_repairs, checkpoints=resume.parts if resume else None,
                selected_references=selected) if not wire.request_keys else []
            work["model_route"]["answer_review"]["point_repairs"] = repairs
            wire_raw = wire.encode_checkpoint(parsed)
            if resume:
                resume.save("reviewed", wire_raw, review_hints, work["model_route"]["answer_review"])
            raw = wire.decode(wire_raw)
            parsed = schema.model_validate_json(raw)
            errors = answer_quantity_errors(parsed.mission_checkpoint.answer, wire.references)
            if errors:
                work["model_route"]["answer_review"]["unresolved_points"] = retain_answer_points(parsed, wire, errors)
                raw = wire.decode(wire.encode_checkpoint(parsed))
                errors = []
        if errors:
            remaining = seconds - (monotonic() - started)
            if remaining <= 5:
                raise ValueError("Provider response failed validation and no repair time remains")
            if remaining > 5:
                work["model_route"]["format_repair"] = True
                repair_system = system + "\nThe previous response failed validation. Correct these validation errors using the original evidence. Omit unsupported optional fields. Do not invent a quote or locator.\n" + json.dumps(errors[:16])
                repair_input = {"original_evidence": provider_input, "previous_invalid_response": wire_raw[:30000],
                    **({"review_hints": review_hints} if review_hints else {})}
                work["model_route"]["format_repair_mode"] = "validation_feedback"
                if resume and evidence_pack.request_characters(repair_system, repair_input, response_schema,
                        provider=service.settings.apertus_provider) > service.settings.apertus_context_chars:
                    # The malformed proposal is disposable; the chosen originals
                    # and the dispatched citation contract must remain complete.
                    repair_system, repair_input = system, provider_input
                    work["model_route"]["format_repair_mode"] = "fresh_bounded_draft"
                    if evidence_pack.request_characters(repair_system, repair_input, response_schema,
                            provider=service.settings.apertus_provider) > service.settings.apertus_context_chars:
                        raise DomainError("The selected evidence exceeds the configured synthesis allowance; the originals remain retained.",
                            422, "research_evidence_group_too_large")
                raw = await service.model_client.complete(repair_system, json.dumps(repair_input, ensure_ascii=False),
                    response_schema=response_schema, budget=InferenceBudget(max_requests=1, max_seconds=remaining), **options)
                raw = response_object(raw, schema)
                if resume and wire.answer:
                    resume.save("draft", raw, review_hints, work["model_route"]["answer_review"])
                raw = decode_provider_response(wire, raw, response_schema) if wire else raw
                if work["phase"] == "brief":
                    parsed = schema.model_validate_json(raw)
                    if getattr(parsed, "mission_checkpoint", None) and await reading_before_publication(parsed):
                        return parsed.model_dump_json()
                    if wire and wire.answer:
                        raw = wire.decode(wire.encode_checkpoint(parsed))
                    if wire and getattr(parsed, "mission_checkpoint", None) and answer_quantity_errors(parsed.mission_checkpoint.answer):
                        from .research_answer_review import complete_citation_context
                        context = await complete_citation_context(service.settings, work, wire,
                            parsed.mission_checkpoint.answer, seconds - (monotonic() - started))
                        work["model_route"]["answer_review"]["citation_context"] = context
                        raw = wire.decode(wire.encode_checkpoint(parsed))
                        parsed = schema.model_validate_json(raw)
                    if getattr(parsed, "mission_checkpoint", None) and answer_quantity_errors(parsed.mission_checkpoint.answer):
                        if not wire:
                            raise ValueError("Answer quantities are absent from their selected original evidence")
                        work["model_route"]["answer_review"]["unresolved_points"] = retain_answer_points(
                            parsed, wire, answer_quantity_errors(parsed.mission_checkpoint.answer))
                        raw = wire.decode(wire.encode_checkpoint(parsed))
        if wire and wire.answer:
            from .research_final_review import finalize
            parsed = schema.model_validate_json(raw)
            def retain_final():
                if resume:
                    resume.save("finalizing", wire.encode_checkpoint(parsed), review_hints, work["model_route"]["answer_review"])
            retain_final()
            final_coverage = await finalize(service, work, wire, parsed,
                seconds - (monotonic() - started), checkpoints=resume.parts if resume else None,
                on_progress=retain_final, defer_pending=resume is not None)
            missing = final_coverage.pop("hints")
            unresolved = [wire.request_keys[key] for key, slot in wire.response_slots.items() if slot["disposition"] == "unresolved"]
            missing.extend({"user_request": request} for request in unresolved
                if request not in {hint["user_request"] for hint in missing})
            if final_coverage.get("question_coverage") is None:
                missing.extend(hint for hint in review_hints if hint.get("review_signal") == "requested_part_missing"
                    and hint["user_request"] not in {value["user_request"] for value in missing})
            else:
                review_hints = [hint for hint in review_hints if hint.get("review_signal") != "requested_part_missing"] + [
                    {**hint, "review_signal": "requested_part_missing"} for hint in missing]
            work["model_route"]["answer_review"]["final_coverage"] = final_coverage
            for hint in missing:
                request = hint["user_request"]
                gap = "This answer has not resolved the requested part: " + request
                key = next((key for key, value in wire.request_keys.items() if value == request), None)
                answer = parsed.mission_checkpoint.answer
                if key is not None:
                    gap = wire.response_slots[key]["remaining_gap"].strip() or gap
                from .research_answer_parts import update_gap
                update_gap(wire, answer, key, gap)
                if gap == "This answer has not resolved the requested part: " + request:
                    wire.workflow_gaps = {*getattr(wire, 'workflow_gaps', set()), gap}
                parsed.mission_checkpoint.reason = "The cited findings answer part of the question; the remaining requested parts are named as gaps."
            if resume:
                resume.parts['workflow_gaps'] = sorted(set(getattr(wire, 'workflow_gaps', set())) &
                    set(parsed.mission_checkpoint.answer.limitations))
                resume.save("finalizing", wire.encode_checkpoint(parsed), review_hints, work["model_route"]["answer_review"])
            from .research_synthesis_resume import deferred_verification

            verification = deferred_verification(work.get("synthesis_checkpoint")) if work.get("allow_checked_partial_delivery") else None
            if verification:
                work["deferred_review_verification"] = verification
                work["model_route"]["answer_review"]["verification"] = verification
            pending = final_coverage.get("factual_review", {}).get("pending_checks", [])
            if resume and pending and not verification:
                code = "research_review_yield" if all(item["reason"] == "step_deadline" for item in pending) else "research_review_incomplete"
                raise DomainError("Some final evidence checks are incomplete. Saved sources and completed checks are retained.",
                    503, code)
            raw = wire.decode(wire.encode_checkpoint(parsed))
            from .research_final_coverage import reconcile, synchronize_projections
            delivered = schema.model_validate_json(raw)
            # decode regroups points by slot and updates wire.point_requests.
            # Any coverage checkpoint must retain that same canonical ordering.
            parsed = delivered
            coverage = await reconcile(service.settings, work, wire, delivered.mission_checkpoint.answer,
                seconds - (monotonic() - started), checkpoints=resume.parts if resume else None,
                on_progress=retain_final if resume else None)
            work["model_route"]["answer_review"]["delivered_coverage"] = coverage
            synchronize_projections(delivered)
            if resume:
                retain_final()
            if (not pending and final_coverage.get("factual_review", {}).get("status") == "checked"
                    and coverage.get("status") in {"checked", "not_applicable"}):
                from .product_research_mission import remember_delivery
                remember_delivery(work, delivered)
            raw = delivered.model_dump_json()
    return response_object(raw, schema)


def decode_provider_response(wire, raw, response_schema):
    """Apply the dispatched citation contract before restoring full host evidence."""
    original = wire.schema
    try:
        wire.schema = response_schema
        return wire.decode(raw)
    finally:
        wire.schema = original


def retain_answer_points(parsed, wire, errors, *, allow_empty=False):
    """Reject unsupported findings without rewriting independent valid siblings."""
    answer = parsed.mission_checkpoint.answer
    rejected = {error["path"][2] for error in errors}
    if len(rejected) == len(answer.points) and not allow_empty:
        raise ValueError("Answer quantities are absent from their selected original evidence")
    bindings = list(wire.point_requests)
    new_gaps = []
    for index in sorted(rejected):
        key = bindings[index] if index < len(bindings) else None
        request = wire.request_keys.get(key)
        gap = ("A cited answer could not be validated for: " + request if request else
            "A finding could not be validated against its cited originals: " + answer.points[index].statement[:300])
        host_notice = True
        if key is not None:
            old_gap = wire.response_slots[key]["remaining_gap"].strip()
            if old_gap and old_gap not in getattr(wire, "workflow_gaps", set()):
                gap, host_notice = old_gap, False
            answer.limitations = [value for value in answer.limitations if value != old_gap]
            wire.response_slots[key].update(disposition="unresolved", remaining_gap=gap)
        if gap not in answer.limitations:
            answer.limitations.append(gap)
        if host_notice:
            wire.workflow_gaps = {*getattr(wire, 'workflow_gaps', set()), gap}
        new_gaps.append(gap)
    answer.points = [point for index, point in enumerate(answer.points) if index not in rejected]
    wire.point_requests = [key for index, key in enumerate(bindings) if index not in rejected]
    answer.status = "partial" if answer.points else "not_found"
    parsed.mission_checkpoint.reason = "The cited findings are retained; findings that could not be validated are named as unresolved parts."
    # Multipart slots own their gaps and reserve space before unrelated limitations.
    owned = [value["remaining_gap"] for value in wire.response_slots.values() if value["remaining_gap"]]
    answer.limitations = list(dict.fromkeys([*owned, *new_gaps, *answer.limitations]))[:8]
    return sorted(rejected)


def answer_quantity_errors(answer, references=None):
    """Reported precision must occur in the selected evidence; this is not a truth score."""
    def quantities(text):
        # Canonicalise digit grouping only, never guess a decimal separator or
        # validate conversions by pooling digits from unrelated quantities.
        # Bibliographic page labels attach directly to a number (p103, pp41–45).
        # They can ground 'page 103'; arbitrary alphanumeric IDs still cannot.
        text = re.sub(r"(?<!\w)(?:pp?|pages?)\.?\s*(?=\d)", " ", text, flags=re.I)
        text = re.sub(r"(?<!\d)\d{1,3}(?:[ ,\u00a0\u202f]\d{3})+(?!\d)",
            lambda match: re.sub(r"[ ,\u00a0\u202f]", "", match[0]), text)
        return numeric_tokens(text)
    errors = []
    for index, point in enumerate(answer.points):
        supplied = set().union(*(quantities(ref.quote) for ref in point.evidence))
        missing = quantities(point.statement) - supplied
        if missing:
            candidates = sorted(((len(quantities(value["quote"]) & missing), -len(value["quote"]), ref, value["quote"])
                for ref, value in (references or {}).items() if quantities(value["quote"]) & missing), reverse=True)
            errors.append({"path": ["answer", "points", index, "statement"], "reason":
                "These numbers are absent from this point's selected windows: " + ", ".join(sorted(missing))
                + ". Cite the actual dated heading or other original passage in addition to the substantive quote when needed. Remove unsupported precision; never infer an unverified conversion.",
                **({"candidate_windows": [{"citation_ref": ref, "text": quote} for _, _, ref, quote in candidates[:8]]} if candidates else {})})
    return errors


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
            rank_passages=False, excerpt_limit=8, **({"blocked_urls": work["blocked_urls"]} if work.get("blocked_urls") else {}), **({"retain_original": {"folder": service.environment_settings.storage_path / "artifacts", "prefix": work["run_id"] + "-" + work["branch_id"]}} if "document_cursor" in work else {}), **({"document_cursor": work["document_cursor"]} if "document_cursor" in work else {}))
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
