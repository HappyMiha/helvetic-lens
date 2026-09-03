"""Small first-party authentication for the single-server public beta."""

from __future__ import annotations

import hashlib
import re
import secrets
import threading
import unicodedata
from dataclasses import dataclass
from datetime import timedelta
from time import monotonic

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from argon2.low_level import Type
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select

from .config import DomainError, Settings
from .db import Database, utcnow
from .models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    OrganizationQuota,
    Profile,
    SecurityEvent,
    User,
    UserSession,
)

SESSION_COOKIE = "helvetic_lens_session"
CSRF_COOKIE = "helvetic_lens_csrf"
_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,
    parallelism=2,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash("helvetic-lens-dummy-password")


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_email(value: str) -> str:
    email = unicodedata.normalize("NFKC", value).strip()
    if any(ord(char) < 32 for char in email) or email.count("@") != 1:
        raise DomainError("Enter a valid email address.", 422, "invalid_email")
    local, domain = email.rsplit("@", 1)
    if not local or len(local) > 64 or not domain:
        raise DomainError("Enter a valid email address.", 422, "invalid_email")
    try:
        ascii_domain = domain.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise DomainError("Enter a valid email address.", 422, "invalid_email") from exc
    normalized = f"{local.casefold()}@{ascii_domain}"
    if len(normalized) > 320 or "." not in ascii_domain or " " in normalized:
        raise DomainError("Enter a valid email address.", 422, "invalid_email")
    return normalized


def _slug(value: str) -> str:
    base = re.sub(
        r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    )
    return (base.strip("-") or "organization")[:80] + "-" + secrets.token_hex(4)


@dataclass(frozen=True)
class Identity:
    user_id: str
    organization_id: str
    role: str
    session_id: str
    csrf_hash: str
    email: str
    name: str
    organization_name: str
    platform_admin: bool = False

    def public(self) -> dict:
        return {
            "authenticated": True,
            "user": {"id": self.user_id, "email": self.email, "name": self.name},
            "organization": {"id": self.organization_id, "name": self.organization_name},
            "role": self.role,
            "platform_admin": self.platform_admin,
        }


