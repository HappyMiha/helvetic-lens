"""Explicit private email consent; never part of a company matching profile."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from sqlalchemy import func, select, update

from .business_monitor_access import require_private_owner
from .config import DomainError
from .models import User
from .monitoring_subjects import _savepoint
from .pollen_contracts import PollenDelivery
from .simap_sources import aware
from .tender_contracts import Contract
from .tender_models import TenderDelivery, TenderEmailPolicy, TenderMonitor
from .tender_repository import owned, positive, timestamp


class EmailConfiguration(Contract):
    timezone: str = Field(default="Europe/Zurich", min_length=1, max_length=64)
    delivery: PollenDelivery = Field(default_factory=PollenDelivery)

    @field_validator("timezone")
    @classmethod
    def known_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Use a known IANA timezone") from None
        return value


def policy(session, monitor):
    return (
        session.get(TenderEmailPolicy, (monitor.id, monitor.email_revision))
        if monitor.email_revision
        else None
    )


def view(session, user_id, monitor_id):
    monitor = owned(session, user_id, monitor_id)
    require_private_owner(monitor, user_id)
    current = policy(session, monitor)
    config = EmailConfiguration.model_validate(current.configuration) if current else EmailConfiguration()
    user = session.get(User, user_id)
    verified = user.email_verified_at is not None
    uncertain = session.scalar(
        select(func.count())
        .select_from(TenderDelivery)
        .where(
            TenderDelivery.monitor_id == monitor.id,
            TenderDelivery.organization_id == monitor.organization_id,
            TenderDelivery.state == "uncertain",
        )
    )
    return {
        "revision": monitor.email_revision,
        "monitor_version": monitor.version,
        "configuration": config.model_dump(mode="json"),
        "consent_active": bool(
            current and config.delivery.email != "off" and verified and current.recipient_email == user.email
        ),
        "email_verified": verified,
        "uncertain_deliveries": uncertain,
        "recipient_email": user.email,
        "consented_at": timestamp(current.created_at) if current and config.delivery.email != "off" else None,
    }


def configure(session, user_id, monitor_id, *, expected_version, configuration, consent, now=None):
    from .tender_lifecycle import cancel_work

    now = aware(now or datetime.now(UTC))
    require_private_owner(owned(session, user_id, monitor_id, write=True), user_id)
    positive(expected_version)
    config = EmailConfiguration.model_validate(configuration)
    wants_email = config.delivery.email != "off"
    if type(consent) is not bool or consent != wants_email:
        raise DomainError(
            "Explicit consent must match the selected email setting.", 422, "tender_email_consent_required"
        )
    monitor = session.scalar(
        select(TenderMonitor)
        .where(TenderMonitor.id == monitor_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    user = session.get(User, user_id)
    if monitor.status == "archived" and wants_email:
        raise DomainError("Archived monitoring cannot enable email.", 409, "tender_archived")
    if wants_email and user.email_verified_at is None:
        raise DomainError(
            "Verify your account email before enabling delivery.", 409, "email_verification_required"
        )
    if monitor.version != expected_version:
        raise DomainError(
            "The monitor changed. Review the current email settings.", 409, "tender_version_conflict"
        )
    with _savepoint(session):
        revision = monitor.email_revision + 1
        changed = session.execute(
            update(TenderMonitor)
            .where(
                TenderMonitor.id == monitor.id,
                TenderMonitor.organization_id == monitor.organization_id,
                TenderMonitor.owner_user_id == user_id,
                TenderMonitor.version == expected_version,
            )
            .values(email_revision=revision, version=expected_version + 1, next_poll_at=now)
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            raise DomainError(
                "Email settings changed concurrently. Refresh before saving.", 409, "tender_version_conflict"
            )
        session.add(
            TenderEmailPolicy(
                monitor_id=monitor.id,
                organization_id=monitor.organization_id,
                revision=revision,
                configuration=config.model_dump(mode="json"),
                recipient_email=user.email if wants_email else None,
                created_at=now,
            )
        )
        session.execute(
            update(TenderDelivery)
            .where(
                TenderDelivery.monitor_id == monitor.id,
                TenderDelivery.organization_id == monitor.organization_id,
                TenderDelivery.state == "pending",
            )
            .values(state="suppressed")
        )
        cancel_work(session, monitor)
        session.flush()
        session.expire(monitor)
    return view(session, user_id, monitor_id)
