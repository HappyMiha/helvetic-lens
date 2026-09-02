import re
import unicodedata
from difflib import SequenceMatcher

DIFF_SCHEMA_VERSION = 4
MIN_MODIFIED_SIMILARITY = 0.58
ALIGNMENT_BAND = 12

_EXPLICIT_ARTICLE_LABEL = re.compile(
    r"^(?P<label>(?:art(?:icle|ikel|icolo)?|стаття)\.?\s*"
    r"\d+[a-zà-ž]*(?:\s*(?:bis|ter|quater))?(?:\s*[.:–—-])?)\s*"
    r"(?P<body>.*)$",
    re.I,
)
_LAYOUT_ROLES = frozenset({"footer", "header", "page_counter", "page_number"})
_NUMBER_TOKEN = re.compile(r"(?<!\w)[+-]?\d+(?:[.,]\d+)*(?:%|‰)?", re.UNICODE)


def canonical_text(value: str) -> str:
    """Return comparison text while leaving the saved evidence untouched."""

    value = unicodedata.normalize("NFC", value or "").replace("\u00ad", "")
    return re.sub(r"\s+", " ", value).casefold().strip()


def _legal_label_and_body(value: str) -> tuple[str | None, str]:
    """Split only an explicit article label; a leading number may be legal evidence."""

    result = canonical_text(value)
    match = _EXPLICIT_ARTICLE_LABEL.fullmatch(result)
    if not match:
        return None, result
    body = match.group("body").strip()
    if len(body) < 3:
        return None, result
    return match.group("label").strip(), body


def _without_legal_label(value: str) -> str:
    return _legal_label_and_body(value)[1]


def _layout_noise(passage: dict) -> bool:
    """Trust explicit extractor metadata instead of guessing from numeric text."""

    return not canonical_text(passage.get("text", "")) or passage.get("layout_role") in _LAYOUT_ROLES


def _evidentiary_numbers(value: str) -> tuple[str, ...]:
    """Keep article labels structural while treating every number in the body as evidence."""

    return tuple(_NUMBER_TOKEN.findall(_without_legal_label(value)))


def _match_key(passage: dict) -> str:
    canonical = canonical_text(passage.get("text", ""))
    body = _without_legal_label(canonical)
    return body if len(body) >= 8 else canonical


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


def _prepare_passage(passage: dict) -> tuple[str, tuple[str, ...], frozenset[str]]:
    text = _without_legal_label(passage["text"])
    words = tuple(re.findall(r"\w+", text, re.UNICODE))
    return text, words, frozenset(words)


def _prepared_similarity(
    left: tuple[str, tuple[str, ...], frozenset[str]],
    right: tuple[str, tuple[str, ...], frozenset[str]],
) -> float:
    old, old_words, old_vocabulary = left
    new, new_words, new_vocabulary = right
    word_ratio = SequenceMatcher(None, old_words, new_words, autojunk=True).ratio()
    vocabulary_ratio = (
        len(old_vocabulary & new_vocabulary) / len(old_vocabulary | new_vocabulary)
        if old_vocabulary or new_vocabulary
        else 1.0
    )
    lexical_ratio = (word_ratio + vocabulary_ratio) / 2
    if lexical_ratio >= MIN_MODIFIED_SIMILARITY:
        return lexical_ratio
    character_ratio = (
        SequenceMatcher(None, old, new, autojunk=True).ratio()
        if max(len(old), len(new)) <= 4000
        else 0.0
    )
    return max(character_ratio, lexical_ratio)


def _passage_similarity(left: dict, right: dict) -> float:
    return _prepared_similarity(_prepare_passage(left), _prepare_passage(right))