class AuthService:
    def __init__(self, database: Database, settings: Settings):
        self.db = database
        self.settings = settings

    @staticmethod
    def _event(session, kind: str, *, organization_id=None, user_id=None, subject=""):
        session.add(
            SecurityEvent(
                organization_id=organization_id,
                user_id=user_id,
                kind=kind,
                subject_hash=token_hash(subject) if subject else None,
            )
        )

    def _new_session(self, session, user: User, membership: OrganizationMembership):
        session_token, csrf_token = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        record = UserSession(
            token_hash=token_hash(session_token),
            csrf_hash=token_hash(csrf_token),
            user_id=user.id,
            organization_id=membership.organization_id,
            expires_at=utcnow() + timedelta(days=self.settings.session_ttl_days),
        )
        session.add(record)
        session.flush()
        return record, session_token, csrf_token

    def register(
        self,
        *,
        email: str,
        password: str,
        name: str,
        organization_name: str,
        invitation_token: str = "",
    ):
        normalized = normalize_email(email)
        person_name = name.strip()
        if not person_name:
            raise DomainError("Enter your name.", 422, "invalid_name")
        if len(password) < 10:
            raise DomainError("Use at least 10 characters for the password.", 422, "weak_password")
        organization_label = organization_name.strip() or f"{person_name}'s workspace"
        with self.db.session(include_all_organizations=True) as session:
            if session.scalar(select(User.id).where(User.email == normalized)):
                self._event(session, "registration_rejected", subject=normalized)
                session.commit()
                raise DomainError("An account with this email already exists.", 409, "email_exists")
            invitation = (
                self._valid_invitation(session, invitation_token, normalized) if invitation_token else None
            )
            organization = (
                session.get(Organization, invitation.organization_id)
                if invitation
                else Organization(name=organization_label[:200], slug=_slug(organization_label))
            )
            user = User(
                email=normalized,
                password_hash=_PASSWORD_HASHER.hash(password),
                name=person_name[:200],
            )
            session.add(user)
            if not invitation:
                session.add(organization)
            session.flush()
            membership = OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role=invitation.role if invitation else "organization_admin",
            )
            session.add(membership)
            if invitation:
                invitation.accepted_at = utcnow()
            else:
                session.add_all(
                    [
                        Profile(id=organization.id, organization_id=organization.id),
                        OrganizationQuota(organization_id=organization.id, values={}),
                    ]
                )
            session.flush()
            record, session_token, csrf_token = self._new_session(session, user, membership)
            self._event(
                session,
                "registration_succeeded",
                organization_id=organization.id,
                user_id=user.id,
            )
            session.commit()
            return self._identity(session, record), session_token, csrf_token

    def login(self, *, email: str, password: str):
        normalized = normalize_email(email)
        with self.db.session(include_all_organizations=True) as session:
            user = session.scalar(select(User).where(User.email == normalized))
            valid = False
            try:
                valid = _PASSWORD_HASHER.verify(
                    user.password_hash if user else _DUMMY_PASSWORD_HASH, password
                )
            except (VerifyMismatchError, InvalidHashError):
                valid = False
            if not user or not valid or not user.active:
                self._event(session, "login_failed", user_id=user.id if user else None, subject=normalized)
                session.commit()
                raise DomainError("Email or password is incorrect.", 401, "invalid_credentials")
            membership = session.scalar(
                select(OrganizationMembership)
                .where(OrganizationMembership.user_id == user.id)
                .order_by(OrganizationMembership.created_at)
                .limit(1)
            )
            if membership is None:
                raise DomainError("This account has no active workspace.", 403, "membership_required")
            if _PASSWORD_HASHER.check_needs_rehash(user.password_hash):
                user.password_hash = _PASSWORD_HASHER.hash(password)
            record, session_token, csrf_token = self._new_session(session, user, membership)
            self._event(
                session,
                "login_succeeded",
                organization_id=membership.organization_id,
                user_id=user.id,
            )
            session.commit()
            return self._identity(session, record), session_token, csrf_token

    def _identity(self, session, record: UserSession) -> Identity:
        user = session.get(User, record.user_id)
        organization = session.get(Organization, record.organization_id)
        membership = session.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == record.organization_id,
                OrganizationMembership.user_id == record.user_id,
            )
        )
        if not user or not organization or not membership:
            raise DomainError("The session is no longer valid.", 401, "session_invalid")
        return Identity(
            user_id=user.id,
            organization_id=organization.id,
            role=membership.role,
            session_id=record.id,
            csrf_hash=record.csrf_hash,
            email=user.email,
            name=user.name,
            organization_name=organization.name,
            platform_admin=user.platform_admin,
        )

    @staticmethod
    def require_admin(identity: Identity):
        if identity.role != "organization_admin":
            raise DomainError(
                "An organization administrator must perform this action.", 403, "admin_required"
            )

    @staticmethod
    def _valid_invitation(session, raw_token: str, email: str) -> OrganizationInvitation:
        invitation = session.scalar(
            select(OrganizationInvitation).where(OrganizationInvitation.token_hash == token_hash(raw_token))
        )
        if (
            not invitation
            or invitation.accepted_at
            or invitation.revoked_at
            or _aware(invitation.expires_at) <= utcnow()
        ):
            raise DomainError("This invitation is invalid or has expired.", 410, "invitation_invalid")
        if invitation.email != email:
            raise DomainError(
                "Sign in with the email address that was invited.", 403, "invitation_email_mismatch"
            )
        return invitation

    def create_invitation(self, identity: Identity, *, email: str, role: str):
        self.require_admin(identity)
        normalized = normalize_email(email)
        if role not in {"organization_admin", "viewer"}:
            raise DomainError("Choose administrator or viewer.", 422, "invalid_role")
        raw_token = secrets.token_urlsafe(32)
        with self.db.session(include_all_organizations=True) as session:
            existing_user = session.scalar(select(User).where(User.email == normalized))
            if existing_user and session.scalar(
                select(OrganizationMembership.id).where(
                    OrganizationMembership.organization_id == identity.organization_id,
                    OrganizationMembership.user_id == existing_user.id,
                )
            ):
                raise DomainError("This person is already a member.", 409, "membership_exists")
            for pending in session.scalars(
                select(OrganizationInvitation).where(
                    OrganizationInvitation.organization_id == identity.organization_id,
                    OrganizationInvitation.email == normalized,
                    OrganizationInvitation.accepted_at.is_(None),
                    OrganizationInvitation.revoked_at.is_(None),
                )
            ):
                pending.revoked_at = utcnow()
            invitation = OrganizationInvitation(
                organization_id=identity.organization_id,
                email=normalized,
                role=role,
                token_hash=token_hash(raw_token),
                invited_by_user_id=identity.user_id,
                expires_at=utcnow() + timedelta(days=7),
            )
            session.add(invitation)
            self._event(
                session,
                "invitation_created",
                organization_id=identity.organization_id,
                user_id=identity.user_id,
                subject=normalized,
            )
            session.commit()
            return {**self._invitation_public(invitation), "token": raw_token}

    def list_invitations(self, identity: Identity):
        self.require_admin(identity)
        with self.db.session(include_all_organizations=True) as session:
            records = session.scalars(
                select(OrganizationInvitation)
                .where(OrganizationInvitation.organization_id == identity.organization_id)
                .order_by(OrganizationInvitation.created_at.desc())
            )
            return [self._invitation_public(record) for record in records]

    @staticmethod
    def _invitation_public(record: OrganizationInvitation):
        now = utcnow()
        status = "accepted" if record.accepted_at else "revoked" if record.revoked_at else "pending"
        if status == "pending" and _aware(record.expires_at) <= now:
            status = "expired"
        return {
            "id": record.id,
            "email": record.email,
            "role": record.role,
            "status": status,
            "expires_at": record.expires_at,
            "created_at": record.created_at,
        }

    def revoke_invitation(self, identity: Identity, invitation_id: str):
        self.require_admin(identity)
        with self.db.session(include_all_organizations=True) as session:
            record = session.get(OrganizationInvitation, invitation_id)
            if not record or record.organization_id != identity.organization_id:
                raise DomainError("The invitation was not found.", 404, "not_found")
            if not record.accepted_at and not record.revoked_at:
                record.revoked_at = utcnow()
            session.commit()
            return self._invitation_public(record)

    def accept_invitation(self, identity: Identity, raw_token: str):
        with self.db.session(include_all_organizations=True) as session:
            invitation = self._valid_invitation(session, raw_token, identity.email)
            membership = session.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == invitation.organization_id,
                    OrganizationMembership.user_id == identity.user_id,
                )
            )
            if not membership:
                membership = OrganizationMembership(
                    organization_id=invitation.organization_id,
                    user_id=identity.user_id,
                    role=invitation.role,
                )
                session.add(membership)
                session.flush()
            invitation.accepted_at = utcnow()
            active_session = session.get(UserSession, identity.session_id)
            active_session.organization_id = invitation.organization_id
            self._event(
                session,
                "invitation_accepted",
                organization_id=invitation.organization_id,
                user_id=identity.user_id,
            )
            session.commit()
            return self._identity(session, active_session)

    def organizations(self, identity: Identity):
        with self.db.session(include_all_organizations=True) as session:
            rows = session.execute(
                select(OrganizationMembership, Organization)
                .join(Organization, Organization.id == OrganizationMembership.organization_id)
                .where(OrganizationMembership.user_id == identity.user_id)
                .order_by(OrganizationMembership.created_at)
            )
            return [
                {
                    "id": organization.id,
                    "name": organization.name,
                    "role": membership.role,
                    "current": organization.id == identity.organization_id,
                }
                for membership, organization in rows
            ]

    def switch_organization(self, identity: Identity, organization_id: str):
        with self.db.session(include_all_organizations=True) as session:
            membership = session.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == organization_id,
                    OrganizationMembership.user_id == identity.user_id,
                )
            )
            if not membership:
                raise DomainError("You are not a member of this organization.", 403, "membership_required")
            active_session = session.get(UserSession, identity.session_id)
            active_session.organization_id = organization_id
            session.commit()
            return self._identity(session, active_session)

    def members(self, identity: Identity):
        with self.db.session(include_all_organizations=True) as session:
            memberships = list(
                session.scalars(
                    select(OrganizationMembership)
                    .where(OrganizationMembership.organization_id == identity.organization_id)
                    .order_by(OrganizationMembership.created_at)
                )
            )
            users = {
                user.id: user
                for user in session.scalars(select(User).where(User.id.in_([m.user_id for m in memberships])))
            }
            return [
                {
                    "id": membership.id,
                    "role": membership.role,
                    "joined_at": membership.created_at,
                    "user": {
                        "id": membership.user_id,
                        "email": users[membership.user_id].email,
                        "name": users[membership.user_id].name,
                    },
                    "current": membership.user_id == identity.user_id,
                }
                for membership in memberships
            ]

    def update_member(self, identity: Identity, membership_id: str, role: str):
        self.require_admin(identity)
        if role not in {"organization_admin", "viewer"}:
            raise DomainError("Choose administrator or viewer.", 422, "invalid_role")
        with self.db.session(include_all_organizations=True) as session:
            membership = session.get(OrganizationMembership, membership_id)
            self._same_organization(identity, membership)
            if membership.role == "organization_admin" and role != membership.role:
                self._require_another_admin(session, identity.organization_id, membership.id)
            membership.role = role
            session.commit()
            return next(item for item in self.members(identity) if item["id"] == membership.id)

    def remove_member(self, identity: Identity, membership_id: str):
        self.require_admin(identity)
        with self.db.session(include_all_organizations=True) as session:
            membership = session.get(OrganizationMembership, membership_id)
            self._same_organization(identity, membership)
            if membership.user_id == identity.user_id:
                raise DomainError(
                    "Another administrator must remove you after handover.",
                    409,
                    "self_removal_requires_handover",
                )
            if membership.role == "organization_admin":
                self._require_another_admin(session, identity.organization_id, membership.id)
            session.query(UserSession).filter(
                UserSession.organization_id == identity.organization_id,
                UserSession.user_id == membership.user_id,
                UserSession.revoked_at.is_(None),
            ).update({UserSession.revoked_at: utcnow()})
            session.delete(membership)
            session.commit()
            return {"deleted": True}

    def handover(self, identity: Identity, membership_id: str):
        self.require_admin(identity)
        with self.db.session(include_all_organizations=True) as session:
            target = session.get(OrganizationMembership, membership_id)
            self._same_organization(identity, target)
            if target.user_id == identity.user_id:
                raise DomainError("Choose another member for the handover.", 422, "invalid_handover")
            current = session.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == identity.organization_id,
                    OrganizationMembership.user_id == identity.user_id,
                )
            )
            target.role = "organization_admin"
            current.role = "viewer"
            session.commit()
            return {"handed_over": True, "administrator_membership_id": target.id}

    @staticmethod
    def _same_organization(identity: Identity, membership: OrganizationMembership | None):
        if not membership or membership.organization_id != identity.organization_id:
            raise DomainError("The member was not found.", 404, "not_found")

    @staticmethod
    def _require_another_admin(session, organization_id: str, excluded_id: str):
        other = session.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.role == "organization_admin",
                OrganizationMembership.id != excluded_id,
            )
        )
        if not other:
            raise DomainError("Promote another administrator before this change.", 409, "last_admin")

    def resolve(self, session_token: str) -> Identity | None:
        if not session_token:
            return None
        now = utcnow()
        with self.db.session(include_all_organizations=True) as session:
            record = session.scalar(
                select(UserSession).where(UserSession.token_hash == token_hash(session_token))
            )
            if not record or record.revoked_at or _aware(record.expires_at) <= now:
                return None
            if (_aware(record.last_seen_at) + timedelta(minutes=5)) < now:
                record.last_seen_at = now
                session.commit()
            return self._identity(session, record)

    def verify_csrf(self, identity: Identity, cookie_token: str, header_token: str):
        if (
            not cookie_token
            or not header_token
            or not secrets.compare_digest(cookie_token, header_token)
            or not secrets.compare_digest(token_hash(header_token), identity.csrf_hash)
        ):
            raise DomainError("Refresh the page and try again.", 403, "csrf_failed")

    def logout(self, identity: Identity):
        with self.db.session(include_all_organizations=True) as session:
            record = session.get(UserSession, identity.session_id)
            if record and not record.revoked_at:
                record.revoked_at = utcnow()
                self._event(
                    session,
                    "logout",
                    organization_id=identity.organization_id,
                    user_id=identity.user_id,
                )
                session.commit()


def _aware(value):
    return value.replace(tzinfo=utcnow().tzinfo) if value.tzinfo is None else value


class RateLimiter:
    def __init__(self, settings: Settings):
        self.production = settings.app_environment == "production"
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=0.25)
        self._memory: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def check(self, bucket: str, subject: str, *, limit: int, window_seconds: int):
        key = f"helvetic-lens:limit:{bucket}:{token_hash(subject)}"
        try:
            with self.redis.pipeline() as pipeline:
                pipeline.incr(key)
                pipeline.expire(key, window_seconds, nx=True)
                count, _ = pipeline.execute()
        except RedisError as exc:
            if self.production:
                raise DomainError(
                    "Request protection is temporarily unavailable.", 503, "rate_limit_unavailable"
                ) from exc
            count = self._memory_increment(key, window_seconds)
        if int(count) > limit:
            raise DomainError("Too many requests. Wait a moment and try again.", 429, "rate_limited")

    def _memory_increment(self, key: str, window_seconds: int) -> int:
        now = monotonic()
        with self._lock:
            count, expires = self._memory.get(key, (0, now + window_seconds))
            if expires <= now:
                count, expires = 0, now + window_seconds
            count += 1
            self._memory[key] = (count, expires)
            return count
