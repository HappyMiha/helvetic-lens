"""Complete persisted comparison -> bounded material evidence, never ranked chunks.

The caller authorizes both saved versions and their work/language/baseline before
calling this pure planner. Every raw passage is audited, even those not sent to AI.
"""

from collections import Counter

from .config import DomainError
from .diffing import DIFF_SCHEMA_VERSION, parse_legal_units
from .interest_assessment import Evidence, MaterialChange, SourceComparison, fingerprint

MATERIAL = {"substantive", "added", "removed", "uncertain"}
PRESENTATION = {"moved", "renumbered", "formatting_only"}


def invalid():
    raise DomainError("The saved comparison no longer covers both exact versions; rebuild it before AI analysis.",
                      409, "interest_comparison_unavailable")


def ancestor_positions(passages):
    """Exact enclosing headings/numbered clauses, not a similarity search."""
    active, result = {}, {}
    for unit in parse_legal_units(passages):
        parent_path = unit["parent_path"]
        # Remove closed siblings/children; retain the exact source position for
        # each currently active path rather than matching repeated heading text.
        active = {key: value for key, value in active.items() if key in parent_path}
        result[unit["position"]] = [active[key] for key in parent_path if key in active]
        if unit["type"] != "passage":
            active[unit["path"][-1]] = unit["position"]
    return result


def plan(comparison, before, after):
    diff = comparison.diff
    if (not isinstance(diff, dict) or diff.get("schema_version") != DIFF_SCHEMA_VERSION
            or diff.get("algorithm") != "legal-unit-hierarchy-and-exact-audit-v6"
            or diff.get("complete") is not True or not isinstance(diff.get("items"), list)
            or comparison.old_version_id != before.id or comparison.new_version_id != after.id
            or before.id == after.id):
        invalid()
    passages = {"old": before.passages, "new": after.passages}
    for side, rows in passages.items():
        if (not isinstance(rows, list) or not rows
                or any(not isinstance(row, dict) or not isinstance(row.get("id"), str)
                       or not isinstance(row.get("text"), str) or not row["text"].strip() for row in rows)
                or type(diff.get(f"{side}_passage_count")) is not int
                or len(rows) != diff.get(f"{side}_passage_count")
                or len({row["id"] for row in rows}) != len(rows)):
            invalid()
    seen = {"old": set(), "new": set()}
    counts, change_ids, changes, evidence = Counter(), set(), [], {}
    ancestors = {side: ancestor_positions(rows) for side, rows in passages.items()}
    presentation = 0

    def add(row, version, side, role):
        item = Evidence(id="ev_" + fingerprint([version.id, row["id"], "event"])[:32],
            version_id=version.id, artifact_id=version.artifact_key, unit_id=row["id"],
            text=row["text"], source_url=version.source_url, source_kind="event", primary_source=True,
            side=side, role=role)
        if item.id not in evidence or role == "material_change":
            evidence[item.id] = item
        return item.id

    for item in diff["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in change_ids:
            invalid()
        change_ids.add(item["id"])
        kind, classification = item.get("kind"), item.get("classification")
        if kind not in {"added", "removed", "modified", "unchanged"}:
            invalid()
        counts[kind] += 1
        for side, rows in passages.items():
            position, row = item.get(f"{side}_position"), item.get(side)
            if row is None:
                if position is not None:
                    invalid()
                continue
            if (type(position) is not int or not 1 <= position <= len(rows)
                    or position in seen[side] or row != rows[position - 1]):
                invalid()
            seen[side].add(position)
        if (item.get("old") is None and item.get("new") is None
                or (kind == "added") != (item.get("old") is None)
                or (kind == "removed") != (item.get("new") is None)):
            invalid()
        if kind == "unchanged":
            if item["old"]["text"] != item["new"]["text"] or classification != "unchanged":
                invalid()
            continue
        if classification not in MATERIAL | PRESENTATION:
            invalid()
        if classification in PRESENTATION:
            # The deterministic algorithm, not the LLM, labels presentation noise.
            # Refuse conflicting stored flags instead of silently hiding uncertainty.
            if item.get("material") is not False or item.get("significance") not in {"structural", "formatting"}:
                invalid()
            presentation += 1
            continue
        if item.get("material") is not True or item.get("significance") not in {"substantive", "uncertain"}:
            invalid()
        context_ids = []
        for side, version, label in (("old", before, "before"), ("new", after, "after")):
            if item[side]:
                context_ids.extend(add(passages[side][position - 1], version, label, "context")
                                   for position in ancestors[side][item[f"{side}_position"]])
        changes.append(MaterialChange(id=item["id"], classification=classification, context_ids=context_ids,
            before_ids=[add(item["old"], before, "before", "material_change")] if item["old"] else [],
            after_ids=[add(item["new"], after, "after", "material_change")] if item["new"] else []))
    if any(seen[side] != set(range(1, len(rows) + 1)) for side, rows in passages.items()):
        invalid()
    counts = {kind: counts[kind] for kind in ("added", "removed", "modified", "unchanged")}
    if (counts != diff.get("counts") or any(type(value) is not int for value in diff["counts"].values())
            or type(diff.get("material_count")) is not int or len(changes) != diff.get("material_count")):
        invalid()
    if not changes:
        # Explicit context, never a fabricated change. Counts describe the full
        # audit; this one citable anchor is not presented as a whole-document read.
        add(after.passages[0], after, "after", "context")
    if len(evidence) > 64 or len(changes) > 64:
        raise DomainError("All material changes exceed the brief envelope; none were sampled or truncated.",
                          409, "interest_context_exceeded")
    context = SourceComparison(id=comparison.id, before_version_id=before.id, after_version_id=after.id,
        diff_fingerprint=fingerprint({key: value for key, value in diff.items() if key != "metrics"}),
        algorithm=diff["algorithm"], old_passage_count=len(before.passages), new_passage_count=len(after.passages),
        counts=counts, presentation_only_count=presentation, changes=changes)
    return list(evidence.values()), context
