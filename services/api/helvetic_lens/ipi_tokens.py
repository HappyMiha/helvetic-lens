"""Encrypted shared OIDC token reuse under a durable renewal lease."""

import hashlib
import json
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from . import trademark_sources as source
from .credential_crypto import CredentialCipher
from .ipi_models import IPITokenCache
from .ipi_protocol import IPIProtocolError
from .ipi_transport import TOKEN_ENDPOINT, clock, exchange
from .monitoring_subjects import _savepoint

CLIENT_ID = "datadelivery-api-client"


def account(settings):
    username, password = settings.ipi_username.get_secret_value(), settings.ipi_password.get_secret_value()
    if (not username or not password or len(username) > 320 or len(password) > 4096
            or any(ord(c) < 32 for c in username + password)):
        raise IPIProtocolError("ipi_credentials_unconfigured")
    return hashlib.sha256(username.encode()).hexdigest(), username, password


def _row(session, account_hash):
    return session.scalar(select(IPITokenCache).where(IPITokenCache.account_hash == account_hash)
        .with_for_update().execution_options(populate_existing=True))


def _decode(row, cipher, account_hash):
    if not row.encrypted_payload:
        return None
    if not cipher.is_encrypted(row.encrypted_payload):
        raise IPIProtocolError("ipi_token_cache_invalid")
    try:
        data = json.loads(cipher.decrypt(row.encrypted_payload))
        if data["account_hash"] != account_hash:
            raise ValueError()
        for key in ("access_until", "refresh_until"):
            source._clock(datetime.fromisoformat(data[key]))
        return data
    except (ValueError, TypeError, KeyError):
        raise IPIProtocolError("ipi_token_cache_invalid") from None


def _token(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 16384 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise IPIProtocolError("ipi_token_response_invalid")
    return value


def _json(payload):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError()
            result[key] = value
        return result
    try:
        value = json.loads(payload, object_pairs_hook=unique)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, UnicodeError):
        raise IPIProtocolError("ipi_token_response_invalid") from None


def obtain(database, settings, client, *, guard, now=clock):
    """Reuse valid access tokens; refresh before refresh expiry; secrets never returned in status."""
    account_hash, username, password = account(settings)
    cipher, instant, lease = CredentialCipher(settings), source._clock(now()), str(uuid4())
    guard()
    with database.session() as session:
        # Concurrent first use can only create one cache row.
        try:
            with _savepoint(session):
                if session.get(IPITokenCache, account_hash) is None:
                    session.add(IPITokenCache(account_hash=account_hash, next_attempt_at=instant))
                    session.flush()
        except IntegrityError:
            pass
        row = _row(session, account_hash)
        if source._utc(row.next_attempt_at) > instant:
            raise IPIProtocolError("ipi_account_backoff",
                retry_after_seconds=max(1, int((source._utc(row.next_attempt_at) - instant).total_seconds()) + 1))
        if row.lease_expires_at and source._utc(row.lease_expires_at) > instant:
            raise IPIProtocolError("ipi_token_renewal_busy")
        previous = _decode(row, cipher, account_hash)
        refresh = False
        if previous:
            access_until = datetime.fromisoformat(previous["access_until"])
            refresh_until = datetime.fromisoformat(previous["refresh_until"])
            refresh = refresh_until > instant and not previous.get("new_session_required")
            if (not previous.get("new_session_required") and access_until > instant + timedelta(seconds=30)
                    and (refresh_until > instant + timedelta(seconds=30) or refresh_until <= instant)):
                return _token(previous["access_token"])
        row.lease_token, row.lease_expires_at = lease, instant + timedelta(seconds=90)
        session.commit()
    form = {"client_id": CLIENT_ID, "grant_type": "refresh_token" if refresh else "password"}
    form.update({"refresh_token": _token(previous["refresh_token"])} if refresh else {"username": username, "password": password})
    try:
        _, headers, payload = exchange(client, TOKEN_ENDPOINT, data=form, guard=guard, now=now)
        if headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            raise IPIProtocolError("ipi_token_response_invalid")
        data, instant = _json(payload), source._clock(now())
        if str(data.get("token_type", "")).lower() != "bearer" or any(
                type(data.get(key)) is not int or not 30 < data[key] <= 36000
                for key in ("expires_in", "refresh_expires_in")):
            raise IPIProtocolError("ipi_token_response_invalid")
        retained = {"account_hash": account_hash, "access_token": _token(data.get("access_token")),
            "refresh_token": _token(data.get("refresh_token")),
            "access_until": (instant + timedelta(seconds=data["expires_in"])).isoformat(),
            "refresh_until": (instant + timedelta(seconds=data["refresh_expires_in"])).isoformat(),
            "new_session_required": bool(refresh and data["expires_in"] < 720)}
        guard()
        with database.session() as session:
            row = _row(session, account_hash)
            if row.lease_token != lease or source._utc(row.lease_expires_at) <= instant:
                raise IPIProtocolError("ipi_token_lease_lost")
            row.encrypted_payload = cipher.encrypt(json.dumps(retained, separators=(",", ":")))
            row.expires_at = max(datetime.fromisoformat(retained["access_until"]), datetime.fromisoformat(retained["refresh_until"]))
            row.lease_token, row.lease_expires_at = None, None
            session.commit()
        return retained["access_token"]
    except Exception as error:
        # A failed/uncertain refresh can consume its token. Drop it, back off and
        # establish a fresh session later; never retry an uncertain refresh immediately.
        with database.session() as session:
            row = _row(session, account_hash)
            if row and row.lease_token == lease:
                row.encrypted_payload, row.lease_token, row.lease_expires_at = None, None, None
                delay = max(900, getattr(error, "retry_after_seconds", None) or 0)
                row.next_attempt_at = source._clock(now()) + timedelta(seconds=delay)
                session.commit()
        raise


def backoff(database, settings, *, delay, now=clock, invalidate=False):
    account_hash, _, _ = account(settings)
    with database.session() as session:
        row = _row(session, account_hash)
        if row:
            row.next_attempt_at = max(source._utc(row.next_attempt_at), source._clock(now()) + timedelta(seconds=max(900, delay or 0)))
            if invalidate:
                row.encrypted_payload = None
            session.commit()
