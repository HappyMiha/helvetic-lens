import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_tender_matching import NOW, facts, profile
from test_tender_semantic import Model, identity, proposal

from helvetic_lens.tender_semantic import assess
from helvetic_lens.tender_semantic_eval import Case, Dataset, evaluate


def case(name, expected=True, split="development", **changes):
    text = f"Case {name}: We require software development and support."
    source = facts(evidence_sha256=hashlib.sha256(text.encode()).hexdigest(),
                   text=[{"text": text, "locator": "/scope/en", "language": "en"}])
    return Case(id=name, family=name, split=split, locale="en-CH", now=NOW, profile=profile(),
                facts=source, expected_relevant=expected, label_reference="synthetic authored test case", **changes)


def dataset(*cases):
    return Dataset(schema_version="tender-semantic-experiment-v1", provenance="synthetic_fixture",
                   author="contract-test-author", cases=cases)


async def prediction(entry, *, score=82, uncertain=False):
    text = entry.facts.text[0].text
    value = proposal(start=text.index("software development"), score=score)
    if uncertain:
        value.update(relevance="uncertain", score=None, facets=[])
    return await assess(entry.profile, entry.facts, now=entry.now, model=Model(json.dumps(value)),
                        identity=identity(), enabled=True)


async def test_counts_false_positives_missed_positives_abstentions_and_missing_predictions():
    entries = (case("positive"), case("false-positive", False), case("low", split="validation"),
               case("abstention", split="validation"), case("missing-negative", False, "validation"))
    results = {entries[0].id: await prediction(entries[0]), entries[1].id: await prediction(entries[1]),
               entries[2].id: await prediction(entries[2], score=30),
               entries[3].id: await prediction(entries[3], uncertain=True)}
    report = evaluate(dataset(*entries), results, threshold=80)
    assert report["metrics"] == {"cases": 5, "true_positive": 1, "false_positive": 1,
                                 "false_negative_including_abstentions": 2, "true_negative": 0,
                                 "abstained_or_failed": 2, "invalid_results": 0,
                                 "prediction_coverage": 0.6,
                                 "precision": 0.5, "recall": 1 / 3}
    assert report["by_split"]["development"]["cases"] == 2
    assert report["by_split_locale"]["validation/en-CH"]["cases"] == 3
    assert report["cases"][-1]["status"] == "missing_result"
    assert report["promotion_allowed"] is False


@pytest.mark.parametrize("field,value", [
    ("profile_sha256", "0" * 64), ("facts_sha256", "0" * 64), ("source_sha256", "0" * 64),
    ("input_sha256", "0" * 64), ("response_sha256", "0" * 64), ("prompt_sha256", "0" * 64),
    ("schema_sha256", "0" * 64), ("promotion", "approved"), ("evaluated_at", "2026-01-01T00:00:00Z"),
    ("status", "success"), ("runtime", None), ("raw_response", "{}"),
])
async def test_tampered_bindings_are_invalid_not_successful_predictions(field, value):
    entry = case("bound")
    result = await prediction(entry)
    result[field] = value
    report = evaluate(dataset(entry), {entry.id: result}, threshold=80)
    assert report["metrics"]["invalid_results"] == 1
    assert report["metrics"]["false_negative_including_abstentions"] == 1
    assert report["cases"][0]["predicted"] is None


async def test_parsed_score_cannot_be_replaced_without_changing_the_captured_response():
    entry = case("raw")
    result = await prediction(entry, score=20)
    result["proposal"]["score"] = 99
    assert evaluate(dataset(entry), {entry.id: result}, threshold=80)["metrics"]["invalid_results"] == 1


@pytest.mark.parametrize("key", ["family", "source", "scope"])
def test_source_and_family_leakage_between_development_and_validation_is_rejected(key):
    first = case("first")
    second = case("second", split="validation")
    value = second.model_dump(mode="json")
    if key == "family":
        value["family"] = first.family
    elif key == "source":
        value["facts"]["evidence_sha256"] = first.facts.evidence_sha256
    else:
        value["facts"]["text"] = first.facts.model_dump(mode="json")["text"]
    with pytest.raises(ValidationError, match="leaks"):
        dataset(first, Case.model_validate_json(json.dumps(value)))


async def test_different_model_runtimes_cannot_be_pooled_as_one_quality_result():
    first, second = case("one"), case("two", split="validation")
    a, b = await prediction(first), await prediction(second)
    b["runtime"]["runtime_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="separate runs"):
        evaluate(dataset(first, second), {first.id: a, second.id: b}, threshold=80)


async def test_exclusion_override_is_rejected_even_if_a_relevant_citation_is_exact():
    entry = case("excluded")
    selected = entry.profile.model_copy(update={"excluded_phrases": ("software development",)})
    entry = entry.model_copy(update={"profile": selected, "expected_relevant": False})
    result = await prediction(entry)
    assert result["status"] == "excluded"
    report = evaluate(dataset(entry), {entry.id: result}, threshold=80)
    assert report["metrics"]["true_negative"] == 1
    result["status"] = "assessed"
    assert evaluate(dataset(entry), {entry.id: result}, threshold=80)["metrics"]["invalid_results"] == 1


def test_missing_dataset_cases_threshold_and_duplicate_cases_are_not_silent_defaults():
    entry = case("one")
    for threshold in (True, -1, 101, "70"):
        with pytest.raises(ValueError):
            evaluate(dataset(entry), {}, threshold=threshold)
    with pytest.raises(ValueError):
        evaluate(dataset(entry), {"unknown": {}}, threshold=70)
    with pytest.raises(ValidationError, match="unique"):
        dataset(entry, entry)


async def test_cli_runs_without_app_env_model_or_database_and_preserves_previous_output(tmp_path):
    entry = case("cli")
    corpus = tmp_path / "dataset.json"
    captured = tmp_path / "results.json"
    output = tmp_path / "report.json"
    corpus.write_text(dataset(entry).model_dump_json(), encoding="utf-8")
    captured.write_text(json.dumps({entry.id: await prediction(entry)}), encoding="utf-8")
    script = Path(__file__).resolve().parents[3] / "scripts" / "evaluate_tender_semantics.py"
    command = [sys.executable, "-B", str(script), "--dataset", str(corpus), "--results", str(captured),
               "--threshold", "80", "--output", str(output)]
    run = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    report = json.loads(output.read_text())
    assert report["metrics"]["true_positive"] == 1 and report["promotion_allowed"] is False
    original = output.read_bytes()
    repeat = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert repeat.returncode != 0 and output.read_bytes() == original
    damaged = copy.deepcopy(json.loads(captured.read_text()))
    damaged[entry.id]["proposal"]["score"] = 99
    assert evaluate(dataset(entry), damaged, threshold=80)["metrics"]["invalid_results"] == 1
