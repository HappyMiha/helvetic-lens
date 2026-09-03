import asyncio
import importlib
import sys

import pytest
from test_manager import manager_factory as manager_factory_fixture


class FakeManager:
    def inference_targets(self):
        return [
            {"slot": "gpu-0", "url": "http://127.0.0.1:18081", "device": 0},
            {"slot": "gpu-1", "url": "http://127.0.0.1:18082", "device": 1},
        ]


def load_gateway(monkeypatch, tmp_path):
    factory = manager_factory_fixture.__wrapped__(tmp_path, monkeypatch)
    manager, _ = factory()
    monkeypatch.setenv("MODEL_MANAGER_CATALOG", str(manager.catalog_path))
    monkeypatch.setenv("MODEL_MANAGER_LIBRARY", str(manager.library_path / "gateway"))
    monkeypatch.setenv("MODEL_MANAGER_LLAMA_SERVER", str(manager.llama_server))
    sys.modules.pop("model_manager.app", None)
    module = importlib.import_module("model_manager.app")
    monkeypatch.setattr(module, "manager", FakeManager())
    return module.FairAdmission()


@pytest.mark.asyncio
async def test_two_replicated_slots_have_distinct_owners(monkeypatch, tmp_path):
    admission = load_gateway(monkeypatch, tmp_path)
    first, _ = await admission.acquire("org-a", "interactive")
    second, _ = await admission.acquire("org-b", "interactive")
    assert {first["slot"], second["slot"]} == {"gpu-0", "gpu-1"}

    third_task = asyncio.create_task(admission.acquire("org-c", "interactive"))
    await asyncio.sleep(0.02)
    assert not third_task.done()
    await admission.release(first, "org-a")
    third, _ = await third_task
    assert third["slot"] == first["slot"]
    await admission.release(second, "org-b")
    await admission.release(third, "org-c")


@pytest.mark.asyncio
async def test_interactive_priority_and_background_aging(monkeypatch, tmp_path):
    admission = load_gateway(monkeypatch, tmp_path)
    first, _ = await admission.acquire("holder-a", "interactive")
    second, _ = await admission.acquire("holder-b", "interactive")
    background = asyncio.create_task(admission.acquire("org-background", "background"))
    await asyncio.sleep(0.02)
    interactive = asyncio.create_task(admission.acquire("org-interactive", "interactive"))
    await asyncio.sleep(0.02)
    await admission.release(first, "holder-a")
    selected, _ = await interactive
    assert selected["slot"] == first["slot"]
    assert not background.done()
    await admission.release(selected, "org-interactive")
    aged, _ = await background
    await admission.release(second, "holder-b")
    await admission.release(aged, "org-background")


@pytest.mark.asyncio
async def test_waiting_organization_gets_a_slot_before_an_active_tenant_expands(
    monkeypatch, tmp_path
):
    admission = load_gateway(monkeypatch, tmp_path)
    first, _ = await admission.acquire("org-a", "interactive")
    second, _ = await admission.acquire("org-a", "interactive")

    org_a_again = asyncio.create_task(admission.acquire("org-a", "interactive"))
    await asyncio.sleep(0.02)
    org_b = asyncio.create_task(admission.acquire("org-b", "interactive"))
    await asyncio.sleep(0.02)

    await admission.release(first, "org-a")
    selected, _ = await org_b
    assert selected["slot"] == first["slot"]
    assert not org_a_again.done()

    snapshot = await admission.snapshot()
    assert snapshot["oldest_wait_ms"] >= 0
    snapshot.pop("oldest_wait_ms")
    assert snapshot == {
        "slots": 2,
        "busy_slots": 2,
        "available_slots": 0,
        "waiting": 1,
        "waiting_organizations": 1,
        "waiting_by_priority": {"interactive": 1, "background": 0},
        "served": 1,
    }

    await admission.release(second, "org-a")
    final, _ = await org_a_again
    await admission.release(selected, "org-b")
    await admission.release(final, "org-a")


@pytest.mark.asyncio
async def test_admission_is_work_conserving_for_one_organization(monkeypatch, tmp_path):
    admission = load_gateway(monkeypatch, tmp_path)
    first, _ = await admission.acquire("org-a", "interactive")
    second, _ = await admission.acquire("org-a", "background")

    assert {first["slot"], second["slot"]} == {"gpu-0", "gpu-1"}
    await admission.release(first, "org-a")
    await admission.release(second, "org-a")
