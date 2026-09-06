"""Synthetic approvals test integrity, never promote a real model."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from helvetic_lens.ai_capabilities import (
    MAX_ARTIFACT_BYTES,
    CapabilityRegistry,
    RuntimeIdentity,
    load_registry,
    resolve_capability,
)

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "scripts/check_ai_capabilities.py"
DEFAULT_REGISTRY = ROOT / "services/api/helvetic_lens/ai-capability-profiles.json"


@pytest.fixture
def artifacts(tmp_path):
    identity = {
        "model_id": "synthetic-fixture", "model_revision": "1" * 40,
        "artifact_sha256": "a" * 64, "tokenizer_sha256": "b" * 64,
        "chat_template_sha256": "c" * 64, "runtime_sha256": "d" * 64,
        "hardware_profile": "synthetic-no-hardware",
    }
    budget = {"context_window_tokens": 4096, "input_tokens": 3000, "output_tokens": 700, "safety_tokens": 396}
    review = {
        "schema_version": "ai-explanation-review-v1",
        "profile_id": "synthetic-explanations", "profile_revision": 1,
        "identity": identity, "task": "ask", "locale": "en-CH", "budget": budget,
        "dataset_sha256": "e" * 64, "results_sha256": "f" * 64,
        "evaluator_revision": "a" * 40, "reviewer": "Synthetic test reviewer",
        "reviewed_at": "2026-09-06T12:00:00Z",
        "review_reference": "Synthetic test record; not a real independent evaluation",
        "independent_review": True, "outcome": "pass",
    }
    registry = {
        "schema_version": "ai-capability-registry-v1",
        "profiles": [{
            "id": review["profile_id"], "revision": 1, "status": "approved", "identity": identity,
            "grants": [{"task": "ask", "locale": "en-CH", "budget": budget,
                        "evaluation": {"path": "review.json", "sha256": "0" * 64}}],
        }],
    }

    def write(*, rehash=True):
        raw = json.dumps(review).encode()
        (tmp_path / "review.json").write_bytes(raw)
        if rehash:
            registry["profiles"][0]["grants"][0]["evaluation"]["sha256"] = hashlib.sha256(raw).hexdigest()
        path = tmp_path / "registry.json"
        path.write_text(json.dumps(registry), encoding="utf-8")
        return path

    write()
    return tmp_path, identity, review, registry, write


def decide(registry, observed_identity, **overrides):
    arguments = {
        "profile_id": "synthetic-explanations",
        "identity": RuntimeIdentity.model_validate(observed_identity), "task": "ask", "locale": "en-CH",
        **overrides,
    }
    return resolve_capability(registry, **arguments)


def test_exact_reviewed_scope_is_allowed_but_provider_is_not_an_input(artifacts):
    root, identity, _, _, write = artifacts
    registry = load_registry(write(), root)
    decision = decide(registry, identity)
    assert decision.mode == "generated_explanation"
    assert decision.reason == "reviewed_scope"
    assert decision.budget.input_tokens == 3000
    assert decision.evaluation.path == "review.json"
    assert len(decision.fingerprint) == 64
    assert decide(registry, identity).fingerprint == decision.fingerprint
    with pytest.raises(TypeError):
        decide(registry, identity, provider="infomaniak")


@pytest.mark.parametrize("overrides,reason", [
    ({"profile_id": None}, "profile_not_selected"),
    ({"profile_id": "other-model"}, "profile_unknown"),
    ({"identity": None}, "runtime_identity_unavailable"),
    ({"locale": "rm-CH"}, "scope_not_reviewed"),
    ({"locale": "en"}, "scope_not_reviewed"),
    ({"locale": "en-US"}, "scope_not_reviewed"),
    ({"locale": ""}, "scope_not_reviewed"),
    ({"task": "impact_report"}, "scope_not_reviewed"),
    ({"task": "relation_impact"}, "scope_not_reviewed"),
])
def test_no_implicit_profile_task_locale_or_identity_fallback(artifacts, overrides, reason):
    root, identity, _, _, write = artifacts
    registry = load_registry(write(), root)
    result = decide(registry, identity, **overrides)
    assert (result.mode, result.reason) == ("selected_evidence", reason)
    assert result.budget is None and result.evaluation is None
    assert result.fingerprint != decide(registry, identity).fingerprint


@pytest.mark.parametrize("field", [
    "model_id", "model_revision", "artifact_sha256", "tokenizer_sha256",
    "chat_template_sha256", "runtime_sha256", "hardware_profile",
])
def test_changed_runtime_cannot_reuse_approval_or_fingerprint(artifacts, field):
    root, identity, _, _, write = artifacts
    registry = load_registry(write(), root)
    changed_value = "9" * 64 if field.endswith("sha256") else "changed"
    if field == "model_revision":
        changed_value = "9" * 40
    changed = {**identity, field: changed_value}
    result = decide(registry, changed)
    assert result.reason == "runtime_identity_mismatch"
    assert result.mode == "selected_evidence"
    assert result.fingerprint != decide(registry, identity).fingerprint


@pytest.mark.parametrize("revision", ["main", "latest", "v1.5", "", "g" * 40])
def test_floating_model_revision_cannot_be_observed_as_immutable(artifacts, revision):
    _, identity, _, _, _ = artifacts
    with pytest.raises(ValidationError):
        RuntimeIdentity.model_validate({**identity, "model_revision": revision})


def test_each_task_and_locale_requires_its_own_verified_artifact(artifacts):
    root, identity, review, data, write = artifacts
    path = write()
    profile = data["profiles"][0]
    profile["grants"] = []
    for task in ("ask", "impact_report"):
        for locale in ("de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"):
            filename = f"{task}-{locale}.json"
            raw = json.dumps({**review, "task": task, "locale": locale}).encode()
            (root / filename).write_bytes(raw)
            profile["grants"].append({
                "task": task, "locale": locale, "budget": review["budget"],
                "evaluation": {"path": filename, "sha256": hashlib.sha256(raw).hexdigest()},
            })
    path.write_text(json.dumps(data), encoding="utf-8")
    registry = load_registry(path, root)
    fingerprints = {
        decide(registry, identity, task=grant.task, locale=grant.locale).fingerprint
        for grant in registry.profiles[0].grants
    }
    assert len(fingerprints) == 10
    assert all(
        decide(registry, identity, task=grant.task, locale=grant.locale).mode == "generated_explanation"
        for grant in registry.profiles[0].grants
    )
    # No silent partial success if even one advertised locale loses its review.
    (root / "impact_report-rm-CH.json").unlink()
    with pytest.raises(FileNotFoundError):
        load_registry(path, root)


@pytest.mark.parametrize("status", ["candidate", "revoked"])
def test_unapproved_profiles_stay_limited_without_loading_old_review(artifacts, status):
    root, identity, _, data, write = artifacts
    before = decide(load_registry(write(), root), identity)
    data["profiles"][0]["status"] = status
    path = write()
    (root / "review.json").unlink()
    result = decide(load_registry(path, root), identity)
    assert result.reason == "profile_not_approved"
    assert result.mode == "selected_evidence"
    assert result.fingerprint != before.fingerprint


@pytest.mark.parametrize("field,value", [
    ("schema_version", "HL-032-local-structured-v2"),
    ("profile_id", "another-profile"), ("profile_revision", 2),
    ("task", "impact_report"), ("locale", "fr-CH"),
    ("independent_review", False), ("independent_review", 1),
    ("outcome", "fail"), ("reviewer", " "),
    ("dataset_sha256", "unknown"), ("results_sha256", ""),
    ("evaluator_revision", "main"),
    ("reviewed_at", "2026-09-06T12:00:00"), ("reviewed_at", "not a date"),
])
def test_transport_success_or_mismatched_review_cannot_approve(artifacts, field, value):
    root, _, review, _, write = artifacts
    review[field] = value
    with pytest.raises(ValueError):
        load_registry(write(), root)


def test_review_must_match_entire_budget_and_runtime(artifacts):
    root, _, review, data, write = artifacts
    # Break shared fixture objects deliberately: test differing reviewed inputs.
    review["budget"] = {**review["budget"], "output_tokens": 600}
    with pytest.raises(ValueError, match="does not match"):
        load_registry(write(), root)
    review["budget"] = data["profiles"][0]["grants"][0]["budget"]
    review["identity"] = {**review["identity"], "runtime_sha256": "0" * 64}
    with pytest.raises(ValueError, match="does not match"):
        load_registry(write(), root)


def test_evidence_missing_or_changed_never_becomes_a_partial_approval(artifacts):
    root, _, review, _, write = artifacts
    path = write()
    (root / "review.json").unlink()
    with pytest.raises(FileNotFoundError):
        load_registry(path, root)
    review["review_reference"] = "Modified after approval"
    with pytest.raises(ValueError, match="checksum"):
        load_registry(write(rehash=False), root)


@pytest.mark.parametrize("path", [
    "../review.json", "/review.json", "C:/review.json", "..\\review.json",
    "file:///review.json", "https://example.test/review.json", "./review.json",
    "sub//review.json", "review.txt",
])
def test_evidence_paths_never_fetch_or_escape_root(artifacts, path):
    root, _, _, data, write = artifacts
    data["profiles"][0]["grants"][0]["evaluation"]["path"] = path
    with pytest.raises(ValueError):
        load_registry(write(), root)


@pytest.mark.parametrize("field,value", [
    ("input_tokens", 3001), ("input_tokens", True), ("input_tokens", "3000"),
    ("output_tokens", 8193), ("safety_tokens", 0),
])
def test_budget_is_strict_and_includes_output_and_safety_reserve(artifacts, field, value):
    root, _, _, data, write = artifacts
    data["profiles"][0]["grants"][0]["budget"][field] = value
    with pytest.raises(ValueError):
        load_registry(write(), root)


def test_profile_or_review_revision_change_invalidates_decision(artifacts):
    root, identity, review, data, write = artifacts
    before = decide(load_registry(write(), root), identity)
    data["profiles"][0]["revision"] = review["profile_revision"] = 2
    after = decide(load_registry(write(), root), identity)
    assert after.mode == "generated_explanation"
    assert after.profile_revision == 2
    assert before.fingerprint != after.fingerprint
    review["review_reference"] = "New independent review artifact"
    assert after.fingerprint != decide(load_registry(write(), root), identity).fingerprint


@pytest.mark.parametrize("duplicate", ["profile", "grant"])
def test_duplicates_do_not_make_resolution_depend_on_order(artifacts, duplicate):
    root, _, _, data, write = artifacts
    target = data["profiles"] if duplicate == "profile" else data["profiles"][0]["grants"]
    target.append(copy.deepcopy(target[0]))
    with pytest.raises(ValueError):
        load_registry(write(), root)


def test_extra_or_missing_approval_fields_are_rejected(artifacts):
    root, _, _, data, write = artifacts
    data["profiles"][0]["cloud_fallback"] = True
    with pytest.raises(ValueError):
        load_registry(write(), root)
    del data["profiles"][0]["cloud_fallback"]
    data["profiles"][0]["grants"] = []
    with pytest.raises(ValidationError):
        CapabilityRegistry.model_validate_json(json.dumps(data))


def test_artifacts_are_bounded_before_parsing(artifacts):
    root, _, _, _, write = artifacts
    path = write()
    path.write_bytes(b" " * (MAX_ARTIFACT_BYTES + 1))
    with pytest.raises(ValueError, match="one MiB"):
        load_registry(path, root)
    path = write()
    (root / "review.json").write_bytes(b" " * (MAX_ARTIFACT_BYTES + 1))
    with pytest.raises(ValueError, match="one MiB"):
        load_registry(path, root)


def test_shipped_registry_approves_nothing_and_cli_does_not_claim_quality():
    registry = load_registry(DEFAULT_REGISTRY, ROOT)
    assert not registry.profiles
    result = resolve_capability(registry, profile_id=None, identity=None, task="ask", locale="en-CH")
    assert result.mode == "selected_evidence"
    for require, exit_code in [(False, 0), (True, 1)]:
        completed = subprocess.run(
            [sys.executable, str(CLI), *(["--require-approved"] if require else [])],
            capture_output=True, text=True, check=False,
        )
        assert completed.returncode == exit_code, completed.stderr
        report = json.loads(completed.stdout)
        assert report["valid"] is True
        assert report["approved_profiles"] == report["approved_task_locale_grants"] == 0
        assert report["explanation_approval_available"] is False
        assert report["semantic_quality_verified_by_this_check"] is False
        assert report["runtime_routing_enabled_by_this_check"] is False


def test_cli_returns_redacted_failure_without_printing_untrusted_artifact(artifacts):
    root, _, _, _, write = artifacts
    path = write()
    path.write_text('{"SECRET_TEST_SENTINEL": "not a registry"}', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(CLI), "--registry", str(path), "--evidence-root", str(root)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "SECRET_TEST_SENTINEL" not in result.stdout + result.stderr
    assert json.loads(result.stdout) == {"valid": False, "error": "invalid_registry_or_review_evidence"}


def test_cli_accepts_verified_synthetic_approval_without_mutations(artifacts):
    root, _, _, _, write = artifacts
    path = write()
    before = {file.name: file.read_bytes() for file in root.iterdir()}
    result = subprocess.run(
        [sys.executable, str(CLI), "--registry", str(path), "--evidence-root", str(root), "--require-approved"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["valid"] is True
    assert report["approved_profiles"] == report["approved_task_locale_grants"] == 1
    assert report["explanation_approval_available"] is True
    assert report["semantic_quality_verified_by_this_check"] is False
    assert report["runtime_routing_enabled_by_this_check"] is False
    assert {file.name: file.read_bytes() for file in root.iterdir()} == before
