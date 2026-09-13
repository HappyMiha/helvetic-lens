"""Verified owner opt-in, independent of location configuration and Today review."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update

from . import jobs
from .config import DomainError
from .hazard_models import HazardDelivery, HazardEmailPolicy, HazardMonitor
from .hazard_repository import _version as positive
from .hazard_repository import owned
from .hazard_sources import _clock as clock
from .hazard_sources import _utc as utc
from .models import User
from .monitoring_subjects import _savepoint
from .pollen_contracts import PollenDelivery


class EmailConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    timezone: str = Field(default="Europe/Zurich", min_length=1, max_length=64)
    delivery: PollenDelivery = Field(default_factory=PollenDelivery)

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Use a known IANA timezone") from None
        return value


def policy(session, monitor):
    return session.get(HazardEmailPolicy, (monitor.id, monitor.email_revision)) if monitor.email_revision else None


def cancel_email_work(session, monitor):
    session.execute(update(HazardDelivery).where(HazardDelivery.monitor_id == monitor.id,
        HazardDelivery.organization_id == monitor.organization_id, HazardDelivery.state == "pending").values(state="suppressed"))
    session.execute(update(jobs.Job).where(jobs.Job.organization_id == monitor.organization_id,
        jobs.Job.target_type == "hazard_monitor", jobs.Job.target_id == monitor.id,
        jobs.Job.type == "hazard_email", jobs.Job.state.not_in(jobs.TERMINAL_STATES)).values(cancel_requested=True))


def view(session, user_id, monitor_id):
    monitor = owned(session, user_id, monitor_id)
    current = policy(session, monitor)
    config = EmailConfiguration.model_validate(current.configuration) if current else EmailConfiguration()
    user = session.get(User, user_id)
    uncertain = session.scalar(select(func.count()).select_from(HazardDelivery).where(
        HazardDelivery.monitor_id == monitor.id, HazardDelivery.organization_id == monitor.organization_id,
        HazardDelivery.state == "uncertain"))
    return {"revision": monitor.email_revision, "monitor_version": monitor.version,
        "configuration": config.model_dump(mode="json"), "email_verified": user.email_verified_at is not None,
        "consent_active": bool(current and config.delivery.email != "off" and user.email_verified_at is not None
                               and current.recipient_email == user.email),
        "recipient_email": user.email, "uncertain_deliveries": uncertain,
        "consented_at": utc(current.created_at).isoformat() if current and config.delivery.email != "off" else None}


def configure(session, user_id, monitor_id, *, expected_version, configuration, consent, now=None):
    now = clock(now)
    owned(session, user_id, monitor_id, write=True)
    positive(expected_version)
    config = EmailConfiguration.model_validate(configuration)
    wants_email = config.delivery.email != "off"
    if type(consent) is not bool or consent != wants_email:
        raise DomainError("Confirm the selected email setting explicitly.", 422, "hazard_email_consent_required")
    monitor = session.scalar(select(HazardMonitor).where(HazardMonitor.id == monitor_id)
        .with_for_update().execution_options(populate_existing=True))
    user = session.get(User, user_id)
    if wants_email and (monitor.status == "archived" or user.email_verified_at is None):
        raise DomainError("Verify your account email and use a non-archived place.", 409, "hazard_email_unavailable")
    if monitor.version != expected_version:
        raise DomainError("The saved place changed. Refresh its email settings.", 409, "hazard_version_conflict")
    if monitor.email_revision >= 1000 and wants_email:
        raise DomainError("The email preference history is full.", 409, "hazard_email_revision_limit")
    if monitor.email_revision >= 1000 and not wants_email:
        current = policy(session, monitor)
        if current is None or EmailConfiguration.model_validate(current.configuration).delivery.email == "off":
            return view(session, user_id, monitor_id)
    with _savepoint(session):
        revision = monitor.email_revision + 1
        changed = session.execute(update(HazardMonitor).where(HazardMonitor.id == monitor.id,
            HazardMonitor.organization_id == monitor.organization_id, HazardMonitor.owner_user_id == user_id,
            HazardMonitor.version == expected_version).values(email_revision=revision,
                version=expected_version + 1).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise DomainError("The email settings changed. Refresh them.", 409, "hazard_version_conflict")
        session.add(HazardEmailPolicy(monitor_id=monitor.id, organization_id=monitor.organization_id,
            revision=revision, configuration=config.model_dump(mode="json"),
            recipient_email=user.email if wants_email else None, created_at=now))
        # Email preference changes do not dismiss Today or cancel source checks.
        cancel_email_work(session, monitor)
        session.flush()
        session.expire(monitor)
    return view(session, user_id, monitor_id)
