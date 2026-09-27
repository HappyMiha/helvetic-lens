"""Pinned local multilingual decisions; no generative model or private corpus."""
import os
from pathlib import Path

import torch
import uvicorn
from laya import Router
from laya import serve

REVISION = "e4e9ddf21a7b1903b7acffd8814ad4307bf63a67"


class LocalRouter(Router):
    def predict(self, state, questions, **kwargs):
        # One short source per request; never silently use the 1,024-token default.
        result = super().predict(state, questions, model="multilingual", max_len=8192)
        result["model"] = "laya-multilingual@" + REVISION
        return result


if __name__ == "__main__":
    os.environ["LAYA_API_KEY"] = Path("/run/secrets/laya_key").read_text().strip()
    torch.set_num_threads(2)
    serve.MAX_QUESTIONS = 2
    serve.MAX_STATE_CHARS = 4000
    serve.MAX_BODY_BYTES = 20000
    router = LocalRouter(device="cpu", standalone_repos=True,
                         revisions={"multilingual": REVISION}, max_loaded=1)
    router.preload(["multilingual"])
    uvicorn.run(serve.create_app(router), host="0.0.0.0", port=8000, access_log=False)
