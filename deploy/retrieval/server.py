"""Local pinned embeddings; no text/vector cache, request logs or hosted fallback."""
import asyncio
import hashlib
import hmac
import json
from pathlib import Path

import torch
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from torch.nn import functional
from transformers import AutoModel, AutoTokenizer

MODEL = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
IDENTITY = MODEL + "@" + REVISION


class Encoder:
    def __init__(self):
        torch.set_num_threads(2)
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION, local_files_only=True, trust_remote_code=False)
        self.model = AutoModel.from_pretrained(MODEL, revision=REVISION, local_files_only=True,
                                               trust_remote_code=False, use_safetensors=True).eval()

    def encode(self, texts):
        lengths = [len(ids) for ids in self.tokenizer(texts, truncation=False)["input_ids"]]
        batch = self.tokenizer(texts, max_length=512, padding=True, truncation=True, return_tensors="pt")
        with torch.inference_mode():
            hidden = self.model(**batch).last_hidden_state
            hidden = hidden.masked_fill(~batch["attention_mask"][..., None].bool(), 0.0)
            pooled = hidden.sum(dim=1) / batch["attention_mask"].sum(dim=1)[..., None]
            vectors = functional.normalize(pooled, p=2, dim=1).tolist()
        return [{"index": index, "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
                 "input_tokens": length, "truncated": length > 512, "embedding": vector}
                for index, (text, length, vector) in enumerate(zip(texts, lengths, vectors))]


def create_app(encoder, key):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    semaphore = asyncio.Semaphore(1)

    def error(code, status):
        return JSONResponse({"error": code}, status_code=status, headers={"Cache-Control": "no-store"})

    @app.get("/health")
    async def health():
        return {"status": "ok", "model": IDENTITY, "dimensions": 384, "max_tokens": 512, "max_batch": 16}

    @app.post("/v1/embeddings")
    async def embeddings(request: Request):
        if not hmac.compare_digest(request.headers.get("authorization", "").encode(), ("Bearer " + key).encode()):
            return error("unauthorized", 401)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 300000:
                return error("body_too_large", 413)
        try:
            payload = json.loads(body)
            texts = payload["input"]
            if (set(payload) != {"input"} or not isinstance(texts, list) or not 1 <= len(texts) <= 16
                    or any(not isinstance(text, str) or not 1 <= len(text) <= 4000
                           or not text.startswith(("query: ", "passage: ")) for text in texts)):
                return error("invalid_input", 422)
        except (ValueError, KeyError, TypeError, RecursionError):
            return error("invalid_input", 422)
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=0.01)
        except TimeoutError:
            return error("busy", 429)
        try:
            # Shield the CPU operation so cancellation cannot release its memory
            # slot while the inference thread is still running.
            work = asyncio.create_task(asyncio.to_thread(encoder.encode, texts))
            try:
                result = await asyncio.shield(work)
            except asyncio.CancelledError:
                await work
                raise
            return JSONResponse({"model": IDENTITY, "data": result}, headers={"Cache-Control": "no-store"})
        except (RuntimeError, ValueError, TypeError, MemoryError):
            return error("inference_unavailable", 503)
        finally:
            semaphore.release()

    return app


if __name__ == "__main__":
    token = Path("/run/secrets/local_key").read_text().strip()
    if len(token) < 24:
        raise RuntimeError("A protected local service token is required.")
    uvicorn.run(create_app(Encoder(), token), host="0.0.0.0", port=8000, access_log=False, limit_concurrency=8)
