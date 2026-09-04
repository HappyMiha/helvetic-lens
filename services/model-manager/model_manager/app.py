from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from .core import ModelManager, ModelManagerError


class Acceptance(BaseModel):
    accepted: bool


@dataclass
class WaitingRequest:
    organization: str
    priority: str
    sequence: int
    queued_at: float


class FairAdmission:
    """One owner per runner with organization fairness and priority aging."""

    def __init__(self):
        self.condition = asyncio.Condition()
        self.waiting: list[WaitingRequest] = []
        self.owners: dict[str, str] = {}
        self.sequence = 0
        self.last_served: dict[str, int] = {}
        self.served = 0

    def _rank(self, item: WaitingRequest, now: float):
        base = 0 if item.priority == "interactive" else 10
        # Background work gains one priority level every 15 seconds so it
        # cannot starve behind a continuous stream of interactive requests.
        aged = max(0, base - int((now - item.queued_at) / 15))
        return (aged, self.last_served.get(item.organization, -1), item.sequence)

    def _winner(self, now: float) -> WaitingRequest:
        active_organizations = set(self.owners.values())
        unrepresented = [
            item for item in self.waiting if item.organization not in active_organizations
        ]
        candidates = unrepresented or self.waiting
        return min(candidates, key=lambda value: self._rank(value, now))

    async def acquire(self, organization: str, priority: str, timeout: float = 300):
        async with self.condition:
            self.sequence += 1
            item = WaitingRequest(organization, priority, self.sequence, time.monotonic())
            self.waiting.append(item)
            deadline = time.monotonic() + timeout
            while True:
                targets = manager.inference_targets()
                available = next(
                    (target for target in targets if target["slot"] not in self.owners),
                    None,
                )
                winner = self._winner(time.monotonic())
                if available and winner is item:
                    self.waiting.remove(item)
                    self.owners[available["slot"]] = organization
                    return available, (time.monotonic() - item.queued_at) * 1000
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.waiting.remove(item)
                    raise TimeoutError("Local inference admission timed out.")
                try:
                    await asyncio.wait_for(self.condition.wait(), timeout=min(remaining, 2))
                except TimeoutError:
                    pass

    async def release(self, target: dict, organization: str):
        async with self.condition:
            owner = self.owners.pop(target["slot"], organization)
            self.served += 1
            self.last_served[owner] = self.served
            self.condition.notify_all()

    async def snapshot(self) -> dict:
        async with self.condition:
            targets = manager.inference_targets()
            now = time.monotonic()
            by_priority = {"interactive": 0, "background": 0}
            for item in self.waiting:
                by_priority[item.priority] = by_priority.get(item.priority, 0) + 1
            oldest_wait_ms = max(
                ((now - item.queued_at) * 1000 for item in self.waiting),
                default=0,
            )
            return {
                "slots": len(targets),
                "busy_slots": len(self.owners),
                "available_slots": max(0, len(targets) - len(self.owners)),
                "waiting": len(self.waiting),
                "waiting_organizations": len({item.organization for item in self.waiting}),
                "waiting_by_priority": by_priority,
                "oldest_wait_ms": round(oldest_wait_ms, 1),
                "served": self.served,
            }


manager = ModelManager(
    Path(os.environ.get("MODEL_MANAGER_CATALOG", "/manager/catalog.json")),
    Path(os.environ.get("MODEL_MANAGER_LIBRARY", "/models")),
    Path(os.environ.get("MODEL_MANAGER_LLAMA_SERVER", "/app/llama-server")),
    os.environ.get("MODEL_MANAGER_RUNTIME_IMAGE", "unrecorded"),
)
app = FastAPI(title="Helvetic Lens private model manager", version="1")
admission = FairAdmission()


@app.on_event("shutdown")
def shutdown_runtime():
    if manager.runner_model_id:
        manager.stop_model(manager.runner_model_id)


@app.exception_handler(ModelManagerError)
def model_manager_error(_request, error: ModelManagerError):
    return JSONResponse(status_code=error.status, content={"detail": error.message, "code": error.code})


@app.get("/health")
def health():
    return {"status": "ok", "runtime_supported": manager.hardware["runtime_supported"]}


@app.get("/v1/inventory")
async def inventory():
    payload = manager.inventory()
    payload["admission"] = await admission.snapshot()
    return payload


@app.get("/v1/profiles/{profile_id}")
def workload_profile(profile_id: str):
    return manager.describe_profile(profile_id)


@app.post("/v1/hardware/probe")
def probe_hardware():
    return manager.refresh_hardware()


@app.post("/v1/models/{model_id}/license")
def accept_license(model_id: str, data: Acceptance):
    return manager.accept_license(model_id, data.accepted)


@app.post("/v1/models/{model_id}/download")
def download(model_id: str, cached: bool = Query(default=False)):
    return manager.start_download(model_id, use_cached_copy=cached)


@app.post("/v1/models/{model_id}/download/pause")
def pause_download(model_id: str):
    return manager.pause_download(model_id)


@app.post("/v1/models/{model_id}/download/cancel")
def cancel_download(model_id: str):
    return manager.cancel_download(model_id)


@app.post("/v1/models/{model_id}/start")
def start_model(model_id: str, profile: str | None = Query(default=None)):
    return manager.start_model(model_id, profile)


@app.post("/v1/models/{model_id}/stop")
def stop_model(model_id: str):
    return manager.stop_model(model_id)


@app.delete("/v1/models/{model_id}")
def remove_model(model_id: str, referenced: bool = Query(default=False)):
    return manager.remove_model(model_id, referenced=referenced)


@app.get("/v1/logs")
def logs():
    return {"lines": manager.log_tail()}


async def proxy_local(
    request: Request,
    path: str,
    organization: str,
    priority: str,
):
    if priority not in {"interactive", "background"}:
        priority = "background"
    try:
        target, queue_wait_ms = await admission.acquire(organization[:80], priority)
    except TimeoutError:
        return JSONResponse(
            status_code=504,
            content={"error": {"code": 504, "message": "Local inference queue timed out."}},
        )
    try:
        body = await request.body()
        headers = {"content-type": request.headers.get("content-type", "application/json")}
        async with httpx.AsyncClient(timeout=300, trust_env=False) as client:
            response = await client.request(
                request.method,
                target["url"] + "/v1/" + path,
                content=body or None,
                headers=headers,
            )
        returned_headers = {
            "content-type": response.headers.get("content-type", "application/json"),
            "x-helvetic-queue-wait-ms": f"{queue_wait_ms:.2f}",
            "x-helvetic-slot": target["slot"],
        }
        return Response(response.content, status_code=response.status_code, headers=returned_headers)
    except httpx.RequestError as exc:
        return JSONResponse(
            status_code=502,
            content={"error": {"code": 502, "message": f"Local runner transport failed: {type(exc).__name__}"}},
        )
    finally:
        await admission.release(target, organization[:80])


@app.api_route("/openai/v1/chat/completions", methods=["POST"])
async def chat_completions(
    request: Request,
    x_helvetic_organization: str = Header(default="default"),
    x_helvetic_priority: str = Header(default="interactive"),
):
    return await proxy_local(
        request, "chat/completions", x_helvetic_organization, x_helvetic_priority
    )


@app.api_route("/openai/v1/models", methods=["GET"])
async def list_local_models(
    request: Request,
    x_helvetic_organization: str = Header(default="default"),
):
    return await proxy_local(request, "models", x_helvetic_organization, "interactive")
