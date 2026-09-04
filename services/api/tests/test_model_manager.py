import copy


class FakeModelManager:
    def __init__(self):
        self.actions = []
        self.model = {
            "id": "apertus-test",
            "family": "Apertus",
            "served_model_id": "local-apertus",
            "sha256": "a" * 64,
            "size_bytes": 100,
            "state": "available",
            "installed": False,
            "license_accepted": False,
            "compatibility": {"status": "compatible", "reason": "Test host is compatible."},
            "requirements": {"recommended_context": 1024},
            "download": {
                "downloaded_bytes": 0,
                "total_bytes": 100,
                "cached_copy_available": True,
                "resumable": False,
            },
        }

    async def inventory(self):
        if self.model["state"] == "downloading":
            self.model.update(state="available", installed=True)
            self.model["download"]["downloaded_bytes"] = 100
        elif self.model["state"] == "starting":
            self.model["state"] = "ready"
        return {
            "catalog_version": 1,
            "runtime_image": "llama.cpp@sha256:test",
            "hardware": {"cuda_devices": [{"name": "Test GPU"}]},
            "deployment": {"state": self.model["state"]},
            "models": [copy.deepcopy(self.model)],
        }

    async def profile(self, profile_id):
        assert profile_id == "assistant-lite"
        return {
            "id": profile_id,
            "display_name": "Marvin local assistant",
            "state": "needs_download",
            "ready": False,
            "reused_active_runner": False,
            "selected_model": {
                "id": "apertus-test",
                "display_name": "Apertus test",
                "served_model_id": "local-apertus",
            },
            "policy": {"cloud_fallback": False, "single_runtime": True},
        }

    async def probe(self):
        return {"cuda_devices": [{"name": "Test GPU"}]}

    async def accept_license(self, model_id, accepted):
        self.model["license_accepted"] = accepted
        return copy.deepcopy(self.model)

    async def command(self, model_id, action, **params):
        self.actions.append((model_id, action, params))
        if action == "download":
            self.model["state"] = "downloading"
        elif action == "start":
            self.model["state"] = "starting"
        elif action == "stop":
            self.model["state"] = "stopped"
        elif action == "remove":
            self.model.update(state="available", installed=False)
        return copy.deepcopy(self.model)


def test_admin_can_accept_download_start_and_remove_allowlisted_model(harness, monkeypatch):
    client, _, service, _ = harness
    manager = FakeModelManager()
    service.model_manager = manager

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr("helvetic_lens.service.asyncio.sleep", no_wait)
    inventory = client.get("/api/admin/models?refresh_hardware=true")
    assert inventory.status_code == 200
    assert inventory.json()["models"][0]["id"] == "apertus-test"

    accepted = client.post(
        "/api/admin/models/apertus-test/license", json={"accepted": True}
    )
    assert accepted.status_code == 200
    assert accepted.json()["license_accepted"] is True

    download = client.post("/api/admin/models/apertus-test/download")
    assert download.status_code == 202
    assert download.json()["state"] == "succeeded"
    assert download.json()["result"]["data"]["model"]["installed"] is True

    started = client.post("/api/admin/models/apertus-test/start")
    assert started.status_code == 202
    assert started.json()["state"] == "succeeded"
    assert started.json()["result"]["data"]["model"]["state"] == "ready"
    selected = client.get("/api/settings/apertus").json()
    assert selected["provider"] == "docker"
    assert selected["model"] == "local-apertus"

    assert client.post("/api/admin/models/apertus-test/stop").json()["state"] == "stopped"
    assert client.delete("/api/admin/models/apertus-test").json()["installed"] is False
    assert ("apertus-test", "download", {"cached": True}) in manager.actions


def test_assistant_runtime_exposes_local_profile_without_admin_access(harness):
    client, _, service, _ = harness
    service.model_manager = FakeModelManager()

    response = client.get("/api/assistant/runtime")

    assert response.status_code == 200
    assert response.json()["id"] == "assistant-lite"
    assert response.json()["policy"]["cloud_fallback"] is False
