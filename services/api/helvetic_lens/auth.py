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
    base = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower())
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

    def public(self) -> dict:
        return {
            "authenticated": True,
            "user": {"id": self.user_id, "email": self.email, "name": self.name},
            "organization": {"id": self.organization_id, "name": self.organization_name},
            "role": self.role,
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

    def register(self, *, email: str, password: str, name: str, organization_name: str):
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
            organization = Organization(name=organization_label[:200], slug=_slug(organization_label))
            user = User(
                email=normalized,
                password_hash=_PASSWORD_HASHER.hash(password),
                name=person_name[:200],
            )
            session.add_all([organization, user])
            session.flush()
            membership = OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role="organization_admin",
            )
            session.add_all(
                [
                    membership,
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
        )

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
