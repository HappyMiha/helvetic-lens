from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .core import ModelManager, ModelManagerError


class Acceptance(BaseModel):
    accepted: bool


manager = ModelManager(
    Path(os.environ.get("MODEL_MANAGER_CATALOG", "/manager/catalog.json")),
    Path(os.environ.get("MODEL_MANAGER_LIBRARY", "/models")),
    Path(os.environ.get("MODEL_MANAGER_LLAMA_SERVER", "/app/llama-server")),
    os.environ.get("MODEL_MANAGER_RUNTIME_IMAGE", "unrecorded"),
)
app = FastAPI(title="Helvetic Lens private model manager", version="1")


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
def inventory():
    return manager.inventory()


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
def start_model(model_id: str):
    return manager.start_model(model_id)


@app.post("/v1/models/{model_id}/stop")
def stop_model(model_id: str):
    return manager.stop_model(model_id)


@app.delete("/v1/models/{model_id}")
def remove_model(model_id: str, referenced: bool = Query(default=False)):
    return manager.remove_model(model_id, referenced=referenced)


@app.get("/v1/logs")
def logs():
    return {"lines": manager.log_tail()}
