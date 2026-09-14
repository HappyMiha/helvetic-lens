"""Ephemeral signed previews and freshly authorized selected-evidence downloads."""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from .membership_locks import lock_organization, lock_platform_users
from .models import OrganizationMembership, User, UserSession
from .monitoring_centre import MODELS, scoped
from .monitoring_evidence_ask import Record
from .monitoring_evidence_packet import FORMAT, canonical, packet
from .monitoring_evidence_versions import fail
from .monitoring_subjects import _actor
from .river_contracts import utc

LIFETIME = timedelta(minutes=5)


def principal(session, identity, now, *, lock=False):
    if identity is None or session.info.get("organization_id") != identity.organization_id:
        fail("authentication_required", 401)
    user = session.get(User, identity.user_id, populate_existing=True)
    login = session.get(UserSession, identity.session_id, populate_existing=True, with_for_update=lock)
    if (user is None or not user.active or login is None or login.user_id != user.id
            or login.organization_id != identity.organization_id or login.revoked_at or utc(login.expires_at) <= now):
        fail("authentication_required", 401)
    _actor(session, user.id)
    return user


def signature(user, identity, value):
    message = canonical([FORMAT, identity.user_id, identity.organization_id, identity.session_id, value])
    return hmac.new(user.password_hash.encode(), message.encode(), hashlib.sha256).hexdigest()


def token(user, identity, value):
    return base64.urlsafe_b64encode(canonical({**value, "signature": signature(user, identity, value)}).encode()).decode()


def decode(user, identity, value, now):
    try:
        if not isinstance(value, str) or len(value) > 4096:
            raise ValueError()
        data = json.loads(base64.b64decode(value, altchars=b"-_", validate=True))
        if set(data) != {"format", "selection", "locale", "prepared_at", "expires_at", "sha256", "signature"}:
            raise ValueError()
        supplied = data.pop("signature")
        if not isinstance(supplied, str) or not hmac.compare_digest(signature(user, identity, data), supplied):
            raise ValueError()
        prepared, expires = (datetime.fromisoformat(data[key]) for key in ("prepared_at", "expires_at"))
        if (data["format"] != FORMAT or prepared.tzinfo is None or expires.tzinfo is None
                or not prepared <= now < expires or expires - prepared != LIFETIME):
            raise ValueError()
        return data
    except (ValueError, TypeError, KeyError, AttributeError):
        fail("monitoring_export_preview_expired", 409)


def lock_scope(session, identity, domain, monitor_id):
    if domain not in MODELS:
        fail("monitoring_export_request_invalid", 422)
    if session.bind.dialect.name == "sqlite":
        connection = session.connection()
        if not connection.connection.driver_connection.in_transaction:
            # Reserve against concurrent mutation without changing any record.
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    model = MODELS[domain]
    row = session.scalar(scoped(model, identity.organization_id, identity.user_id).where(model.id == monitor_id)
        .with_for_update().execution_options(populate_existing=True))
    if row is None:
        fail("monitoring_evidence_not_found", 404)
    # Match native monitor-before-membership/account mutation ordering.
    lock_organization(session, identity.organization_id)
    lock_platform_users(session, identity.user_id)
    session.execute(select(OrganizationMembership.id).where(
        OrganizationMembership.organization_id == identity.organization_id,
        OrganizationMembership.user_id == identity.user_id).with_for_update()).all()


def prepare(database, settings, identity, record, *, locale, revision_id=None, now=None):
    now = now or datetime.now(UTC)
    with database.session() as session:
        user = principal(session, identity, now)
        result = packet(session, settings, user.id, record, locale=locale,
            prepared_at=now, now=now, revision_id=revision_id)
        manifest = result["manifest"]
        value = {"format": FORMAT, "selection": manifest["selection"], "locale": locale,
            "prepared_at": now.isoformat(), "expires_at": (now + LIFETIME).isoformat(), "sha256": result["sha256"]}
        principal(session, identity, now)
        return {"manifest": manifest, "bytes": result["bytes"], "sha256": result["sha256"],
            "filename": result["filename"], "expires_at": value["expires_at"], "confirmation_token": token(user, identity, value)}


def download(database, settings, identity, confirmation_token, *, now=None):
    fixed_now = now
    now = now or datetime.now(UTC)
    try:
        with database.session() as session:
            user = principal(session, identity, now)
            value = decode(user, identity, confirmation_token, now)
            selection = value["selection"]
            lock_scope(session, identity, selection["domain"], selection["monitor_id"])
            # The identity and token must still be valid after waiting for locks.
            current = fixed_now or datetime.now(UTC)
            user = principal(session, identity, current, lock=True)
            value = decode(user, identity, confirmation_token, current)
            business = selection["domain"] in {"tenders", "ip", "auctions"}
            sequenced = selection["domain"] in {"warnings", "commute", "traffic"}
            record = Record(selection["domain"], selection["monitor_id"], selection["item_id"],
                selection["sequence"] if sequenced else None)
            result = packet(session, settings, identity.user_id, record, locale=value["locale"],
                prepared_at=datetime.fromisoformat(value["prepared_at"]), now=current,
                revision_id=selection["revision_id"] if business else None)
            # Also enforce elapsed-time rights/retention at the end of assembly.
            final_time = fixed_now or datetime.now(UTC)
            if final_time != current:
                result = packet(session, settings, identity.user_id, record, locale=value["locale"],
                    prepared_at=datetime.fromisoformat(value["prepared_at"]), now=final_time,
                    revision_id=selection["revision_id"] if business else None)
            user = principal(session, identity, final_time, lock=True)
            decode(user, identity, confirmation_token, final_time)
            if result["manifest"]["selection"] != selection or result["sha256"] != value["sha256"]:
                fail("monitoring_export_evidence_changed", 409)
            # No export or source content is persisted, and no caller transaction
            # is committed. Locks last until this scoped read transaction closes.
            return result
    except OperationalError:
        fail("monitoring_export_retry", 409)
