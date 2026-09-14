"""Fixed-origin access checks. No source admission, private query or coverage claim."""

import json
import time
from datetime import UTC, datetime

import httpx

from . import (
    air_sources,
    commute_acquisition,
    hazard_meteoalarm,
    pollen_collector,
    river_sources,
    road_acquisition,
)
from .ipi_tokens import CLIENT_ID, account
from .ipi_transport import TOKEN_ENDPOINT
from .transport_feed import ALERTS, TRIPS


def requests(domain, settings):
    headers = {"Accept-Encoding": "identity", "User-Agent": "HelveticLens-Monitoring/2"}
    if domain == "ip":
        _, username, password = account(settings)
        return [("account", httpx.Request("POST", TOKEN_ENDPOINT, headers=headers,
            data={"client_id": CLIENT_ID, "grant_type": "password", "username": username, "password": password}), "token")]
    if domain == "commute":
        result = []
        for name, source, key in (("trip_updates", TRIPS, settings.commute_gtfs_rt_key),
                                  ("service_alerts", ALERTS, settings.commute_gtfs_sa_key)):
            value = key.get_secret_value()
            result.append((name, httpx.Request("GET", commute_acquisition.ENDPOINTS[source],
                headers={**headers, "Authorization": "Bearer " + value}) if value else None, "binary"))
        return result
    if domain == "traffic":
        key = settings.road_source_key.get_secret_value()
        return [("traffic", httpx.Request("POST", road_acquisition.ENDPOINT,
            headers={**headers, "Authorization": "Bearer " + key, "SOAPAction": road_acquisition.SOAP_ACTION,
                "Content-Type": "text/xml; charset=utf-8"}, content=road_acquisition.REQUEST_BODY) if key else None, "xml")]
    if domain == "river":
        return [("catalogue", httpx.Request("POST", river_sources.GRAPHQL, headers=headers,
            json={"query": river_sources.CATALOG_QUERY}), "json")]
    url, kind = {
        "pollen": (pollen_collector.STAC, "json"),
        "air": (air_sources.API, "json"),
        "warnings": (hazard_meteoalarm.FEED_URL, "xml"),
        "tenders": ("https://www.simap.ch/api/codes/v1/cpv/search?query=45000000&language=en", "json"),
        "auctions": ("https://www.aste.ti.ch/it/", "html"),
    }[domain]
    return [("public", httpx.Request("GET", url, headers=headers), kind)]


def check(domain, settings, *, client=None, monotonic=time.monotonic):
    from .ipi_protocol import IPIProtocolError
    try:
        targets = requests(domain, settings)
    except IPIProtocolError:
        return {"checked_at": datetime.now(UTC).isoformat(), "coverage_verified": False,
            "channels": [{"id": "account", "state": "credentials_required"}]}
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(5, connect=3), trust_env=False, follow_redirects=False)
    results = []
    started = monotonic()
    try:
        for name, request, kind in targets:
            state = "credentials_required"
            if request is not None:
                state = "unavailable"
                response = None
                try:
                    request.extensions["timeout"] = {"connect": 3.0, "read": 5.0, "write": 5.0, "pool": 3.0}
                    if monotonic() - started > 15:
                        raise ValueError()
                    response = client.send(request, stream=True, follow_redirects=False, auth=None)
                    status = response.status_code
                    state = "access_denied" if status in (401, 403) else "rate_limited" if status == 429 else "redirect_not_followed" if 300 <= status < 400 else "unavailable"
                    if status == 200:
                        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                        matches = {"json": "json" in content_type, "token": "json" in content_type,
                            "xml": "xml" in content_type, "html": content_type == "text/html",
                            "binary": content_type in ("application/octet-stream", "application/x-protobuf", "application/x-google-protobuf")}
                        state = "unexpected_response"
                        if matches[kind]:
                            # For a transport check consume at most one small chunk. Only
                            # the bounded token response needs complete JSON validation.
                            body = bytearray()
                            for chunk in response.iter_bytes(chunk_size=8192):
                                if monotonic() - started > 15 or len(body) + len(chunk) > 65536:
                                    raise ValueError()
                                body.extend(chunk)
                                if kind != "token":
                                    break
                            if body:
                                state = "http_accessible"
                            if kind == "token":
                                token = json.loads(body)
                                state = "authenticated" if (isinstance(token, dict) and isinstance(token.get("access_token"), str)
                                    and token["access_token"] and str(token.get("token_type", "")).lower() == "bearer") else "unexpected_response"
                except (httpx.HTTPError, ValueError, UnicodeError):
                    state = "unavailable"
                finally:
                    if response is not None:
                        response.close()
            results.append({"id": name, "state": state})
    finally:
        if owned:
            client.close()
    return {"checked_at": datetime.now(UTC).isoformat(), "coverage_verified": False, "channels": results}
