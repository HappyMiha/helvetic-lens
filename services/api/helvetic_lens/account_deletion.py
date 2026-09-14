"""Authenticated, password-confirmed account erasure with a fresh scoped preview."""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime

from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from .account_deletion_plan import fail, inventory
from .account_erasure_store import (
    erase_selected,
    private_document_version_count,
    retained_references,
    select_private_rows,
)
from .auth import _PASSWORD_HASHER
from .config import DomainError
from .membership_locks import lock_organization, lock_platform_users
from .models import OrganizationMembership, User, UserSession
from .monitoring_centre import MODELS
from .river_contracts import utc


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def require_session(session, identity, now, *, lock=False):
    if identity is None:
        fail("authentication_required", 401)
    user = session.get(User, identity.user_id, populate_existing=True)
    record = session.get(UserSession, identity.session_id, populate_existing=True, with_for_update=lock)
    if (not user or not user.active or not record or record.user_id != user.id
            or record.organization_id != identity.organization_id or record.revoked_at
            or utc(record.expires_at) <= now):
        fail("authentication_required", 401)
    return user


def signature(user, identity, payload):
    # A password hash is never sent to the client. Binding the proof to it also
    # invalidates previews after password reset/rehash; session and workspace
    # binding prevent reuse through another browser identity.
    message = canonical([user.id, identity.session_id, identity.organization_id, payload])
    return hmac.new(user.password_hash.encode(), message, hashlib.sha256).hexdigest()


def proof(user, identity, fingerprint, now):
    payload = {"v": 1, "fingerprint": fingerprint, "expires": int(now.timestamp()) + 900}
    return base64.urlsafe_b64encode(canonical({**payload, "signature": signature(user, identity, payload)})).decode()


def verify_proof(user, identity, token, now):
    try:
        if not isinstance(token, str) or len(token) > 1024:
            raise ValueError()
        data = json.loads(base64.b64decode(token, altchars=b"-_", validate=True))
        if set(data) != {"v", "fingerprint", "expires", "signature"}:
            raise ValueError()
        supplied = data.pop("signature")
        if data["v"] != 1 or type(data["expires"]) is not int or not now.timestamp() < data["expires"] <= now.timestamp() + 900:
            raise ValueError()
        if not isinstance(supplied, str) or not hmac.compare_digest(signature(user, identity, data), supplied):
            raise ValueError()
        return data["fingerprint"]
    except (ValueError, TypeError, KeyError):
        fail("account_deletion_preview_expired", 409)


def prepare(session, user, identity):
    plan = inventory(session, user.id, identity.organization_id)
    public = {**plan.public, "private_document_versions": 0, "private_artifact_files": 0}
    if not public["can_delete"]:
        return public, None, plan.erase_organizations
    selection = select_private_rows(session, user, plan.erase_organizations)
    try:
        retained_references(session, selection)
    except DomainError as error:
        if error.code != "account_deletion_retained_reference":
            raise
        public["can_delete"] = False
        public["blockers"] = [*public["blockers"], {"kind": "retained_workspace_reference"}]
    public["fingerprint"] = hashlib.sha256(canonical([public["fingerprint"],
        {name: sorted(keys) for name, keys in selection.keys.items() if keys}])).hexdigest()
    public["private_document_versions"] = private_document_version_count(session, selection)
    public["private_artifact_files"] = len(selection.artifacts)
    return public, selection, plan.erase_organizations


def preview(auth, identity, *, now=None):
    now = now or datetime.now(UTC)
    with auth.db.session(include_all_organizations=True) as session:
        user = require_session(session, identity, now)
        public, _, _ = prepare(session, user, identity)
        public["confirmation_token"] = proof(user, identity, public["fingerprint"], now) if public["can_delete"] else None
        public["artifact_retention_hours"] = auth.settings.orphan_artifact_retention_hours
        public["development_mail_retention_hours"] = auth.settings.auth_mail_retention_hours
        public["cleanup_interval_hours"] = 24
        return public


def lock_scope(session, user_id):
    if session.bind.dialect.name == "sqlite":
        session.execute(update(User).where(User.id == user_id).values(active=User.active)
            .execution_options(synchronize_session=False))
    # Native writers lock monitor before person. New children also require a
    # parent FK lock; rebuilding the full selection below catches earlier writes.
    for _, model in sorted(MODELS.items()):
        table = model.__table__
        session.execute(select(table.c.id).where(table.c.owner_user_id == user_id)
            .order_by(table.c.id).with_for_update()).all()
    organizations = list(session.scalars(select(OrganizationMembership.organization_id).where(
        OrganizationMembership.user_id == user_id).order_by(OrganizationMembership.organization_id)))
    for identifier in organizations:
        lock_organization(session, identifier)
    lock_platform_users(session, user_id)
    session.execute(select(OrganizationMembership.id).where(OrganizationMembership.user_id == user_id)
        .order_by(OrganizationMembership.id).with_for_update()).all()


def erase(auth, identity, *, password, confirmation_token, confirmed, erase_workspaces, now=None):
    fixed_now = now
    now = now or datetime.now(UTC)
    if confirmed is not True or not isinstance(password, str) or not 1 <= len(password) <= 1024:
        fail("account_deletion_confirmation_required", 422)
    try:
        with auth.db.session(include_all_organizations=True) as session:
            user = require_session(session, identity, now)
            expected = verify_proof(user, identity, confirmation_token, now)
            verified_hash = user.password_hash
            try:
                valid = _PASSWORD_HASHER.verify(verified_hash, password)
            except (VerifyMismatchError, InvalidHashError):
                valid = False
            if not valid:
                fail("invalid_credentials", 401)
            lock_scope(session, user.id)
            current = fixed_now or datetime.now(UTC)
            user = require_session(session, identity, current, lock=True)
            if user.password_hash != verified_hash:
                fail()
            verify_proof(user, identity, confirmation_token, current)
            public, selection, organizations = prepare(session, user, identity)
            if not public["can_delete"] or selection is None or public["fingerprint"] != expected:
                fail()
            if sorted(erase_workspaces) != sorted(organizations):
                fail("account_deletion_workspace_confirmation_required", 422)
            erase_selected(session, user, selection)
            session.commit()
            return {"deleted": True, "authenticated": False,
                "private_artifact_files": len(selection.artifacts),
                "artifact_retention_hours": auth.settings.orphan_artifact_retention_hours,
                "cleanup_interval_hours": 24}
    except (IntegrityError, OperationalError):
        # A competing writer, dependency or lock conflict rolls back the whole
        # transaction. Never return a partially-erased account as a success.
        fail()
