"""One bounded, permitted native page per scheduler tick, followed by private projection."""

import httpx

from . import ipi_acquisition as acquisition
from . import ipi_tokens
from .config import DomainError
from .ipi_protocol import IPIProtocolError
from .ipi_transport import API_ENDPOINT, clock, exchange


def readiness(settings):
    if not settings.trademark_watch_enabled or not settings.ipi_source_enabled:
        return "disabled"
    if not settings.ipi_source_permission_id:
        return "permission_required"
    try:
        ipi_tokens.account(settings)
    except IPIProtocolError:
        return "credentials_required"
    return "configured"


def collect(database, settings, *, client=None, now=clock):
    state = readiness(settings)
    if state != "configured":
        return {"state": state, "coverage_verified": False}
    ticket, owned = None, client is None
    client = client or httpx.Client(timeout=10, follow_redirects=False, trust_env=False)
    try:
        with database.session() as session:
            ticket = acquisition.claim(session, settings.ipi_source_permission_id, now=now())
            session.commit()
        if ticket["state"] != "claimed":
            return ticket

        def guard():
            if readiness(settings) != "configured":
                raise IPIProtocolError("ipi_source_configuration_changed")
            with database.session() as session:
                acquisition.validate_ticket(session, ticket, now=now())

        token = ipi_tokens.obtain(database, settings, client, guard=guard, now=now)
        status, headers, payload = exchange(client, API_ENDPOINT, content=ticket["request"], token=token, guard=guard, now=now)
        received = now()
        with database.session() as session:
            result = acquisition.admit(session, ticket, status=status, headers=headers,
                payload=payload, received_at=received, now=now())
            session.commit()
        return result
    except (DomainError, IPIProtocolError) as error:
        delay = getattr(error, "retry_after_seconds", None)
        if isinstance(error, IPIProtocolError) and error.code != "ipi_account_backoff" and (
                delay is not None or error.code in {"ipi_http_401", "ipi_http_403"}):
            ipi_tokens.backoff(database, settings, delay=delay, now=now, invalidate=error.code in {"ipi_http_401", "ipi_http_403"})
        if ticket and ticket.get("state") == "claimed":
            try:
                with database.session() as session:
                    acquisition.fail(session, ticket, code=error.code, now=now(), retry_after_seconds=delay)
                    session.commit()
            except DomainError:
                pass  # A replaced permission/lease never authorizes old-worker writes.
        return {"state": "unavailable", "reason": error.code, "coverage_verified": False}
    finally:
        if owned:
            client.close()
