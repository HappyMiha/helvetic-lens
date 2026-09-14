"""Fixed-origin IPI HTTP transport. No private queries, cookies, redirects or logs."""

import time
from datetime import UTC, datetime

import httpx

from .ipi_protocol import MAX_BYTES, IPIProtocolError, retry_after

TOKEN_ENDPOINT = "https://idp.ipi.ch/auth/realms/egov/protocol/openid-connect/token"
API_ENDPOINT = "https://www.swissreg.ch/public/api/v1"


def clock():
    return datetime.now(UTC)


def exchange(client, url, *, content=None, data=None, token=None, guard=lambda: None,
             now=clock, monotonic=time.monotonic):
    if url not in {TOKEN_ENDPOINT, API_ENDPOINT} or (url == TOKEN_ENDPOINT) != (data is not None):
        raise IPIProtocolError("ipi_transport_endpoint_invalid")
    if token is not None and (url != API_ENDPOINT or not isinstance(token, str)
            or not 1 <= len(token) <= 16384 or any(ord(c) < 33 or ord(c) > 126 for c in token)):
        raise IPIProtocolError("ipi_token_invalid")
    headers = {"Accept": "application/json" if data is not None else "application/zip, application/xml",
        "Accept-Encoding": "identity", "User-Agent": "HelveticLens-Monitoring/2"}
    if data is None:
        headers["Content-Type"] = "application/xml"
        headers["Authorization"] = "Bearer " + (token or "")
    maximum = 65536 if data is not None else MAX_BYTES
    # A standalone request excludes injected client default auth, headers, cookies and query params.
    request = httpx.Request("POST", url, headers=headers, content=content, data=data,
        extensions={"timeout": {"connect": 5.0, "read": 10.0, "write": 10.0, "pool": 5.0}})
    started = monotonic()
    guard()
    try:
        response = client.send(request, stream=True, follow_redirects=False, auth=None)
        try:
            if response.status_code != 200:
                delays = [retry_after(value, now=now()) for value in response.headers.get_list("retry-after")]
                raise IPIProtocolError(f"ipi_http_{response.status_code}",
                    retry_after_seconds=max((d for d in delays if d is not None), default=None))
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise IPIProtocolError("ipi_transport_encoding_unavailable")
            length = response.headers.get("content-length")
            if length is not None and (not length.isascii() or not length.isdigit() or len(length) > 10 or int(length) > maximum):
                raise IPIProtocolError("ipi_response_size_invalid")
            result = bytearray()
            for chunk in response.iter_raw():
                if monotonic() - started > 45:
                    raise IPIProtocolError("ipi_transport_deadline")
                if len(result) + len(chunk) > maximum:
                    raise IPIProtocolError("ipi_response_size_invalid")
                result.extend(chunk)
            guard()
            return response.status_code, response.headers, bytes(result)
        finally:
            response.close()
    except httpx.HTTPError:
        raise IPIProtocolError("ipi_transport_unavailable") from None
