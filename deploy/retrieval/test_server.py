"""Run inside the isolated retrieval image; no model calls or provider secrets."""
import asyncio
import threading
import unittest

import httpx
from server import IDENTITY, create_app


class Contract(unittest.IsolatedAsyncioTestCase):
    async def test_auth_limits_no_echo_and_no_store(self):
        calls = []
        class Encoder:
            def encode(self, texts):
                calls.append(texts)
                return [{"index": 0, "embedding": [1.0]}]
        app = create_app(Encoder(), "fixture-only-local-token")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://local") as client:
            assert (await client.get("/health")).json()["model"] == IDENTITY
            assert (await client.post("/v1/embeddings", json={"input": ["query: secret"]})).status_code == 401
            headers = {"Authorization": "Bearer fixture-only-local-token"}
            for body in ({"input": ["private-sentinel"]}, {"input": ["query: text"] * 17}, {"input": [True]}, ["input"]):
                response = await client.post("/v1/embeddings", json=body, headers=headers)
                assert response.status_code == 422 and "private-sentinel" not in response.text
            assert (await client.post("/v1/embeddings", content=b"x" * 300001, headers=headers)).status_code == 413
            assert not calls
            response = await client.post("/v1/embeddings", json={"input": ["query: fixture"]}, headers=headers)
            assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
            assert calls == [["query: fixture"]]

    async def test_busy_slot_survives_cancelled_http_task_and_failures_do_not_echo_text(self):
        entered, release = threading.Event(), threading.Event()
        class Encoder:
            def encode(self, texts):
                entered.set()
                release.wait(5)
                raise RuntimeError("private-sentinel")
        app = create_app(Encoder(), "fixture-only-local-token")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://local",
                                    headers={"Authorization": "Bearer fixture-only-local-token"}) as client:
            first = asyncio.create_task(client.post("/v1/embeddings", json={"input": ["query: fixture"]}))
            assert await asyncio.to_thread(entered.wait, 2)
            first.cancel()
            response = await client.post("/v1/embeddings", json={"input": ["query: fixture"]})
            assert response.status_code == 429 and "private-sentinel" not in response.text
            release.set()
            await asyncio.gather(first, return_exceptions=True)
            response = await client.post("/v1/embeddings", json={"input": ["query: fixture"]})
            assert response.status_code == 503 and "private-sentinel" not in response.text


if __name__ == "__main__":
    unittest.main()
