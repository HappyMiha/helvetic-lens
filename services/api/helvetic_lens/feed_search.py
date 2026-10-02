"""Narrow server-to-server public discovery for the owner's Legal Feed product."""
import asyncio
import hmac
import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.responses import JSONResponse

from .config import DomainError
from .decision_engines import DecisionUnavailable
from .search_channels import searxng

PATH = "/api/integrations/legal-feed/search"


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=3, max_length=4000)


async def handle(request, settings, limiter):
    def reply(body, status=200):
        return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})

    key = settings.legal_feed_search_token.get_secret_value()
    supplied = request.headers.get("authorization", "")
    if not key or not hmac.compare_digest(supplied.encode(), ("Bearer " + key).encode()):
        return reply({"detail": "Service authentication required."}, 401)
    if request.method != "POST":
        return reply({"detail": "Use POST."}, 405)
    if not settings.searxng_base_url:
        return reply({"detail": "Search service unavailable."}, 503)
    try:
        await asyncio.to_thread(limiter.check, "legal_feed_search", "service", limit=30, window_seconds=60)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 24000:
                return reply({"detail": "Search request too large."}, 413)
        value = SearchInput.model_validate_json(body)
        result = await searxng(settings, value.query, "web", limit=12)
    except (ValidationError, json.JSONDecodeError):
        return reply({"detail": "Provide a query of 3 to 4000 characters."}, 422)
    except DomainError as error:
        return reply({"detail": error.message}, error.status)
    except DecisionUnavailable:
        return reply({"detail": "Search engines temporarily unavailable."}, 503)
    if not result["items"] and result.get("omitted_records", 0):
        return reply({"detail": "Search returned no usable public links."}, 503)
    return reply({"provider": "SearXNG", "partial": result["status"] == "partial",
        "results": [{"title": item["title"], "link": item["url"], "snippet": item["summary"]}
                    for item in result["items"]]})
