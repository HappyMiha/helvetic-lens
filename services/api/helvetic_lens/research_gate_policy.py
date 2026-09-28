"""Conservative decision policy and offline selection, never an accuracy score."""
from .decision_engines import DecisionUnavailable, probability

VERSION = "laya-rejection-guard/v1"
MODEL = "laya-multilingual@e4e9ddf21a7b1903b7acffd8814ad4307bf63a67"
THRESHOLDS = (.50, .65, .80, .90, .95)


def guarded_verdict(choice, scores, threshold):
    """Only defer a rejection. The provider scores are uncalibrated telemetry."""
    if threshold not in THRESHOLDS or choice not in {"relevant", "uncertain", "unrelated"}:
        raise ValueError("Unrecognized rejection policy")
    if set(scores) != {"relevant", "uncertain", "unrelated"}:
        raise DecisionUnavailable("invalid_response")
    values = {key: probability(value) for key, value in scores.items()}
    if abs(sum(values.values()) - 1) > .002 or values[choice] + .00001 < max(values.values()):
        raise DecisionUnavailable("invalid_response")
    return "uncertain" if choice == "unrelated" and values[choice] < threshold else choice


def guarded_observations(observations, threshold):
    result = []
    for row in observations:
        next_row = dict(row)
        if row["outcome"] in {"relevant", "uncertain", "unrelated"}:
            if row.get("model") != MODEL:
                raise ValueError("Unvalidated model")
            next_row["outcome"] = guarded_verdict(row["outcome"], row["probabilities"], threshold)
        result.append(next_row)
    return result


def comparison(cases, observations, threshold):
    from .research_evaluation import gate_metrics

    baseline = gate_metrics(cases, observations)
    guarded = gate_metrics(cases, guarded_observations(observations, threshold))
    before, after = (m["groups"]["all"] for m in (baseline, guarded))
    raw, changed = (m["outcomes_by_label"] for m in (before, after))
    deferred = sum(changed[label]["uncertain"] - raw[label]["uncertain"] for label in ("0", "1"))
    complete = len(observations) == len(cases) and all(row["outcome"] in {"relevant", "uncertain", "unrelated"} for row in observations)
    return {"threshold": threshold, "baseline": baseline, "guarded": guarded,
        "complete": complete, "deferred_rejections": deferred,
        "extra_review_fraction": deferred / len(cases) if cases else None,
        "negative_rejections_retained": changed["0"]["unrelated"],
        "negative_rejections_baseline": raw["0"]["unrelated"],
        "positive_rejections": changed["1"]["unrelated"],
        "positive_rejections_baseline": raw["1"]["unrelated"],
        "positive_labels": after["positive_labels"]}


def within_burden(result):
    return (result["extra_review_fraction"] is not None and result["extra_review_fraction"] <= .20
        and result["negative_rejections_retained"] >= result["negative_rejections_baseline"] / 2)


def select_development(cases, observations):
    results = [comparison(cases, observations, threshold) for threshold in THRESHOLDS]
    eligible = [r for r in results if r["complete"] and r["positive_labels"] > 0
        and r["positive_rejections"] == 0 and within_burden(r)]
    eligible.sort(key=lambda r: (-r["negative_rejections_retained"], r["threshold"]))
    return {"policy": VERSION, "threshold": eligible[0]["threshold"] if eligible else None,
        "selected_from": "development_only", "candidates": results}


def promotion(result):
    checks = {"complete": result["complete"], "has_positive_labels": result["positive_labels"] > 0,
        "positive_exclusions_no_worse": result["positive_rejections"] <= result["positive_rejections_baseline"],
        "positive_exclusions_at_most_five_percent": result["positive_rejections"] <= .05 * result["positive_labels"],
        "bounded_extra_review": within_burden(result), "actually_defers_rejection": result["deferred_rejections"] > 0}
    return {"passed": all(checks.values()), "checks": checks,
        "scope": "Small public snippet/full-passage proxy only; professional acceptance remains OPEN."}
