"""Bounded measured selection; the persisted comparison is never edited."""

from __future__ import annotations

import copy
import json

from .config import DomainError

MAX_COUNT_PROBES = 8
MIN_WINDOW_CHARACTERS = 80


def _selection(payload: dict, rows: list[list], original_count: int, *, limited: bool) -> dict:
    candidate = copy.deepcopy(payload)
    candidate["evidence"]["rows"] = rows
    if limited:
        candidate["coverage"] = {
            **candidate.get("coverage", {}), "complete": False, "limited": True,
            "included_passages": len(rows),
            "scope": "Only the explicitly supplied rows/windows are model evidence. The complete saved comparison remains available outside this request.",
        }
        candidate["evidence"]["selection"] = {"available_rows": original_count, "included_rows": len(rows), "complete": False}
        context = candidate.get("deterministic_diff") or candidate.get("document_context")
        if context is not None:
            context["complete"] = False
            context["batch_passages"] = len(rows)
            if "change_items" in context:
                columns = candidate["evidence"]["columns"]
                ids = {row[columns.index("change_id")] for row in rows}
                context["change_items"] = [item for item in context["change_items"] if item[0] in ids]
                context["batch_counts"] = {
                    kind: sum(item[1] == kind for item in context["change_items"])
                    for kind in ("added", "removed", "modified", "unchanged")
                }
    return candidate


