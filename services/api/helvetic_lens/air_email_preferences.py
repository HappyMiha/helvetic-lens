"""Explicit verified-owner email consent, separate from air interest settings."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update

from . import jobs
from .air_contracts import utc as _utc
from .air_email_models import AirDelivery, AirEmailPolicy
from .air_runtime import owned
from .config import DomainError
from .models import User
from .monitoring_subjects import _savepoint
from .pollen_contracts import PollenDelivery


def clock(value):
    if value.tzinfo is None:
        raise ValueError("Use an aware delivery clock")
    return _utc(value)


def _fail(code, status=409):
    raise DomainError("Air email preferences are unavailable or changed.", status, code)


def _version(value):
    if type(value) is not int or value < 1:
        _fail("air_version_invalid", 422)


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
    return session.get(AirEmailPolicy, (monitor.id, monitor.email_revision)) if monitor.email_revision else None


def cancel_email_work(session, monitor):
    session.execute(update(AirDelivery).where(AirDelivery.monitor_id == monitor.id,
        AirDelivery.organization_id == monitor.organization_id, AirDelivery.state == "pending")
        .values(state="suppressed").execution_options(synchronize_session=False))
    session.execute(update(jobs.Job).where(jobs.Job.organization_id == monitor.organization_id,
        jobs.Job.target_type == "air_monitor", jobs.Job.target_id == monitor.id,
        jobs.Job.type == "air_email", jobs.Job.state.not_in(jobs.TERMINAL_STATES)).values(cancel_requested=True))


def view(session, user_id, monitor_id):
    monitor = owned(session, user_id, monitor_id)
    current = policy(session, monitor)
    config = EmailConfiguration.model_validate(current.configuration) if current else EmailConfiguration()
    user = session.get(User, user_id)
    uncertain = session.scalar(select(func.count()).select_from(AirDelivery).where(
        AirDelivery.monitor_id == monitor.id, AirDelivery.organization_id == monitor.organization_id,
        AirDelivery.state == "uncertain"))
    return {"revision": monitor.email_revision, "monitor_version": monitor.version,
        "configuration": config.model_dump(mode="json"), "email_verified": user.email_verified_at is not None,
        "consent_active": bool(current and config.delivery.email != "off" and user.email_verified_at is not None
                               and current.recipient_email == user.email),
        "recipient_email": user.email, "uncertain_deliveries": uncertain,
        "consented_at": _utc(current.created_at).isoformat() if current and config.delivery.email != "off" else None}


def configure(session, user_id, monitor_id, *, expected_version, configuration, consent, now):
    from .air_delivery import prepare_monitor
    now = clock(now)
    _version(expected_version)
    config = EmailConfiguration.model_validate(configuration)
    wants_email = config.delivery.email != "off"
    if type(consent) is not bool or consent != wants_email:
        _fail("air_email_consent_required", 422)
    with _savepoint(session):
        monitor = owned(session, user_id, monitor_id, write=True)
        user = session.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
        if monitor.version != expected_version:
            _fail("air_version_conflict")
        if wants_email and (monitor.status == "archived" or user.email_verified_at is None):
            _fail("air_email_unavailable")
        if wants_email and monitor.email_revision >= 1000:
            _fail("air_email_revision_limit")
        monitor.email_revision, monitor.version = monitor.email_revision + 1, monitor.version + 1
        session.add(AirEmailPolicy(monitor_id=monitor.id, organization_id=monitor.organization_id,
            revision=monitor.email_revision, configuration=config.model_dump(mode="json"),
            recipient_email=user.email if wants_email else None, created_at=now))
        cancel_email_work(session, monitor)
        session.flush()
        prepare_monitor(session, monitor, now=now)
    return view(session, user_id, monitor_id)