def _align_replacement(
    old: list[dict],
    new: list[dict],
    old_offset: int,
    new_offset: int,
) -> list[tuple[int | None, int | None]]:
    """Align replacements in bounded memory with one rule for every block size."""

    if not old:
        return [(None, new_offset + index) for index in range(len(new))]
    if not new:
        return [(old_offset + index, None) for index in range(len(old))]
    rows, columns = len(old), len(new)
    shortest = min(rows, columns)
    band = max(ALIGNMENT_BAND, (max(rows, columns) + shortest - 1) // shortest)
    old_prepared = [_prepare_passage(passage) for passage in old]
    new_prepared = [_prepare_passage(passage) for passage in new]
    costs: list[dict[int, float]] = []
    moves: list[dict[int, str]] = []
    for row in range(rows + 1):
        center = round(row * columns / rows)
        start, end = max(0, center - band), min(columns, center + band)
        row_costs: dict[int, float] = {}
        row_moves: dict[int, str] = {}
        for column in range(start, end + 1):
            if row == 0 and column == 0:
                row_costs[column] = 0.0
                row_moves[column] = ""
                continue
            candidates: list[tuple[float, int, str]] = []
            if row and column in costs[row - 1]:
                candidates.append((costs[row - 1][column] + 1, 2, "removed"))
            if column and column - 1 in row_costs:
                candidates.append((row_costs[column - 1] + 1, 1, "added"))
            if row and column and column - 1 in costs[row - 1]:
                similarity = _prepared_similarity(
                    old_prepared[row - 1], new_prepared[column - 1]
                )
                if similarity >= MIN_MODIFIED_SIMILARITY:
                    candidates.append(
                        (costs[row - 1][column - 1] + (1 - similarity), 0, "modified")
                    )
            if candidates:
                choice = min(candidates)
                row_costs[column], row_moves[column] = choice[0], choice[2]
        costs.append(row_costs)
        moves.append(row_moves)

    if columns not in costs[rows]:
        raise RuntimeError("The bounded deterministic alignment could not reach its endpoint.")

    aligned: list[tuple[int | None, int | None]] = []
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
        elif move == "added":
            column -= 1
            aligned.append((None, new_offset + column))
        else:
            raise RuntimeError("The bounded deterministic alignment has an incomplete path.")
    aligned.reverse()
    return aligned


def _pair_exact_moves(
    pairs: list[tuple[int | None, int | None]], old: list[dict], new: list[dict]
) -> tuple[list[tuple[int | None, int | None]], set[tuple[int, int]]]:
    """Pair unique exact unmatched passages as moves without dropping evidence."""

    removed: dict[str, list[tuple[int, int]]] = {}
    added: dict[str, list[tuple[int, int]]] = {}
    for pair_index, (old_index, new_index) in enumerate(pairs):
        if old_index is not None and new_index is None:
            key = canonical_text(old[old_index].get("text", ""))
            if key:
                removed.setdefault(key, []).append((pair_index, old_index))
        elif old_index is None and new_index is not None:
            key = canonical_text(new[new_index].get("text", ""))
            if key:
                added.setdefault(key, []).append((pair_index, new_index))

    replacements: dict[int, tuple[int, int]] = {}
    consumed_removals: set[int] = set()
    moved_pairs: set[tuple[int, int]] = set()
    for key in removed.keys() & added.keys():
        if len(removed[key]) != 1 or len(added[key]) != 1:
            continue
        removed_pair_index, old_index = removed[key][0]
        added_pair_index, new_index = added[key][0]
        consumed_removals.add(removed_pair_index)
        replacements[added_pair_index] = (old_index, new_index)
        moved_pairs.add((old_index, new_index))

    result = []
    for pair_index, pair in enumerate(pairs):
        if pair_index not in consumed_removals:
            result.append(replacements.get(pair_index, pair))
    return result, moved_pairs


def _classification(
    left: dict | None, right: dict | None, kind: str, moved: bool = False
) -> tuple[str, str]:
    if moved:
        return "structural", "moved"
    if kind == "unchanged":
        return "unchanged", "unchanged"
    if left is None or right is None:
        if _evidentiary_numbers((left or right or {}).get("text", "")):
            return "substantive", kind
        if _layout_noise(left or right or {}):
            return "formatting", "layout_only"
        return "substantive", kind
    if _evidentiary_numbers(left["text"]) != _evidentiary_numbers(right["text"]):
        return "substantive", "modified"
    if _layout_noise(left) and _layout_noise(right):
        return "formatting", "layout_only"
    if canonical_text(left["text"]) == canonical_text(right["text"]):
        return "formatting", "layout_only"
    old_label, old_body = _legal_label_and_body(left["text"])
    new_label, new_body = _legal_label_and_body(right["text"])
    if old_label and new_label and old_label != new_label and old_body == new_body:
        return "structural", "renumbered"
    return "substantive", "modified"


def compare_passages(old: list[dict], new: list[dict]) -> dict:
    """Return a complete raw evidence diff plus deterministic significance labels."""

    pairs: list[tuple[int | None, int | None]] = []
    matcher = SequenceMatcher(
        None,
        [_match_key(passage) for passage in old],
        [_match_key(passage) for passage in new],
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

    pairs, moved_pairs = _pair_exact_moves(pairs, old, new)

    items = []
    counts = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}
    classification_counts = {
        "substantive": 0,
        "structural": 0,
        "formatting": 0,
        "uncertain": 0,
    }
    for old_index, new_index in pairs:
        left = old[old_index] if old_index is not None else None
        right = new[new_index] if new_index is not None else None
        moved = (
            old_index is not None
            and new_index is not None
            and (old_index, new_index) in moved_pairs
        )
        kind = (
            "added"
            if left is None
            else "removed"
            if right is None
            else "unchanged"
            if left["text"] == right["text"]
            else "modified"
        )
        if moved:
            kind = "modified"
        significance, change_type = _classification(left, right, kind, moved)
        old_parts, new_parts = word_parts(left["text"] if left else "", right["text"] if right else "")
        items.append(
            {
                "id": f"c{len(items) + 1:05d}",
                "kind": kind,
                "significance": significance,
                "change_type": change_type,
                "material": significance == "substantive",
                "old": left,
                "new": right,
                "old_position": old_index + 1 if old_index is not None else None,
                "new_position": new_index + 1 if new_index is not None else None,
                "old_parts": old_parts,
                "new_parts": new_parts,
            }
        )
        counts[kind] += 1
        if significance in classification_counts:
            classification_counts[significance] += 1

    old_covered = [item["old_position"] for item in items if item["old"] is not None]
    new_covered = [item["new_position"] for item in items if item["new"] is not None]
    if sorted(old_covered) != list(range(1, len(old) + 1)) or sorted(new_covered) != list(
        range(1, len(new) + 1)
    ):
        raise RuntimeError("The deterministic comparison did not cover every saved passage.")
    material_count = classification_counts["substantive"] + classification_counts["uncertain"]
    return {
        "schema_version": DIFF_SCHEMA_VERSION,
        "algorithm": "bounded-canonical-passage-sequence-v4",
        "granularity": "article_or_passage",
        "complete": True,
        "old_passage_count": len(old),
        "new_passage_count": len(new),
        "items": items,
        "counts": counts,
        "classification_counts": classification_counts,
        "material_count": material_count,
        "changed": bool(counts["added"] + counts["removed"] + counts["modified"]),
        "material_changed": bool(material_count),
    }
