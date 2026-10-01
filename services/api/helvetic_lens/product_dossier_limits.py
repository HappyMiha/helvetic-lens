"""Personal dossier allowance requests and administrator decisions from email."""
from html import escape
from typing import Literal
from uuid import UUID

from fastapi import Request
from pydantic import Field, field_validator
from sqlalchemy import select

from . import jobs
from .auth_mail import AuthMailer
from .db import utcnow
from .legal_profiles import Input
from .membership_locks import lock_organization
from .models import User
from .product_api import Product, fail
from .product_models import DossierAllowance, DossierLimitRequest
from .product_research_admission import LIMIT, request_payload, state

RECIPIENT = "info@helveticlens.ch"
MAIL_JOB = "dossier_limit_email"


class Increase(Input):
    request_key: UUID
    requested_limit: int = Field(ge=4, le=100000, strict=True)
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator("reason")
    @classmethod
    def reason_text(cls, value):
        if len(value.strip()) < 5:
            raise ValueError("Briefly explain why you need more dossiers.")
        return value.strip()


class Decision(Input):
    expected_revision: int = Field(ge=1, strict=True)
    action: Literal["approve", "reject"]
    limit: int | None = Field(default=None, ge=1, le=100000, strict=True)


def admin(session, identity):
    user = session.get(User, identity.user_id)
    if not user or not user.active or not user.platform_admin:
        fail("Platform administration is required to decide dossier limits.", 403, "platform_admin_required")


def record(session, identifier):
    row = session.get(DossierLimitRequest, str(identifier))
    if not row:
        fail("This limit request is no longer available.", 404)
    return row


def admin_payload(session, row):
    user = session.get(User, row.user_id)
    return {**request_payload(row), "user": {"id": user.id, "name": user.name, "email": user.email},
        "allowance": state(session, row.user_id), "previous_limit": row.previous_limit}


def routes(router, service, actor):
    @router.post("/dossier-limit-requests", status_code=202)
    def request_increase(product: Product, data: Increase, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, identity.organization_id)
            session.scalar(select(User).where(User.id == identity.user_id).with_for_update())
            previous = session.scalar(select(DossierLimitRequest).where(DossierLimitRequest.user_id == identity.user_id,
                DossierLimitRequest.request_key == str(data.request_key)))
            if previous:
                if previous.requested_limit != data.requested_limit or previous.reason != data.reason:
                    fail("This request key belongs to a different limit request.", 409)
                return request_payload(previous)
            pending = session.scalar(select(DossierLimitRequest).where(DossierLimitRequest.user_id == identity.user_id,
                DossierLimitRequest.status == "pending"))
            if pending:
                fail("Your earlier limit request is awaiting a decision.", 409, "limit_request_pending")
            current = state(session, identity.user_id)
            if data.requested_limit <= current["limit"]:
                fail("Choose a total dossier limit higher than your current limit.")
            row = DossierLimitRequest(user_id=identity.user_id, request_key=str(data.request_key),
                requested_limit=data.requested_limit, reason=data.reason, previous_limit=current["limit"])
            session.add(row)
            session.flush()
            jobs.enqueue(session, job_type=MAIL_JOB, target_type="dossier_limit_request", target_id=row.id,
                queue="maintenance", idempotency_key=MAIL_JOB + ":" + row.id, max_attempts=3)
            session.commit()
            return request_payload(row)

    @router.get("/dossier-limit-requests/{identifier}")
    def read_request(product: Product, identifier: UUID, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            admin(session, identity)
            return admin_payload(session, record(session, identifier))

    @router.post("/dossier-limit-requests/{identifier}/decision")
    def decide(product: Product, identifier: UUID, data: Decision, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            admin(session, identity)
            row = record(session, identifier)
            session.scalar(select(User).where(User.id == row.user_id).with_for_update())
            session.refresh(row)
            requested = data.limit if data.limit is not None else row.requested_limit
            if data.action == "reject" and data.limit is not None:
                fail("A rejected request does not set a new limit.")
            if row.status != "pending":
                expected = "approved" if data.action == "approve" else "rejected"
                if row.status == expected and (expected == "rejected" or row.approved_limit == requested):
                    return admin_payload(session, row)
                fail("This request already has a different decision. Refresh to see it.", 409)
            if row.revision != data.expected_revision:
                fail("This limit request changed. Refresh before deciding.", 409)
            allowance = session.get(DossierAllowance, row.user_id)
            if data.action == "approve":
                if not allowance:
                    allowance = DossierAllowance(user_id=row.user_id, limit=LIMIT, revision=1)
                    session.add(allowance)
                if requested <= allowance.limit:
                    fail("An increase must set a higher total than the current allowance.", 409)
                row.previous_limit = allowance.limit
                allowance.limit, allowance.revision = requested, allowance.revision + 1
                row.approved_limit = requested
            row.status = "approved" if data.action == "approve" else "rejected"
            row.decided_by_user_id, row.decided_at = identity.user_id, utcnow()
            row.revision += 1
            session.commit()
            return admin_payload(session, row)


def deliver(database, settings, identifier, *, mailer=None):
    with database.session() as session:
        row = record(session, identifier)
        if row.status != "pending" or row.mailed_at:
            return {"state": "already_handled"}
        user = session.get(User, row.user_id)
        if not user or not user.active:
            return {"state": "account_unavailable"}
        url = f"https://legal.helveticlens.ch/limit-requests/{row.id}"
        links = [("Approve requested limit", url + "?action=approve"),
            ("Set another limit", url + "?action=adjust"), ("Reject request", url + "?action=reject")]
        content = (f"Dossier limit request from {user.name} ({user.email})\n"
            f"Current total: {state(session, row.user_id)['limit']}\nRequested total: {row.requested_limit}\n"
            f"Reason: {row.reason}\n\nLegal and Pharma share this account limit.\n"
            "Open an action, sign in as platform administrator and confirm the decision.\n")
        body = content + "\n".join(f"{label}: {link}" for label, link in links)
        html = "<html><body><h1>Dossier limit request</h1><p>" + escape(content).replace("\n", "<br>") + "</p>" + "".join(
            f'<p><a href="{escape(link, quote=True)}">{label}</a></p>' for label, link in links) + "</body></html>"
        try:
            mode = (mailer or AuthMailer(settings)).send_message(RECIPIENT, "Helvetic Lens — dossier limit request",
                body, html, message_id=f"<dossier-limit-{row.id}@helveticlens.ch>")
        except Exception:
            row.mail_state = "retrying"
            session.commit()
            raise
        row.mail_state = "sent" if mode == "smtp" else "unavailable"
        row.mailed_at = utcnow() if mode == "smtp" else None
        session.commit()
        return {"state": row.mail_state}
