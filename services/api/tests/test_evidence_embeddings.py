"""Private inputs cannot be routed to hosted endpoints or unvalidated vectors."""
import pytest
from pydantic import SecretStr

from helvetic_lens import evidence_embeddings as embeddings
from helvetic_lens.config import Settings
from helvetic_lens.decision_engines import DecisionUnavailable

pytestmark = pytest.mark.functional


@pytest.mark.parametrize("url", ["https://example.org/v1/embeddings", "http://evil.local/v1/embeddings",
    "http://user:password@localhost/v1/embeddings", "http://localhost/v1/embeddings?secret=x",
    "http://localhost/v1/systemone", "http://127.0.0.1:0/v1/embeddings"])
async def test_external_or_ambiguous_destination_is_rejected_without_network(monkeypatch, url):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Network must not be attempted")
    monkeypatch.setattr(embeddings, "bounded_json", forbidden)
    engine = embeddings.LocalEmbeddings(Settings(evidence_embedding_url=url, laya_api_key=SecretStr("fixture")))
    with pytest.raises(DecisionUnavailable, match="invalid_configuration"):
        await engine.encode(["query: private fixture"])


@pytest.mark.parametrize("change", ["model", "identity", "index", "dimension", "nan", "norm", "tokens", "truncated"])
async def test_response_identity_normalization_order_and_bounds(monkeypatch, change):
    text = "query: fixture"
    row = {"index": 0, "input_sha256": embeddings.text_hash(text), "input_tokens": 8,
           "truncated": False, "embedding": [1.0] + [0.0] * 383}
    body = {"model": embeddings.MODEL, "data": [row]}
    if change == "model":
        body["model"] = "different-model"
    elif change == "identity":
        row["input_sha256"] = "b" * 64
    elif change == "index":
        row["index"] = True
    elif change == "dimension":
        row["embedding"] = [1.0]
    elif change == "nan":
        row["embedding"][0] = float("nan")
    elif change == "norm":
        row["embedding"] = [0.0] * 384
    elif change == "tokens":
        row["input_tokens"] = True
    else:
        row["truncated"] = True
    async def respond(*args, **kwargs):
        return body
    monkeypatch.setattr(embeddings, "bounded_json", respond)
    engine = embeddings.LocalEmbeddings(Settings(evidence_embedding_url="http://127.0.0.1:18762/v1/embeddings", laya_api_key=SecretStr("fixture")))
    with pytest.raises(DecisionUnavailable, match="invalid_response"):
        await engine.encode([text])
