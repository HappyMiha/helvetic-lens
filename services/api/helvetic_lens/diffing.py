import re
from difflib import SequenceMatcher

DIFF_SCHEMA_VERSION = 2
MIN_MODIFIED_SIMILARITY = 0.32
MAX_ALIGNMENT_CELLS = 40_000


def word_parts(old: str, new: str) -> tuple[list[dict], list[dict]]:
    left = re.findall(r"\s+|\w+|[^\w\s]", old, re.UNICODE)
    right = re.findall(r"\s+|\w+|[^\w\s]", new, re.UNICODE)
    old_parts, new_parts = [], []
    autojunk = max(len(left), len(right)) > 200
    for kind, i, j, k, m in SequenceMatcher(None, left, right, autojunk=autojunk).get_opcodes():
        if i < j:
            old_parts.append({"text": "".join(left[i:j]), "kind": "equal" if kind == "equal" else "removed"})
        if k < m:
            new_parts.append({"text": "".join(right[k:m]), "kind": "equal" if kind == "equal" else "added"})
    return old_parts, new_parts


def _passage_similarity(left: dict, right: dict) -> float:
    old = re.sub(r"\s+", " ", left["text"]).casefold().strip()
    new = re.sub(r"\s+", " ", right["text"]).casefold().strip()
    old_words = re.findall(r"\w+", old, re.UNICODE)
    new_words = re.findall(r"\w+", new, re.UNICODE)
    word_ratio = SequenceMatcher(None, old_words, new_words, autojunk=True).ratio()
    old_vocabulary, new_vocabulary = set(old_words), set(new_words)
    vocabulary_ratio = (
        len(old_vocabulary & new_vocabulary) / len(old_vocabulary | new_vocabulary)
        if old_vocabulary or new_vocabulary
        else 1.0
    )
    character_ratio = (
        SequenceMatcher(None, old, new, autojunk=True).ratio()
        if max(len(old), len(new)) <= 4000
        else 0.0
    )
    return max(word_ratio, vocabulary_ratio, character_ratio)


def _align_replacement(
    old: list[dict],
    new: list[dict],
    old_offset: int,
    new_offset: int,
) -> list[tuple[int | None, int | None]]:
    """Align similar replacements and keep every saved passage exactly once."""

    if not old:
        return [(None, new_offset + index) for index in range(len(new))]
    if not new:
        return [(old_offset + index, None) for index in range(len(old))]
    if len(old) * len(new) > MAX_ALIGNMENT_CELLS:
        aligned = []
        common = min(len(old), len(new))
        for index in range(common):
            if _passage_similarity(old[index], new[index]) >= MIN_MODIFIED_SIMILARITY:
                aligned.append((old_offset + index, new_offset + index))
            else:
                aligned.extend([(old_offset + index, None), (None, new_offset + index)])
        aligned.extend((old_offset + index, None) for index in range(common, len(old)))
        aligned.extend((None, new_offset + index) for index in range(common, len(new)))
        return aligned

    rows, columns = len(old), len(new)
    costs = [[0.0] * (columns + 1) for _ in range(rows + 1)]
    moves = [[""] * (columns + 1) for _ in range(rows + 1)]
    for row in range(1, rows + 1):
        costs[row][0], moves[row][0] = float(row), "removed"
    for column in range(1, columns + 1):
        costs[0][column], moves[0][column] = float(column), "added"
    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            similarity = _passage_similarity(old[row - 1], new[column - 1])
            modified = (
                costs[row - 1][column - 1] + (1 - similarity)
                if similarity >= MIN_MODIFIED_SIMILARITY
                else float("inf")
            )
            # Prefer a valid modification, then an add, then a remove on exact cost ties. During
            # reverse traversal this keeps an unrelated removal before its following addition.
            choice = min(
                (modified, 0, "modified"),
                (costs[row][column - 1] + 1, 1, "added"),
                (costs[row - 1][column] + 1, 2, "removed"),
            )
            costs[row][column], moves[row][column] = choice[0], choice[2]

    aligned = []
    row, column = rows, columns
    while row or column:
        move = moves[row][column]
        if move == "modified":
            row -= 1
            column -= 1
            aligned.append((old_offset + row, new_offset + column))
        elif move == "removed":
            row -= 1
            aligned.append((old_offset + row, None))
        else:
            column -= 1
            aligned.append((None, new_offset + column))
    aligned.reverse()
    return aligned


def compare_passages(old: list[dict], new: list[dict]) -> dict:
    """Return a deterministic, complete diff over the two saved passage sequences."""

    pairs: list[tuple[int | None, int | None]] = []
    matcher = SequenceMatcher(
        None,
        [p["text"] for p in old],
        [p["text"] for p in new],
        autojunk=max(len(old), len(new)) > 200,
    )
    for operation, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if operation == "equal":
            pairs.extend(zip(range(old_start, old_end), range(new_start, new_end), strict=True))
        else:
            pairs.extend(
                _align_replacement(
                    old[old_start:old_end],
                    new[new_start:new_end],
                    old_start,
                    new_start,
                )
            )

    items = []
    counts = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}
    for old_index, new_index in pairs:
        left = old[old_index] if old_index is not None else None
        right = new[new_index] if new_index is not None else None
        kind = (
            "added"
            if left is None
            else "removed"
            if right is None
            else "unchanged"
            if left["text"] == right["text"]
            else "modified"
        )
        old_parts, new_parts = word_parts(left["text"] if left else "", right["text"] if right else "")
        items.append(
            {
                "id": f"c{len(items) + 1:05d}",
                "kind": kind,
                "old": left,
                "new": right,
                "old_position": old_index + 1 if old_index is not None else None,
                "new_position": new_index + 1 if new_index is not None else None,
                "old_parts": old_parts,
                "new_parts": new_parts,
            }
        )
        counts[kind] += 1

    old_covered = sum(item["old"] is not None for item in items)
    new_covered = sum(item["new"] is not None for item in items)
    if old_covered != len(old) or new_covered != len(new):
        raise RuntimeError("The deterministic comparison did not cover every saved passage.")
    return {
        "schema_version": DIFF_SCHEMA_VERSION,
        "algorithm": "passage-sequence-v2",
        "granularity": "article_or_passage",
        "complete": True,
        "old_passage_count": len(old),
        "new_passage_count": len(new),
        "items": items,
        "counts": counts,
        "changed": bool(counts["added"] + counts["removed"] + counts["modified"]),
    }
