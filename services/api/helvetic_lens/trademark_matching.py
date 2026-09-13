"""Bounded explained B7 candidates. Never a legal assessment or coverage claim."""

import unicodedata
from dataclasses import dataclass

from .trademark_contracts import MATCHER_VERSION, NORMALIZATION_VERSION, exact, fingerprint, words

MAX_DISTANCE_CELLS = 1_000_000


@dataclass
class Budget:
    remaining: int = MAX_DISTANCE_CELLS


def distance(left, right, budget):
    """Optimal string alignment distance, with adjacent transpositions."""
    cells = len(left) * len(right)
    if cells > budget.remaining:
        return None
    budget.remaining -= cells
    previous = list(range(len(right) + 1))
    older = None
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            value = min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b))
            if older is not None and j > 1 and a == right[j - 2] and left[i - 2] == b:
                value = min(value, older[j - 2] + 1)
            current.append(value)
        older, previous = previous, current
    return previous[-1]


def scripts(value):
    return frozenset(unicodedata.name(c, "UNKNOWN").split()[0] for c in value if c.isalpha())


def soundex(value):
    """English Soundex; other scripts/diacritics return unknown, never stripped."""
    if not value or any(c not in "abcdefghijklmnopqrstuvwxyz" for c in value):
        return None
    groups = ("bfpv", "cgjkqsxz", "dt", "l", "mn", "r")
    codes = {letter: str(number) for number, group in enumerate(groups, 1) for letter in group}
    result, previous = value[0].upper(), codes.get(value[0])
    for char in value[1:]:
        code = codes.get(char)
        if code is not None and code != previous:
            result += code
        # H/W separate letters without breaking a consonant-code run; vowels do.
        if char not in "hw":
            previous = code
    return (result + "000")[:4]


def goods_evidence(brand, facts, statements):
    class_overlap = None if facts.classes is None else sorted(set(brand.relevant_classes) & set(facts.classes))
    matches = []
    for interest in brand.goods_services:
        found = False
        for phrase in interest.phrases:
            if found:
                break
            target = " " + " ".join(words(phrase.text)) + " "
            for index, (statement, tokens) in enumerate(statements):
                if (statement.language or "").lower().split("-")[0] != phrase.language:
                    continue
                if target in tokens:
                    matches.append({"interest": interest.name, "phrase": phrase.text, "language": phrase.language,
                        "statement_index": index, "class_number": statement.class_number,
                        "basis": "explicit_phrase"})
                    found = True
                if found:
                    break
    state = "unknown" if (not brand.goods_services or facts.goods_services is None
                          or any(s.language is None for s, _ in statements)) else "not_established"
    if matches:
        state = "direct_phrases" if len(matches) == len(brand.goods_services) else "partial"
    return {"state": state, "matches": matches, "class_overlap": class_overlap,
            "classes_prove_goods_similarity": False}


def assess(portfolio, facts, *, calibrations=(), now, max_distance_cells=MAX_DISTANCE_CELLS):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Candidate assessment requires an aware clock")
    if type(max_distance_cells) is not int or not 0 <= max_distance_cells <= MAX_DISTANCE_CELLS:
        raise ValueError("Invalid comparison budget")
    by_language = {}
    for calibration in calibrations:
        if calibration.language in by_language:
            raise ValueError("Use one current calibration per language")
        by_language[calibration.language] = calibration
    budget, results = Budget(max_distance_cells), []
    statements = [(s, " " + " ".join(words(s.text)) + " ") for s in facts.goods_services or ()]
    for brand in portfolio.brands:
        methods, unavailable = [], []
        goods = goods_evidence(brand, facts, statements)
        owner_hits = [owner for owner in facts.owners or () if exact(owner) in {exact(n) for n in brand.owners_of_interest}]
        if owner_hits:
            methods.append({"kind": "owner_interest", "owners": owner_hits})
        if brand.owners_of_interest and facts.owners is None:
            unavailable.append("owners_unknown")
        calibration = by_language.get(brand.language)
        calibration_ready = (calibration is not None and calibration.reviewed_at <= now < calibration.valid_until
            and calibration.normalization_version == NORMALIZATION_VERSION and calibration.matcher_version == MATCHER_VERSION)
        if facts.mark is None:
            unavailable.append("verbal_mark_unknown")
        else:
            right = exact(facts.mark)
            for variant in (brand.name, *brand.word_variants):
                left = exact(variant)
                if left == right:
                    if brand.exact_name:
                        methods.append({"kind": "exact", "brand_variant": variant, "source_mark": facts.mark})
                    continue
                if not brand.similar_names:
                    continue
                if not calibration_ready:
                    unavailable.append("similarity_calibration_unavailable")
                    continue
                if scripts(left) != scripts(right):
                    unavailable.append("cross_script_similarity_unavailable")
                    continue
                change = distance(left, right, budget)
                if change is None:
                    unavailable.append("comparison_budget_exhausted")
                    continue
                score = 100 * (max(len(left), len(right)) - change) // max(len(left), len(right), 1)
                if score >= calibration.lexical_minimum:
                    methods.append({"kind": "lexical", "brand_variant": variant, "source_mark": facts.mark,
                        "score": score, "distance": change, "method": "optimal-string-alignment-v1"})
                elif calibration.word_extension_minimum is not None:
                    left_words, right_words = words(left), words(right)
                    short, long = sorted((left_words, right_words), key=len)
                    if short and len(short) < len(long) and (" " + " ".join(short) + " ") in (" " + " ".join(long) + " "):
                        extension_score = 100 * sum(map(len, short)) // max(1, sum(map(len, long)))
                        if extension_score >= calibration.word_extension_minimum:
                            methods.append({"kind": "lexical", "brand_variant": variant, "source_mark": facts.mark,
                                "score": extension_score, "distance": change, "method": "whole-word-extension-v1"})
                if calibration.phonetic_method == "soundex-en-v1":
                    left_key, right_key = soundex(left), soundex(right)
                    if left_key is None or right_key is None:
                        unavailable.append("phonetic_form_unavailable")
                    elif left_key == right_key and score >= calibration.phonetic_lexical_floor:
                        methods.append({"kind": "phonetic", "brand_variant": variant, "source_mark": facts.mark,
                            "method": "soundex-en-v1", "language": "en", "key": left_key,
                            "lexical_score": score})
                else:
                    unavailable.append("phonetic_method_unavailable")
        candidate = bool(methods)
        results.append({"brand_key": brand.key, "state": "candidate" if candidate else "unavailable" if unavailable else "not_selected",
            "classification": "candidate_for_ip_review" if candidate else None,
            "priority": ("high" if goods["matches"] else "review") if candidate else None,
            "methods": methods, "goods_services": goods, "unavailable": sorted(set(unavailable)),
            "calibration_sha256": calibration.fingerprint() if calibration_ready else None})
    material = {"profile": portfolio.fingerprint(), "facts": facts.material_fingerprint(),
                "matcher": MATCHER_VERSION, "normalization": NORMALIZATION_VERSION, "results": results}
    return {"official_id": facts.official_id, "source_sha256": facts.source_sha256,
            "matcher_version": MATCHER_VERSION, "normalization_version": NORMALIZATION_VERSION,
            "profile_sha256": portfolio.fingerprint(), "facts_sha256": facts.material_fingerprint(),
            "decision_sha256": fingerprint(material), "results": results,
            "coverage_verified": False, "legal_conflict_confirmed": False}
