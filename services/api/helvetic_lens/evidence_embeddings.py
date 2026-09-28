"""Bounded local retrieval adapter beside the shared Jev/Laya decision layer."""
import hashlib
import math
import struct
from urllib.parse import urlsplit

from .decision_engines import DecisionUnavailable, bounded_json

MODEL = "intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3"
DIMENSIONS = 384
BATCH = 16
MAX_RECORDS = 20000


def passage(item):
    statement = item["statement"][:600]
    return "passage: " + item["title"][:300] + "\n" + (statement + "\n" if statement else "") + item["quote"][:2400]


def text_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def validate_vector(values):
    if (not isinstance(values, (list, tuple)) or len(values) != DIMENSIONS
            or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1.01 for v in values)
            or abs(sum(v * v for v in values) - 1) > 0.01):
        raise DecisionUnavailable("invalid_response")
    return tuple(float(v) for v in values)


def pack(values):
    return struct.pack("<384f", *validate_vector(values))


def unpack(value):
    if not isinstance(value, bytes) or len(value) != DIMENSIONS * 4:
        raise DecisionUnavailable("invalid_response")
    return validate_vector(struct.unpack("<384f", value))


class LocalEmbeddings:
    """Operator-only loopback/container endpoint; no hosted/private fallback."""
    def __init__(self, settings):
        self.url = settings.evidence_embedding_url
        self.key = settings.laya_api_key.get_secret_value()

    async def encode(self, texts):
        if not self.url or not self.key:
            raise DecisionUnavailable("not_configured")
        try:
            parsed = urlsplit(self.url)
            if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "helvetic-lens-retrieval")
                    or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or parsed.path != "/v1/embeddings" or parsed.port == 0):
                raise ValueError()
        except ValueError:
            raise DecisionUnavailable("invalid_configuration") from None
        if not 1 <= len(texts) <= BATCH or any(not 1 <= len(text) <= 4000 for text in texts):
            raise DecisionUnavailable("invalid_input")
        body = await bounded_json(self.url, self.key, {"input": texts}, timeout=25, limit=350000)
        try:
            if body["model"] != MODEL or len(body["data"]) != len(texts):
                raise ValueError()
            result = []
            for index, (text, row) in enumerate(zip(texts, body["data"])):
                if (type(row["index"]) is not int or row["index"] != index or row["input_sha256"] != text_hash(text)
                        or type(row["input_tokens"]) is not int or not 1 <= row["input_tokens"] <= 16000
                        or type(row["truncated"]) is not bool or row["truncated"] != (row["input_tokens"] > 512)):
                    raise ValueError()
                result.append({"vector": validate_vector(row["embedding"]),
                    "input_tokens": row["input_tokens"], "truncated": row["truncated"]})
            return result
        except (TypeError, KeyError, ValueError, AttributeError):
            raise DecisionUnavailable("invalid_response") from None
