import re
from difflib import SequenceMatcher
from itertools import zip_longest


def word_parts(old: str, new: str) -> tuple[list[dict], list[dict]]:
    left = re.findall(r"\s+|\w+|[^\w\s]", old, re.UNICODE)
    right = re.findall(r"\s+|\w+|[^\w\s]", new, re.UNICODE)
    old_parts, new_parts = [], []
    for kind, i, j, k, m in SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
        if i < j:
            old_parts.append({"text": "".join(left[i:j]), "kind": "equal" if kind == "equal" else "removed"})
        if k < m:
            new_parts.append({"text": "".join(right[k:m]), "kind": "equal" if kind == "equal" else "added"})
    return old_parts, new_parts


def compare_passages(old: list[dict], new: list[dict]) -> dict:
    items = []
    counts = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}
    matcher = SequenceMatcher(None, [p["text"] for p in old], [p["text"] for p in new], autojunk=False)
    for operation, i, j, k, m in matcher.get_opcodes():
        for left, right in zip_longest(old[i:j], new[k:m]):
            kind = (
                "unchanged"
                if operation == "equal"
                else "added"
                if left is None
                else "removed"
                if right is None
                else "modified"
            )
            old_parts, new_parts = word_parts(left["text"] if left else "", right["text"] if right else "")
            items.append(
                {
                    "id": f"c{len(items) + 1:05d}",
                    "kind": kind,
                    "old": left,
                    "new": right,
                    "old_parts": old_parts,
                    "new_parts": new_parts,
                }
            )
            counts[kind] += 1
    return {
        "items": items,
        "counts": counts,
        "changed": bool(counts["added"] + counts["removed"] + counts["modified"]),
    }
