"""Reviewed, disjoint API test tiers; new tests default to integration."""

import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

TEST_ROOT = Path(__file__).resolve().parents[1] / "services/api/tests"
INVENTORY = TEST_ROOT / "suites.json"
TIERS = ("smoke", "functional", "integration")
SUITES = (*TIERS, "release", "full")


def load_inventory(path=None):
    inventory = json.loads((path or INVENTORY).read_text(encoding="utf-8"))
    if set(inventory) != {"smoke", "functional"}:
        raise ValueError("The test inventory must contain smoke and functional selectors.")
    for selectors in inventory.values():
        if (not isinstance(selectors, list) or not selectors
                or any(not isinstance(value, str) or not value for value in selectors)
                or len(set(selectors)) != len(selectors)):
            raise ValueError("Test selectors must be unique, nonempty strings.")
    return inventory


def tier_for(node, inventory):
    module = node.split("::", 1)[0]
    matches = [tier for tier, selectors in inventory.items() if module in selectors or node in selectors]
    if len(matches) > 1:
        raise ValueError(f"Test belongs to multiple tiers: {node}")
    return matches[0] if matches else "integration"


def selected_tiers(suite):
    return TIERS if suite in {None, "full"} else ("smoke", "functional") if suite == "release" else (suite,)


def pytest_addoption(parser):
    parser.addoption("--test-suite", choices=SUITES, default=None,
                     help="API test tier; release = smoke + functional, full = every test.")


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    inventory = load_inventory()
    suite = config.getoption("--test-suite")
    allowed = selected_tiers(suite)
    selected, deselected, seen = [], [], set()
    for item in items:
        if not Path(item.path).is_relative_to(TEST_ROOT):
            selected.append(item)
            continue
        module = Path(item.path).relative_to(TEST_ROOT).as_posix()
        name = item.nodeid.split("::", 1)[1].split("[", 1)[0]
        node = f"{module}::{name}"
        seen.update((module, node))
        try:
            tier = tier_for(node, inventory)
        except ValueError as error:
            raise pytest.UsageError(str(error)) from error
        if tier == "functional" and "harness" in item.fixturenames:
            raise pytest.UsageError(f"Application fixture cannot be functional-only: {node}")
        item.add_marker(getattr(pytest.mark, tier))
        item.user_properties.append(("test_suite", tier))
        (selected if tier in allowed else deselected).append(item)
    # Tier commands always collect the complete API tree. A removed/renamed
    # critical check must fail, never silently reduce the release gate.
    if suite is not None:
        missing = set().union(*map(set, inventory.values())) - seen
        if missing:
            raise pytest.UsageError("Stale test suite selectors: " + ", ".join(sorted(missing)))
    config.hook.pytest_deselected(items=deselected)
    items[:] = selected


def pytest_terminal_summary(terminalreporter):
    counts = defaultdict(Counter)
    for outcome in ("passed", "failed", "error", "skipped"):
        for report in terminalreporter.stats.get(outcome, []):
            tier = dict(report.user_properties).get("test_suite")
            if tier and (report.when == "call" or outcome in {"error", "skipped"}):
                counts[tier][outcome] += 1
    if counts:
        terminalreporter.write_sep("-", "API test suites")
        for tier in TIERS:
            if tier in counts:
                terminalreporter.write_line(f"{tier}: " + ", ".join(
                    f"{count} {outcome}" for outcome, count in counts[tier].items()))
