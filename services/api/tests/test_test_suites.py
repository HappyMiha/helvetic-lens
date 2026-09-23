"""Exercise real pytest collection: selection cannot silently lose coverage."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.pytest_suites import load_inventory, tier_for

ROOT = Path(__file__).resolve().parents[3]


def fixture_tree(tmp_path, inventory=None):
    for name in ("startup", "parser", "database", "new_feature"):
        (tmp_path / f"test_{name}.py").write_text(
            f"from pathlib import Path\ndef test_{name}():\n"
            f"    Path({name!r}).write_text('executed')\n"
        )
    (tmp_path / "suites.json").write_text(json.dumps(inventory or {
        "smoke": ["test_startup.py"], "functional": ["test_parser.py"],
    }))
    (tmp_path / "conftest.py").write_text(
        "from pathlib import Path\nimport scripts.pytest_suites as policy\n"
        "policy.TEST_ROOT = Path(__file__).parent\npolicy.INVENTORY = policy.TEST_ROOT / 'suites.json'\n"
        "from scripts.pytest_suites import pytest_addoption, pytest_collection_modifyitems, pytest_terminal_summary\n"
    )
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n smoke: startup\n functional: logic\n integration: database\n"
    )


@pytest.mark.parametrize("suite,executed", [
    ("smoke", {"startup"}), ("functional", {"parser"}),
    ("integration", {"database", "new_feature"}),
    ("release", {"startup", "parser"}),
    ("full", {"startup", "parser", "database", "new_feature"}),
])
def test_real_pytest_selection_keeps_tiers_disjoint_and_unknown_tests_in_integration(tmp_path, suite, executed):
    fixture_tree(tmp_path)
    result = subprocess.run([sys.executable, "-m", "pytest", "--test-suite", suite, "-q"],
                            cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(ROOT)},
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {name for name in ("startup", "parser", "database", "new_feature")
            if (tmp_path / name).exists()} == executed
    assert f"{len(executed)} passed" in result.stdout


def test_renamed_critical_test_fails_selection_instead_of_silently_shrinking_gate(tmp_path):
    fixture_tree(tmp_path, {"smoke": ["test_removed.py"], "functional": ["test_parser.py"]})
    result = subprocess.run([sys.executable, "-m", "pytest", "--test-suite", "release", "-q"],
                            cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(ROOT)},
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 4 and "Stale test suite selectors" in result.stderr
    assert not (tmp_path / "startup").exists()


def test_overlapping_selectors_cannot_run_the_same_check_in_two_tiers():
    with pytest.raises(ValueError, match="multiple tiers"):
        tier_for("test_one.py::test_one", {"smoke": ["test_one.py"],
                                          "functional": ["test_one.py::test_one"]})


def test_reviewed_inventory_preserves_privacy_persistence_and_queue_smoke_checks():
    inventory = load_inventory()
    for node in ("test_auth.py::test_registration_creates_private_workspace_and_revocable_cookie_session",
                 "test_organization_isolation.py::test_private_records_are_hidden_and_public_fedlex_artifacts_are_reused",
                 "test_workflow.py::test_sources_versions_paused_state_and_results_survive_new_app",
                 "test_jobs.py::test_outbox_dispatch_and_worker_claim_are_idempotent"):
        assert tier_for(node, inventory) == "smoke"
    assert tier_for("test_new_feature.py::test_new_feature", inventory) == "integration"