def _shorten(rows: list[list], columns: list[str], evidence: list[dict]) -> bool:
    changed = False
    text_index, number_index = columns.index("text"), columns.index("row_number")
    for row in rows:
        visible = row[text_index]
        if len(visible) <= MIN_WINDOW_CHARACTERS:
            continue
        index = row[number_index] - 1
        source = evidence[index]
        original = source["text"]
        offset = source.get("_model_offset") or 0
        if original[offset:offset + len(visible)] != visible:
            offset = original.find(visible)
        if offset < 0:
            raise DomainError("The selected window does not match saved evidence.", 422, "invalid_evidence_window")
        size = max(MIN_WINDOW_CHARACTERS, len(visible) // 2)
        anchor = offset
        if source.get("change_id"):
            other = next((item for item in evidence if item.get("change_id") == source["change_id"] and item.get("side") != source.get("side")), None)
            if other:
                anchor = 0
                while anchor < min(len(original), len(other["text"])) and original[anchor] == other["text"][anchor]:
                    anchor += 1
                anchor = max(offset, anchor - size // 4)
        start = max(offset, min(anchor, offset + len(visible) - size))
        text = original[start:start + size]
        row[text_index] = text
        evidence[index] = {**source, "_model_text": text, "_model_offset": start}
        changed = True
    return changed


async def fit_numbered_evidence(client, system: str, payload: dict, schema: dict, evidence: list[dict], budget, allocation: dict):
    """Try the full dossier first, then whole changes, then exact citable windows.

    Row numbers stay stable. Callers must validate selection against the returned
    allowed numbers, not merely the original numeric range. No generation occurs
    here; the gateway will recheck the final request under its execution lease.
    """
    table = payload["evidence"]
    columns = table["columns"]
    number_index, text_index = columns.index("row_number"), columns.index("text")
    rows = copy.deepcopy(table["rows"])
    if not rows or [row[number_index] for row in rows] != list(range(1, len(evidence) + 1)):
        raise DomainError("The numbered evidence is inconsistent.", 422, "invalid_evidence_rows")
    references = [dict(item) for item in evidence]
    groups: dict[str, list[int]] = {}
    for row in rows:
        number = row[number_index]
        passage = references[number - 1]
        key = passage.get("change_id") or f"row:{number}"
        groups.setdefault(key, []).append(number)
    ordered = sorted(groups, key=lambda key: (0 if references[groups[key][0] - 1].get("change_kind") == "modified" else 1, groups[key][0]))
    probes = []
    shortened = False
    try:
        for _ in range(MAX_COUNT_PROBES):
            allowed = {number for key in ordered for number in groups[key]}
            active = [row for row in rows if row[number_index] in allowed]
            limited = len(active) != len(evidence) or shortened
            candidate = _selection(payload, active, len(evidence), limited=limited)
            wire_schema = copy.deepcopy(schema)
            citations = wire_schema["properties"]["citation_rows"]
            citations["items"]["enum"] = sorted(allowed)
            citations["maxItems"] = min(10, len(allowed))
            measured = await client.count_prompt(system, json.dumps(candidate, ensure_ascii=False), response_schema=wire_schema, budget=budget)
            probes.append(measured.model_dump(mode="json"))
            if measured.fits:
                spans = []
                for row in active:
                    number = row[number_index]
                    passage = references[number - 1]
                    spans.append({
                        "row_number": number, "version_id": passage["version_id"], "passage_id": passage["passage_id"],
                        "change_id": passage.get("change_id"), "start": passage.get("_model_offset") or 0,
                        "characters": len(row[text_index]), "excerpted": row[text_index] != passage["text"],
                    })
                allocation.update({
                    "schema_version": "measured-evidence-v1", "status": "fit", "count_probes": len(probes),
                    "initial_rows": len(evidence), "row_numbers": sorted(allowed),
                    "omitted_row_numbers": sorted(set(range(1, len(evidence) + 1)) - allowed),
                    "windows": spans, "limited": limited or any(span["excerpted"] for span in spans),
                    "evidence_input_characters": len(json.dumps({
                        key: candidate[key] for key in ("evidence", "deterministic_diff", "document_context") if key in candidate
                    }, ensure_ascii=False)),
                    "measurements": probes,
                })
                # Preserve indices so original numeric references cannot silently
                # point at a different saved passage after allocation.
                evidence[:] = references
                return candidate, allowed, wire_schema
            if len(ordered) > 1:
                ordered = ordered[:max(1, len(ordered) // 2)]
            else:
                if not _shorten(active, columns, references):
                    break
                shortened = True
                # active rows are references into rows; their windows now changed.
        raise DomainError(
            "The local prompt still cannot fit with a minimal evidence window. Reduce custom instructions, "
            "company context or output length, or choose a larger verified context. The complete saved comparison remains available.",
            422, "model_context_exceeded",
        )
    finally:
        if not allocation:
            allocation.update({"schema_version": "measured-evidence-v1", "status": "failed", "count_probes": len(probes), "measurements": probes})
        client.trace_event({"evidence_allocation": copy.deepcopy(allocation)})


def allocated_coverage(evidence: list[dict], coverage: dict, batches: list[dict]) -> tuple[list[dict], dict]:
    allocations = [batch.get("token_allocation") for batch in batches if batch.get("token_allocation")]
    if not allocations:
        return evidence, coverage
    selected = []
    for batch in batches:
        allocation = batch.get("token_allocation")
        numbers = allocation.get("row_numbers", []) if allocation else range(1, len(batch["evidence"]) + 1)
        selected.extend(batch["evidence"][number - 1] for number in numbers)
    characters = sum(len(item.get("_model_text") or item["text"]) for item in selected)
    limited = coverage.get("limited", False) or any(item.get("limited") for item in allocations)
    change_ids = sorted({item["change_id"] for item in selected if item.get("change_id")})
    result = {
        **coverage, "included_passages": len(selected), "included_characters": characters,
        "processed_passages": len(selected), "processed_characters": characters,
        "limited": limited, "complete": bool(coverage.get("complete")) and not limited,
        "token_allocation": {"schema_version": "measured-evidence-v1", "batches": allocations},
        "excerpted_passages": sum(item.get("_model_text") is not None for item in selected),
        "selected_change_ids": change_ids,
        "selected_evidence_ids": [f"{item['version_id']}:{item['passage_id']}" for item in selected],
        "planned_largest_batch_input_characters": coverage.get("largest_batch_input_characters"),
        "largest_batch_input_characters": max((
            batch.get("token_allocation", {}).get("evidence_input_characters", batch.get("estimated_input_characters", 0))
            for batch in batches
        ), default=0),
    }
    if "reviewed_material_items" in result:
        result["reviewed_material_items"] = len(change_ids)
    if limited:
        result["scope"] = (
            f"AI received {len(selected)} saved passage windows selected within the measured token budget. "
            "This is partial evidence coverage; the complete saved comparison and original versions remain available for inspection."
        )
    return selected, result
